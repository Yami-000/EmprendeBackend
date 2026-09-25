# -*- coding: utf-8 -*-
"""Mide el efecto de anadir palabras clave al corpus. No invoca al LLM.

Cruza dos ejes:

  FUENTE de las palabras clave (todas mecanicas, ninguna mira el banco de
  preguntas, para no ajustar al conjunto de prueba):
    tfidf      terminos que distinguen al documento de los otros 12
    marcadas   encabezados markdown y terminos en **negrita**: lo que el autor
               del documento ya senalo como importante
    union      las dos, hasta 5

  DONDE viven:
    A (texto)      la linea de palabras clave forma parte del fragmento, asi que
                   tambien la lee el juez
    B (desacople)  el fragmento se INDEXA con las palabras clave y se GUARDA sin
                   ellas. El recuperador las aprovecha, el juez no las ve.

Por que las palabras clave van en CADA fragmento y no solo en el primero del
documento: all-MiniLM-L6-v2 solo lee los primeros 256 tokens y los fragmentos
tienen mediana 402, asi que lo que este mas abajo no influye en el retrieval.

Uso:
    python scripts/medir_palabras_clave.py
    python scripts/medir_palabras_clave.py --n 3
"""
import argparse, collections, io, json, logging, math, os, re, sys, unicodedata, uuid

logging.disable(logging.CRITICAL)
import chromadb
from sentence_transformers import SentenceTransformer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "ai-service"))
from ingest import _chunk_text

DOCS = os.path.join(RAIZ, "ai-service", "docs", "sii")
BANCO = os.path.join(RAIZ, "tests", "dataset", "banco_preguntas_respuestas.json")
EMB = "all-MiniLM-L6-v2"

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=5, help="palabras clave por documento")
ap.add_argument("--k", type=int, default=6)
ap.add_argument("--sin-grafo", action="store_true",
                help="quita las cabeceras del grafo, para comparar contra el estado previo a la 1.7")
args = ap.parse_args()

_CAB = re.compile(r"(?m)^\*\*(Requiere antes|Habilita después|Nodo):\*\*.*$\n?")
VACIAS = set("""de la el en y a los las un una que se del al por con para su sus
es son como o mas más no ni lo le les este esta estos estas ser sobre entre
cuando donde cual cuales debe deben puede pueden tiene tienen hay si sin tras
cada todo toda todos todas segun según desde hasta ante antes despues después
tambien también solo sólo muy fin parte caso casos forma manera proceso etapa
etapas paso pasos requiere requieren mediante realizarse implica necesario
correctamente seleccionar informa comenzará cumple datos""".split())


def norm(t):
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"(?m)^\s*[-*+]\s+", "", t)
    t = re.sub(r"(?m)^\s*\d+[.)]\s+", "", t)
    return re.sub(r"\s+", " ", t).strip().lower()


FUENTE = {}
for f in sorted(os.listdir(DOCS)):
    if f.endswith(".md"):
        t = io.open(os.path.join(DOCS, f), encoding="utf-8").read()
        # Las cabeceras del grafo SE CONSERVAN: ya estan adoptadas en el corpus
        # y la comparacion debe ser contra lo desplegado, no contra el estado
        # anterior. Quitarlas atribuiria a las palabras clave lo que ya dio la 1.7.
        FUENTE[f] = t if not args.sin_grafo else _CAB.sub("", t)

BANCO_D = json.load(io.open(BANCO, encoding="utf-8-sig"))
RESP = [p for p in BANCO_D if p["ground_truth"]["md_origen"]]
_TODO = norm(" || ".join(FUENTE.values()))
VERIF = [p for p in RESP if norm(p["ground_truth"].get("cita_anclaje")) in _TODO]


def claves_tfidf(n):
    N = len(FUENTE)
    pal = {f: [w for w in re.findall(r"[a-záéíóúñü]{4,}", t.lower()) if w not in VACIAS]
           for f, t in FUENTE.items()}
    df = collections.Counter()
    for v in pal.values():
        df.update(set(v))
    out = {}
    for f, v in pal.items():
        tf = collections.Counter(v)
        tot = sum(tf.values()) or 1
        p = {w: (c / tot) * math.log(N / df[w]) for w, c in tf.items() if df[w] < N}
        out[f] = [w for w, _ in sorted(p.items(), key=lambda kv: -kv[1])[:n]]
    return out


