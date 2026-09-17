# Plan 1.4 — Deduplicación del corpus

**Prioridad:** 🟡 Media · **Origen:** OP-4 · **Ejecutar después de:** `iteracion_1.3_modelo`

## Objetivo

Eliminar la redundancia entre documentos para que los archivos específicos dejen
de competir contra copias de su propio contenido.

## Hipótesis

Dos documentos "paraguas" duplican material de otros cuatro y acaparan la mitad
del retrieval:

| Documento | Chunks | Ocupación del top-6 |
|---|---:|---:|
| `inicio_actividades_formalizacion_sii.md` | 17 | 30,3% |
| `obligaciones_tributarias_y_tipos_sociedad.md` | 9 | 20,7% |
| `costos_y_plazos_formalizacion.md` | 2 | 3,0% |
| `tipos_sociedad_chile.md` | 3 | 2,0% |
| `patente_municipal.md` | 1 | 1,7% |

Contenido duplicado detectado en la validación cruzada con NotebookLM (25 de 50
preguntas respondibles tienen el dato en dos archivos distintos):

| Tema | Archivo específico | Archivo paraguas |
|---|---|---|
| Tipos de sociedad | `tipos_sociedad_chile.md` | `obligaciones_tributarias_y_tipos_sociedad.md` |
| Costos y plazos | `costos_y_plazos_formalizacion.md` | ídem |
| Formularios y tasas | `formularios_tributarios_chile.md` | ídem |
| Inicio de actividades | `inicio_actividades_sii.md` | `inicio_actividades_formalizacion_sii.md` |

Esto explica mejor el problema histórico de "`tipos_sociedad_chile.md` no aparece
en top-3 para la query 'tipos de sociedades'" que la hipótesis original de que
los embeddings no conectaban con la query: el retriever probablemente sí trae el
contenido correcto, pero desde el archivo paraguas.

## Pasos

1. Definir un archivo canónico por tema y recortar la sección duplicada del otro,
   dejando en su lugar una referencia.
2. Re-indexar y medir con `scripts/medir_retrieval.py`.
3. Actualizar `md_origen` y `md_alternativos` en
   `tests/dataset/banco_preguntas_respuestas.json` según el nuevo reparto.

## Precaución

`inicio_actividades_formalizacion_sii.md` **no puede eliminarse**: además del
material duplicado contiene secciones únicas (cooperativas, permisos
complementarios, ventajas de formalizar, pasos de tuempresaenundia.cl). El
recorte debe ser quirúrgico, sección por sección.

## Métricas objetivo

| Métrica | Actual | Objetivo |
|---|---:|---:|
| Ocupación del documento más frecuente | 30,3% | ≤ 20% |
| recall@6 | 88% | ≥ 90% |

## Criterio de éxito

Ocupación máxima ≤ 20% sin que baje el recall@6 y sin pérdida de contenido
verificable: las 50 preguntas respondibles deben seguir teniendo fuente.
