# -*- coding: utf-8 -*-
"""Arnes de evaluacion end-to-end del banco de 100 preguntas.

Replica el pipeline de produccion (embed -> ChromaDB -> Ollama) y separa
los dos modos de fallo del RAG:

  - RETRIEVAL : el chunk correcto no llego al contexto
  - GENERACION: el chunk llego, pero el modelo no lo uso o alucino

Soporta dos modos:

  UN PASO (default)  : una sola llamada al modelo, con _build_system_prompt.
  DOS PASOS (--dos-pasos, iteracion 1.6): primero un juez binario decide si el
      contexto contiene la respuesta; solo si dice SI se llama al redactor. Si
      dice NO se devuelve FRASE_ABSTENCION sin segunda llamada.

IMPORTANTE: importa los prompts DESDE api.py. No copiarlos aqui: una copia
diverge y se termina midiendo algo distinto de lo que corre en produccion.

Uso:
    python scripts/evaluar_banco.py <etiqueta> [modelo] [k] [num_predict]
                                    [--dos-pasos] [--juez M] [--redactor M]
                                    [--num-predict-juez N]
Ej:
    python scripts/evaluar_banco.py v1
    python scripts/evaluar_banco.py qwen7b qwen2.5:7b 6 300
    python scripts/evaluar_banco.py dospasos_A --dos-pasos --juez llama3.2 --redactor llama3.2
"""
import argparse, json, io, os, re, sys, time
import chromadb, httpx
from sentence_transformers import SentenceTransformer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI = os.path.join(RAIZ, "ai-service")
sys.path.insert(0, AI)
from api import _build_system_prompt, _build_judge_prompt, FRASE_ABSTENCION, JUEZ_PROMPT_BASES

# Posicionales conservados por compatibilidad: los comandos documentados en
# README.md y resultado_1.3.md los usan. Las flags nuevas se suman sin romperlos.
ap = argparse.ArgumentParser()
ap.add_argument("etiqueta")
ap.add_argument("modelo", nargs="?", default="llama3.2")
ap.add_argument("k", nargs="?", type=int, default=6)
ap.add_argument("num_predict", nargs="?", type=int, default=300)
ap.add_argument("--dos-pasos", action="store_true",
                help="activa el pipeline juez+redactor (iteracion 1.6)")
ap.add_argument("--juez", default=None, help="modelo juez (default: el posicional modelo)")
ap.add_argument("--redactor", default=None, help="modelo redactor (default: el posicional modelo)")
ap.add_argument("--num-predict-juez", type=int, default=5,
                help="tokens maximos del juez; alcanza para SI/NO")
ap.add_argument("--juez-prompt", default="estricto", choices=sorted(JUEZ_PROMPT_BASES),
                help="calibracion del prompt del juez (ver JUEZ_PROMPT_BASES en api.py)")
ap.add_argument("--limite", type=int, default=None,
                help="procesar solo las primeras N preguntas (smoke test)")
ap.add_argument("--ids", default=None,
                help="procesar solo estos IDs: lista con comas, o @archivo con "
                     "un ID por linea. Para pruebas dirigidas a un subconjunto "
                     "(ver scripts/subconjunto_dato_integro.py). Excluye --limite.")
args = ap.parse_args()

if args.ids and args.limite:
    ap.error("--ids y --limite son excluyentes: el subconjunto ya define el alcance")


def leer_ids(spec):
    """Lista de IDs desde '@archivo' (uno por linea) o 'A,B,C'."""
    crudo = io.open(spec[1:], encoding="utf-8-sig").read() if spec.startswith("@") else spec
    partes = crudo.replace(",", " ").replace(";", " ").split()
    return [x for x in partes if not x.startswith("#")]

BANCO = os.path.join(RAIZ, "tests", "dataset", "banco_preguntas_respuestas.json")
OUT = os.path.join(RAIZ, "tests", "iteraciones", "resultados_%s.json" % args.etiqueta)
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


