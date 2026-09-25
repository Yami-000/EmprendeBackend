import logging
import os
import unicodedata
from pathlib import Path

import chromadb
try:
    # Newer chromadb versions deprecate Settings-based construction
    from chromadb.config import Settings  # type: ignore
except Exception:
    Settings = None
import uuid
# Use simple dicts for documents to avoid langchain.schema dependency

# INFO, no DEBUG: en DEBUG las librerias HTTP vuelcan cada cabecera de la
# descarga del modelo y sepultan las lineas que importan (archivos, fragmentos,
# validacion del grafo).
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs" / "sii"
CHROMA_DIR = BASE_DIR / "chroma_db"

# Debe coincidir exactamente con el modelo que usa api.py para embeber las queries:
# indexar y consultar con modelos distintos produce vectores incomparables.
MODEL_NAME = "all-MiniLM-L6-v2"


def find_markdown_files(root_dir: Path):
    return sorted(root_dir.rglob("*.md"))


def load_documents(files):
    documents = []
    for file_path in files:
        try:
            text = Path(file_path).read_text(encoding="utf-8")
            logger.debug("Loaded file %s, length %d", file_path, len(text) if text else 0)
            if not text or not text.strip():
                logger.warning("Archivo vacío o sin contenido útil: %s", file_path)
                continue
            meta = {"source": str(file_path)}
            meta.update(_parse_grafo(text, Path(file_path).stem))
            doc = {"page_content": text, "metadata": meta}
            documents.append(doc)
        except Exception as exc:
            logger.error("Error al cargar %s: %s", file_path, exc)
    return documents


class AristaColgante(Exception):
    """Una arista apunta a un nodo que ningún documento declara."""


def validar_grafo(documents):
    """Comprueba que toda arista apunte a un nodo existente.

    Las aristas se escriben a mano en los documentos, así que un id mal tecleado
    es un error esperable. Debe romper la ingesta de forma visible: un grafo con
    aristas colgantes degrada en silencio y el fallo aparecería mucho después,
    como preguntas que dejan de recuperar a su vecino sin razón aparente.
    """
    nodos = {d["metadata"]["nodo"] for d in documents}
    colgantes = []
    for d in documents:
        m = d["metadata"]
        for campo in ("requiere_antes", "habilita_despues"):
            for destino in [x for x in m.get(campo, "").split(",") if x]:
                if destino not in nodos:
                    colgantes.append("%s: %s -> %s" % (
                        os.path.basename(m["source"]), campo, destino))
    if colgantes:
        raise AristaColgante(
            "Aristas que apuntan a nodos inexistentes:\n  " + "\n  ".join(colgantes)
            + "\n\nNodos declarados: " + ", ".join(sorted(nodos)))
    aristas = sum(len([x for x in d["metadata"].get(c, "").split(",") if x])
                  for d in documents for c in ("requiere_antes", "habilita_despues"))
    logger.info("Grafo validado: %d nodos, %d aristas", len(nodos), aristas)


import re

# Iteración 1.7. Campos de grafo que un documento puede declarar en su cabecera:
#
#   **Nodo:** patente_municipal
#   **Requiere antes:** inicio_actividades_sii, certificado_de_zonificacion
#   **Habilita después:** operacion_del_local
#
# Se escriben a mano. Ese es justamente el punto: extraer entidades y relaciones
# automáticamente era lo que hacía cara esta línea, y declararlas cuesta una
# cabecera por documento.
_CAMPOS_GRAFO = {
    "nodo": "nodo",
    "requiere antes": "requiere_antes",
    "habilita despues": "habilita_despues",
}
_CAMPO_RE = re.compile(r"^\s*\*\*([^:*]+):\*\*\s*(.+?)\s*$", re.MULTILINE)


def _sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFKD", t)
                   if not unicodedata.combining(c))


def _parse_grafo(text, stem, lineas_cabecera=15):
    """Extrae los campos de grafo de la cabecera del documento.

    El id del nodo cae por defecto al nombre del archivo sin extensión, de modo
    que un documento sin cabecera sigue siendo un nodo válido y las aristas de
    otros pueden apuntarle. Solo hay que declarar `Nodo:` cuando se quiere un id
    distinto del nombre del archivo.

    ChromaDB solo admite escalares en la metadata, así que las listas viajan
    como cadenas separadas por comas.
    """
    cabecera = "\n".join(text.split("\n")[:lineas_cabecera])
    out = {"nodo": stem, "requiere_antes": "", "habilita_despues": ""}
    for etiqueta, valor in _CAMPO_RE.findall(cabecera):
        clave = _CAMPOS_GRAFO.get(_sin_tildes(etiqueta).strip().lower())
        if not clave:
            continue
        if clave == "nodo":
            out["nodo"] = valor.strip()
        else:
            # "ninguno" y las glosas tras un guión no son nodos.
            destinos = [v.strip() for v in valor.split("—")[0].split(",")]
            destinos = [v for v in destinos
                        if v and _sin_tildes(v).lower() not in ("ninguno", "ninguna", "-")]
            out[clave] = ",".join(destinos)
    return out


