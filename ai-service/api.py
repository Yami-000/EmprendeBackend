import asyncio
import os
import time
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import chromadb
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

from sentence_transformers import SentenceTransformer

# Contrato unico del embedder. Si esto y ingest.py dejan de coincidir, los
# vectores del indice y los de la consulta no son comparables.
from embedding import MODEL_NAME, para_consulta
import traza


BASE_DIR = Path(__file__).resolve().parent
CHROMA_DIR = BASE_DIR / "chroma_db"
CHROMA_COLLECTION = "sii_markdown"
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2"

# Respuesta canónica cuando el contexto no contiene la información pedida.
# Vive aquí como constante porque la usan dos rutas distintas: la regla #3 del
# system prompt (el modelo la emite) y el pipeline de dos pasos (se devuelve
# directo cuando el juez dictamina que no hay respaldo, sin llamar al redactor).
FRASE_ABSTENCION = (
    "Lo siento, mi base de conocimientos actual no incluye esa información "
    "específica sobre las normativas del SII."
)

import logging
logger = logging.getLogger(__name__)

# Detector de abstencion. Vive JUNTO a FRASE_ABSTENCION porque depende de ella: la
# primera entrada de la lista es un fragmento de esa frase.
#
# Es un heuristico LEXICO, y conviene saberlo porque las dos metricas end-to-end mas
# importantes -alucinacion y abstencion indebida- se calculan sobre el. Un modelo que
# exprese la abstencion con otras palabras se contaria como respondiendo. La lista
# tuvo que ampliarse tras la corrida de llama3.1:8b, porque los modelos grandes
# RAZONAN la ausencia del dato en vez de usar la frase canonica del prompt.
#
# Lo importan tanto evaluar_banco.py como evaluar_endpoint.py: una copia divergente
# haria que las dos mediciones no fueran comparables.
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


app = FastAPI(title="ai-service RAG API")


class ChatRequest(BaseModel):
    query: str
    history: Optional[List[Dict[str, Any]]] = None


# Globals populated at startup
_st_model: Optional[SentenceTransformer] = None
_chroma_client: Optional[chromadb.Client] = None
_collection: Optional[Any] = None


@app.on_event("startup")
async def startup_event():
    global _st_model, _chroma_client, _collection
    # Load sentence-transformers model in a thread to avoid blocking event loop
    def load_st():
        return SentenceTransformer(MODEL_NAME)

    _st_model = await asyncio.to_thread(load_st)

    # Init chromadb client
    try:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = _chroma_client.get_or_create_collection(name=CHROMA_COLLECTION)
    except Exception as e:
        _chroma_client = None
        _collection = None
        # don't raise here; we'll return 500 on requests if needed


async def _embed_text(text: str) -> List[float]:
    if _st_model is None:
        raise RuntimeError("Embedding model not loaded")
    # run encode in thread
    # para_consulta agrega el prefijo de CONSULTA. Usar el de pasaje aca
    # invertiria la asimetria que el modelo aprendio.
    emb = await asyncio.to_thread(
        _st_model.encode, [para_consulta(text)], show_progress_bar=False)
    vec = emb[0]
    return [float(x) for x in vec]


def _build_system_prompt(fragments: List[Dict[str, Any]]) -> str:
    base = f"""Eres 'Ecia', asistente tributario y legal especializado EXCLUSIVAMENTE en normativa chilena vigente.

TERMINOLOGÍA OBLIGATORIA — usa SOLO estos términos chilenos:
- Identificación personal: "Cédula de Identidad" (NUNCA "DNI", "pasaporte" como documento estándar, ni "NIT")
- Número de empresa: "RUT" (NUNCA "NIF", "NIT", "RUC")
- SII = "Servicio de Impuestos Internos" (NUNCA "Servicio de Integración Nacional" ni ninguna otra variante)
- Tipos de sociedad válidos: Persona Natural con Giro, MEF, EIRL, SRL, SpA, SA abierta, SA cerrada, Sociedad Colectiva, Sociedad Comanditaria
- Instituciones válidas: SII, Notaría, Diario Oficial, Conservador de Bienes Raíces, Municipalidad, SEREMI de Salud, Ministerio de Economía

REGLAS ABSOLUTAS:
1. USA ÚNICAMENTE la información del 'Contexto recuperado'. Nada más.
2. PROHIBIDO inventar o extrapolar de otros países. No existen en Chile: "matrícula mercantil", "DNI", "NIT", "RUC", "Cámara de Comercio" como ente formalizador, "hacienda pública".
3. Si la respuesta NO está en el contexto, di EXACTAMENTE: "{FRASE_ABSTENCION}"
4. NUNCA inventes costos, plazos, formularios ni instituciones.

FORMATO:
- Máximo 3-5 oraciones o listado corto.
- Sin introducción ni cierre. Directo al punto.
- Sin frases como "Por supuesto", "Claro que sí", "Entiendo tu pregunta"."""
    ctx_lines = ["\nContexto recuperado:"]
    for i, f in enumerate(fragments, 1):
        src = f.get("metadata", {}).get("source", "")
        doc = f.get("document", f.get("page_content", ""))
        snippet = doc.replace('\n', ' ')[:1400]
        ctx_lines.append(f"[{i}] Fuente: {src}\n{snippet}\n")
    # Probado 2026-09-17: mover la regla de abstención a un cierre tras el contexto
    # subió la alucinación de 34% a 78%. Reforzar "usa el contexto" justo antes de
    # generar empuja al modelo a forzar una respuesta con los fragmentos a mano.
    # Ver tests/iteraciones/experimento_prompt_v2.md antes de reintentarlo.
    return base + "\n" + "\n".join(ctx_lines)