def claves_marcadas(n):
    N = len(FUENTE)
    cand = {}
    for f, t in FUENTE.items():
        c = re.findall(r"(?m)^#{1,6}\s+(.+)$", t) + re.findall(r"\*\*([^*]{3,60})\*\*", t)
        c = [t.strip().split("\n")[0].lstrip("# ").strip()] + c
        cand[f] = [re.sub(r"[:(].*$", "", x).strip(" .·—-") for x in c]
        cand[f] = [x for x in cand[f] if 3 <= len(x) <= 46]
    df = collections.Counter()
    for v in cand.values():
        df.update(set(x.lower() for x in v))
    out = {}
    for f, v in cand.items():
        tf = collections.Counter(x.lower() for x in v)
        orig = {x.lower(): x for x in v}
        p = {w: c * math.log(N / df[w]) for w, c in tf.items() if df[w] < N}
        out[f] = [orig[w] for w, _ in sorted(p.items(), key=lambda kv: -kv[1])[:n]]
    return out


def claves_union(n):
    a, b = claves_marcadas(n), claves_tfidf(n)
    out = {}
    for f in FUENTE:
        vistas, res = set(), []
        for x in [y for par in zip(b[f], a[f] + [""] * n) for y in par]:
            if x and x.lower() not in vistas:
                vistas.add(x.lower())
                res.append(x)
            if len(res) >= n:
                break
        out[f] = res
    return out


M = SentenceTransformer(EMB)
CLIENTE = chromadb.EphemeralClient()


def construir(claves, desacoplar):
    """claves=None -> corpus tal cual. desacoplar -> indexa con, guarda sin."""
    guardados, indexados, metas = [], [], []
    for f, t in FUENTE.items():
        linea = ("Palabras clave: " + ", ".join(claves[f]) + "\n\n") if claves else ""
        for c in _chunk_text(t):
            indexados.append(linea + c)
            guardados.append(c if desacoplar else linea + c)
            metas.append({"source": f})
    col = CLIENTE.create_collection(name="pc_" + uuid.uuid4().hex[:8])
    col.add(ids=[str(i) for i in range(len(guardados))],
            embeddings=[[float(x) for x in e] for e in M.encode(indexados, show_progress_bar=False)],
            documents=guardados, metadatas=metas)
    return col


def evaluar(col, k):
    hit = anc = 0
    for p in RESP:
        gt = p["ground_truth"]
        esp = {os.path.basename(x) for x in [gt["md_origen"]] + gt.get("md_alternativos", []) if x}
        v = [float(x) for x in M.encode([p["pregunta"]], show_progress_bar=False)[0]]
        q = col.query(query_embeddings=[v], n_results=k)
        if esp & {m["source"] for m in q["metadatas"][0]}:
            hit += 1
    for p in VERIF:
        cita = norm(p["ground_truth"]["cita_anclaje"])
        v = [float(x) for x in M.encode([p["pregunta"]], show_progress_bar=False)[0]]
        q = col.query(query_embeddings=[v], n_results=k)
        if any(cita in norm(d) for d in q["documents"][0]):
            anc += 1
    return hit, anc


FUENTES = {"tfidf": claves_tfidf(args.n),
           "marcadas": claves_marcadas(args.n),
           "union": claves_union(args.n)}

print("%d palabras clave por documento, k=%d, techo del anclaje %d"
      % (args.n, args.k, len(VERIF)))
print()
print("%-30s %-10s %s" % ("variante", "recall@%d" % args.k, "anclaje@%d" % args.k))
print("-" * 52)
h, a = evaluar(construir(None, False), args.k)
print("%-30s %2d/50      %2d/%d" % ("base (sin palabras clave)", h, a, len(VERIF)))
for nombre, cl in FUENTES.items():
    for etq, des in (("A en el texto", False), ("B desacoplado", True)):
        h, a = evaluar(construir(cl, des), args.k)
        print("%-30s %2d/50      %2d/%d" % ("%s / %s" % (nombre, etq), h, a, len(VERIF)))
print()
print("Las tres fuentes son mecanicas: ninguna mira el banco de preguntas.")
