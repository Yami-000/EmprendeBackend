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
| Embeddings | `sentence-transformers`, `multilingual-e5-small` (384 dims, ventana 512 tokens). El nombre vive solo en `ai-service/embedding.py` |
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
| `ai-service/embedding.py` | **Contrato único del embedder:** `MODEL_NAME` y los prefijos `query:`/`passage:`. Lo importan `ingest.py`, `api.py` y los scripts de medición. Antes el nombre del modelo estaba escrito a mano en siete archivos |
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
| `scripts/medir_retrieval.py` | Recall@k y anclaje@k sin invocar al LLM (segundos). El informe vive en `reporte()` bajo `__main__`, para que otros scripts importen `verificables` y `anclaje_presente` sin disparar la impresión |
| `scripts/subconjunto_dato_integro.py` | IDs cuyo dato de anclaje llega íntegro al juez. Sobre ese subconjunto la sensibilidad del juez se mide sin fallos de retrieval de por medio |
| `scripts/subconjunto_sin_respaldo.py` | IDs sin respaldo en el corpus, leídos de `md_origen`. Mitad de control: mide alucinación y especificidad |
| `scripts/medir_ventana_embedder.py` | Cuánto del corpus ve el embedder, y `anclaje@6` partido según la cita caiga dentro o fuera de la ventana. **La brecha entre esas dos filas** reveló el techo del retrieval. Segundos, sin LLM |
| `scripts/ablacion_chunking.py` | Compara configuraciones de chunking en colecciones temporales **en memoria**: no toca el índice real ni invoca al LLM, ~10 s por variante. Reporta los fragmentos que exceden el truncado de `api.py` y los que exceden la ventana del embedder |
| `scripts/comparar_corridas.py` | Dos corridas pregunta por pregunta. Separa **especificidad del juez**, **atajadas por el redactor** y **alucinación**, que no son lo mismo, y avisa por la **asimetría** de los vuelcos y no por su cantidad |
| `scripts/sonda_descomposicion.py` | Aísla la forma de la pregunta del retrieval: recupera el contexto con la pregunta original y luego consulta al juez la original y cada subpregunta. Validó la premisa de B2 sin implementarlo |
| `scripts/generar_predicados.py` | Convierte filas de tabla del corpus en frases-predicado, con plantillas derivadas de los **encabezados de cada tabla** y ciegas al banco. `--solo-si-cabe` aplica solo donde el archivo conserva su número de fragmentos |
| `scripts/medir_palabras_clave.py`, `medir_grafo.py` | Mediciones dirigidas de las iteraciones 1.8 y 1.7. Históricas: sirven para reproducirlas |
| `scripts/populate_ground_truth.py`, `generate_ground_truth_csv.py`, `generate_ground_truth_report.py`, `apply_exclusion_filter.py` | Herramientas de construcción y auditoría del ground truth (2026-09-17). No se usan en el ciclo de medición |
| `scripts/run_baseline_test.py` | Runner del baseline 1.0. Superado por `evaluar_banco.py` |
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

**Ventana del embedder: 512 tokens, y ya no es una restricción.**
`multilingual-e5-small` lee 512 y los fragmentos tienen mediana **283** tokens y
máximo **380**: **0 de 28 exceden la ventana**, así que todo el corpus influye en el
retrieval.

**Hasta la 1.14 esto era el techo del proyecto.** Con `all-MiniLM-L6-v2` (256
tokens) 22 de 28 fragmentos lo excedían y el 32% del corpus era invisible para el
recuperador. Medido entonces: `anclaje@6` acertaba 91% cuando la cita caía dentro de
la ventana y 50% cuando caía fuera. **Cualquier número medido antes de la 1.14
pertenece a ese régimen.**

Consecuencia práctica: **`CHUNK_SIZE` se puede volver a discutir.** Estaba limitado
por esta ventana además del truncado de `api.py`; ahora hay margen de 512 tokens.

**Embeddings:** `multilingual-e5-small`, definido **en un solo lugar**
(`ai-service/embedding.py`) e importado por `ingest.py`, `api.py` y los scripts de
medición. Indexar y consultar con modelos distintos produce vectores incomparables, y
eso ya pasó: antes del 2026-09-17 `ingest.py` intentaba `nomic-embed-text` (768 dims)
con respaldo silencioso a MiniLM (384) — coincidían por accidente. Hasta la 1.14 el
nombre estaba escrito a mano en **siete** archivos y la protección era la disciplina;
ahora es estructural.

Ese módulo también define los prefijos `query:` y `passage:`, que la familia E5
exige: sin ellos rinde peor, y con el prefijo cambiado **peor que sin ninguno**.

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
`rglob("*.md")`. Indexa **13 archivos** que producen **28 fragmentos** con el
tope vigente de 1400 caracteres. (Eran 48 con el tope de 800 del baseline; varias
secciones de este archivo se escribieron en esa época.)

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
re-ingesta duplicaba los fragmentos.