# Variantes del prompt del juez. Se mantienen ambas porque el experimento las
# compara: cambiar la calibración del juez es la variable bajo estudio en la
# iteración 1.6, y sobrescribir una perdería la posibilidad de reproducirla.
JUEZ_PROMPT_BASES = {
    # A1 (2026-09-22): especificidad 50/50 pero 9 falsos negativos sobre datos
    # que sí estaban en el contexto. Sospecha: "ante cualquier duda responde NO"
    # domina sobre el resto en un modelo de 3B.
    "estricto": """Eres un verificador estricto. Tu única tarea es decidir si el CONTEXTO de abajo contiene la información necesaria para responder la PREGUNTA de forma completa y específica.

Reglas:
- Responde con UNA sola palabra: SI o NO.
- Responde SI solo si el contexto menciona explícitamente el dato pedido (cifra, plazo, nombre de institución, definición, procedimiento), no solo un tema relacionado o parecido.
- Responde NO si el contexto trata un tema similar pero no contiene el dato específico que pide la pregunta.
- Ante cualquier duda, responde NO.
- No expliques tu respuesta. No agregues nada más que SI o NO.""",

    # 1.12 (2026-09-26): idéntico a 'estricto' salvo la enumeración de tipos de
    # dato, que agrega dos: comparación y delimitación.
    #
    # POR QUÉ: tras la 1.10, tres preguntas seguían negadas con el predicado en
    # el contexto —en el PUESTO 1 dos de ellas— así que no era retrieval.
    # PREG-064 y 084 preguntan "¿cuál es la diferencia entre...?" y PREG-010
    # "¿en el SII o en otra institución?". La lista de 'estricto' era
    # (cifra, plazo, nombre de institución, definición, procedimiento): una
    # comparación no es ninguna de esas cinco, y el juez la aplicaba al pie de
    # la letra.
    #
    # NO ES 'flexible', QUE ESTÁ REFUTADO DOS VECES. Esta variante NO toca el
    # umbral de certeza: conserva "Ante cualquier duda, responde NO" y sigue
    # exigiendo mención explícita. Solo amplía QUÉ CUENTA como dato. Lo que
    # destruía la especificidad en 'flexible' era admitir el dato "redactado con
    # otras palabras" y "repartido entre varios fragmentos", que es aflojar el
    # umbral, no la taxonomía.
    "estricto_taxonomia": """Eres un verificador estricto. Tu única tarea es decidir si el CONTEXTO de abajo contiene la información necesaria para responder la PREGUNTA de forma completa y específica.

Reglas:
- Responde con UNA sola palabra: SI o NO.
- Responde SI solo si el contexto menciona explícitamente el dato pedido (cifra, plazo, nombre de institución, definición, procedimiento, comparación entre dos figuras, o delimitación de qué organismo interviene y cuál no), no solo un tema relacionado o parecido.
- Responde NO si el contexto trata un tema similar pero no contiene el dato específico que pide la pregunta.
- Ante cualquier duda, responde NO.
- No expliques tu respuesta. No agregues nada más que SI o NO.""",

    # A2 (2026-09-23): quita el sesgo hacia negar y nombra explícitamente las
    # formas en que el dato puede aparecer. Varios falsos negativos de A1
    # (PREG-076 "25% / 27%", PREG-067 "$110.000 – $380.000") tenían el dato
    # dentro de una tabla markdown.
    "flexible": """Eres un verificador. Tu única tarea es decidir si el CONTEXTO de abajo contiene información suficiente para responder la PREGUNTA.

Reglas:
- Responde con UNA sola palabra: SI o NO.
- Responde SI si el dato que pide la pregunta aparece en el contexto, aunque esté redactado con otras palabras, dentro de una tabla, o repartido entre varios fragmentos.
- Responde NO únicamente si el contexto no contiene ese dato: porque trata otro tema, o porque menciona el tema sin dar la información pedida.
- No expliques tu respuesta. No agregues nada más que SI o NO.""",
}


