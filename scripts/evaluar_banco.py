# -*- coding: utf-8 -*-
"""Arnes de evaluacion end-to-end del banco de 100 preguntas.

Replica el pipeline de produccion (embed -> ChromaDB -> Ollama) y separa
los dos modos de fallo del RAG:

  - RETRIEVAL : el chunk correcto no llego al contexto
  - GENERACION: el chunk llego, pero el modelo no lo uso o alucino

IMPORTANTE: importa _build_system_prompt DESDE api.py. No copiar el prompt
aqui: una copia diverge y se termina midiendo algo distinto de lo que corre.

Uso:
    python scripts/evaluar_banco.py <etiqueta> [modelo] [k] [num_predict]
Ej:
    python scripts/evaluar_banco.py v1
    python scripts/evaluar_banco.py qwen7b qwen2.5:7b 6 300
"""
import json, io, os, re, sys, time
import chromadb, httpx
from sentence_transformers import SentenceTransformer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI = os.path.join(RAIZ, "ai-service")
sys.path.insert(0, AI)
from api import _build_system_prompt          # fuente unica de verdad

ETIQUETA = sys.argv[1] if len(sys.argv) > 1 else "run"
MODELO = sys.argv[2] if len(sys.argv) > 2 else "llama3.2"
K = int(sys.argv[3]) if len(sys.argv) > 3 else 6
NUM_PREDICT = int(sys.argv[4]) if len(sys.argv) > 4 else 300

BANCO = os.path.join(RAIZ, "tests", "dataset", "banco_preguntas_respuestas.json")
OUT = os.path.join(RAIZ, "tests", "iteraciones", "resultados_%s.json" % ETIQUETA)
OLLAMA = "http://localhost:11434/api/chat"
EMB = "all-MiniLM-L6-v2"                      # debe coincidir con ingest.py y api.py

ABST = ["no incluye esa informaci", "base de conocimientos", "lo siento",
        "no puedo responder", "no está en el contexto", "no dispongo",
        "no tengo informaci", "no se encuentra en el contexto",
        "no cuento con", "no aparece en el contexto",
        # Detectados en la corrida llama3.1:8b (2026-09-22): modelos más grandes
        # razonan la ausencia de dato en vez de usar la frase canónica del prompt.
        "no se especifica", "no se menciona", "no se indica",
        "no está especificado", "no se detalla", "no proporciona"]

def abstuvo(t):
    b = t.lower()
    return any(p in b for p in ABST)

def anclas(gt):
    """Datos verificables de la respuesta esperada: cifras, siglas, instituciones."""
    txt = (gt.get("respuesta_esperada") or "") + " " + (gt.get("cita_anclaje") or "")
    out = set(re.findall(r"\d[\d.,]*\s*(?:UF|UTM|CLP|%)?", txt))
    out |= set(re.findall(r"\b(?:F\d{2}|EIRL|SRL|SpA|SA|MEF|SII|RUT|CVE|DTE|SEREMI|IVA|UF|UTM)\b", txt))
    out |= set(re.findall(r"\b(?:notar\w+|municipalidad|diario oficial|conservador|abril|enero|julio)\b", txt.lower()))
    return {a.strip() for a in out if len(a.strip()) > 1}

def main():
    d = json.load(io.open(BANCO, encoding="utf-8-sig"))
    m = SentenceTransformer(EMB)
    col = chromadb.PersistentClient(path=os.path.join(AI, "chroma_db")).get_or_create_collection("sii_markdown")
    res, t0 = [], time.time()
    print("modelo=%s  k=%d  num_predict=%d  preguntas=%d" % (MODELO, K, NUM_PREDICT, len(d)), flush=True)

    for i, p in enumerate(d, 1):
        gt = p["ground_truth"]
        esperado = gt["md_origen"] is not None
        esp = {os.path.basename(x) for x in ([gt["md_origen"]] + gt.get("md_alternativos", [])) if x}

        vec = [float(x) for x in m.encode([p["pregunta"]], show_progress_bar=False)[0]]
        q = col.query(query_embeddings=[vec], n_results=K)
        frags = [{"document": doc, "metadata": mt}
                 for doc, mt in zip(q["documents"][0], q["metadatas"][0])]
        got = [os.path.basename(f["metadata"].get("source", "?")) for f in frags]

        try:
            r = httpx.post(OLLAMA, timeout=180, json={
                "model": MODELO, "stream": False,
                "messages": [{"role": "system", "content": _build_system_prompt(frags)},
                             {"role": "user", "content": p["pregunta"]}],
                "options": {"temperature": 0.0, "top_p": 0.1,
                            "num_predict": NUM_PREDICT, "num_ctx": 4096}})
            ans = r.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            ans = "<<ERROR: %s>>" % e

        anc = anclas(gt) if esperado else set()
        cub = {a for a in anc if a.lower() in ans.lower()}
        res.append({"id": p["id"], "pregunta": p["pregunta"], "respondible": esperado,
                    "esperado": sorted(esp), "recuperado": got,
                    "retrieval_hit": bool(esp & set(got)) if esperado else None,
                    "abstuvo": abstuvo(ans), "anclas": sorted(anc), "anclas_ok": sorted(cub),
                    "cobertura": round(len(cub) / len(anc), 2) if anc else None,
                    "respuesta": ans})
        if i % 20 == 0:
            print("  %3d/%d  (%.0fs)" % (i, len(d), time.time() - t0), flush=True)
        json.dump(res, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    R = [x for x in res if x["respondible"]]
    N = [x for x in res if not x["respondible"]]
    cob = [x["cobertura"] for x in R if x["cobertura"] is not None]
    hit = sum(1 for x in R if x["retrieval_hit"])
    ab_r = sum(1 for x in R if x["abstuvo"])
    ab_n = sum(1 for x in N if x["abstuvo"])
    aluc = len(N) - ab_n

    print()
    print("=" * 62)
    print("RESULTADO  [%s]  %s" % (ETIQUETA, MODELO))
    print("=" * 62)
    print("RESPONDIBLES (%d)" % len(R))
    print("  retrieval_hit@%-2d ............ %2d  (%3.0f%%)" % (K, hit, 100.0 * hit / len(R)))
    print("  abstuvo indebidamente ...... %2d  (%3.0f%%)" % (ab_r, 100.0 * ab_r / len(R)))
    print("  cobertura de datos ......... %3.0f%%" % (100 * sum(cob) / len(cob) if cob else 0))
    print("NO RESPONDIBLES (%d)" % len(N))
    print("  abstuvo (correcto) ......... %2d  (%3.0f%%)" % (ab_n, 100.0 * ab_n / len(N)))
    print("  ALUCINO .................... %2d  (%3.0f%%)" % (aluc, 100.0 * aluc / len(N)))
    print()
    print("  fallos de generacion ....... %2d   (abstencion indebida + alucinacion)" % (ab_r + aluc))
    print("  fallos de retrieval ........ %2d" % (len(R) - hit))
    print()
    print("-> %s" % OUT)

if __name__ == "__main__":
    main()
