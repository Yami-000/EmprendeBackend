# CONTEXTO TÉCNICO DEL SISTEMA

> **Alcance de este documento.** Describe el estado del código tal como está
> hoy, verificado contra el árbol de trabajo. Lo que está *en investigación*
> —qué se probó, qué se refutó, qué sigue— vive en
> [`ESTADO_INVESTIGACION.md`](ESTADO_INVESTIGACION.md), no aquí.
>
> **Última verificación:** 2026-09-23, contra el código en `main` + rama 1.6.

---

## 1. Visión general y stack

**Ecia** es un chatbot que responde consultas sobre formalización de PYMEs y
trámites del SII (normativa chilena) mediante un pipeline RAG. El canal de
entrada activo es un bot de Telegram.

```
Telegram ──> src/bot.js ──HTTP──> ai-service/api.py ──> ChromaDB (recuperación)
                 │                        │
                 │                        └──HTTP──> Ollama (generación)
                 └──> Sequelize ──> Postgres | SQLite (historial)
```

| Capa | Tecnología |
|---|---|
| Bot + API HTTP | Node.js **ESM** (`"type": "module"`), `express`, `telegraf` |
| Servicio RAG | Python, `fastapi` + `uvicorn` |
| Vector store | ChromaDB persistente en `ai-service/chroma_db/` |
| Embeddings | `sentence-transformers`, `all-MiniLM-L6-v2` (384 dims) |
| LLM | Ollama, `llama3.2` (3B) |
| Historial | `sequelize` → Postgres (Supabase), fallback SQLite en archivo |

**Dependencias Node activas:** `express`, `telegraf`, `axios`, `sequelize`,
`pg`, `pg-hstore`, `sqlite3`, `dotenv`, `joi`, `uuid`, `bcryptjs`,
`@supabase/supabase-js`.
**Declaradas pero sin referencias en `src/`:** `mammoth`, `@langchain/classic`,
`@langchain/core`, `@opentelemetry/api`.

**Dependencias Python** (`ai-service/requirements.txt`): `fastapi`, `uvicorn`,
`chromadb`, `sentence-transformers`, `httpx`, `pydantic`, `ollama`, `langchain`.
⚠️ `langchain` y `ollama` figuran en el manifest pero **ningún módulo del
pipeline los importa**: `ingest.py` usa `chromadb` y `sentence-transformers`
directamente, y `api.py` habla con Ollama por HTTP con `httpx`.

---

## 2. Inventario de archivos

### Pipeline RAG (Python)

| Ruta | Responsabilidad |
|---|---|
| `ai-service/api.py` | FastAPI. Expone `POST /chat` con respuesta en streaming (SSE). Orquesta embedding → recuperación → Ollama |
| `ai-service/ingest.py` | Script CLI offline. Lee `docs/sii/*.md`, los fragmenta, embebe y **recrea** la colección de ChromaDB |
| `ai-service/convert_docx.py` | Convierte `.docx` a `.md`. Pre-procesamiento, fuera del flujo de ejecución |
| `ai-service/debug_*.py` | Cuatro scripts de diagnóstico manual (`chunk`, `inspect`, `retrieval`, `run`) |
| `ai-service/chroma_db/` | Persistencia del vector store. **No versionado** |

### Backend Node

| Ruta | Responsabilidad |
|---|---|
| `src/index.js` | Punto de entrada. Conecta la DB, levanta HTTP y arranca el bot |
| `src/server.js` | Express. CORS configurable y `GET /health`. Única ruta expuesta |
| `src/bot.js` | Bot Telegraf. Carga historial, hace `POST` a `RAG_URL`, persiste la respuesta |
| `src/config/db.js` | Sequelize. Postgres, con fallback a SQLite en archivo |
| `src/models/*.js` | `Usuario`, `Chat`, `Mensaje` |
| `src/validations/*.js` | Esquemas `joi` |

### Evaluación