def parse_juicio(texto):
    """SI/NO del juez. Ante ambiguedad, error o vacio devuelve False.

    El fail-safe apunta deliberadamente hacia NO: un falso NO cuesta una
    abstencion indebida, un falso SI cuesta una alucinacion. Preferimos lo
    primero.
    """
    t = (texto or "").strip().upper()
    if re.match(r"^\W*(SI|SÍ)\b", t):
        return True
    return False


def llamar_ollama(modelo, system_prompt, pregunta, num_predict):
    """Devuelve (texto, latencia_s). Los errores viajan como texto <<ERROR: ...>>."""
    t0 = time.time()
    try:
        r = httpx.post(OLLAMA, timeout=180, json={
            "model": modelo, "stream": False,
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": pregunta}],
            "options": {"temperature": 0.0, "top_p": 0.1,
                        "num_predict": num_predict, "num_ctx": 4096}})
        texto = r.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        texto = "<<ERROR: %s>>" % e
    return texto, time.time() - t0


def pct(n, total):
    """Porcentaje tolerante a total=0: --ids puede dejar una mitad vacia."""
    return 100.0 * n / total if total else 0.0


def anclas(gt):
    """Datos verificables de la respuesta esperada: cifras, siglas, instituciones."""
    txt = (gt.get("respuesta_esperada") or "") + " " + (gt.get("cita_anclaje") or "")
    out = set(re.findall(r"\d[\d.,]*\s*(?:UF|UTM|CLP|%)?", txt))
    out |= set(re.findall(r"\b(?:F\d{2}|EIRL|SRL|SpA|SA|MEF|SII|RUT|CVE|DTE|SEREMI|IVA|UF|UTM)\b", txt))
    out |= set(re.findall(r"\b(?:notar\w+|municipalidad|diario oficial|conservador|abril|enero|julio)\b", txt.lower()))
    return {a.strip() for a in out if len(a.strip()) > 1}


