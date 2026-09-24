# -*- coding: utf-8 -*-
"""Mide el retrieval contra el banco. No invoca al LLM: corre en segundos.

Reporta dos metricas distintas, y la diferencia entre ambas es el punto:

  recall@k        A NIVEL DE ARCHIVO. Acierta si alguno de los k fragmentos
                  viene de un archivo que contiene la respuesta, aunque ese
                  fragmento concreto no traiga el dato. Es OPTIMISTA.

  anclaje@k       A NIVEL DE CHUNK. Acierta solo si la cita de anclaje del
                  ground truth aparece INTEGRA en alguno de los k fragmentos.
                  Es lo que realmente ve el juez del pipeline de dos pasos.

                  OJO CON EL TECHO: 14 de las 50 citas del banco no existen
                  literalmente en ningun .md porque el ground truth las
                  parafrasea. Para esas preguntas ninguna tecnica de chunking
                  puede dar positivo, asi que la metrica se reporta sobre el
                  subconjunto verificable y el script imprime ese techo. No
                  comparar el numerador contra 50.

La iteracion 1.6 mostro que la primera esconde a la segunda: en modo de un paso
el modelo rellenaba con memoria parametrica lo que el chunk no traia, y el fallo
quedaba enmascarado. Optimizar contra recall@k a secas lleva a conclusiones
equivocadas.

Uso:  python scripts/medir_retrieval.py
"""
import json, io, os, collections, re, unicodedata
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


def norm(t):
    """Compara ignorando tildes, mayusculas y espaciado.

    El banco guarda varias citas sin tildes ('Declaracion') mientras el corpus
    las lleva ('Declaracion' con tilde), asi que una comparacion literal daria
    falsos negativos.
    """
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().lower()


def docs_recuperados(q, k):
    v = [float(x) for x in m.encode([q], show_progress_bar=False)[0]]
    r = col.query(query_embeddings=[v], n_results=k)
    return r["documents"][0]


def anclaje_presente(p, k):
    """La cita de anclaje aparece integra en algun fragmento recuperado?"""
    cita = norm(p["ground_truth"].get("cita_anclaje"))
    if not cita:
        return None
    return any(cita in norm(d) for d in docs_recuperados(p["pregunta"], k))

# Techo del anclaje: preguntas cuya cita existe literalmente en el corpus fuente.
DOCS = os.path.join(AI, "docs", "sii")
_fuente = norm(" || ".join(
    io.open(os.path.join(DOCS, f), encoding="utf-8").read()
    for f in sorted(os.listdir(DOCS)) if f.endswith(".md")))
verificables = [p for p in resp if norm(p["ground_truth"].get("cita_anclaje")) in _fuente]

print("indice: %d chunks" % col.count())
print("techo del anclaje: %d de %d preguntas tienen su cita literal en el corpus"
      % (len(verificables), len(resp)))
print()
print("  %-12s %-20s %s" % ("", "recall (archivo)", "anclaje (chunk)"))
for k in (1, 3, 6, 8, 10):
    hit = sum(1 for p in resp if esperados(p) & set(recuperados(p["pregunta"], k)))
    anc = sum(1 for p in verificables if anclaje_presente(p, k))
    print("  k=%-10d %2d/%d  (%3.0f%%)          %2d/%d  (%3.0f%%)"
          % (k, hit, len(resp), 100.0 * hit / len(resp),
             anc, len(verificables), 100.0 * anc / len(verificables)))

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

sin_ancla = [(p["id"], p["pregunta"][:46]) for p in verificables if not anclaje_presente(p, K)]
print()
print("-- el dato NO llega integro con k=%d: %d --" % (K, len(sin_ancla)))
for pid, q in sin_ancla:
    print("   %s" % pid)

print()
print("-- ocupacion del top-%d (%d slots) --" % (K, sum(ocup.values())))
for a, c in ocup.most_common():
    print("   %-46s %3d  (%4.1f%%)" % (a, c, 100.0 * c / sum(ocup.values())))
