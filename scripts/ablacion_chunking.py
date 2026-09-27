# -*- coding: utf-8 -*-
"""Compara configuraciones de chunking sin tocar el indice real ni invocar al LLM.

Construye una coleccion temporal en memoria por cada variante y mide las dos
metricas que importan:

  recall@k    a nivel de ARCHIVO   (optimista, ver medir_retrieval.py)
  anclaje@k   a nivel de CHUNK     (la cita del ground truth, integra)

Existe porque la iteracion 1.1 cambio cinco variables a la vez y el resultado
empeoro sin que se pudiera atribuir a cual. Cada variante cuesta ~10 s, asi que
no hay excusa para cambiar dos cosas juntas.

Uso:
    python scripts/ablacion_chunking.py
    python scripts/ablacion_chunking.py --topes 800,1200,1400 --solapes 0,200
"""
import argparse, io, json, logging, os, re, sys, unicodedata, uuid

logging.disable(logging.CRITICAL)          # silencia el DEBUG de chromadb/httpx
import chromadb
from sentence_transformers import SentenceTransformer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DEF = os.path.join(RAIZ, "ai-service", "docs", "sii")
BANCO = os.path.join(RAIZ, "tests", "dataset", "banco_preguntas_respuestas.json")
import sys, os as _os
sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "ai-service"))
# Importado de ai-service/embedding.py para que no pueda divergir del indice.
from embedding import MODEL_NAME as EMB, para_consulta, para_pasaje  # noqa: E402
# Los prefijos importan: la familia E5 se entreno con 'query:' y 'passage:',
# y medir sin ellos daria numeros que no se pueden comparar con el pipeline
# real. Se aplican igual que en ingest.py y api.py.
TRUNCADO_API = 1400                        # api.py recorta cada fragmento a esto
# La ventana del embedder es el otro limite, y desde la 1.14 es el que manda al
# subir el tope: un fragmento que la excede vuelve a ser parcialmente invisible
# para el retrieval. Se reporta por variante.
VENTANA = None                             # se lee del modelo al cargarlo

ap = argparse.ArgumentParser()
ap.add_argument("--topes", default="800,1200,1400,1600",
                help="tamanos de fragmento a probar, separados por coma")
ap.add_argument("--solapes", default="0,150,200",
                help="solapes a probar, separados por coma")
ap.add_argument("--ks", default="6,8,10", help="valores de k a reportar")
ap.add_argument("--docs", default=None,
                help="corpus alternativo (ej. ai-service/docs/sii_piloto) para "
                     "comparar una reescritura contra el corpus vigente sin tocarlo")
args = ap.parse_args()
DOCS = os.path.join(RAIZ, args.docs) if args.docs else DOCS_DEF