def main():
    d = json.load(io.open(BANCO, encoding="utf-8-sig"))
    if args.ids:
        pedidos = leer_ids(args.ids)
        indice = {p["id"]: p for p in d}
        faltan = [i for i in pedidos if i not in indice]
        if faltan:
            sys.exit("IDs que no estan en el banco: %s" % ", ".join(faltan))
        d = [indice[i] for i in pedidos]
    if args.limite:
        d = d[:args.limite // 2] + d[50:50 + (args.limite - args.limite // 2)]
    m = SentenceTransformer(EMB)
    col = chromadb.PersistentClient(path=os.path.join(AI, "chroma_db")).get_or_create_collection("sii_markdown")
    res, t0 = [], time.time()

    juez_modelo = args.juez or args.modelo
    redactor_modelo = args.redactor or args.modelo
    if args.dos_pasos:
        print("modo=DOS PASOS  juez=%s (%s)  redactor=%s  k=%d  preguntas=%d"
              % (juez_modelo, args.juez_prompt, redactor_modelo, args.k, len(d)), flush=True)
    else:
        print("modo=un paso  modelo=%s  k=%d  num_predict=%d  preguntas=%d"
              % (args.modelo, args.k, args.num_predict, len(d)), flush=True)

    for i, p in enumerate(d, 1):
        gt = p["ground_truth"]
        esperado = gt["md_origen"] is not None
        esp = {os.path.basename(x) for x in ([gt["md_origen"]] + gt.get("md_alternativos", [])) if x}

        vec = [float(x) for x in m.encode([p["pregunta"]], show_progress_bar=False)[0]]
        q = col.query(query_embeddings=[vec], n_results=args.k)
        frags = [{"document": doc, "metadata": mt}
                 for doc, mt in zip(q["documents"][0], q["metadatas"][0])]
        got = [os.path.basename(f["metadata"].get("source", "?")) for f in frags]

        if args.dos_pasos:
            juicio_txt, juez_lat = llamar_ollama(
                juez_modelo, _build_judge_prompt(frags, args.juez_prompt),
                p["pregunta"], args.num_predict_juez)
            dijo_si = parse_juicio(juicio_txt)
            if dijo_si:
                ans, redactor_lat = llamar_ollama(
                    redactor_modelo, _build_system_prompt(frags), p["pregunta"], args.num_predict)
            else:
                # Sin segunda llamada: este camino es mas rapido que el de un paso.
                ans, redactor_lat = FRASE_ABSTENCION, 0.0
        else:
            ans, _lat = llamar_ollama(
                args.modelo, _build_system_prompt(frags), p["pregunta"], args.num_predict)
            juicio_txt = dijo_si = juez_lat = redactor_lat = None

        anc = anclas(gt) if esperado else set()
        cub = {a for a in anc if a.lower() in ans.lower()}
        res.append({"id": p["id"], "pregunta": p["pregunta"], "respondible": esperado,
                    "esperado": sorted(esp), "recuperado": got,
                    "retrieval_hit": bool(esp & set(got)) if esperado else None,
                    "abstuvo": abstuvo(ans), "anclas": sorted(anc), "anclas_ok": sorted(cub),
                    "cobertura": round(len(cub) / len(anc), 2) if anc else None,
                    "respuesta": ans,
                    "modo": "dos_pasos" if args.dos_pasos else "un_paso",
                    "juez_prompt": args.juez_prompt if args.dos_pasos else None,
                    "juez_respuesta": juicio_txt,
                    "juez_dijo_si": dijo_si,
                    "juez_latencia_s": round(juez_lat, 2) if juez_lat is not None else None,
                    "redactor_latencia_s": round(redactor_lat, 2) if redactor_lat is not None else None})
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

    etq = "%s / %s" % (juez_modelo, redactor_modelo) if args.dos_pasos else args.modelo
    print()
    print("=" * 62)
    print("RESULTADO  [%s]  %s" % (args.etiqueta, etq))
    print("=" * 62)
    print("RESPONDIBLES (%d)" % len(R))
    print("  retrieval_hit@%-2d ............ %2d  (%3.0f%%)" % (args.k, hit, pct(hit, len(R))))
    print("  abstuvo indebidamente ...... %2d  (%3.0f%%)" % (ab_r, pct(ab_r, len(R))))
    print("  cobertura de datos ......... %3.0f%%" % (100 * sum(cob) / len(cob) if cob else 0))
    print("NO RESPONDIBLES (%d)" % len(N))
    print("  abstuvo (correcto) ......... %2d  (%3.0f%%)" % (ab_n, pct(ab_n, len(N))))
    print("  ALUCINO .................... %2d  (%3.0f%%)" % (aluc, pct(aluc, len(N))))
    print()
    print("  fallos de generacion ....... %2d   (abstencion indebida + alucinacion)" % (ab_r + aluc))
    print("  fallos de retrieval ........ %2d" % (len(R) - hit))

    if args.dos_pasos:
        n_si = sum(1 for x in R if x["juez_dijo_si"])
        n_no = sum(1 for x in N if not x["juez_dijo_si"])
        lat_juez = [x["juez_latencia_s"] for x in res if x["juez_latencia_s"] is not None]
        lat_red = [x["redactor_latencia_s"] for x in res if x["redactor_latencia_s"]]
        print()
        print("JUEZ")
        print("  sensibilidad  (SI en respondibles) ..... %2d/%d  (%3.0f%%)"
              % (n_si, len(R), pct(n_si, len(R))))
        print("  especificidad (NO en no respondibles) .. %2d/%d  (%3.0f%%)"
              % (n_no, len(N), pct(n_no, len(N))))
        print("  latencia media juez .................... %.1fs"
              % (sum(lat_juez) / len(lat_juez) if lat_juez else 0.0))
        if lat_red:
            print("  latencia media redactor (camino SI) .... %.1fs" % (sum(lat_red) / len(lat_red)))
            print("  camino NO (sin 2da llamada) ............ %d de %d preguntas"
                  % (len(res) - len(lat_red), len(res)))
    print()
    print("-> %s" % OUT)


if __name__ == "__main__":
    main()
