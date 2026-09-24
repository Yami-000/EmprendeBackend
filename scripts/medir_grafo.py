# -*- coding: utf-8 -*-
"""Mide la expansion por grafo del retrieval. No invoca al LLM: corre en segundos.

Compara cuatro configuraciones para separar dos efectos que se confunden si se
prueban juntos:

  base          corpus sin cabeceras de grafo, retrieval vectorial puro
  cabecera      corpus CON cabeceras, sin expandir  -> aisla el efecto de que
                las tres lineas del encabezado cambien el embedding
  sumar         cabeceras + vecinos anadidos a los k existentes
                (mas contexto: el juez lee mas y tarda mas)
  desplazar     cabeceras + vecinos que reemplazan a los peor rankeados
                (mismo contexto: no encarece al juez, pero puede perder algo)

La eleccion entre 'sumar' y 'desplazar' se toma con estos numeros, no a priori:
el juez ya esta en 12,3 s por pregunta y el 98% de su costo es leer contexto.

Uso:
    python scripts/medir_grafo.py
    python scripts/medir_grafo.py --k 6 --desde 2 --max-vecinos 4
"""
import argparse, io, json, logging, os, re, sys, unicodedata, uuid

logging.disable(logging.CRITICAL)
import chromadb
from sentence_transformers import SentenceTransformer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "ai-service"))
from ingest import _chunk_text, _parse_grafo

BANCO = os.path.join(RAIZ, "tests", "dataset", "banco_preguntas_respuestas.json")
EMB = "all-MiniLM-L6-v2"

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="ai-service/docs/sii",
                help="corpus sin cabeceras de grafo")
ap.add_argument("--grafo", default="ai-service/docs/sii_grafo",
                help="corpus con las aristas declaradas")
ap.add_argument("--k", type=int, default=6)
ap.add_argument("--desde", type=int, default=1,
                help="cuantos fragmentos del top aportan sus vecinos")
ap.add_argument("--max-vecinos", type=int, default=4,
                help="tope de fragmentos vecinos a traer")
args = ap.parse_args()


def norm(t):
    """Identica a la de medir_retrieval.py: sin tildes, sin vinetas, espaciado."""
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"(?m)^\s*[-*+]\s+", "", t)
    t = re.sub(r"(?m)^\s*\d+[.)]\s+", "", t)
    return re.sub(r"\s+", " ", t).strip().lower()


BANCO_D = json.load(io.open(BANCO, encoding="utf-8-sig"))
RESP = [p for p in BANCO_D if p["ground_truth"]["md_origen"]]
M = SentenceTransformer(EMB)
CLIENTE = chromadb.EphemeralClient()


def indexar(dir_rel):
    """Devuelve (coleccion, fragmentos, metadatas) para un corpus."""
    raiz = os.path.join(RAIZ, dir_rel)
    docs, metas = [], []
    for f in sorted(os.listdir(raiz)):
        if not f.endswith(".md"):
            continue
        texto = io.open(os.path.join(raiz, f), encoding="utf-8").read()
        g = _parse_grafo(texto, os.path.splitext(f)[0])
        for c in _chunk_text(texto):
            docs.append(c)
            m = {"source": f}
            m.update(g)
            metas.append(m)
    col = CLIENTE.create_collection(name="g_" + uuid.uuid4().hex[:8])
    col.add(ids=[str(i) for i in range(len(docs))],
            embeddings=[[float(x) for x in e] for e in M.encode(docs, show_progress_bar=False)],
            documents=docs, metadatas=metas)
    return col, docs, metas


def vecinos_de(meta):
    salida = []
    for campo in ("requiere_antes", "habilita_despues"):
        salida += [x for x in meta.get(campo, "").split(",") if x]
    return salida