# Iteración 1.1. Medido con scripts/medir_retrieval.py sobre el banco:
# con 800 la mayoría de las secciones no cabía entera y el dato pedido llegaba
# partido entre dos fragmentos. Subir el tope a 1400 sube la proporción de
# preguntas cuyo dato llega ÍNTEGRO al contexto de 22/36 a 31/36 con k=8.
#
# 1400 no es arbitrario: es el límite al que api.py trunca cada fragmento al
# armar el prompt. Con este tope ningún fragmento del corpus actual lo supera
# (máximo real 1378), así que el truncado no vuelve a partir el dato justo
# antes de que el modelo lo lea. Si se sube CHUNK_SIZE hay que subir también
# ese truncado, o el recorte anula la mejora.
#
# Se probó y descartó una reescritura estructural (un fragmento por sección de
# markdown, sin solape): empeoró el anclaje a 18/36. Ver resultado_1.1.md.
CHUNK_SIZE = 1400
CHUNK_OVERLAP = 200


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
    if not text:
        return []
    # Split by markdown headings or double newlines to preserve structure
    parts = re.split(r'(?m)(?=^#{1,6}\s)', text)
    if len(parts) == 1:
        parts = text.split('\n\n')

    chunks = []
    current = []
    current_len = 0

    for part in parts:
        p = part.strip()
        if not p:
            continue
        plen = len(p)
        if current_len + plen <= chunk_size or not current:
            current.append(p)
            current_len += plen
        else:
            chunk = "\n\n".join(current)
            chunks.append(chunk)
            # start new chunk with overlap
            if chunk_overlap and chunk_overlap < len(chunk):
                overlap_text = chunk[-chunk_overlap:]
                current = [overlap_text, p]
                current_len = len(overlap_text) + plen
            else:
                current = [p]
                current_len = plen

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def split_documents(documents):
    split_docs = []
    for idx, doc in enumerate(documents):
        logger.debug("Splitting doc %d: %s", idx, doc.get('metadata', {}).get('source'))
        try:
            text = doc.get('page_content') or doc.get('content') or ''
            logger.debug("Doc text length: %d", len(text) if text else 0)
            chunks = _chunk_text(text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
            logger.debug("Chunks generated for doc %s: %d", doc.get('metadata', {}).get('source'), len(chunks))
            for c in chunks:
                # dict(...) copia por fragmento: ademas de evitar que todos
                # compartan el mismo objeto, arrastra los campos de grafo
                # (nodo, requiere_antes, habilita_despues) a cada uno.
                split_docs.append({"page_content": c,
                                   "metadata": dict(doc.get('metadata', {}))})
        except Exception as exc:
            logger.error("Error al segmentar documento %s: %s", getattr(doc, 'metadata', {}).get('source'), exc)
    return split_docs


# Iteración 1.8. Palabras clave por documento, derivadas del propio corpus.
#
# POR QUÉ EXISTEN: all-MiniLM-L6-v2 solo lee los primeros 256 tokens de cada
# fragmento y los fragmentos tienen mediana 402, así que un tercio del corpus no
# influye en el retrieval. El prefijo es un presupuesto escaso, y medido contra
# el banco las palabras clave son lo que mejor lo aprovecha:
#
#   prefijo                          recall@6   anclaje@6
#   ninguno                            46/50      25/37
#   cabeceras del grafo (1.7)          48/50      26/37
#   palabras clave                     48/50      29/37   <- adoptado
#   ambos                              47/50      28/37
#
# POR QUÉ SE DERIVAN Y NO SE ESCRIBEN A MANO: elegirlas mirando el banco de
# preguntas sería ajustar al conjunto de prueba. Estas salen solo del corpus.
N_CLAVES = 5

_VACIAS = set("""de la el en y a los las un una que se del al por con para su sus
es son como o mas más no ni lo le les este esta estos estas ser sobre entre
cuando donde cual cuales debe deben puede pueden tiene tienen hay si sin tras
cada todo toda todos todas segun según desde hasta ante antes despues después
tambien también solo sólo muy fin parte caso casos forma manera proceso etapa
etapas paso pasos requiere requieren mediante realizarse implica necesario
correctamente seleccionar informa comenzará cumple datos""".split())


def _palabras_clave(textos, n=N_CLAVES):
    """Devuelve {clave_de_documento: [palabras]}, alternando dos fuentes.

    - TF-IDF contra el resto del corpus: términos que distinguen al documento.
    - Marcadas por el autor: encabezados markdown y **negritas**.

    Se alternan porque por separado rinden peor que juntas (27/37 y 27/37 contra
    29/37 de la unión): el TF-IDF aporta términos sueltos y las marcadas aportan
    frases, y las preguntas usan de las dos formas.
    """
    import collections, math

    N = max(len(textos), 1)

    def top(cand, peso):
        df = collections.Counter()
        for v in cand.values():
            df.update({x.lower() for x in v})
        out = {}
        for k, v in cand.items():
            tf = collections.Counter(x.lower() for x in v)
            orig = {x.lower(): x for x in v}
            tot = sum(tf.values()) or 1
            p = {w: peso(c, tot) * math.log(N / df[w]) for w, c in tf.items() if df[w] < N}
            out[k] = [orig[w] for w, _ in sorted(p.items(), key=lambda kv: -kv[1])[:n]]
        return out

    sueltas = top({k: [w for w in re.findall(r"[a-záéíóúñü]{4,}", t.lower())
                       if w not in _VACIAS] for k, t in textos.items()},
                  lambda c, tot: c / float(tot))

    marcadas_cand = {}
    for k, t in textos.items():
        c = re.findall(r"(?m)^#{1,6}\s+(.+)$", t) + re.findall(r"\*\*([^*]{3,60})\*\*", t)
        c = [t.strip().split("\n")[0].lstrip("# ").strip()] + c
        c = [re.sub(r"[:(].*$", "", x).strip(" .·—-") for x in c]
        marcadas_cand[k] = [x for x in c if 3 <= len(x) <= 46]
    marcadas = top(marcadas_cand, lambda c, tot: float(c))

    out = {}
    for k in textos:
        vistas, res = set(), []
        for x in [y for par in zip(sueltas[k], marcadas[k] + [""] * n) for y in par]:
            if x and x.lower() not in vistas:
                vistas.add(x.lower())
                res.append(x)
            if len(res) >= n:
                break
        out[k] = res
    return out


def create_vector_store(documents):
    from sentence_transformers import SentenceTransformer

    st_model = SentenceTransformer(MODEL_NAME)
    logger.info("Using sentence-transformers %s", MODEL_NAME)

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        # Recrear la colección: collection.add() acumula, así que sin esto
        # cada re-ingesta duplicaría todos los chunks.
        try:
            client.delete_collection(name="sii_markdown")
            logger.info("Colección previa eliminada")
        except Exception:
            pass
        collection = client.create_collection(name="sii_markdown")

        # documents are plain dicts produced by split_documents
        texts = [d.get('page_content', '') for d in documents]
        metadatas = [d.get('metadata', {}) for d in documents]
        ids = [str(uuid.uuid4()) for _ in texts]

        # Iteración 1.8: el texto que se INDEXA no es el que se GUARDA.
        #
        # El indexado lleva delante las palabras clave del documento, para que
        # caigan dentro de la ventana de 256 tokens del embedder. El guardado es
        # el fragmento limpio, que es lo que leerá el juez: así el vocabulario
        # trabaja en el recuperador sin meter ruido en el contexto del modelo.
        # A nivel de retrieval ambas variantes miden igual (48/50 y 29/37); se
        # elige esta porque no altera lo que el modelo ve.
        indexables = []
        for d, t in zip(documents, texts):
            pal = d.get("metadata", {}).get("claves", "")
            sep = chr(10) * 2
            indexables.append(("Palabras clave: " + pal + sep + t) if pal else t)

        embeddings_list = st_model.encode(indexables, show_progress_bar=False)
        # Ensure embeddings are plain Python floats (avoid numpy types that print verbosely)
        cleaned_embeddings = [[float(x) for x in emb] for emb in embeddings_list]

        # Use explicit keyword names expected by chromadb
        collection.add(ids=ids, embeddings=cleaned_embeddings, metadatas=metadatas, documents=texts)
        try:
            client.persist()
        except Exception:
            logger.debug("chromadb client has no persist() or persistence handled by settings")
        return collection
    except Exception as exc:
        logger.exception("Error al crear el vector store: %s", exc)
        raise


def main():
    if not DOCS_DIR.exists():
        logger.error("Directorio de documentos no existe: %s", DOCS_DIR)
        return

    markdown_files = find_markdown_files(DOCS_DIR)
    if not markdown_files:
        logger.error("No se encontraron archivos markdown en %s", DOCS_DIR)
        return

    logger.info("Archivos encontrados: %d", len(markdown_files))
    docs = load_documents(markdown_files)
    if not docs:
        logger.error("No se pudo cargar ningún documento válido.")
        return

    validar_grafo(docs)

    # Las palabras clave se derivan del texto COMPLETO de cada documento, antes
    # de fragmentar: hacerlo sobre los fragmentos concatenados contaria dos veces
    # el solape y cambiaria los terminos elegidos.
    claves = _palabras_clave({d["metadata"]["source"]: d["page_content"] for d in docs})
    for d in docs:
        d["metadata"]["claves"] = ", ".join(claves.get(d["metadata"]["source"], []))
        logger.info("claves %-46s %s",
                    os.path.basename(d["metadata"]["source"]), d["metadata"]["claves"])

    chunks = split_documents(docs)
    if not chunks:
        logger.error("No se generaron fragmentos de documentos.")
        return

    logger.info("Fragmentos generados: %d", len(chunks))
    create_vector_store(chunks)
    logger.info("Ingesta completada. Vector DB guardada en %s", CHROMA_DIR)


if __name__ == "__main__":
    main()
