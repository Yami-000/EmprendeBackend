# -*- coding: utf-8 -*-
"""Mide cuanto del corpus queda fuera de la ventana del embedder.

`all-MiniLM-L6-v2` tiene `max_seq_length = 256` tokens. Los fragmentos del
indice tienen mediana ~382 tokens, asi que el vector de cada chunk se calcula
SOLO con su primer tramo: todo lo que viene despues es invisible para la
busqueda vectorial, aunque el juez si lo lea (api.py sirve 1400 caracteres).

Esto no es lo mismo que el truncado de `api.py`. Son dos recortes distintos:

  embedder (256 tokens) -> decide QUE chunks se recuperan
  api.py (1400 chars)   -> decide QUE lee el juez de cada chunk recuperado

Un dato que cae fuera de la ventana solo se recupera por carambola: porque el
tramo visible del chunk resulta parecido a la pregunta.

Reporta:
  - tamano de los chunks en tokens y cuantos exceden la ventana
  - que porcentaje del corpus es invisible
  - para cada cita de anclaje verificable, si cae dentro o fuera
  - anclaje@6 partido por esa condicion, que es el numero que importa

No invoca al LLM: corre en segundos.

Uso:  python scripts/medir_ventana_embedder.py
"""
import json, io, os, re, unicodedata, statistics, logging
logging.disable(logging.WARNING)
import chromadb
from sentence_transformers import SentenceTransformer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI = os.path.join(RAIZ, "ai-service")
BANCO = os.path.join(RAIZ, "tests", "dataset", "banco_preguntas_respuestas.json")
EMB = "all-MiniLM-L6-v2"
K = 6


def norm(t):
    """Mismo normalizador que medir_retrieval.py, para que los numeros se puedan cruzar."""
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"(?m)^\s*[-*+]\s+", "", t)
    t = re.sub(r"(?m)^\s*\d+[.)]\s+", "", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def cargar():
    d = json.load(io.open(BANCO, encoding="utf-8-sig"))
    m = SentenceTransformer(EMB)
    col = chromadb.PersistentClient(path=os.path.join(AI, "chroma_db")).get_or_create_collection("sii_markdown")
    return d, m, col


def posicion_en_tokens(m, doc, cita_norm):
    """Aproxima en que token del chunk empieza la cita.

    Se estima por la fraccion de texto normalizado que la precede, en vez de
    tokenizar dos veces: alcanza para decidir dentro/fuera de la ventana y no
    depende de reconstruir los offsets del tokenizador.
    """
    nd = norm(doc)
    if cita_norm not in nd:
        return None
    frac = nd.index(cita_norm) / max(1, len(nd))
    return frac * len(m.tokenizer.tokenize(doc))


def reporte():
    banco, m, col = cargar()
    W = m.max_seq_length
    docs = col.get()["documents"]
    toks = [len(m.tokenizer.tokenize(d)) for d in docs]

    print(f"ventana del embedder ({EMB}): {W} tokens")
    print(f"indice: {len(docs)} chunks | tokens: mediana {statistics.median(toks):.0f}, "
          f"min {min(toks)}, max {max(toks)}")
    print(f"chunks que exceden la ventana: {sum(1 for t in toks if t > W)} de {len(docs)}")
    invis = sum(max(0, t - W) for t in toks)
    print(f"tokens fuera de la ventana: {invis} de {sum(toks)} "
          f"({100 * invis / sum(toks):.0f}% del corpus)")
    print("  (fuera de la ventana no implica invisible: depende de como ingest.py")
    print("   calcule el vector. Truncando si lo es; promediando ventanas, no.)\n")

    resp = [p for p in banco if p["ground_truth"].get("md_origen")]
    dentro, fuera = [], []
    for p in resp:
        cita = norm(p["ground_truth"].get("cita_anclaje"))
        if not cita:
            continue
        for d in docs:
            pos = posicion_en_tokens(m, d, cita)
            if pos is not None:
                (dentro if pos < W else fuera).append((p["id"], round(pos)))
                break

    print(f"citas de anclaje DENTRO de la ventana: {len(dentro)}")
    print(f"citas de anclaje FUERA de la ventana:  {len(fuera)}")
    print(f"   {sorted(i for i, _ in fuera)}\n")

    idx = {p["id"]: p for p in resp}

    def recupera(i):
        p = idx[i]
        cita = norm(p["ground_truth"]["cita_anclaje"])
        v = [float(x) for x in m.encode([p["pregunta"]], show_progress_bar=False)[0]]
        r = col.query(query_embeddings=[v], n_results=K)
        return any(cita in norm(d) for d in r["documents"][0])

    d_ok = sum(1 for i, _ in dentro if recupera(i))
    f_ok = sum(1 for i, _ in fuera if recupera(i))
    print(f"anclaje@{K} segun donde cae la cita:")
    print(f"  dentro de la ventana: {d_ok}/{len(dentro)} "
          f"({100 * d_ok / max(1, len(dentro)):.0f}%)")
    print(f"  fuera de la ventana:  {f_ok}/{len(fuera)} "
          f"({100 * f_ok / max(1, len(fuera)):.0f}%)")
    print("\nLA BRECHA ENTRE ESAS DOS FILAS ES EL NUMERO QUE IMPORTA.")
    print("Con el vector truncado a la ventana medía 91% contra 50%: 41 puntos, y")
    print("era el techo del retrieval. La 1.11 promedia ventanas para cerrarla; si")
    print("vuelve a abrirse, algo rompió _embeber_completo en ingest.py.")


if __name__ == "__main__":
    reporte()