| Ruta | Responsabilidad |
|---|---|
| `scripts/evaluar_banco.py` | Arnés end-to-end. Separa fallos de recuperación de fallos de generación. Importa los prompts **desde `api.py`** para no medir una copia divergente |
| `scripts/medir_retrieval.py` | Recall@k sin invocar al LLM (segundos) |
| `tests/dataset/` | Banco de 100 preguntas: las 50 primeras respondibles, las 50 siguientes sin respaldo |

### Código muerto detectado

Los siguientes archivos **no son importados por ningún módulo alcanzable desde
`src/index.js`**, y las dependencias que necesitarían (`firebase`,
`firebase-admin`) ya se eliminaron de `package.json` el 2026-09-06 — si algo los
importara, fallaría en tiempo de ejecución:

```
src/config/firebaseAdmin.js       src/config/firestoreHelpers.js
src/config/firebaseAuth.js        src/config/firestoreMensajes.js
src/config/supabase.js            src/graphql/resolvers.js
src/validations/firebaseAuthValidation.js   src/graphql/schemas.js
```

Son residuo del proyecto anterior ("Krrete-BackEnd"). Candidatos a eliminación
tras verificar en staging.

---

## 3. Configuración del motor LLM

Definida en `ai-service/api.py`:

| Parámetro | Valor | Dónde |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.2` (3B) | constante de módulo |
| `OLLAMA_URL` | `http://localhost:11434/api/chat` | constante de módulo |
| `temperature` | `0.0` | `options` de la llamada |
| `top_p` | `0.1` | `options` |
| `num_predict` | `300` | `options` |
| `num_ctx` | `4096` | `options` |
| `stream` | `True` | cuerpo de la petición |
| timeout HTTP | `60` s | `httpx.AsyncClient(timeout=60)` |

**⚠️ Ventana del embedder: 256 tokens.** `all-MiniLM-L6-v2` tiene
`max_seq_length = 256`, y los fragmentos actuales tienen mediana 402 tokens y
máximo 496: **24 de 28 exceden la ventana y un 33% del corpus no influye en el
retrieval**. Lo que está más allá del token 256 solo lo lee el juez, no el
recuperador. Es la restricción que gobierna cualquier cambio de `CHUNK_SIZE` o de
vocabulario del corpus.

**Embeddings:** `all-MiniLM-L6-v2` en `ingest.py` **y** en `api.py`. La
constante en `ingest.py` lleva un comentario explícito de que ambos deben
coincidir: indexar y consultar con modelos distintos produce vectores
incomparables. Antes del 2026-09-17 `ingest.py` intentaba `nomic-embed-text`
(768 dims) con respaldo silencioso a MiniLM (384) — coincidían por accidente.

---

## 4. Estado y sesión en Telegram

- El historial se persiste con Sequelize en los modelos `Usuario`, `Chat` y
  `Mensaje`. `src/bot.js` carga los últimos `HISTORY_LIMIT = 6` mensajes y
  guarda la respuesta del asistente.
- La DB principal es Postgres (Supabase) vía `DB_HOST`, `DB_NAME`, `DB_USER`,
  `DB_PASSWORD`. En `development`, si la conexión falla, cae a **SQLite en
  archivo** (`./data/dev.sqlite`), no en memoria: el historial sobrevive a los
  reinicios. La carpeta `data/` se crea automáticamente.
- `ai-service/api.py` mantiene en memoria el `SentenceTransformer` y la conexión
  a ChromaDB. Al reiniciar se re-inicializan; el índice persiste en disco.

---

## 5. Pipeline RAG en detalle

### Corpus

`ingest.py` define `DOCS_DIR = BASE_DIR / "docs" / "sii"` e itera con
`rglob("*.md")`. Indexa **13 archivos** que producen **48 fragmentos**.

⚠️ **`ai-service/docs/` contiene 79 `.md` adicionales que NO se indexan** —
documentos financieros de la CMF (acciones, bonos, calculadoras de ahorro)
ajenos al dominio del SII. Están fuera de `docs/sii/`, así que nunca entraron a
ChromaDB. Esta distinción causó un error de ground truth que tardó semanas en
detectarse: 24 de 52 preguntas citaban archivos no indexados.

