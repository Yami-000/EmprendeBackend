# CONTEXTO TÉCNICO DEL SISTEMA

## 1. Visión General y Stack Tecnológico Real

- Propósito central del sistema: Chatbot conversacional que responde consultas sobre normativa (principalmente SII / normativa chilena) usando un pipeline RAG (recuperación + LLM) y exponiendo un servicio HTTP (FastAPI) que consume un vectorstore (ChromaDB) y un motor LLM (Ollama). El canal principal de entrada activo es un bot de Telegram que orquesta consultas y guarda historial en una base de datos relacional.
- Lenguajes: JavaScript/Node.js (backend + bot) y Python (servicio RAG y herramientas de ingestión).
- Tecnologías detectadas (manifests y código):
  - Node.js: `express`, `telegraf`, `sequelize`, `sqlite3`, `pg`, `dotenv`, `axios`, `uuid`, `firebase`, `bcryptjs` (ver `package.json`).
  - Python: `fastapi`, `uvicorn`, `langchain`, `chromadb`, `ollama`, `sentence-transformers`, `httpx`, `pydantic` (ver `ai-service/requirements.txt`).
  - Embeddings / ML: `sentence-transformers` (modelo `all-MiniLM-L6-v2` usado como fallback), y referencia a `nomic-embed-text` en el ingest (`ai-service/ingest.py`).
  - Vector DB: ChromaDB (persistencia en `ai-service/chroma_db`).
  - LLM: Ollama (cliente HTTP desde `ai-service/api.py`).
  - DB relacional: Postgres (Supabase) por defecto vía `sequelize`; fallback a SQLite in-memory en desarrollo (`src/config/db.js`).

## 2. Inventario Exhaustivo de Archivos y Responsabilidades

