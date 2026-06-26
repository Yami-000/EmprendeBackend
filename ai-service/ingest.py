import logging
import os
from pathlib import Path

import chromadb
try:
    # Newer chromadb versions deprecate Settings-based construction
    from chromadb.config import Settings  # type: ignore
except Exception:
    Settings = None
import uuid
# Use simple dicts for documents to avoid langchain.schema dependency

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"
CHROMA_DIR = BASE_DIR / "chroma_db"

MODEL_NAME = "nomic-embed-text"


def find_markdown_files(root_dir: Path):
    return sorted(root_dir.rglob("*.md"))


def load_documents(files):
    documents = []
    for file_path in files:
        try:
            text = Path(file_path).read_text(encoding="utf-8")
            logger.debug("Loaded file %s, length %d", file_path, len(text) if text else 0)
            if not text or not text.strip():
                logger.warning("Archivo vacío o sin contenido útil: %s", file_path)
                continue
            doc = {"page_content": text, "metadata": {"source": str(file_path)}}
            documents.append(doc)
        except Exception as exc:
            logger.error("Error al cargar %s: %s", file_path, exc)
    return documents


import re


def _chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 150):
    if not text:
        return []
    # Split by markdown headings or double newlines to preserve structure
    parts = re.split(r'(?m)(?=^#{1,6}\s)', text)
    if len(parts) == 1:
        parts = text.split('\n\n')

    chunks = []
    current = []
    current_len = 0

    for part in parts:
        p = part.strip()
        if not p:
            continue
        plen = len(p)
        if current_len + plen <= chunk_size or not current:
            current.append(p)
            current_len += plen
        else:
            chunk = "\n\n".join(current)
            chunks.append(chunk)
            # start new chunk with overlap
            if chunk_overlap and chunk_overlap < len(chunk):
                overlap_text = chunk[-chunk_overlap:]
                current = [overlap_text, p]
                current_len = len(overlap_text) + plen
            else:
                current = [p]
                current_len = plen

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def split_documents(documents):
    split_docs = []
    for idx, doc in enumerate(documents):
        logger.debug("Splitting doc %d: %s", idx, doc.get('metadata', {}).get('source'))
        try:
            text = doc.get('page_content') or doc.get('content') or ''
            logger.debug("Doc text length: %d", len(text) if text else 0)
            chunks = _chunk_text(text, chunk_size=800, chunk_overlap=150)
            logger.debug("Chunks generated for doc %s: %d", doc.get('metadata', {}).get('source'), len(chunks))
            for c in chunks:
                split_docs.append({"page_content": c, "metadata": doc.get('metadata', {})})
        except Exception as exc:
            logger.error("Error al segmentar documento %s: %s", getattr(doc, 'metadata', {}).get('source'), exc)
    return split_docs


def create_vector_store(documents):
    # Try OllamaEmbeddings first; fall back to sentence-transformers if unavailable
    embeddings = None
    try:
        from langchain.embeddings import OllamaEmbeddings
        embeddings = OllamaEmbeddings(model=MODEL_NAME)
        logger.info("Using OllamaEmbeddings with model %s", MODEL_NAME)
    except Exception:
        logger.warning("OllamaEmbeddings not available in LangChain; trying sentence-transformers fallback")
        try:
            from sentence_transformers import SentenceTransformer

            st_model = SentenceTransformer("all-MiniLM-L6-v2")

            class STEmbeddings:
                def embed_documents(self, texts):
                    embs = st_model.encode(texts, show_progress_bar=False)
                    return [list(e) for e in embs]

                def embed_query(self, text):
                    emb = st_model.encode([text], show_progress_bar=False)
                    return list(emb[0])

            embeddings = STEmbeddings()
            logger.info("Using sentence-transformers fallback (all-MiniLM-L6-v2)")
        except Exception:
            logger.exception("No suitable embeddings available. Install Ollama integration or sentence-transformers.")
            raise
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        try:
            client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory=str(CHROMA_DIR)))
            collection = client.get_or_create_collection(name="sii_markdown")
        except ValueError:
            # chromadb Settings-based construction is deprecated in recent versions.
            # Fall back to the new client ctor which manages persistence differently.
            logger.warning("Chroma Settings deprecated; falling back to chromadb.Client() ctor")
            client = chromadb.Client()
            collection = client.get_or_create_collection(name="sii_markdown")

        # documents are plain dicts produced by split_documents
        texts = [d.get('page_content', '') for d in documents]
        metadatas = [d.get('metadata', {}) for d in documents]
        ids = [str(uuid.uuid4()) for _ in texts]

        embeddings_list = embeddings.embed_documents(texts)
        # Ensure embeddings are plain Python floats (avoid numpy types that print verbosely)
        cleaned_embeddings = [[float(x) for x in emb] for emb in embeddings_list]

        # Use explicit keyword names expected by chromadb
        collection.add(ids=ids, embeddings=cleaned_embeddings, metadatas=metadatas, documents=texts)
        try:
            client.persist()
        except Exception:
            logger.debug("chromadb client has no persist() or persistence handled by settings")
        return collection
    except Exception as exc:
        logger.exception("Error al crear el vector store: %s", exc)
        raise


def main():
    if not DOCS_DIR.exists():
        logger.error("Directorio de documentos no existe: %s", DOCS_DIR)
        return

    markdown_files = find_markdown_files(DOCS_DIR)
    if not markdown_files:
        logger.error("No se encontraron archivos markdown en %s", DOCS_DIR)
        return

    logger.info("Archivos encontrados: %d", len(markdown_files))
    docs = load_documents(markdown_files)
    if not docs:
        logger.error("No se pudo cargar ningún documento válido.")
        return

    chunks = split_documents(docs)
    if not chunks:
        logger.error("No se generaron fragmentos de documentos.")
        return

    logger.info("Fragmentos generados: %d", len(chunks))
    create_vector_store(chunks)
    logger.info("Ingesta completada. Vector DB guardada en %s", CHROMA_DIR)


if __name__ == "__main__":
    main()