# Iteración 1.16 (B2). Descomposición de preguntas comparativas, SOLO para el juez.
#
# POR QUÉ: la 1.12 demostró con scripts/sonda_descomposicion.py que el juez de 3B
# verifica UN HECHO A LA VEZ. Con el mismo contexto y el mismo prompt, PREG-084 da
# NO como "¿cuál es la diferencia entre los tipos de socios?" y SI a sus dos
# subpreguntas por separado. No es la instrucción del prompt —refutado tres veces—
# es la tarea: pedirle una relación entre dos hechos.
#
# POR QUÉ UNA REGLA Y NO UN MODELO: generar subpreguntas con un LLM cuesta una
# llamada más por consulta y produce texto fuera del corpus, que es el modo de
# fallo que mató la Fase 0 de la 1.9. El patrón "diferencia entre X y Y" cubre 6
# de las 100 preguntas del banco y se parte con una expresión regular: gratis y
# determinista.
#
# POR QUÉ 'TODAS' Y NO 'ALGUNA': una comparación necesita los DOS lados en el
# contexto. Exigir que todas las subpreguntas den SI es lo que protege la
# especificidad — de las 6 que encajan en el patrón, 2 son preguntas SIN respaldo
# (PREG-007 y PREG-029) y el corpus no tiene alguno de sus lados.
#
# LO QUE NO HACE, deliberadamente: no toca el retrieval ni el redactor. El
# contexto se recupera con la pregunta ORIGINAL y el redactor recibe la pregunta
# ORIGINAL. Si la descomposición alimentara el retrieval podría traer contexto que
# hace parecer pertinente algo que no lo es, y eso sí tocaría la especificidad.
_COMPARATIVA = re.compile(
    r"\bdiferencias?\b[^?]*?\bentre\b\s+(.+?)\s*\??$", re.IGNORECASE)


def descomponer_comparativa(pregunta: str) -> List[str]:
    """Subpreguntas por definición para una pregunta comparativa, o [] si no aplica.

    "¿Qué diferencia existe entre una SA Cerrada y una SA Abierta?"
      -> ["¿Qué caracteriza a una SA Cerrada?",
          "¿Qué caracteriza a una SA Abierta?"]

    Devuelve [] cuando no reconoce el patrón, que es lo correcto: es mejor no
    descomponer que descomponer mal. El caso "entre los tipos de socios en una
    Sociedad Comanditaria" no tiene dos lados separables por " y " y cae acá.
    """
    m = _COMPARATIVA.search(pregunta or "")
    if not m:
        return []
    cola = m.group(1).strip()
    # Se parte por el ULTIMO " y ": en "una EIRL y una Persona Natural con Giro"
    # el primer " y " no existe, pero en enumeraciones mas largas el ultimo es el
    # que separa los dos terminos que se comparan.
    partes = re.split(r"\s+y\s+", cola)
    if len(partes) < 2:
        return []
    izq = " y ".join(partes[:-1]).strip(" ,.")
    der = partes[-1].strip(" ,.?")
    if not izq or not der or len(izq) < 3 or len(der) < 3:
        return []
    return ["¿Qué caracteriza a %s?" % izq, "¿Qué caracteriza a %s?" % der]


def _build_judge_prompt(fragments: List[Dict[str, Any]], variante: str = "estricto") -> str:
    """Prompt del juez binario del pipeline de dos pasos (iteración 1.6).

    Decide si el contexto contiene la respuesta, sin redactarla. Deliberadamente
    NO incluye las reglas de terminología chilena de _build_system_prompt: esas
    aplican a la redacción, y un prompt más corto reduce la superficie de fallo
    de la única decisión que importa aquí.

    El fail-safe ante ambigüedad NO vive aquí sino en el parseo de la respuesta
    (parse_juicio): instruir al modelo a dudar hacia NO resultó demasiado
    agresivo en A1.
    """
    base = JUEZ_PROMPT_BASES[variante]
    ctx_lines = ["\nCONTEXTO:"]
    for i, f in enumerate(fragments, 1):
        src = f.get("metadata", {}).get("source", "")
        doc = f.get("document", f.get("page_content", ""))
        # El aplanado esta medido y es neutro: quitarlo recupera 1 de las 8 del
        # nucleo duro y deja el end-to-end igual (1.10 Fase 1). Los caracteres son
        # identicos en ambas versiones, asi que el truncado no recorta ninguna cita.
        snippet = doc.replace('\n', ' ')[:1400]
        ctx_lines.append(f"[{i}] Fuente: {src}\n{snippet}\n")
    return base + "\n" + "\n".join(ctx_lines)


