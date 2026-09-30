# -*- coding: utf-8 -*-
"""Mide el banco A TRAVES DEL ENDPOINT /chat, no replicando el pipeline.

POR QUE EXISTE
--------------
scripts/evaluar_banco.py consulta ChromaDB y Ollama directamente, replicando la
logica del pipeline con los prompts importados de api.py. Es mas rapido y aisla
variables, pero tiene una consecuencia que paso desapercibida durante 16
iteraciones: el pipeline de dos pasos, que lleva la alucinacion de 34% a 0%,
NUNCA se habia implementado en api.py. Todas las metricas del proyecto eran del
arnes, no del sistema que usa la gente.

Este script cierra ese hueco. Habla HTTP con el endpoint real, parsea el SSE como
lo hace src/bot.js, y mide lo que el usuario recibe de verdad.

QUE MIDE, Y QUE NO
------------------
Mide las dos metricas que decide el usuario final:

  abstencion indebida   callo teniendo el dato      (sobre las 50 respondibles)
  ALUCINACION           respondio sin respaldo      (sobre las 50 sin respaldo)

NO puede medir sensibilidad ni especificidad del juez, porque el endpoint no
expone el veredicto: desde afuera no se distingue "el juez dijo NO" de "el juez
dijo SI y el redactor abstuvo igual". Para eso sigue haciendo falta el arnes. Las
dos herramientas son complementarias, no sustitutas.

REQUISITOS
----------
El endpoint tiene que estar corriendo, y Ollama detras:

    ollama serve
    cd ai-service && uvicorn api:app --host 0.0.0.0 --port 11400

Uso:  python scripts/evaluar_endpoint.py <etiqueta> [--url URL] [--limite N]
      python scripts/evaluar_endpoint.py prod_2.0 --limite 10
"""
import argparse, io, json, os, sys, time

import httpx

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI = os.path.join(RAIZ, "ai-service")
sys.path.insert(0, AI)
# El detector de abstencion se IMPORTA de api.py, igual que en evaluar_banco.py.
# Una copia divergente haria que las dos mediciones no fueran comparables, que es
# justo el problema que este script existe para no repetir.
from api import abstuvo  # noqa: E402

BANCO = os.path.join(RAIZ, "tests", "dataset", "banco_preguntas_respuestas.json")

ap = argparse.ArgumentParser()
ap.add_argument("etiqueta")
ap.add_argument("--url", default="http://localhost:11400/chat")
ap.add_argument("--limite", type=int, default=None,
                help="N preguntas, mitad de cada lado del banco")
ap.add_argument("--timeout", type=int, default=180)
args = ap.parse_args()

OUT = os.path.join(RAIZ, "tests", "iteraciones",
                   "resultados_endpoint_%s.json" % args.etiqueta)


def texto_de_sse(cuerpo: str) -> str:
    """Reconstruye la respuesta como lo hace src/bot.js.

    El bot separa por lineas, quita el prefijo 'data: ', intenta JSON.parse y usa
    message.content; si el parseo falla, agrega el texto crudo. Replicar ESE
    parseo es el punto: si el endpoint emitiera algo que el bot no entiende, este
    script lo veria igual que el bot.
    """
    out = []
    for linea in cuerpo.split("\n"):
        linea = linea.strip()
        if not linea or not linea.startswith("data:"):
            continue
        payload = linea[5:].strip()
        if payload == "[DONE]":
            continue
        try:
            out.append((json.loads(payload).get("message") or {}).get("content", ""))
        except Exception:
            out.append(payload)
    return "".join(out)


def main():
    d = json.load(io.open(BANCO, encoding="utf-8-sig"))
    if args.limite:
        mitad = args.limite // 2
        d = d[:mitad] + d[50:50 + (args.limite - mitad)]

    print("endpoint: %s   preguntas: %d\n" % (args.url, len(d)), flush=True)
    res, t0 = [], time.time()
    with httpx.Client(timeout=args.timeout) as cli:
        for i, p in enumerate(d, 1):
            esperado = bool(p["ground_truth"].get("md_origen"))
            t1 = time.time()
            try:
                r = cli.post(args.url, json={"query": p["pregunta"]})
                r.raise_for_status()
                ans = texto_de_sse(r.text).strip()
                err = None
            except Exception as exc:
                ans, err = "", str(exc)
            lat = time.time() - t1
            res.append({"id": p["id"], "pregunta": p["pregunta"],
                        "respondible": esperado, "respuesta": ans,
                        "abstuvo": abstuvo(ans) if ans else True,
                        "error": err, "latencia_s": round(lat, 2)})
            if i % 10 == 0:
                print("   %d/%d  (%.0fs)" % (i, len(d), time.time() - t0), flush=True)

    R = [x for x in res if x["respondible"]]
    N = [x for x in res if not x["respondible"]]
    ab_r = sum(1 for x in R if x["abstuvo"])
    ab_n = sum(1 for x in N if x["abstuvo"])
    aluc = len(N) - ab_n
    errs = [x for x in res if x["error"]]
    lats = [x["latencia_s"] for x in res if not x["error"]]

    print("\n" + "=" * 62)
    print("RESULTADO POR ENDPOINT  [%s]" % args.etiqueta)
    print("=" * 62)
    if R:
        print("RESPONDIBLES (%d)" % len(R))
        print("  abstuvo indebidamente ...... %2d  (%3.0f%%)"
              % (ab_r, 100.0 * ab_r / len(R)))
    if N:
        print("NO RESPONDIBLES (%d)" % len(N))
        print("  abstuvo (correcto) ......... %2d  (%3.0f%%)"
              % (ab_n, 100.0 * ab_n / len(N)))
        print("  ALUCINO .................... %2d  (%3.0f%%)"
              % (aluc, 100.0 * aluc / len(N)))
    if lats:
        print("\n  latencia por consulta ...... %.1fs de media, %.1fs de pico"
              % (sum(lats) / len(lats), max(lats)))
    if errs:
        print("\n  ERRORES DE TRANSPORTE ...... %d  %s"
              % (len(errs), ", ".join(x["id"] for x in errs[:6])))
        print("  (un error cuenta como abstencion: el usuario no recibe respuesta)")
    print("\n  duracion total ............. %.1f min" % ((time.time() - t0) / 60))

    io.open(OUT, "w", encoding="utf-8").write(
        json.dumps(res, ensure_ascii=False, indent=1))
    print("\n-> %s" % OUT)


if __name__ == "__main__":
    main()
