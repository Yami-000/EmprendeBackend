# Plan 1.1 — Mejora de chunking

**Prioridad:** 🟡 Media · **Origen:** OP-1 · **Ejecutar después de:** `iteracion_1.3_modelo`

> Actualizado 2026-09-17. El plan original proponía chunking por tokens como vía
> principal contra la alucinación. Las mediciones del baseline muestran que el
> retrieval explica solo 9 de 31 fallos, así que esta iteración pasa a segundo
> plano detrás de OP-3 (modelo).

## Objetivo

Reemplazar el chunking por límite de caracteres (800) por un corte que respete la
estructura del documento, y medir el impacto en recall@k.

## Hipótesis

El chunking actual acumula secciones hasta llenar 800 caracteres, lo que produce
dos efectos medidos:

1. **Distribución desigual.** `inicio_actividades_formalizacion_sii.md` genera 17
   chunks de 48 y acapara el 30,3% del top-6; `patente_municipal.md` tiene 1 solo
   chunk y aparece en el 1,7%.
2. **Vectores diluidos.** Los archivos cortos quedan como un único chunk que
   mezcla todos sus temas, lo que los vuelve poco competitivos frente a chunks
   temáticamente concentrados.

Cortar por encabezado markdown debería dar un chunk por sección y equilibrar la
competencia entre documentos.

## Techo medido

```
recall@1  = 44%      Fallos con k=6: PREG-006, 078, 089, 110, 112, 116
recall@3  = 84%      (+3 a nivel de chunk: PREG-010, 079, 109)
recall@6  = 88%   <- actual
recall@10 = 94%
```

**Máximo recuperable por esta vía: 9 preguntas.** Subir `k` de 6 a 10 ya aporta
parte de la mejora sin tocar el chunking, y es un cambio de una línea.

## Pasos

1. Modificar `_chunk_text` en `ai-service/ingest.py` para cortar por encabezado
   markdown (`^#{1,6}\s`) en lugar de acumular hasta 800 caracteres.
2. Re-indexar: `python ingest.py` (ya es idempotente, recrea la colección).
3. Medir solo retrieval, que corre en segundos sin invocar al LLM:
   `python scripts/medir_retrieval.py`
4. Si recall@6 mejora, medir end-to-end: `python scripts/evaluar_banco.py chunking`

## Métricas objetivo

| Métrica | Actual | Objetivo |
|---|---:|---:|
| recall@6 | 88% | ≥ 95% |
| Ocupación del documento más frecuente en top-6 | 30,3% | ≤ 20% |
| Fallos de retrieval | 9 | ≤ 3 |

## Criterio de éxito

recall@6 ≥ 95% **sin** que suban los fallos de generación end-to-end.

## Riesgo

Más chunks implica fragmentos más cortos y, con el mismo `k`, menos información
total en el contexto. Con un modelo pequeño esto puede cortar por la mitad la
información que necesita. Medir `k` = 6, 8 y 10 antes de fijar el valor.
