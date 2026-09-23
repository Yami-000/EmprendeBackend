# BITÁCORA DE EVOLUCIÓN Y CAMBIOS DEL PROYECTO

> **REGLA PARA ASISTENTES IA Y DESARROLLADORES:** Este documento es dinámico y obligatorio. Cada vez que se realice un cambio de arquitectura, refactorización, eliminación de código muerto, actualización de librerías o corrección de bugs, se DEBE agregar una entrada a este archivo antes de cerrar la tarea.

## Registro Histórico de Cambios
| Fecha (YYYY-MM-DD) | Módulo / Archivo | Tipo de Cambio (Fix/Refactor/Feature/Docs) | Resumen del Cambio | Impacto / Dependencias Afectadas |
|---|---|---|---|---|
| 2026-09-06 | Repositorio Completo | Docs | Inicio de auditoría técnica y creación de documentación viva (`CONTEXTO.md`, `Bitacora.md`) | Generación de `CONTEXTO.md` y `Bitacora.md` para uso por modelos IA y desarrolladores |
| 2026-09-06 | RAG / Seguridad / Frontend | Docs/Audit | Auditoría Fase 2: mapeo RAG, revisión de código muerto frontend y evaluación de seguridad/resiliencia | Identifica riesgos: credenciales en repo, timeouts inexistentes, riesgo de prompt injection, dependencias frontend no usadas |
| 2026-09-06 | Seguridad / Infraestructura | Fix | Limpieza inmediata: remoción del archivo de credenciales del árbol de trabajo, añadido de `credentials/` y `data/` a .gitignore, eliminación de `firebase` y `firebase-admin` de `package.json` | Credenciales movidas fuera del repo; dependencias eliminadas del manifest; se recomienda rotación y purgado del historial |
| 2026-09-06 | Auditoría Fase 1 | Docs/Validation | Fase 1 validada y operativa tras smoke tests: RAG en http://0.0.0.0:11400, backend Node arrancando, y persistencia SQLite en `./data/dev.sqlite` | Cambios aplicados: timeouts, num_ctx, persistencia local; pendiente saneamiento y modernización RAG |
| 2026-09-06 | Testing / Tests/ | Docs | Añadida `METODOLOGIA_TESTING.md` y estructura `tests/` (dataset y plantillas de iteración) para institucionalizar protocoles de evaluación y experimentación | Permite ejecutar benchmarks y documentar iteraciones experimentales; próximo: correr baseline y llenar `resultado_1.0.md` |
| 2026-09-17 | `tests/dataset/` | Fix/Data | Banco de preguntas ampliado a 100 (50 respondibles / 50 sin respaldo) y ground truth corregido: 24 de 52 preguntas citaban archivos fuera de `docs/sii/`, 11 de ellos documentos financieros de la CMF ajenos al SII | Auditado con revisión propia + validación cruzada con NotebookLM (99% concordancia). 21 reclasificadas, 18 eliminadas, 18 creadas. Rollback: `git revert` del commit; el banco previo queda en el historial |
| 2026-09-17 | `ai-service/ingest.py` | Fix | Modelo de embeddings fijado a `all-MiniLM-L6-v2`; antes intentaba `nomic-embed-text` (768 dims) con respaldo silencioso a MiniLM (384) mientras `api.py` usaba siempre MiniLM | Elimina riesgo de divergencia índice/consulta. **Requiere re-ingesta**: `cd ai-service && python ingest.py`. Rollback: revertir el commit y re-ingestar |
| 2026-09-17 | `ai-service/ingest.py` | Fix | La ingesta recrea la colección antes de insertar; antes `collection.add()` acumulaba y reindexar duplicaba los 48 fragmentos | Hace la ingesta idempotente. Resuelve la sospecha histórica de duplicados en ChromaDB |
| 2026-09-17 | `.gitignore`, `ai-service/chroma_db/` | Refactor | `chroma_db` y `__pycache__` salen del control de versiones | **Tras hacer pull hay que ejecutar `python ingest.py` una vez** para reconstruir el índice local; ya no viene en el repo |
| 2026-09-17 | `ai-service/docs/sii/inicio_actividades_sii.md` | Fix | Corregida una palabra en cirílico («независимо») que contaminaba el vector de ese fragmento | Requiere re-ingesta para propagarse al índice |
| 2026-09-17 | `scripts/` | Feature | Añadidos `evaluar_banco.py` (pipeline completo, separa fallos de recuperación de fallos de generación) y `medir_retrieval.py` (recall sin invocar al modelo) | El arnés importa el system prompt desde `api.py` en vez de copiarlo, para no medir una versión divergente |
| 2026-09-17 | `ai-service/api.py` | Docs | Experimento fallido: mover la regla de abstención tras el contexto subió la alucinación de 34% a 78%. Revertido | Documentado en `tests/iteraciones/experimento_prompt_v2.md`. `api.py` queda en el estado del baseline v1 |
| 2026-09-17 | `tests/iteraciones/` | Docs | Baseline 1.0 medido y planes reordenados según evidencia: modelo de generación a prioridad alta, chunking a media | De 31 fallos, 22 son de generación y 9 de recuperación |
| 2026-09-22 | `README.md` | Docs | Reescrito por completo: describía un proyecto anterior ("Krrete-BackEnd" con Firebase Auth, eliminado el 2026-09-06) y citaba un archivo `PROJECT_OVERVIEW.mb` inexistente. Ahora documenta la arquitectura real (Ollama + ai-service FastAPI + bot Node), instalación, variables de entorno y cómo evaluar el RAG | Sin impacto funcional; corrige documentación que llevaba desde mayo sin reflejar el pivot del proyecto |

