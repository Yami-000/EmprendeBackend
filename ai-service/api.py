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
        _chroma_client = chromadb.Client()
        # Use get_or_create to tolerate missing persisted collection
        try:
            _collection = _chroma_client.get_or_create_collection(name=CHROMA_COLLECTION)
        except Exception:
            _collection = _chroma_client.get_collection(name=CHROMA_COLLECTION)
    except Exception as e:
        # If collection is not found or client fails, keep None and raise on requests
        _chroma_client = None
        _collection = None
        app.logger = getattr(app, "logger", None)
        # don't raise here; we'll return 500 on requests if needed


async def _embed_text(text: str) -> List[float]:
    if _st_model is None:
        raise RuntimeError("Embedding model not loaded")
    # run encode in thread
    emb = await asyncio.to_thread(_st_model.encode, [text], show_progress_bar=False)
    vec = emb[0]
    return [float(x) for x in vec]


def _build_system_prompt(fragments: List[Dict[str, Any]]) -> str:
    base = """Eres 'Ecia', un asistente legal y tributario experto en la formalización de PYMEs en Chile y normativas del SII (Servicio de Impuestos Internos).
REGLA DE ORO: Tienes estrictamente prohibido inventar información, leyes, nombres de trámites o tipos de sociedades.
Tu única fuente de verdad es el 'Contexto recuperado' que se te proporciona abajo.
Si el usuario pregunta algo y la respuesta NO está en el contexto, debes responder EXACTAMENTE: "Lo siento, mi base de conocimientos actual no incluye esa información específica sobre las normativas del SII."
Responde siempre en español, de forma clara, profesional y en formato Markdown."""
    ctx_lines = ["\nContexto recuperado:"]
    for i, f in enumerate(fragments, 1):
        src = f.get("metadata", {}).get("source", "")
        doc = f.get("document", f.get("page_content", ""))
        snippet = doc.replace('\n', ' ')[:800]
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
        fragments = await _query_chroma(query_vec, k=4)
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
            "top_p": 0.1
        }
    }

    async def event_stream() -> AsyncGenerator[str, None]:
        # Connect to Ollama and stream response
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream("POST", OLLAMA_URL, json=ollama_body) as resp:
                    if resp.status_code != 200:
                        text = await resp.aread()
                        # If Ollama returns non-200, fallback to context
                        fallback = "Respuesta del servicio de LLM no disponible. Contexto recuperado:\n\n"
                        for i, f in enumerate(fragments, 1):
                            src = f.get("metadata", {}).get("source", "")
                            doc = f.get("document", "")
                            snippet = doc.replace('\n', ' ')[:800]
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
                                snippet = doc.replace('\n', ' ')[:800]
                                fallback += f"[{i}] {src}: {snippet}\n\n"
                            yield f"data: {fallback}\n\n"
                            return

                        # Normal streaming: forward to client as SSE data events
                        yield f"data: {text}\n\n"
            except httpx.RequestError as e:
                yield f"event: error\ndata: Ollama request failed: {str(e)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
