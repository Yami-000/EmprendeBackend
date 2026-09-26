import asyncio
import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import chromadb
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

from sentence_transformers import SentenceTransformer


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
        return SentenceTransformer("all-MiniLM-L6-v2")

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
    emb = await asyncio.to_thread(_st_model.encode, [text], show_progress_bar=False)
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
        # Iteracion 1.10, Fase 1: NO aplanar los saltos de linea. El aplanado
        # convertia las tablas markdown en una fila de pipes sin estructura.
        # Ningun chunk del indice supera los 1400 caracteres (max. 1378), asi
        # que el truncado no recorta ninguna cita.
        snippet = doc[:1400]
        ctx_lines.append(f"[{i}] Fuente: {src}\n{snippet}\n")
    return base + "\n" + "\n".join(ctx_lines)


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

    # Embed the query
    try:
        query_vec = await _embed_text(payload.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding error: {str(e)}")

    # Retrieve top-k
    try:
        fragments = await _query_chroma(query_vec, k=6)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")

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
                yield f"event: error\ndata: Ollama request failed: {str(e)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
