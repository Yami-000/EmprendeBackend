# Plan 1.1 — Mejora Chunking

Objetivo: Reemplazar chunking por límite en tokens en lugar de caracteres, medir impacto en Recall y Fidelity.

Hipótesis: Token-based chunking reducirá alucinaciones y mejorará recall al ajustar fragmentos al contexto del modelo.

Pasos:
1. Implementar script de chunking en `ai-service/ingest.py` parametrizado por tokens.
2. Re-indexar la colección `sii_markdown` en ChromaDB.
3. Ejecutar el benchmark `tests/dataset/banco_preguntas.json` y comparar métricas con baseline.

Criterio de éxito: Promedio de las 3 métricas de contenido mejora en >= 0.5 puntos.