# Iteración 2.0. El juez en producción, y el parseo de su veredicto.
#
# Hasta acá el pipeline de dos pasos vivía SOLO en scripts/evaluar_banco.py. Todo
# lo medido en 16 iteraciones era del arnés, no del bot: /chat servía un paso, que
# alucina 34%. Esto lo porta.
#
# num_predict=5 porque el juez solo responde SI o NO. No es una micro-optimización:
# el 98% de su costo es leer el contexto, pero dejarle 300 tokens de salida invita a
# que explique su veredicto y eso rompe el parseo.
NUM_PREDICT_JUEZ = 5


def parse_juicio(texto: str) -> bool:
    """SI/NO del juez. Ante ambiguedad, error o vacio devuelve False.

    El fail-safe apunta deliberadamente hacia NO: un falso NO cuesta una abstencion
    indebida, un falso SI cuesta una alucinacion. En normativa tributaria preferimos
    lo primero.

    Es la MISMA funcion que scripts/evaluar_banco.py usa para medir. Si las dos
    divergieran, produccion se comportaria distinto de lo que dicen las metricas —
    que es exactamente el problema que esta iteracion corrige.
    """
    t = (texto or "").strip().upper()
    return bool(re.match(r"^\W*(SI|SÍ)\b", t))


async def _juzgar(fragments: List[Dict[str, Any]], pregunta: str) -> bool:
    """Una llamada NO streameada al juez. True si el contexto contiene el dato."""
    body = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": _build_judge_prompt(fragments)},
            {"role": "user", "content": pregunta},
        ],
        "stream": False,
        "options": {"temperature": 0.0, "top_p": 0.1,
                    "num_predict": NUM_PREDICT_JUEZ, "num_ctx": 4096},
    }
    # Timeout propio y mas corto que el del redactor: el juez emite 5 tokens, asi
    # que si tarda mas de 60 s algo esta mal y conviene fallar hacia la abstencion
    # en vez de dejar al usuario esperando el timeout del bot.
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(OLLAMA_URL, json=body)
        r.raise_for_status()
        crudo = (r.json().get("message") or {}).get("content", "")
    # Se devuelve tambien el texto crudo: la traza lo muestra, y es lo que
    # delata un problema de parseo (un juez que explica en vez de decir SI/NO).
    return parse_juicio(crudo), crudo


