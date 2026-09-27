# -*- coding: utf-8 -*-
"""Sonda: valida o mata B2 (descomponer la pregunta) sin implementar B2.

B2 supone que el juez niega las preguntas COMPARATIVAS y DISYUNTIVAS porque
piden una relacion entre dos datos, y que descomponerlas en preguntas por
definiciones -un tipo que el prompt si admite- las recuperaria.

Implementar B2 cuesta una llamada extra al modelo por consulta y cambia el
pipeline. Esta sonda prueba solo la premisa, y cuesta un minuto:

  - recupera el top-6 con la pregunta ORIGINAL, igual que produccion
  - le pregunta al juez con ese MISMO contexto, primero la original y despues
    cada subpregunta

Si el juez dice NO a la original y SI a las subpreguntas, la premisa se sostiene
y vale implementar B2. Si dice NO a todo, el problema no es la forma de la
pregunta y B2 tampoco lo va a resolver.

Las subpreguntas estan escritas a mano aca y NO se toca el banco: son un
instrumento de diagnostico, no una version nueva del conjunto de prueba.

Uso:  python scripts/sonda_descomposicion.py [variante_de_prompt]
"""
import json, io, os, sys, logging
logging.disable(logging.WARNING)
import httpx
import chromadb
from sentence_transformers import SentenceTransformer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI = os.path.join(RAIZ, "ai-service")
sys.path.insert(0, AI)
from api import _build_judge_prompt, JUEZ_PROMPT_BASES  # noqa: E402

BANCO = os.path.join(RAIZ, "tests", "dataset", "banco_preguntas_respuestas.json")
OLLAMA = "http://localhost:11434/api/chat"
MODELO = "llama3.2"
K = 6

# Las tres que resisten, con su descomposicion en preguntas por definicion.
SUB = {
    "PREG-010": [
        "¿Qué institución otorga la patente municipal?",
        "¿Qué trámites se realizan en el SII?",
    ],
    "PREG-064": [
        "¿Qué caracteriza a una SA Cerrada?",
        "¿Qué caracteriza a una SA Abierta?",
    ],
    "PREG-084": [
        "¿Qué responsabilidad tienen los socios gestores de una Sociedad Comanditaria?",
        "¿Qué responsabilidad tienen los socios comanditarios?",
    ],
}


def juez(prompt_sistema, pregunta):
    r = httpx.post(OLLAMA, timeout=180, json={
        "model": MODELO, "stream": False,
        "messages": [{"role": "system", "content": prompt_sistema},
                     {"role": "user", "content": pregunta}],
        "options": {"temperature": 0.0, "top_p": 0.1,
                    "num_predict": 8, "num_ctx": 4096}})
    t = (r.json().get("message", {}).get("content", "") or "").strip()
    return t, t.upper().lstrip("\\W").startswith(("SI", "SÍ"))


def main():
    variante = sys.argv[1] if len(sys.argv) > 1 else "estricto"
    if variante not in JUEZ_PROMPT_BASES:
        sys.exit("variantes: %s" % ", ".join(JUEZ_PROMPT_BASES))
    banco = {p["id"]: p for p in json.load(io.open(BANCO, encoding="utf-8-sig"))}
    m = SentenceTransformer("all-MiniLM-L6-v2")
    col = chromadb.PersistentClient(
        path=os.path.join(AI, "chroma_db")).get_or_create_collection("sii_markdown")

    print("prompt del juez: %s | modelo: %s | k=%d\n" % (variante, MODELO, K))
    for pid, subs in SUB.items():
        p = banco[pid]
        # el contexto se recupera con la pregunta ORIGINAL: la sonda aisla el
        # efecto de reformular lo que se le PREGUNTA al juez, no lo que se busca
        v = [float(x) for x in m.encode([p["pregunta"]], show_progress_bar=False)[0]]
        r = col.query(query_embeddings=[v], n_results=K)
        frags = [{"document": d, "metadata": mt}
                 for d, mt in zip(r["documents"][0], r["metadatas"][0])]
        sistema = _build_judge_prompt(frags, variante)

        print("=" * 72)
        print("%s  %s" % (pid, p["pregunta"]))
        txt, ok = juez(sistema, p["pregunta"])
        print("   original ....... %-3s  (%s)" % ("SI" if ok else "NO", txt[:24]))
        for s in subs:
            txt, ok = juez(sistema, s)
            print("   sub ............ %-3s  %s" % ("SI" if ok else "NO", s[:58]))


if __name__ == "__main__":
    main()