### Fragmentación — 🔴 problema activo

`_chunk_text(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)`, en caracteres.
Los valores vigentes son **1400 y 200** desde la iteración 1.1, y la iteración 1.15
confirmó por barrido que son el **óptimo**: subirlos degrada el `anclaje@3` y bajarlos
también.

1. Divide por encabezados markdown — `re.split(r'(?m)(?=^#{1,6}\s)', text)`. Si
   no hay encabezados, por doble salto de línea.
2. **Acumula** secciones consecutivas hasta llegar a 1400 caracteres, de modo que
   un fragmento puede mezclar varias secciones distintas.
3. El solape se toma como **rebanada cruda de caracteres** del fragmento
   anterior: `overlap_text = chunk[-200:]`.

El paso 3 es el que causa daño. Medido sobre el índice actual (28 fragmentos,
embedder e5-small):

```
13 de 28 fragmentos (46%) empiezan a mitad de frase
```

Era 30 de 48 (62%) cuando el chunking usaba 800 caracteres. Bajó porque fragmentos
más grandes necesitan menos cortes, no porque el solape haya cambiado de naturaleza.

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
- Top-k: `_query_chroma(query_vec, k=3)` en `chat_endpoint`. **Bajó de 6 a 3 en la
  iteración 1.14** y es el embedder nuevo lo que lo permite: `anclaje@3` con e5 es
  30/37, mejor que el 28/37 que daba MiniLM con `k=6`. Con `k=6` el juez filtra
  PREG-045. De paso bajó la latencia del juez de 12,7 s a 6,9 s.
- **Métrica de similitud: no especificada, y es indistinto.** La colección se crea
  sin `hnsw:space`, así que ChromaDB usa **L2** por defecto. **Eso no afecta el
  ranking:** el modelo incluye capa `Normalize` y los vectores salen **unitarios**, y
  para vectores unitarios `‖a−b‖² = 2 − 2·cos`, o sea el mismo orden por construcción.
  Verificado el 2026-09-27: normas 1,000000 y **top-6 idéntico en 50 de 50 preguntas**.
  Declararlo explícito sigue valiendo como documentación, pero **no es una hipótesis de
  mejora** — la línea OP-5 quedó cerrada como no-op.

### Generación

`_build_system_prompt` construye el prompt con reglas de terminología chilena
(Cédula de Identidad y no DNI, RUT y no NIT, etc.), cuatro reglas absolutas y el
contexto recuperado al final, cada fragmento truncado a 1400 caracteres.

⚠️ **El orden de las secciones del prompt no es arbitrario.** Mover la regla de
abstención a un cierre después del contexto subió la alucinación de 34% a 78%.
Hay un comentario de advertencia en el código; leer
`tests/iteraciones/experimento_prompt_v2.md` antes de reordenarlo.

`api.py` también expone `_build_judge_prompt` y `JUEZ_PROMPT_BASES`, del pipeline de
dos pasos de la iteración 1.6. **Desde la 2.0 el endpoint `/chat` sirve ese pipeline**:
`decidir_si_responder()` juzga antes de redactar, y el camino `NO` devuelve
`FRASE_ABSTENCION` **sin llamar al modelo** — por eso rechazar es más rápido que
responder.

Alrededor de esa decisión hay tres reglas, todas **fuera** del modelo:

| Regla | Cuándo actúa | Qué hace |
|---|---|---|
| `es_saludo()` | antes del retrieval | contesta un saludo sin consultar al modelo |
| `partir_compuesta()` + veto (2.1) | el juez ya dijo `SI` | **anula** el `SI` si ninguna mitad de una pregunta `"X y Y"` se verifica |
| `descomponer_comparativa()` (1.16) | el juez ya dijo `NO` | **rescata** una comparativa si TODAS sus subpreguntas dan `SI` |

Las dos últimas son simétricas y **no se solapan**: una solo puede rechazar y la otra
solo puede aprobar, y cada una se dispara en la rama opuesta del veredicto.

⚠️ **El texto de ayuda de la abstención vive en el endpoint, no en el system prompt**,
y va como **sufijo** de `FRASE_ABSTENCION` sin reemplazarla: `abstuvo()` detecta un
fragmento de esa frase y sobre él se calculan la alucinación y la abstención indebida
de 19 iteraciones.

