"""Prueba qué chunks recupera ChromaDB para preguntas problemáticas."""
import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer

CHROMA_DIR = Path(__file__).resolve().parent / "chroma_db"
model = SentenceTransformer("all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path=str(CHROMA_DIR))
col = client.get_collection("sii_markdown")

queries = [
    "tipos de sociedades disponibles en Chile EIRL SpA SRL",
    "obligaciones tributarias F29 F22 formularios",
    "documentos necesarios formalizar empresa",
    "Tu Empresa en un Día cómo funciona pasos",
]

for q in queries:
    vec = model.encode([q])[0].tolist()
    res = col.query(query_embeddings=[vec], n_results=3)
    print(f"\n=== {q} ===")
    for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
        src = meta.get("source", "")
        print(f"  [{src.split(chr(92))[-1]}] {doc[:200].replace(chr(10), ' ')}")