async def decidir_si_responder(fragments: List[Dict[str, Any]],
                               pregunta: str, t=None) -> bool:
    """El juez, con la descomposicion de comparativas como segunda oportunidad.

    Devuelve True si hay que llamar al redactor.

    NOTA SOBRE EL ORDEN, que no es arbitrario: la descomposicion solo se intenta
    cuando el juez ya dijo NO, asi que no puede convertir un SI en NO y su costo
    recae unicamente en los casos que de otro modo se perderian. Y se exige que
    TODAS las subpreguntas den SI: una comparacion necesita los dos lados en el
    contexto, y esa conjuncion es lo que protege la especificidad. Medido: de las 5
    preguntas del banco que el patron cubre, 2 son sin respaldo y las dos dieron NO
    en ambas subpreguntas.

    Si el juez falla por red o por error de Ollama, se devuelve False: abstenerse.
    Preferimos callar antes que responder sin haber verificado.
    """
    def _t(etiqueta, detalle="", seg=None):
        if t is not None:
            t.paso(etiqueta, detalle, seg)

    def _sub(detalle):
        if t is not None:
            t.sub(detalle)

    try:
        t1 = time.time()
        veredicto, crudo = await _juzgar(fragments, pregunta)
        _t("JUEZ", "%-3s  respondio: %r" % ("SI" if veredicto else "NO",
                                            (crudo or "").strip()[:20]),
           time.time() - t1)
        if veredicto:
            # 2.1: veto de compuestas. El juez aprueba una pregunta "X y Y" si
            # reconoce UNA parte, y eso filtro una alucinacion real desde
            # Telegram. Si NINGUNA de las dos mitades se sostiene sola, su
            # aprobacion no se apoya en nada y se rechaza. Solo se veta cuando
            # las dos dan NO: exigir que las dos den SI rompia PREG-105.
            mitades = partir_compuesta(pregunta)
            if not mitades:
                _t("COMPUESTA", "no aplica, se acepta el SI")
                return True
            _t("COMPUESTA", "es compuesta: se comprueba cada mitad")
            veredictos = []
            for m in mitades:
                ok, _ = await _juzgar(fragments, m)
                veredictos.append(ok)
                _sub("%-3s %s" % ("SI" if ok else "NO", m[:44]))
            if not any(veredictos):
                _t("VETO", "ninguna mitad se verifica -> se ANULA el SI")
                logger.info("Veto de compuesta: el juez aprobo '%s' pero "
                            "ninguna mitad se verifica.", pregunta[:60])
                return False
            _t("COMPUESTA", "al menos una mitad se verifica -> se mantiene")
            return True

        subs = descomponer_comparativa(pregunta)
        if not subs:
            _t("RESCATE", "no es comparativa: nada que intentar")
            return False
        _t("RESCATE", "es comparativa: se parte en subpreguntas")
        for sub in subs:
            ok, _ = await _juzgar(fragments, sub)
            _sub("%-3s %s" % ("SI" if ok else "NO", sub[:44]))
            if not ok:
                _t("RESCATE", "una subpregunta falla -> se abstiene")
                return False
        _t("RESCATE", "todas las subpreguntas dan SI -> se responde")
        return True
    except Exception as exc:
        _t("ERROR", "el juez fallo (%s). Se abstiene." % str(exc)[:34])
        logger.warning("El juez fallo (%s). Se abstiene por precaucion.", exc)
        return False


def _sse_texto(texto: str) -> str:
    """Un texto suelto, con la forma que el bot ya sabe parsear.

    src/bot.js separa por lineas, quita el prefijo 'data: ', intenta JSON.parse y
    usa message.content. Emitir el mismo sobre que Ollama evita tocar el bot: el
    camino de abstencion se ve igual que una respuesta, solo que sin modelo detras.
    """
    return "data: %s\n\n" % json.dumps(
        {"message": {"role": "assistant", "content": texto}, "done": True},
        ensure_ascii=False)

# Iteración 2.1. Veto de preguntas compuestas, y la ayuda al abstenerse.
#
# EL FALLO QUE ORIGINA ESTO, reportado desde Telegram el 2026-09-30:
#
#   "Que es el sii?"                              -> abstiene  (correcto)
#   "Que es el SII y cual es su mision?"          -> RESPONDE, e inventa
#
# La segunda respuesta afirmaba que el SII se encarga de "la recaudacion de los
# ingresos publicos", que no esta en el corpus y ademas es FALSO: el SII gira, la
# Tesoreria recauda. Es la misma confusion que PREG-045 testea.
#
# EL MECANISMO, medido con scripts/sonda_compuestas.py (3 repeticiones cada una,
# retrieval real con k=3, veredicto deterministico en las 7):
#
#   ¿Que es el SII?                                          NO
#   ¿Cual es su mision institucional?                        NO
#   ¿Que es el SII y cual es su mision institucional?        NO
#   ¿Que es el servicio de impuestos internos (SII) y        SI   <- LA FUGA
#    cual es su mision institucional?
#   ... la misma, escrita sin tildes                         NO
#   ¿Que es el RUT y cual es su mision?                      NO
#   ¿Que es la Tesoreria y cual es su funcion?               NO
#
# En una pregunta COMPUESTA el juez puede aprobar reconociendo UNA parte: aca
# aprueba el conjunto mientras rechaza las DOS mitades por separado. Es el espejo
# del caso comparativo de la 1.16: alli exigia las dos y fallaba, aca le basta
# una.
#
# HONESTIDAD SOBRE LA EVIDENCIA: de las 7 variantes probadas la fuga reproduce en
# UNA, y es justo la forma larga que se escribio en Telegram. Las variantes con
# 'RUT' y la forma corta del SII, que una version anterior de este comentario daba
# como fugas, NO reproducen. El caso es deterministico (3 de 3) pero es UNO: esto
# tapa una fuga verificada, no una clase de fugas cuantificada.
#
# Y la fuga depende de la ORTOGRAFIA: con el mismo trio de documentos, la forma
# con tildes da SI y la misma sin tildes da NO. No es inestabilidad del juez
# —cada una es deterministica— sino sensibilidad al texto de la pregunta.
#
# POR QUE UN VETO Y NO UNA CONJUNCION: exigir que las dos mitades den SI arregla
# la fuga pero ROMPE una pregunta legitima del banco. PREG-019 ("¿Que es el F29 y
# que obligaciones tributarias principales se declaran en el?") da SI en la
# primera mitad y NO en la segunda, y hoy se responde bien: la conjuncion la
# rechazaria. El veto solo actua cuando NINGUNA mitad se verifica, que es cuando
# la aprobacion del compuesto no se apoya en nada.
#
#   caso                      juez   mitades   conjuncion   veto
#   la fuga del SII            SI     NO, NO      NO         NO   arregla
#   PREG-019                   SI     SI, NO      NO !       SI   conserva
#   PREG-062/107/109/115       SI     SI, SI      SI         SI   conserva
#
# MEDIDO SOBRE EL BANCO COMPLETO por el endpoint: el veto se disparo 0 veces en
# 100 preguntas. El juez aprobo 5 compuestas y las 5 tenian al menos una mitad
# verificable. Cero vuelcos contra el control: no es que el saldo empate, es que
# ninguna pregunta cambio de resultado.
#
# ALCANCE: 13 de las 100 preguntas del banco encajan en el patron (7 respondibles,
# 6 sin respaldo). El costo son 2 llamadas extra al juez, y solo cuando ya dijo SI
# a una compuesta.

