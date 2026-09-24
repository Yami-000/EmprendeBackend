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
DOCS = os.path.join(RAIZ, "ai-service", "docs", "sii")
BANCO = os.path.join(RAIZ, "tests", "dataset", "banco_preguntas_respuestas.json")
EMB = "all-MiniLM-L6-v2"                   # debe coincidir con ingest.py y api.py
TRUNCADO_API = 1400                        # api.py recorta cada fragmento a esto

ap = argparse.ArgumentParser()
ap.add_argument("--topes", default="800,1200,1400,1600",
                help="tamanos de fragmento a probar, separados por coma")
ap.add_argument("--solapes", default="0,150,200",
                help="solapes a probar, separados por coma")
ap.add_argument("--ks", default="6,8,10", help="valores de k a reportar")
args = ap.parse_args()


def norm(t):
    """Normaliza para comparar: sin tildes, sin mayusculas, espaciado colapsado.

    El banco guarda varias citas sin tildes mientras el corpus las lleva; una
    comparacion literal daria falsos negativos.
    """
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
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
    col.add(ids=[str(uuid.uuid4()) for _ in docs],
            embeddings=[[float(x) for x in e] for e in M.encode(docs, show_progress_bar=False)],
            documents=docs, metadatas=metas)

    def top(q, k):
        v = [float(x) for x in M.encode([q], show_progress_bar=False)[0]]
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
cab = "  ".join("k=%-2d rec/anc" % k for k in KS)
print("%-22s %7s %6s %6s | %s" % ("tope / solape", "chunks", "media", ">1400", cab))
print("-" * (52 + len(cab)))
for tope in [int(x) for x in args.topes.split(",")]:
    for solape in [int(x) for x in args.solapes.split(",")]:
        if solape >= tope:
            continue
        docs, r = evaluar(tope, solape)
        largos = [len(d) for d in docs]
        # Un fragmento por encima del truncado de api.py vuelve a perder el dato
        # justo antes de que el modelo lo lea: la mejora se anula ahi.
        exceden = sum(1 for l in largos if l > TRUNCADO_API)
        print("%-22s %7d %6d %6s | %s" % (
            "%d / %d" % (tope, solape), len(docs), sum(largos) // len(largos),
            ("%d !" % exceden) if exceden else "0",
            "  ".join("%2d/%2d" % (r[k][0], r[k][1]) for k in KS)))
print()
print("anc = preguntas cuya cita llega INTEGRA, sobre %d. '>1400' = fragmentos que"
      % len(VERIF))
print("api.py truncaria, reintroduciendo la mutilacion que esta metrica detecta.")