`traza.py` registra ese recorrido en `logs/traza.log` y en stdout, para mirarlo en
vivo. **No es un log de producción:** escribe la pregunta del usuario en claro.

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
| 5 | ~~Pipeline de dos pasos solo en el arnés, no en `/chat`~~ — **cerrada 2026-09-30 (iteración 2.0)**. `/chat` sirve el pipeline de dos pasos y se verificó **a través del endpoint**: 0/50 de alucinación, 99 de 100 preguntas idénticas al arnés, 0 errores de transporte | ✅ Producción se comporta como lo medido. `scripts/evaluar_endpoint.py` permite volver a comprobarlo |
| 6 | Sanitización de fragments contra prompt injection | 🟢 Baja — OP-2 |
| 8 | ~~El juez recibe las tablas aplanadas, sin estructura~~ — **cerrada 2026-09-25**: des-aplanar recupera 1 de 8 del núcleo duro y 0 end-to-end, y el contexto no crece (28415 caracteres en ambas versiones). No era el formato | ✅ Medida y descartada (1.10 Fase 1) |
| 9 | ~~El corpus codifica relaciones como columnas de tabla; el prompt del juez veta inferirlas~~ — **resuelta 2026-09-26**: declarar la relación en prosa antes de la tabla lleva el núcleo duro de 0 a 5 de 8 y la sensibilidad a 23/29 | ✅ 1.10 Fase 2 |
| 11 | ~~Preguntas **comparativas y disyuntivas**: el juez de 3B verifica un hecho a la vez~~ — **atacada 2026-09-27 (1.16)**: `descomponer_comparativa()` combina los veredictos **fuera** del modelo y suma 3 preguntas (34/50 → 37/50) sin costo de especificidad | ◐ Parcial. Sin cubrir: PREG-084 (sin dos lados separables), PREG-010 (disyuntiva). PREG-064 no entra: su cita caía fuera de la ventana del embedder |
| 12 | PREG-118 regresó con la Fase 2: su chunk de anclaje quedó en el puesto 7. Es el punto que falta de `anclaje@6` (28/37) | 🟡 Barata — mover el predicado de PREG-115 dentro de su archivo |
| 10 | ~~El redactor puede abstenerse pese al `SI` del juez~~ — **medida 2026-09-26**: 6 de 185 casos (3,2%) en 12 corridas, y **0 en la configuración de la 1.10**. Los predicados arreglaron ese eslabón de paso: no eran dos problemas, era uno | ✅ Marginal, no amerita iteración. Vigilar: es un fallo silencioso que solo aparece en `abstuvo indebidamente`, no en `sensibilidad` |
| 13 | ~~El presupuesto de 256 tokens del prefijo es el techo estructural del retrieval~~ — **resuelta 2026-09-27**: `multilingual-e5-small` lee **512 tokens** y ningún fragmento la excede (0 de 28, contra 22 de 28). `anclaje@6` 28 → **36/37**, `anclaje@8` **37/37**. El prefijo dejó de ser escaso, así que las palabras clave y los predicados ya no compiten | ✅ 1.14 |
| 15 | La especificidad del juez es 49/50 y el 0% de alucinación depende de que **el redactor** abstenga en PREG-045, no de que el juez acierte | 🟠 Garantía frágil. Un cambio que toque al redactor puede destapar la fuga |
| 16 | `CHUNK_SIZE` sigue en 1400 caracteres, acoplado al truncado de `api.py`. Con 512 tokens de ventana los fragmentos podrían crecer **sin volverse invisibles** | 🟡 Variable nueva, sin medir. Se reabrió con la 1.14 |
| 17 | El juez aprueba una pregunta compuesta `"X y Y"` reconociendo **una** parte, o ninguna: filtró una alucinación real desde Telegram | ◐ **Tapada 2026-09-30 (2.1)** por el veto, a costo cero (0 vuelcos en 100). El patrón es léxico: una compuesta unida por coma o `"además"` no se parte |
| 18 | El veredicto del juez depende de la **ortografía** de la pregunta: con el mismo contexto, la misma pregunta con y sin tildes recibe veredictos opuestos, cada uno determinístico | 🔴 Sin cuantificar. **Un caso que no reproduce no prueba que la fuga no exista.** Reproducible con `scripts/sonda_compuestas.py` |
| 19 | La traza escribe la **pregunta del usuario en claro** en `logs/traza.log` | 🟠 Aceptable para desarrollar. Con usuarios reales hay que decidir qué se guarda y por cuánto tiempo |
| 7 | Sin reintentos ni circuit breaker hacia Ollama | 🟢 Baja |

---

## 8. Documentación relacionada

| Documento | Contenido |
|---|---|
| [`INFORME_INVESTIGACION.md`](INFORME_INVESTIGACION.md) | Síntesis: metodología, las 18 hipótesis con su resultado, configuración óptima, limitaciones y próximos pasos |
| [`ESTADO_INVESTIGACION.md`](ESTADO_INVESTIGACION.md) | Mapa de las líneas de investigación y callejones sin salida ya medidos |
| [`CLAUDE.md`](CLAUDE.md) | Reglas de trabajo para asistentes de IA |
| [`Bitacora.md`](Bitacora.md) | Registro cronológico de cambios con pasos de rollback |
| [`METODOLOGIA_TESTING.md`](METODOLOGIA_TESTING.md) | Protocolo de evaluación y estrategia de ramas |
| [`README.md`](README.md) | Instalación, arranque y uso |