# Un ' y ' seguido de INTERROGATIVO marca una segunda pregunta. Sin esa exigencia
# la regla partiria conjunciones de verbos y sustantivos, que no son dos
# preguntas: PREG-045 dice "recaudar y cobrar" y PREG-069 "declarar y pagar".
# Partir ahi produce mitades sin sentido y el veto rechazaria preguntas validas.
_INTERROGATIVO = (r"(?:qu[eé]|cu[aá]l(?:es)?|qui[eé]n(?:es)?|c[oó]mo|cu[aá]ndo|"
                  r"d[oó]nde|cu[aá]nto?s?|para\s+qu[eé]|ante\s+qui[eé]n(?:es)?|"
                  r"desde\s+cu[aá]ndo|por\s+qu[eé]|en\s+qu[eé])\b")
_COMPUESTA = re.compile(r"\s+y\s+(?=" + _INTERROGATIVO + ")", re.IGNORECASE)


def partir_compuesta(pregunta: str) -> List[str]:
    """Las dos mitades de una pregunta compuesta, o [] si no lo es.

    "¿Qué es el SII y cuál es su misión institucional?"
      -> ["¿Qué es el SII?", "¿cuál es su misión institucional?"]

    Se parte por el PRIMER ' y ' seguido de interrogativo: en una pregunta con
    tres partes, las dos primeras quedan juntas del lado izquierdo, que es
    suficiente para el veto. No se intenta una descomposición completa porque el
    veto solo necesita saber si ALGUNA parte se sostiene.
    """
    q = (pregunta or "").strip()
    m = _COMPUESTA.search(q)
    if not m:
        return []
    izq = q[:m.start()].strip().lstrip("¿").strip(" ,.")
    der = q[m.end():].strip().strip(" ,.")
    if len(izq) < 8 or len(der) < 4:
        return []
    return ["¿%s?" % izq.rstrip("?"), "¿%s?" % der.rstrip("?")]


# Texto que se agrega a la abstención para que el usuario sepa qué SI puede
# preguntar. Va como sufijo y NO reemplaza a FRASE_ABSTENCION: el detector
# abstuvo() busca un fragmento de esa frase, y las metricas de alucinacion y
# abstencion indebida se calculan sobre el. Cambiar la frase romperia la
# comparabilidad con las 18 iteraciones anteriores.
#
# Y va en el ENDPOINT, no en el system prompt: meterlo en el prompt cambiaria lo
# que el redactor genera, que es una variable medida. Esto es solo presentacion.
AYUDA_ABSTENCION = (
    "\n\nPuedo ayudarte con trámites de formalización de empresas en Chile:\n"
    "• Tipos de empresa: EIRL, SpA, SRL, SA, MEF\n"
    "• Constitución: Tu Empresa en un Día y régimen tradicional\n"
    "• Costos y plazos de cada trámite\n"
    "• Inicio de Actividades y RUT ante el SII\n"
    "• Patente municipal y permisos sanitarios\n"
    "• Obligaciones tributarias: F29, F22, libros de contabilidad\n\n"
    "Probá con algo como: «¿Cuánto cuesta constituir una SpA?» o "
    "«¿Quién inscribe la empresa en el Registro de Comercio?»"
)