### Ciclo de ingesta

Proceso **offline y manual**. `api.py` no ingesta en el arranque; solo abre la
colección existente. Tras un `pull` hay que ejecutar `python ingest.py` una vez,
porque `chroma_db/` no está versionado.

La ingesta es **idempotente**: `create_vector_store` hace `delete_collection`
antes de `create_collection`. Antes, `collection.add()` acumulaba y cada
re-ingesta duplicaba los 48 fragmentos.

### Fragmentación — 🔴 problema activo

`_chunk_text(chunk_size=800, chunk_overlap=150)`, en caracteres:

1. Divide por encabezados markdown — `re.split(r'(?m)(?=^#{1,6}\s)', text)`. Si
   no hay encabezados, por doble salto de línea.
2. **Acumula** secciones consecutivas hasta llegar a 800 caracteres, de modo que
   un fragmento puede mezclar varias secciones distintas.
3. El solape se toma como **rebanada cruda de caracteres** del fragmento
   anterior: `overlap_text = chunk[-150:]`.

El paso 3 es el que causa daño. Medido sobre el índice actual:

```
30 de 48 fragmentos (62%) empiezan a mitad de frase
```

Empiezan con una cola de 150 caracteres arrancada del fragmento previo, que
suele pertenecer a otra sección. Ejemplos reales del índice:

```
"del tipo de empresa\nSe define la estructura legal previamente..."
"escritura |\n| Inicio de Actividades en SII | Gratuito | Dentro de 2 meses..."
```

El segundo muestra una **tabla markdown partida por la mitad**, sin encabezado
de columnas. Es el mecanismo detrás del caso PREG-076 documentado en
`ESTADO_INVESTIGACION.md`.

**Nota importante para quien trabaje esta línea:** el corte por encabezados ya
existe. Lo que hay que arreglar es el solape por caracteres y la acumulación de
secciones, no añadir una división estructural que ya está.

La distribución de fragmentos también es muy desigual:

| Archivo | Fragmentos |
|---|---:|
| `inicio_actividades_formalizacion_sii.md` | 17 |
| `obligaciones_tributarias_y_tipos_sociedad.md` | 9 |
| `documentacion_formalizacion.md` | 3 |
| `formularios_tributarios_chile.md` | 3 |
| `tipos_sociedad_chile.md` | 3 |

No hay tokenización por tokens de modelo; todos los parámetros son longitudes en
caracteres y la equivalencia tokens↔caracteres no está calibrada.

### Recuperación

- Vector store: `chromadb.PersistentClient`, colección `sii_markdown`.
- Top-k: `_query_chroma(query_vec, k=6)` en `chat_endpoint`.
- **Métrica de similitud: no especificada.** La colección se crea sin
  `hnsw:space`, así que ChromaDB usa **L2** por defecto. `encode()` **no
  normaliza** salvo que se le pase `normalize_embeddings=True`, y sin normalizar
  L2 y coseno no producen el mismo ranking. Es deuda técnica abierta — línea
  OP-5 en `ESTADO_INVESTIGACION.md`.

### Generación

`_build_system_prompt` construye el prompt con reglas de terminología chilena
(Cédula de Identidad y no DNI, RUT y no NIT, etc.), cuatro reglas absolutas y el
contexto recuperado al final, cada fragmento truncado a 1400 caracteres.

⚠️ **El orden de las secciones del prompt no es arbitrario.** Mover la regla de
abstención a un cierre después del contexto subió la alucinación de 34% a 78%.
Hay un comentario de advertencia en el código; leer
`tests/iteraciones/experimento_prompt_v2.md` antes de reordenarlo.

`api.py` también expone `_build_judge_prompt` y `JUEZ_PROMPT_BASES`, del
pipeline de dos pasos de la iteración 1.6. **El endpoint `/chat` sigue siendo de
un paso**: el pipeline de dos pasos vive por ahora solo en el arnés de
evaluación. Llevarlo a producción es trabajo pendiente.

