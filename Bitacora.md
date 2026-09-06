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

## Deuda Técnica Inicial Detectada (Línea Base)
 - [x] Eliminar `credentials/*.json` del repositorio, rotar claves y usar un secret manager (alto riesgo de exposición).
 - [x] Revisar y remover dependencias no usadas (`firebase`, `firebase-admin`) si no son requeridas por backend.
 - [ ] Implementar sanitización y límites en el contenido recuperado para mitigar Prompt Injection (escapar instrucciones en `.md`).
 - [ ] Definir y documentar la métrica de similitud utilizada por ChromaDB o crear la colección con parámetros explícitos (actualmente: [NO DETECTADO EN EL REPOSITORIO]).
 - [x] Persistencia local en desarrollo: cambiar fallback SQLite in-memory por archivo `./data/dev.sqlite`.
 - [x] Añadir timeouts en llamadas RAG/Ollama y establecer `num_ctx` inicial en 4096.
 - [ ] Implementar el Roadmap de Refactorización (Fase 1-3): limpieza frontend, robustecimiento operativo y modernización del RAG; crear tickets/PRs y registrar avances en la bitácora.

## Backlog Prioritario (post-Fase1)
- [ ] Sanitización de fragments recuperados antes de su inclusión en el `system` prompt (mitigación de Prompt Injection).
- [ ] Modernización del chunking a token-based (usar tokenizer del modelo) y evaluación/benchmark de vectorstore local (ChromaDB vs Qdrant/Faiss).

## Instrucciones para elaborar nuevas entradas
- Cada entrada nueva debe contener: Fecha (YYYY-MM-DD), Módulo/Archivo afectado, Tipo de Cambio, Resumen corto, Impacto y Dependencias.
- Antes de cerrar cualquier PR que modifique la arquitectura o migraciones de datos, agregue una línea en esta bitácora describiendo la modificación y los pasos de rollback si aplica.

---

Archivo generado automáticamente el 2026-09-06 como parte de la Fase 1 de auditoría.
