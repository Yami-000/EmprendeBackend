# -*- coding: utf-8 -*-
"""Mide recall@k del retriever contra el banco. No invoca al LLM: corre en segundos.

Util para iterar sobre chunking / k / modelo de embeddings sin pagar el costo
de generacion. Reporta ademas que documentos acaparan el top-k, para detectar
redundancia del corpus.

Uso:  python scripts/medir_retrieval.py
"""
import json, io, os, collections
import chromadb
from sentence_transformers import SentenceTransformer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI = os.path.join(RAIZ, "ai-service")
BANCO = os.path.join(RAIZ, "tests", "dataset", "banco_preguntas_respuestas.json")
EMB = "all-MiniLM-L6-v2"

d = json.load(io.open(BANCO, encoding="utf-8-sig"))
resp = [p for p in d if p["ground_truth"]["md_origen"]]
m = SentenceTransformer(EMB)
col = chromadb.PersistentClient(path=os.path.join(AI, "chroma_db")).get_or_create_collection("sii_markdown")

def esperados(p):
    gt = p["ground_truth"]
    return {os.path.basename(x) for x in [gt["md_origen"]] + gt.get("md_alternativos", [])}

def recuperados(q, k):
    v = [float(x) for x in m.encode([q], show_progress_bar=False)[0]]
    r = col.query(query_embeddings=[v], n_results=k)
    return [os.path.basename(mt.get("source", "?")) for mt in r["metadatas"][0]]

print("indice: %d chunks" % col.count())
print()
for k in (1, 3, 6, 10):
    hit = sum(1 for p in resp if esperados(p) & set(recuperados(p["pregunta"], k)))
    print("  recall@%-2d = %2d/%d  (%3.0f%%)" % (k, hit, len(resp), 100.0 * hit / len(resp)))

K = 6
fallos, ocup = [], collections.Counter()
for p in resp:
    got = recuperados(p["pregunta"], K)
    ocup.update(got)
    if not (esperados(p) & set(got)):
        fallos.append((p["id"], p["pregunta"][:48]))

print()
print("-- fallos con k=%d: %d --" % (K, len(fallos)))
for pid, q in fallos:
    print("   %s %s" % (pid, q))

print()
print("-- ocupacion del top-%d (%d slots) --" % (K, sum(ocup.values())))
for a, c in ocup.most_common():
    print("   %-46s %3d  (%4.1f%%)" % (a, c, 100.0 * c / sum(ocup.values())))