---

## 6. Seguridad y resiliencia

### Secretos

Cargados con `dotenv`. **Ya no hay credenciales en el repositorio**: el archivo
de Service Account de Firebase se removió el 2026-09-06 y `credentials/` está en
`.gitignore`. Se recomendó rotar esa clave en el proveedor.

| Variable | Defecto | Obligatoria |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Sí, para el bot |
| `RAG_URL` | `http://localhost:11400/chat` | No |
| `PORT` | `4000` | No |
| `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | — | Sí para Postgres; si no, fallback SQLite |
| `DB_PORT` | `5432` | No |
| `NODE_ENV` | `development` | No |
| `CORS_ORIGINS` / `CORS_ORIGIN` | `*` | No |

### Timeouts

Ambos lados **tienen timeout**: `httpx.AsyncClient(timeout=60)` en `api.py` y
`timeout: 60000` en la llamada de `axios` desde `bot.js`, con mensaje de error
amigable si el backend no responde. No hay reintentos ni circuit breaker.

### Desajuste de puertos

`bot.js` apunta por defecto a `http://localhost:11400/chat`, así que el servicio
RAG debe levantarse en ese puerto:

```bash
uvicorn ai-service.api:app --host 0.0.0.0 --port 11400
```

`OLLAMA_URL` (`:11434`) es otra cosa: es Ollama, no el servicio RAG. No
confundirlos.

### Prompt injection

`_build_system_prompt` concatena los fragmentos recuperados directamente en el
prompt de sistema, sin sanitizar. Un `.md` con texto en forma de instrucción
podría influir en el modelo.

**Riesgo actual bajo**: el corpus es de elaboración propia y controlada, y no se
observaron casos en las evaluaciones. Pasa a relevante si se ingestan documentos
de terceros. Es la línea OP-2 en `ESTADO_INVESTIGACION.md`, con prioridad baja
por esa razón.

### Manejo de errores

- `api.py` atrapa fallos en `startup_event` y continúa con `_collection = None`,
  devolviendo HTTP 500 en las peticiones. Si Ollama falla o responde con error,
  el stream devuelve los fragmentos recuperados como respaldo.
- `bot.js` captura errores de DB y continúa sin historial: resiliente, pero
  puede ocultar fallos.

---

## 7. Deuda técnica abierta

| # | Asunto | Estado |
|---|---|---|
| 1 | Solape por caracteres que parte el 62% de los fragmentos | 🔴 Alta — OP-1 |
| 2 | Métrica de similitud del índice sin especificar (L2 por defecto, vectores sin normalizar) | 🟡 OP-5 |
| 3 | Código muerto del proyecto anterior en `src/config/` y `src/graphql/` | 🟡 Limpieza pendiente |
| 4 | `langchain`, `ollama` y cuatro paquetes npm declarados sin uso | 🟢 Limpieza de manifests |
| 5 | Pipeline de dos pasos solo en el arnés, no en `/chat` | 🟡 Portar a producción |
| 6 | Sanitización de fragments contra prompt injection | 🟢 Baja — OP-2 |
| 7 | Sin reintentos ni circuit breaker hacia Ollama | 🟢 Baja |

---

## 8. Documentación relacionada

| Documento | Contenido |
|---|---|
| [`ESTADO_INVESTIGACION.md`](ESTADO_INVESTIGACION.md) | Mapa de las líneas de investigación y callejones sin salida ya medidos |
| [`CLAUDE.md`](CLAUDE.md) | Reglas de trabajo para asistentes de IA |
| [`Bitacora.md`](Bitacora.md) | Registro cronológico de cambios con pasos de rollback |
| [`METODOLOGIA_TESTING.md`](METODOLOGIA_TESTING.md) | Protocolo de evaluación y estrategia de ramas |
| [`README.md`](README.md) | Instalación, arranque y uso |