## Deuda Técnica Inicial Detectada (Línea Base)
 - [x] Eliminar `credentials/*.json` del repositorio, rotar claves y usar un secret manager (alto riesgo de exposición).
 - [x] Revisar y remover dependencias no usadas (`firebase`, `firebase-admin`) si no son requeridas por backend.
 - [ ] Implementar sanitización y límites en el contenido recuperado para mitigar Prompt Injection (escapar instrucciones en `.md`).
 - [ ] Definir y documentar la métrica de similitud utilizada por ChromaDB o crear la colección con parámetros explícitos (actualmente: [NO DETECTADO EN EL REPOSITORIO]).
 - [x] Persistencia local en desarrollo: cambiar fallback SQLite in-memory por archivo `./data/dev.sqlite`.
 - [x] Añadir timeouts en llamadas RAG/Ollama y establecer `num_ctx` inicial en 4096.
 - [ ] **Nuevo 2026-09-17 — prioridad alta:** sustituir `llama3.2` (3B) por un modelo de 7–8B. Alucina en el 34% de las preguntas sin respaldo y no discrimina de forma confiable si el contexto responde la pregunta. Ver `tests/iteraciones/iteracion_1.3_modelo/plan_1.3.md`.
 - [ ] Implementar el Roadmap de Refactorización (Fase 1-3): limpieza frontend, robustecimiento operativo y modernización del RAG; crear tickets/PRs y registrar avances en la bitácora.

## Backlog Prioritario (post-Fase1)
- [ ] Sanitización de fragments recuperados antes de su inclusión en el `system` prompt (mitigación de Prompt Injection). **Prioridad baja 2026-09-17**: sin casos observados en el baseline; el corpus es de elaboración propia. Medida preventiva para cuando se ingesten documentos de terceros.
- [ ] Modernización del chunking a token-based (usar tokenizer del modelo) y evaluación/benchmark de vectorstore local (ChromaDB vs Qdrant/Faiss). **Reprioritizado 2026-09-17 a media**: el baseline mide recall@6 = 88%; el techo de esta vía es de 9 preguntas frente a 22 por la vía de generación. Ver `tests/iteraciones/iteracion_1.1_chunking/plan_1.1.md`.

## Instrucciones para elaborar nuevas entradas
- Cada entrada nueva debe contener: Fecha (YYYY-MM-DD), Módulo/Archivo afectado, Tipo de Cambio, Resumen corto, Impacto y Dependencias.
- Antes de cerrar cualquier PR que modifique la arquitectura o migraciones de datos, agregue una línea en esta bitácora describiendo la modificación y los pasos de rollback si aplica.

---

Archivo generado automáticamente el 2026-09-06 como parte de la Fase 1 de auditoría.