def consultar(col, docs, metas, pregunta, k, modo):
    """Devuelve (fragmentos, archivos) tras aplicar el modo de expansion."""
    v = [float(x) for x in M.encode([pregunta], show_progress_bar=False)[0]]
    r = col.query(query_embeddings=[v], n_results=k)
    idx = [int(i) for i in r["ids"][0]]
    if modo == "ninguno":
        return [docs[i] for i in idx], [metas[i]["source"] for i in idx]

    # Nodos ya presentes: no tiene sentido traer un vecino que ya esta.
    presentes = {metas[i]["nodo"] for i in idx}
    objetivo = []
    for i in idx[:args.desde]:
        for n in vecinos_de(metas[i]):
            if n not in presentes and n not in objetivo:
                objetivo.append(n)

    # De cada nodo vecino se trae el fragmento MAS PARECIDO A LA PREGUNTA, no el
    # primero: un nodo puede tener varios fragmentos y el primero suele ser la
    # introduccion del documento, justo la parte sin datos. Probar el grafo con
    # el fragmento equivocado mediria una version debil de la idea.
    extra = []
    for n in objetivo:
        if len(extra) >= args.max_vecinos:
            break
        cand = [j for j, m in enumerate(metas)
                if m["nodo"] == n and j not in idx and j not in extra]
        if not cand:
            continue
        sub = col.query(query_embeddings=[v], n_results=len(cand),
                        where={"nodo": n})
        mejor = next((int(i) for i in sub["ids"][0] if int(i) in cand), cand[0])
        extra.append(mejor)

    if modo == "sumar":
        final = idx + extra
    else:                      # desplazar: el contexto total no crece
        final = idx[:max(0, k - len(extra))] + extra
    return [docs[i] for i in final], [metas[i]["source"] for i in final]


def evaluar(col, docs, metas, modo, k):
    hit = anc = 0
    total_frag = 0
    _todo = norm(" || ".join(docs))
    verif = [p for p in RESP if norm(p["ground_truth"].get("cita_anclaje")) in _todo]
    for p in RESP:
        d, s = consultar(col, docs, metas, p["pregunta"], k, modo)
        total_frag += len(d)
        gt = p["ground_truth"]
        esp = {os.path.basename(x) for x in [gt["md_origen"]] + gt.get("md_alternativos", []) if x}
        if esp & set(s):
            hit += 1
    for p in verif:
        d, _ = consultar(col, docs, metas, p["pregunta"], k, modo)
        cita = norm(p["ground_truth"]["cita_anclaje"])
        if any(cita in norm(x) for x in d):
            anc += 1
    return hit, anc, len(verif), total_frag / float(len(RESP))


col_b, docs_b, metas_b = indexar(args.base)
col_g, docs_g, metas_g = indexar(args.grafo)

nodos = {m["nodo"] for m in metas_g}
aristas = sum(len(vecinos_de(m)) for m in {m["source"]: m for m in metas_g}.values())
print("corpus base : %s  (%d fragmentos)" % (args.base, len(docs_b)))
print("corpus grafo: %s  (%d fragmentos, %d nodos, %d aristas)"
      % (args.grafo, len(docs_g), len(nodos), aristas))
print("k=%d  vecinos desde el top-%d  maximo %d vecinos"
      % (args.k, args.desde, args.max_vecinos))
print()
print("%-12s %-10s %-12s %s" % ("variante", "recall", "anclaje", "frag/pregunta"))
print("-" * 52)
for etq, col, docs, metas, modo in (
        ("base",      col_b, docs_b, metas_b, "ninguno"),
        ("cabecera",  col_g, docs_g, metas_g, "ninguno"),
        ("sumar",     col_g, docs_g, metas_g, "sumar"),
        ("desplazar", col_g, docs_g, metas_g, "desplazar")):
    h, a, tot, media = evaluar(col, docs, metas, modo, args.k)
    print("%-12s %2d/%-7d %2d/%-9d %.1f" % (etq, h, len(RESP), a, tot, media))
print()
print("'frag/pregunta' es lo que el juez tendria que leer: su costo es 98% contexto.")