# Saludos y mensajes que no son preguntas. Se contestan sin consultar el modelo:
# ademas de la mala experiencia, cada uno costaba ~7 s de juez para nada.
#
# La lista es corta y la comparacion es sobre el texto COMPLETO normalizado, no
# por subcadena: "hola" saluda, pero "hola, cuanto cuesta una SpA?" es una
# pregunta y tiene que seguir al pipeline. Verificado que ninguna de las 100
# preguntas del banco cae aca.
_SALUDOS = {"hola", "hola!", "buenas", "buenos dias", "buenas tardes",
            "buenas noches", "hey", "holi", "que tal", "como estas",
            "buen dia", "saludos", "start", "/start", "ayuda", "/ayuda",
            "help", "/help", "gracias", "chao", "adios"}

BIENVENIDA = (
    "Hola. Soy un asistente sobre formalización de empresas y trámites del SII "
    "en Chile." + AYUDA_ABSTENCION.replace("\n\nPuedo ayudarte con trámites de "
                                           "formalización de empresas en Chile:",
                                           "")
)


def es_saludo(texto: str) -> bool:
    """El mensaje es un saludo o un comando, no una pregunta."""
    t = unicodedata.normalize("NFKD", (texto or "").strip().lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.strip(" ¿?¡!.,").strip()
    return t in _SALUDOS


async def _query_chroma(query_vec: List[float], k: int = 4) -> List[Dict[str, Any]]:
    if _collection is None:
        raise RuntimeError("Chroma collection not available")
    # chroma expects a list of queries
    results = _collection.query(query_embeddings=[query_vec], n_results=k)
    # results typically contains 'documents' and 'metadatas'
    docs = []
    documents = results.get("documents") or []
    metadatas = results.get("metadatas") or []
    for doc, meta in zip(documents[0] if documents and isinstance(documents[0], list) else documents, metadatas[0] if metadatas and isinstance(metadatas[0], list) else metadatas):
        docs.append({"document": doc, "metadata": meta})
    return docs


@app.post("/chat")
async def chat_endpoint(payload: ChatRequest):
    # Validate chroma ready
    if _collection is None:
        raise HTTPException(status_code=500, detail="ChromaDB collection not available")

    # 2.1: un saludo no es una pregunta. Se contesta sin consultar al modelo:
    # ademas de la mala experiencia de recibir "no incluye esa informacion" ante
    # un "hola", cada saludo costaba ~7 s de juez para nada.
    if es_saludo(payload.query):
        t = traza.Consulta(payload.query)
        t.cerrar("SALUDO", "no es pregunta: bienvenida sin consultar al modelo")

        async def solo_bienvenida() -> AsyncGenerator[str, None]:
            yield _sse_texto(BIENVENIDA)
        return StreamingResponse(solo_bienvenida(),
                                 media_type="text/event-stream")

    t = traza.Consulta(payload.query)

    # Embed the query
    try:
        _t0 = time.time()
        query_vec = await _embed_text(payload.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding error: {str(e)}")

    # Retrieve top-k
    try:
        # Iteración 1.14: k baja de 6 a 3, y es el embedder nuevo lo que lo
        # permite. Con multilingual-e5-small, anclaje@3 es 30/37 — mejor que el
        # 28/37 que daba MiniLM con k=6. Medido sobre el banco completo:
        #
        #             sensibilidad  especificidad  ALUCINACION  latencia juez
        #   k=6          38/50         49/50          1/50         13,0 s
        #   k=3          34/50         49/50          0/50          6,9 s
        #
        # Con k=6 el juez aprueba PREG-045 ("¿qué organismo recauda los impuestos
        # girados por el SII?", cuya respuesta es la Tesorería y no está en el
        # corpus) y el redactor la contesta mal. Con k=3 no llega ese contexto.
        # El 98% del costo del juez es leer contexto, así que k=3 casi lo parte
        # en dos: una consulta respondida baja de 17,5 s a 10,3 s de media.
        fragments = await _query_chroma(query_vec, k=3)
        t.paso("RETRIEVE", "k=3", time.time() - _t0)
        for _n, _f in enumerate(fragments, 1):
            t.sub("%d  %s" % (_n, os.path.basename(
                _f.get("metadata", {}).get("source", "?"))))
    except Exception as e:
        t.cerrar("ERROR", "retrieval: %s" % e)
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")

    # Iteración 2.0: PRIMER PASO. El juez decide si el contexto contiene el dato
    # antes de que nadie redacte nada. Es lo que lleva la alucinación de 34% a 0%,
    # y hasta esta iteración vivía solo en el arnés de evaluación.
    if not await decidir_si_responder(fragments, payload.query, t):
        t.cerrar("ABSTIENE", "sin segunda llamada al modelo")
        # El camino NO **no llama al modelo**: devuelve la frase canónica directo.
        # Por eso el pipeline de dos pasos es MAS RAPIDO que el de un paso cuando
        # rechaza — medido sobre el banco, 62 de 100 preguntas se resuelven con una
        # sola llamada.
        async def solo_abstencion() -> AsyncGenerator[str, None]:
            yield _sse_texto(FRASE_ABSTENCION + AYUDA_ABSTENCION)
        return StreamingResponse(solo_abstencion(),
                                 media_type="text/event-stream")

    # SEGUNDO PASO: el redactor. Recibe la pregunta ORIGINAL, nunca las
    # subpreguntas de la descomposición: esas son un instrumento del juez.
    # La traza NO se cierra aca: se cierra dentro de event_stream, cuando el
    # stream termina. Si se cerrara aca, el TIEMPO de una consulta respondida
    # dejaria fuera toda la redaccion, que es la parte mas lenta, y el numero
    # seria enganoso justo en el caso que interesa medir.
    t.paso("REDACTOR", "el juez aprobo: se llama al modelo para redactar")
    system_prompt = _build_system_prompt(fragments)

    # Build messages for Ollama
    messages = [{"role": "system", "content": system_prompt}]

    if payload.history:
        # Añade los mensajes previos de la base de datos
        messages.extend(payload.history)

    messages.append({"role": "user", "content": payload.query})

    ollama_body = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": 0.0,
            "top_p": 0.1,
            "num_predict": 300,
            "num_ctx": 4096
        }
    }
    async def event_stream() -> AsyncGenerator[str, None]:
        # Connect to Ollama and stream response
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                async with client.stream("POST", OLLAMA_URL, json=ollama_body) as resp:
                    if resp.status_code != 200:
                        text = await resp.aread()
                        # DEUDA CONOCIDA, anterior a la 2.0: este camino manda al
                        # usuario el contexto recuperado EN CRUDO, no una
                        # respuesta. La traza lo deja visible en vez de que
                        # parezca una respuesta normal.
                        t.cerrar("FALLBACK", "Ollama respondio %s: se envia el "
                                             "contexto EN CRUDO" % resp.status_code)
                        # If Ollama returns non-200, fallback to context
                        fallback = "Respuesta del servicio de LLM no disponible. Contexto recuperado:\n\n"
                        for i, f in enumerate(fragments, 1):
                            src = f.get("metadata", {}).get("source", "")
                            doc = f.get("document", "")
                            snippet = doc.replace('\n', ' ')[:1400]
                            fallback += f"[{i}] {src}: {snippet}\n\n"
                        yield f"data: {fallback}\n\n"
                        return
                    async for chunk in resp.aiter_bytes():
                        if not chunk:
                            continue
                        # decode chunk
                        try:
                            text = chunk.decode("utf-8")
                        except Exception:
                            text = chunk.decode("latin-1", errors="ignore")

                        # Detect common error patterns from Ollama in the stream
                        lowered = text.lower()
                        if "cuda" in lowered or "out of memory" in lowered or 'error' in lowered and 'llama' in lowered:
                            t.cerrar("FALLBACK", "error en el stream: se envia el "
                                                 "contexto EN CRUDO")
                            # produce a helpful fallback message using retrieved fragments
                            fallback = "Respuesta del servicio de LLM no disponible (error de ejecución). Contexto recuperado:\n\n"
                            for i, f in enumerate(fragments, 1):
                                src = f.get("metadata", {}).get("source", "")
                                doc = f.get("document", "")
                                snippet = doc.replace('\n', ' ')[:1400]
                                fallback += f"[{i}] {src}: {snippet}\n\n"
                            yield f"data: {fallback}\n\n"
                            return

                        # Normal streaming: forward to client as SSE data events
                        yield f"data: {text}\n\n"
            except httpx.RequestError as e:
                t.cerrar("ERROR", "el redactor fallo: %s" % str(e)[:40])
                yield f"event: error\ndata: Ollama request failed: {str(e)}\n\n"
            finally:
                # cerrar() es idempotente: si alguno de los caminos de arriba ya
                # cerro la traza con su propia etiqueta, esto no la duplica.
                t.cerrar("LISTO", "respuesta enviada")

    return StreamingResponse(event_stream(), media_type="text/event-stream")
