# PLAN — Saneamiento del Embedding y Baseline de Evaluación

**Fecha:** 2026-09-17
**Estado inicial medido:** 48 chunks, 13 archivos, 384 dims, 0 duplicados

---

## Diagnóstico

### Lo que NO es el problema

| Sospecha | Verificación | Resultado |
|---|---|---|
| Documentos de la CMF contaminando el índice | `ingest.py:18` indexa solo `docs/sii/` | ❌ Nunca estuvieron indexados |
| Chunks duplicados por re-ingestas | Hash MD5 de los 48 documentos | ❌ 0 duplicados |
| Mismatch de dimensiones índice/consulta | Ambos en 384 dims (MiniLM) | ❌ Coinciden (por accidente, ver abajo) |
| Retrieval roto | recall@6 = 88% sobre 50 preguntas | ❌ Funciona razonablemente |

### Lo que SÍ es el problema

**1. Base desactualizada** — `chroma_db` se generó el 2026-09-06, antes de corregir el texto en cirílico de `inicio_actividades_sii.md`. El chunk defectuoso sigue indexado.

**2. Selección de modelo de embeddings frágil** — `ingest.py` intenta `OllamaEmbeddings("nomic-embed-text")` (768 dims) y solo cae a `all-MiniLM-L6-v2` (384 dims) porque el import de langchain falla. `api.py` usa MiniLM siempre, sin condicional. La coincidencia actual es accidental: si el import llegara a funcionar, la ingesta escribiría 768 dims contra un lector de 384.

**3. Corpus redundante** — Dos documentos "paraguas" duplican contenido de otros cuatro y acaparan el retrieval:

| Documento | Chunks | Ocupación del top-6 |
|---|---|---|
| `inicio_actividades_formalizacion_sii.md` | 17 | 30,3% |
| `obligaciones_tributarias_y_tipos_sociedad.md` | 9 | 20,7% |
| *(los otros 11 archivos)* | 22 | 49,0% |
| `costos_y_plazos_formalizacion.md` | 2 | 3,0% |
| `tipos_sociedad_chile.md` | 3 | 2,0% |
| `patente_municipal.md` | 1 | 1,7% |

**4. Chunking por tamaño, no por estructura** — `_chunk_text` acumula secciones hasta 800 caracteres. Los archivos cortos quedan como un único chunk que mezcla todos sus temas, lo que diluye su vector y los vuelve poco competitivos.

### Baseline de retrieval medido

```
recall@1  = 22/50  (44%)
recall@3  = 42/50  (84%)
recall@6  = 44/50  (88%)   <- k actual
recall@10 = 47/50  (94%)
```

Fallos con k=6: PREG-006, 078, 089, 110, 112, 116.
En PREG-078 y PREG-089 el contenido recuperado **sí permite responder** (viene de otro archivo del corpus), por lo que el recall efectivo es ~92%.

---

## Fases

### Fase 0 — Consistencia y actualización ✅ COMPLETADA (2026-09-17)

Cambios aplicados en `ingest.py`:

1. `MODEL_NAME = "all-MiniLM-L6-v2"` fijo, con comentario que explica por qué debe coincidir con `api.py`.
2. Eliminado el intento de `OllamaEmbeddings` y su fallback silencioso: ahora usa sentence-transformers directo.
3. `create_vector_store` borra y recrea la colección antes de insertar. Sin esto, `collection.add()` acumulaba y cada re-ingesta duplicaba todos los chunks.
4. `chroma_db` borrado y regenerado.

Verificación posterior:

```
chunks           : 48
dimension        : 384
archivos         : 13
duplicados       : 0
chunks cirilicos : ninguno
"independientemente" en indice: True
```

**Riesgo eliminado:** ingesta y consulta ya no pueden divergir de modelo sin aviso.
**Bug propagado corregido:** la corrección del cirílico ya está reflejada en el índice.

### Fase 1 — Baseline end-to-end ✅ COMPLETADA (2026-09-17)

Resultado completo en [`iteraciones/iteracion_1.0_baseline/resultado_1.0_e2e.md`](iteraciones/iteracion_1.0_baseline/resultado_1.0_e2e.md).

```
RESPONDIBLES (50)     retrieval_hit@6 ....... 44/50 (88%)
                      abstuvo indebidamente . 12/50 (24%)
                      cobertura de datos .... 57%

NO RESPONDIBLES (50)  abstuvo (correcto) .... 33/50 (66%)
                      ALUCINO ............... 17/50 (34%)

ATRIBUCION            retrieval ..............  9
                      generacion ............. 22
```

**Conclusión:** la generación pesa 2,4× más que el retrieval. Las Fases 2 y 3
tienen un techo de 9 preguntas recuperables y no tocan el problema principal.

**Reprioriza el plan:** antes de Fase 2 conviene iterar el prompt (mover la regla
de abstención después del contexto, recortar `num_predict`) y, si eso no basta,
saltar a Fase 4.

### Fase 1 — Diseño original *(referencia)*

Correr las 100 preguntas contra el pipeline completo y separar los dos modos de fallo:

- **Fallo de retrieval:** el chunk correcto no llegó al contexto.
- **Fallo de generación:** el chunk llegó, pero el modelo no lo usó o alucinó.

Métricas objetivo:
- Acierto en las 50 respondibles.
- **Tasa de abstención** en las 50 no respondibles (que responda la frase de rechazo del system prompt).
- Tasa de alucinación = no respondibles contestadas con contenido inventado.

**Por qué antes de optimizar:** el historial registra 28–31/40 con el retrieval ya funcionando al 88%. Si el fallo dominante es de generación, mejorar el embedding no moverá el puntaje.

### Fase 2 — Chunking estructural *(pendiente)*

Cortar por encabezado markdown en lugar de acumular hasta 800 caracteres. Los archivos cortos pasarían de 1 chunk genérico a 1 chunk por sección. Subir `k` de 6 a 8–10.

Contrapartida: más chunks implica más contexto, y un modelo de 2B parámetros se confunde con contextos largos. Solo tiene sentido si la Fase 1 muestra que el fallo es de retrieval.

### Fase 3 — Deduplicar el corpus *(pendiente)*

Decidir un archivo canónico por tema y recortar la copia. Cuidado: `inicio_actividades_formalizacion_sii.md` contiene material único (cooperativas, permisos complementarios, ventajas de formalizar) — no se puede eliminar entero.

### Fase 4 — Modelo de generación *(pendiente)*

`llama3.2` de 2B parámetros no sigue instrucciones estrictas de RAG con consistencia. Probar un modelo de 7–8B es, según el historial del proyecto, el cambio con mayor impacto esperado.