def norm(t):
    """Normaliza: sin tildes, sin mayusculas, espaciado colapsado, sin vinetas.

    El banco guarda varias citas sin tildes mientras el corpus las lleva, y
    varias transcriben dos lineas de una lista sin el '- ' inicial. Sin ignorar
    ambas cosas la comparacion daria falsos negativos: PREG-064 contaba como no
    verificable pese a estar textual en el corpus.

    Debe mantenerse identica a la de medir_retrieval.py o las dos herramientas
    reportarian techos distintos.
    """
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"(?m)^\s*[-*+]\s+", "", t)
    t = re.sub(r"(?m)^\s*\d+[.)]\s+", "", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def chunk(text, tope, solape):
    """Reproduce _chunk_text de ingest.py con tope y solape parametrizados."""
    parts = re.split(r'(?m)(?=^#{1,6}\s)', text)
    if len(parts) == 1:
        parts = text.split('\n\n')
    chunks, actual, largo = [], [], 0
    for part in parts:
        p = part.strip()
        if not p:
            continue
        if largo + len(p) <= tope or not actual:
            actual.append(p)
            largo += len(p)
        else:
            c = "\n\n".join(actual)
            chunks.append(c)
            if solape and solape < len(c):
                ov = c[-solape:]
                actual, largo = [ov, p], len(ov) + len(p)
            else:
                actual, largo = [p], len(p)
    if actual:
        chunks.append("\n\n".join(actual))
    return chunks


FUENTE = {f: io.open(os.path.join(DOCS, f), encoding="utf-8").read()
          for f in sorted(os.listdir(DOCS)) if f.endswith(".md")}
BANCO_D = json.load(io.open(BANCO, encoding="utf-8-sig"))
RESP = [p for p in BANCO_D if p["ground_truth"]["md_origen"]]
_TODO = norm(" || ".join(FUENTE.values()))
VERIF = [p for p in RESP if norm(p["ground_truth"].get("cita_anclaje")) in _TODO]

M = SentenceTransformer(EMB)
CLIENTE = chromadb.EphemeralClient()
KS = [int(x) for x in args.ks.split(",")]


def evaluar(tope, solape):
    docs, metas = [], []
    for nombre, texto in FUENTE.items():
        for c in chunk(texto, tope, solape):
            docs.append(c)
            metas.append({"source": nombre})
    col = CLIENTE.create_collection(name="abl_" + uuid.uuid4().hex[:8])
    indexables = [para_pasaje(d) for d in docs]
    col.add(ids=[str(uuid.uuid4()) for _ in docs],
            embeddings=[[float(x) for x in e]
                        for e in M.encode(indexables, show_progress_bar=False)],
            documents=docs, metadatas=metas)

    def top(q, k):
        v = [float(x) for x in M.encode([para_consulta(q)], show_progress_bar=False)[0]]
        r = col.query(query_embeddings=[v], n_results=k)
        return r["documents"][0], [m["source"] for m in r["metadatas"][0]]

    out = {}
    for k in KS:
        hit = 0
        for p in RESP:
            gt = p["ground_truth"]
            esp = {os.path.basename(x) for x in [gt["md_origen"]] + gt.get("md_alternativos", []) if x}
            if esp & set(top(p["pregunta"], k)[1]):
                hit += 1
        anc = 0
        for p in VERIF:
            cita = norm(p["ground_truth"]["cita_anclaje"])
            if any(cita in norm(d) for d in top(p["pregunta"], k)[0]):
                anc += 1
        out[k] = (hit, anc)
    CLIENTE.delete_collection(col.name)
    return docs, out


print("respondibles: %d    con cita literal en el corpus (techo del anclaje): %d"
      % (len(RESP), len(VERIF)))
print()
VENTANA = M.max_seq_length
print("ventana del embedder: %d tokens (%s)" % (VENTANA, EMB))
print()
cab = "  ".join("k=%-2d rec/anc" % k for k in KS)
print("%-22s %7s %6s %6s %7s | %s"
      % ("tope / solape", "chunks", "media", ">api", ">ventana", cab))
print("-" * (61 + len(cab)))
for tope in [int(x) for x in args.topes.split(",")]:
    for solape in [int(x) for x in args.solapes.split(",")]:
        if solape >= tope:
            continue
        docs, r = evaluar(tope, solape)
        largos = [len(d) for d in docs]
        # Un fragmento por encima del truncado de api.py vuelve a perder el dato
        # justo antes de que el modelo lo lea: la mejora se anula ahi.
        exceden = sum(1 for l in largos if l > TRUNCADO_API)
        # Y el otro limite, que desde la 1.14 es el que manda al subir el tope:
        # un fragmento mas largo que la ventana vuelve a ser parcialmente
        # invisible para el retrieval, que es el problema que la 1.14 resolvio.
        fuera = sum(1 for d in docs if len(M.tokenizer.tokenize(d)) > VENTANA)
        print("%-22s %7d %6d %6s %7s | %s" % (
            "%d / %d" % (tope, solape), len(docs), sum(largos) // len(largos),
            ("%d !" % exceden) if exceden else "0",
            ("%d !!" % fuera) if fuera else "0",
            "  ".join("%2d/%2d" % (r[k][0], r[k][1]) for k in KS)))
print()
print("anc = preguntas cuya cita llega INTEGRA, sobre %d." % len(VERIF))
print("'>api'     = fragmentos que api.py truncaria a %d caracteres, reintroduciendo" % TRUNCADO_API)
print("             la mutilacion que esta metrica detecta. Subir el tope obliga a")
print("             subir ese truncado tambien, o la mejora se anula ahi.")
print("'>ventana' = fragmentos mas largos que los %d tokens del embedder. Esos vuelven" % VENTANA)
print("             a ser parcialmente invisibles para el retrieval: es el techo que")
print("             la 1.14 levanto y que subir el tope puede volver a bajar.")