| Ruta Relativa del Archivo | Responsabilidad Principal | Módulos / Servicios que Importa | Archivos / Componentes que lo Consumen |
|---|---|---|---|
| Prompt/Auditoria.md | Prompt de auditoría (este archivo) que describe la Fase 1 y entregables. | Ninguno | Operación humana / IA que ejecuta la auditoría |
| package.json | Manifest de Node.js; dependencias y scripts `start`/`dev`. | N/A | `src/index.js` al arrancar el servidor Node/JS |
| ai-service/requirements.txt | Manifest de dependencias Python para `ai-service`. | N/A | Entorno Python / despliegue del servicio RAG |
| ai-service/api.py | Servicio FastAPI que expone `/chat` y orquesta: embedding (SentenceTransformer), recuperación (ChromaDB) y llamada a Ollama. | `chromadb`, `fastapi`, `sentence_transformers`, `httpx`, `ollama` (cliente HTTP), `asyncio` | Consumido por clientes HTTP (por ejemplo `src/bot.js` vía `RAG_URL`) |
| ai-service/ingest.py | Script de ingestión: lee `docs/sii/*.md`, los chunkea, genera embeddings (OllamaEmbeddings o sentence-transformers fallback) y escribe en ChromaDB persistente. | `chromadb`, `sentence_transformers`, `langchain` (intento de `OllamaEmbeddings`) | Utilizado para crear/actualizar `ai-service/chroma_db` (vector store) |
| ai-service/convert_docx.py | Convierte `.docx` en `docs/` a `.md` en `docs/sii/`. | `docx` (python-docx) | Operación de pre-procesamiento de contenido documental |
| ai-service/chroma_db/ | Persistencia del vectorstore (archivos generados por ChromaDB). | N/A | Accedido por `ai-service/api.py` y `ai-service/ingest.py` |
| src/index.js | Punto de entrada Node: conecta DB y arranca servidor HTTP y bot de Telegram. | `./server.js`, `./config/db.js`, `./bot.js` | Orquesta inicio de la aplicación Node |
| src/server.js | Servidor HTTP Express, middleware CORS mínimo y ruta `/health`. | `express` | Consumido por `src/index.js` para exponer health endpoint |
| src/config/db.js | Configuración de conexión a DB (Sequelize). Intenta Postgres (Supabase) y cae a SQLite in-memory en `development`. | `sequelize`, `dotenv` | Consumido por `src/index.js` y `src/models/index.js` |
| src/bot.js | Bot de Telegram (Telegraf): recibe mensajes, guarda/hace lookup de historial en DB, y hace POST al servicio RAG (`RAG_URL`). | `telegraf`, `axios`, `dotenv`, `./models/index.js` | Ejecutado por `src/index.js`; clientes: usuarios de Telegram |
| src/models/*.js | Modelos Sequelize `Usuario`, `Chat`, `Mensaje`. | `sequelize` | Consumidos por `src/bot.js` y por cualquier lógica que manipule conversaciones |
| ai-service/docs/ (docs/sii/*.md) | Documentación normativa que sirve como contenido fuente para RAG. | N/A | Ingestada por `ai-service/ingest.py` y recuperada por `ai-service/api.py` vía ChromaDB |
| ai-service/debug_*.py | Scripts de depuración y pruebas (varios) | Varia por script | Operaciones de diagnóstico manual |
| chroma_db/chroma.sqlite3 | Archivo SQLite usado por ChromaDB en este workspace. | N/A | Leído por `ai-service/api.py` cuando `PersistentClient(path=...)` está configurado |
| credentials/emprende-...firebase-adminsdk-*.json | Credenciales Firebase (Service Account). | N/A | Posible uso por integraciones Firebase en código o despliegue |

> Nota: el inventario anterior prioriza los archivos que participan en el pipeline RAG, el bot Telegram y la persistencia. Hay muchos `docs/*.md` utilizados como corpus; se recomienda un inventario adicional si se requiere archivo-a-archivo.

## 3. Configuración del Motor LLM (Ollama)

- Modelos detectados en el repositorio:
  - Inferencia (servicio RAG): `OLLAMA_MODEL = "llama3.2"` (definido en `ai-service/api.py`).
  - Embeddings / ingest: `MODEL_NAME = "nomic-embed-text"` (definido en `ai-service/ingest.py`).
  - Fallback embeddings: `sentence-transformers` modelo `all-MiniLM-L6-v2` (usado en `ai-service/api.py` y `ai-service/ingest.py` como fallback).

- Parámetros de inferencia detectados (extraídos de llamadas a Ollama en `ai-service/api.py`):
  - `temperature`: 0.0 (fijado explícitamente en el cuerpo enviado a Ollama).
  - `top_p`: 0.1 (fijado explícitamente).
  - `num_predict` (equivalente a longitud de predicción en Ollama): 300 (fijado explícitamente como `num_predict`).
  - `stream`: True (streaming habilitado en `ai-service/api.py`).
  - `OLLAMA_URL`: `http://localhost:11434/api/chat` (definido en `ai-service/api.py`).
  - Cliente HTTP: `httpx.AsyncClient(timeout=None)` → no hay timeout aplicado en el cliente Python (timeout explícito = None).

- Parámetros NO DETECTADOS EN EL REPOSITORIO:
  - `num_ctx` (context window / contexto máximo en tokens): [NO DETECTADO EN EL REPOSITORIO] — por defecto Ollama usa 2048 tokens; en este código no hay ninguna variable que fije explícitamente `num_ctx`.
  - Timeouts globales o reintentos de Ollama: no se detecta manejo de reintentos ni timeout distinto de `None` (ver `httpx.AsyncClient(timeout=None)`).

## 4. Gestión de Estado y Sesión en Telegram

- Mecanismo de seguimiento del `chat_id` / historial:
  - El historial se persiste en una base de datos relacional mediante los modelos Sequelize `Usuario`, `Chat` y `Mensaje` (ver `src/models/*.js`).
  - `src/bot.js` intenta cargar los `HISTORY_LIMIT` mensajes recientes desde `Mensaje` y, tras la respuesta del asistente, guarda el mensaje del asistente en la tabla `Mensaje`.

- Dónde vive el historial (según configuración):
  - Por diseño la DB principal es Postgres (Supabase) usando variables de entorno (`DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) en `src/config/db.js`.
  - En `development` si la conexión a Postgres falla, el código cae a una instancia SQLite en memoria (`storage: ':memory:'`) como fallback. Esto significa que en entornos de desarrollo sin Postgres, el historial se pierde al reiniciar el proceso.

- Impacto técnico ante reinicio del backend:
  - Si la aplicación está conectada a Postgres (producción/Supabase correctamente configurado), el contexto conversacional persiste entre reinicios y no se pierde el historial.
  - Si no hay acceso a Postgres y se usa el fallback SQLite in-memory (el comportamiento por defecto en `development`), entonces TODO el historial almacenado en memoria se perderá al reiniciar el servicio → pérdida del contexto del usuario.
  - Además, `ai-service/api.py` mantiene pocos elementos en memoria: el SentenceTransformer `_st_model` y la conexión a ChromaDB en variables globales; si el servicio se reinicia, estos objetos se re-inicializan y la caché/estado local se pierde (aunque ChromaDB persistida en disco permite reconstruir la recuperación si el vectorstore existe).

---

### Observaciones críticas y recomendaciones rápidas (Fase 1)
- Detectado desajuste en endpoints/puertos entre componentes: `ai-service/api.py` usa `OLLAMA_URL` en puerto `11434` y `src/bot.js` por defecto apunta a `http://localhost:11400/chat` (variable `RAG_URL`). Esto sugiere dos rutas/puertos distintos para el servicio RAG; validar y unificar `RAG_URL`/`OLLAMA_URL`.
- `num_ctx` no está fijado explícitamente en el código: comprobar límites de contexto del modelo Ollama y definirlo si se requiere contexto extendido.
- No se detectan políticas de reintento ni timeouts razonables para llamadas a Ollama o para el servicio RAG (ambos usan `timeout=None`/`timeout: 0`), lo cual puede bloquear recursos en fallos de red; recomendamos definir timeouts y reintentos.
- Hay código residual de frontend mencionado en el prompt; no se detectó frontend moderno en `src/` (parece server+bot only) → revisar ramas/otros directorios para identificar y eliminar código muerto.

## 5. Mapeo Profundo del Pipeline RAG Actual

- Fuente de Documentos:
  - Ruta primaria detectada: `ai-service/docs/sii/` (ingest.py define `DOCS_DIR = BASE_DIR / "docs" / "sii"`). El repositorio contiene numerosos `.md` en `ai-service/docs/` y `docs/` en la raíz; `ingest.py` itera sobre `rglob('*.md')` dentro de `docs/sii`.
  - Lectura: `ingest.py` usa `Path.read_text(encoding='utf-8')` para cargar el contenido entero de cada `.md` y descarta archivos vacíos.
  - Filtros: No se detectan filtros avanzados por metadata, fechas ni patrones — sólo extensión `.md` y una comprobación básica de contenido vacío.

- Ciclo de Ingesta:
  - La ingesta es un proceso offline/por separado: `ai-service/ingest.py` es un script CLI independiente que debe ejecutarse manualmente (o por cron/CI) para reconstruir/actualizar el vectorstore.
  - `ai-service/api.py` en `startup_event` NO ejecuta la ingesta; sólo inicializa `SentenceTransformer` y abre `chromadb.PersistentClient(path=...)` y obtiene/crea la colección. Por tanto el indexado es persistente y dependiente de la ejecución previa de `ingest.py`.
  - Conclusión: Los documentos no se re-indexan por mensaje de Telegram ni en cada arranque; queda bajo responsabilidad de un job de ingesta explícito.

- Chunking y Tokenización:
  - `ingest.py` implementa `_chunk_text` con `chunk_size=800` y `chunk_overlap=150` (caracteres), y divide preferentemente en encabezados Markdown (`^#{1,6}\s`) antes de usar saltos de línea dobles.
  - No se realiza tokenización basada en tokens de modelo; los parámetros usan longitud en caracteres. Por tanto, equivalencia tokens↔caracteres no está calibrada.

- Embeddings y Búsqueda Vectorial:
  - Embeddings en ingesta: intenta `langchain.embeddings.OllamaEmbeddings(model=MODEL_NAME)` con `MODEL_NAME = "nomic-embed-text"`; si falla, cae al fallback `sentence-transformers` (`all-MiniLM-L6-v2`).
  - Embeddings en runtime (consulta): `ai-service/api.py` usa `SentenceTransformer("all-MiniLM-L6-v2")` con `_st_model.encode(...)` para generar el vector de consulta.
  - Vector store: `chromadb.PersistentClient(path=str(CHROMA_DIR))` y colección `sii_markdown`.
  - Top-k: en `chat_endpoint` el código llama a `_query_chroma(query_vec, k=6)` → `k=6` (top-6) detectado.
  - Métrica de similitud: [NO DETECTADO EN EL REPOSITORIO] — la colección se crea sin parámetros explícitos de similitud/metric; por tanto no hay confirmación en código si Chroma usa `cosine`, `dot` u otra métrica.

- Cuellos de Botella detectados:
  - Ingesta por lotes puede agotar memoria si se vectorizan muchos documentos sin batching; `embed_documents` suele devolver todos los embeddings en memoria antes de persistir.
  - `SentenceTransformer` se carga en el hilo de arranque (`startup_event`) y mantiene el modelo en memoria — útil para latencia, pero consume RAM.
  - `ai-service/api.py` usa `httpx.AsyncClient(timeout=None)` y `ollama_body['stream']=True` → llamadas largas/pendientes pueden quedarse abiertas y consumir conexiones si Ollama cuelga.
  - `bot.js` usa `axios` con `timeout: 0` (sin timeout) y edita mensajes de Telegram en intervalos; streaming de respuestas muy largas puede causar límites con la API de Telegram o inconsistencias en ediciones.
  - El fallback a SQLite en memoria para la DB (si Postgres falla) produce pérdida de contexto al reiniciar y afecta experiencia conversacional y trazabilidad.

## 6. Auditoría de Código Muerto (Frontend Descartado)

- Inventario Residual detectado:
  - No se detectan archivos de frontend activos (`index.html`, `public/`, `build/`, `dist/`, carpetas `client/`, ni proyectos `react`/`vite`/`next`) en el árbol `src/` o en la raíz del repo.
  - Evidencias de frontend histórico: `.gitignore` contiene entradas relacionadas con Next/Vite/Svelte (`.next`, `.vitepress/dist`, `.svelte-kit/`, etc.) → indica que hubo un frontend en algún punto o plantilla base.
  - Dependencias posiblemente no utilizadas: `firebase`, `firebase-admin` aparecen en `package.json` pero no hay `import`/`require` activos en `src/` o `ai-service/` (no se detectaron referencias en el código actual). Esto sugiere dependencias candidatas para remover tras validación.
  - Credenciales incluidas en repo: `credentials/emprende-73e05-firebase-adminsdk-fbsvc-dc2b367ca8.json` → archivo de credenciales sensible (Service Account) presente en el repositorio: RIESGO DE SEGURIDAD.

- Puntos de Acoplamiento Backend-Frontend:
  - CORS: `src/server.js` usa `CORS_ORIGINS`/`CORS_ORIGIN` (variables de entorno) — esto es típico para permitir un frontend remoto; sin embargo no existe un middleware que sirva artefactos estáticos actualmente.
  - Endpoints expuestos: sólo `/health` en `src/server.js`; no hay rutas de servir assets que indiquen acoplamiento directo.
  - Variables de entorno y dependencias en `package.json` (por ejemplo Firebase, Supabase) pueden haber sido usadas por el frontend previamente.

- Plan de Desacoplamiento Seguro (pasos resumidos):
  1. Añadir tests/registro: ejecutar un pass de integración que arranque el backend en entorno de staging y verifique rutas críticas (`/health`, bot, ingesta) funcionando.
  2. Eliminar referencias en el código: buscar y eliminar importaciones reales de `firebase`/frontend. Ya no detectadas; marcar como candidato para prueba.
  3. Mover `credentials/*.json` fuera del repo e introducir secret manager (env var `GOOGLE_APPLICATION_CREDENTIALS` o secrets en CI/CD). Rotar claves si ya estuvieron públicas.
  4. Probar `npm install --production` y arrancar en staging: confirmar que la app funciona sin `firebase` ni paquetes frontend. Ejecutar smoke tests.
  5. Si todo OK, quitar deps de `package.json`, actualizar `README` y `Bitacora.md`, y hacer PR que documente la eliminación y pasos de rollback.

## 7. Seguridad, Resiliencia y Manejo de Errores

- Gestión de Secretos:
  - Variables cargadas vía `dotenv` (`dotenv.config()` en `src/index.js` y `src/bot.js`). Variables detectadas en el código:
    - `TELEGRAM_BOT_TOKEN` (usado en `src/bot.js`) — obligatoria para el bot.
    - `RAG_URL` (usado en `src/bot.js`, default `http://localhost:11400/chat`).
    - `PORT` (usado en `src/index.js`, default `4000`).
    - `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` (usados en `src/config/db.js`).
    - `NODE_ENV` (controla fallback a SQLite in-memory).
    - `CORS_ORIGINS` / `CORS_ORIGIN` (usado en `src/server.js`).
  - Hallazgo crítico: `credentials/emprende-...firebase-adminsdk-*.json` está presente en el repo — exponerlo es un riesgo alto; se recomienda eliminarlo del repo, rotar las credenciales y colocar la clave en un secret manager.

- Manejo de Caídas y Timeouts:
  - `ai-service/api.py` usa `httpx.AsyncClient(timeout=None)` y `ollama` streaming → sin timeout. `bot.js` usa `axios` con `timeout: 0`. Ambos patrones significan que conexiones colgadas pueden mantener recursos indefinidamente.
  - Excepciones: `ai-service/api.py` atrapa errores en `startup_event` y continúa con `_collection = None`, devolviendo HTTP 500 en peticiones. `bot.js` captura errores DB y continua sin historial — esto es resiliente, pero puede ocultar fallos.
  - Recomendación: aplicar timeouts sensatos (ej. 30–120 s para llamadas LLM), reintentos exponenciales y circuit breaker para evitar saturación de conexiones.

- Vulnerabilidades de Prompting (Prompt Injection):
  - `ai-service/_build_system_prompt` concatena fragmentos recuperados (`page_content`) directamente en el `system` prompt enviado al LLM. Si los `.md` contienen líneas con formato instructivo ("Instrucciones del sistema:") o contenido malicioso, el LLM podría ejecutar o priorizar esas instrucciones.
  - Riesgo adicional: documentos del corpus no son validados ni sanitizados; un atacante con capacidad de modificar los `.md` en el vectorstore (o inyectar documentos) puede manipular la conducta del asistente.
  - Mitigaciones mínimas recomendadas:
    1. Escapar o eliminar secciones que parezcan instrucciones dirigidas al modelo (líneas que comiencen con `You are`, `System:`, `Assistant:` o similares).
    2. Enviar los fragmentos como datos referenciados (ej. `Contexto recuperado: [FUENTE: ...] >>>`), no como texto interpretativo que pueda incluir directivas.
    3. Limitar el `system` prompt a reglas y un wrapper declarativo; mover la recuperación de documentos a `user` o a un documento separado con un prefijo claro como "SÓLO CONTEXTO" y luego instruir al modelo a no seguir instrucciones encontradas en el contexto.
    4. Firmar/verificar integridad de documentos de confianza o usar control de acceso antes de ingestar fuentes externas.

- Matriz de Variables de Entorno (detected)

| Nombre | Tipo | Valor por Defecto (si aplica) | Obligatoria |
|---|---:|---|---:|
| TELEGRAM_BOT_TOKEN | string | [NO] | Sí (si se activa el bot de Telegram) |
| RAG_URL | string | http://localhost:11400/chat | No (se puede ejecutar sin) |
| PORT | número | 4000 | No |
| DB_HOST | string | [NO] | Sí (si se desea Postgres); fallback a SQLite in-memory en `development` |
| DB_PORT | número | 5432 | No |
| DB_NAME | string | [NO] | Sí (para Postgres) |
| DB_USER | string | [NO] | Sí (para Postgres) |
| DB_PASSWORD | string | [NO] | Sí (para Postgres) |
| NODE_ENV | string | development | No |
| CORS_ORIGINS / CORS_ORIGIN | string | '*' | No |

---

Fin de las secciones añadidas para la Fase 2.

## 8. Roadmap de Refactorización Priorizado

Este roadmap está priorizado en tres fases ejecutables y comprobables. Cada paso incluye acciones concretas y comandos sugeridos.

Fase 1 — Limpieza Quirúrgica del Frontend (rápido, bajo riesgo)
- Objetivo: eliminar restos del frontend y credenciales expuestas.
- Pasos concretos:
  1. Remover credenciales sensibles del repo (rotar luego en el proveedor):
     - Comando sugerido:
       ```bash
       git rm --cached credentials/emprende-73e05-firebase-adminsdk-fbsvc-dc2b367ca8.json
       echo "credentials/" >> .gitignore
       git commit -m "chore(secrets): remover credenciales del repo"
       ```
     - Luego: rotar la Service Account en Google Cloud / Firebase y almacenar la nueva clave en un secret manager (GitHub Secrets / Azure Key Vault / Vault).
  2. Validar que `firebase` y `firebase-admin` no sean requeridos en runtime. En un entorno de staging, ejecutar:
       ```bash
       npm uninstall firebase firebase-admin || true
       npm install --no-save # comprobar que la app arranca sin esas deps
       ```
  3. Eliminar directorios de frontend obsoletos si existen (`public/`, `build/`, `.next`, `dist/`). Comprobar con `git status` y `git rm -r` tras validación.

Fase 2 — Robustecimiento Operativo (mediano plazo)
- Objetivo: mejorar resiliencia y manejo de errores en producción.
- Pasos concretos:
  1. Añadir timeouts y reintentos:
     - En `ai-service/api.py`, cambiar `httpx.AsyncClient(timeout=None)` por `httpx.AsyncClient(timeout=60)` y envolver llamadas a Ollama con reintentos exponenciales (ej. `httpx.Retry` o backoff manual).
     - En `src/bot.js`, ajustar `axios` para usar `timeout: 60000` y aplicar un retry limitado al realizar la petición a `RAG_URL`.
  2. Implementar circuit-breaker: evitar abrir muchas conexiones simultáneas a Ollama si detectamos fallos persistentes.
  3. Forzar persistencia en disco del vectorstore y pruebas de integridad: comprobar `ai-service/chroma_db/` y asegurar que `ai-service/ingest.py` se ejecute en CI al actualizar docs.

Fase 3 — Modernización del RAG (mayor esfuerzo)
- Objetivo: rendimiento y seguridad en el pipeline de búsqueda y generación.
- Pasos concretos:
  1. Reescribir la tokenización/chunking para usar límites en tokens (no solo caracteres) y parametrizar `chunk_size` en tokens. Instrumentar un mapeo tokens↔caracteres usando el tokenizer del modelo o `tiktoken` equivalente.
  2. Establecer `num_ctx` y estrategia de ventana deslizante: evaluar modelos y definir `num_ctx` en la configuración de Ollama, documentarlo en `CONTEXTO.md`.
  3. Fortalecer la construcción de prompts: sanitizar fragments (remover instrucciones implícitas), prefijar con `SÓLO CONTEXTO:` y añadir validaciones de integridad (hashes o firmas) para fuentes de confianza.
  4. Evaluar Vector DB alternativos (Qdrant, Faiss, Milvus) y benchmarking; si se mantiene ChromaDB, crear tests de performance y ajustes de metric (cosine/dot).

KPIs y pruebas sugeridas:
- Tiempo p95 de respuesta para consultas simples < 2s (sin contar streaming de generación).
- Tasa de fallo por petición < 0.5% en 30 días.
- Integridad: 100% de documentos sensibles fuera del repo; claves rotadas.

---

Fin del Roadmap de Refactorización.

## Cambios aplicados (resumen)

- Seguridad y limpieza inmediata:
  - `credentials/` agregado a `.gitignore` y archivo de credenciales removido del árbol de trabajo (`credentials/emprende-...json`).
  - Dependencias `firebase` y `firebase-admin` eliminadas de `package.json` (se recomienda ejecutar `npm prune` y reinstalar en staging).

- Persistencia en desarrollo:
  - Fallback SQLite actualizado a archivo persistente `./data/dev.sqlite`. La carpeta `data/` se crea automáticamente al inicializar la DB en modo `development`.

- Resiliencia y parámetros del pipeline:
  - `ai-service/api.py`: `httpx.AsyncClient` usa `timeout=60` y se añadió `num_ctx: 4096` en las `options` enviadas a Ollama.
  - `src/bot.js`: la petición a `RAG_URL` usa `timeout: 60000` y ahora tiene manejo de error amigable al usuario cuando el backend no responde.
  - Documentación recomendada: arrancar el servicio RAG con `uvicorn ai-service.api:app --host 0.0.0.0 --port 11400` y ajustar `RAG_URL` si el servicio escucha en otro host/puerto.

