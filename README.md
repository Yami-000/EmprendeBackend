# EmprendeBackend — Ecia

Backend de **Ecia**, un bot de Telegram que asesora sobre formalización de
PYMEs y trámites tributarios ante el Servicio de Impuestos Internos (SII) de
Chile, usando un pipeline RAG (recuperación + LLM) sobre un corpus normativo
propio.

> Este README reemplaza una versión desactualizada (última actualización real:
> mayo 2026) que describía un proyecto anterior ("Krrete", con autenticación
> Firebase). Esa integración ya no existe en el código.

## Arquitectura

Tres procesos independientes que deben correr en simultáneo:

| Proceso | Rol | Puerto |
|---|---|---|
| **Ollama** | Motor LLM local (`llama3.2` por defecto) | `11434` |
| **ai-service** (Python / FastAPI) | RAG: embeddings + ChromaDB + orquesta la llamada a Ollama | `11400` |
| **Backend Node** (Express + Telegraf) | Bot de Telegram, persistencia de historial | `4000` |

```
Usuario (Telegram)
      │
      ▼
 src/bot.js  ──POST──▶  ai-service/api.py  ──▶  ChromaDB (retrieval)
      │                        │
      ▼                        ▼
 Postgres/SQLite          Ollama (llama3.2)
 (historial)
```

## Requisitos previos

- Node.js 18+ y npm
- Python 3.10+ con un entorno virtual en `ai-service/.venv`
- [Ollama](https://ollama.com) instalado, con al menos un modelo descargado
  (`ollama pull llama3.2`)
- Un token de bot de Telegram ([@BotFather](https://t.me/BotFather))

## Instalación

```bash
# Dependencias Node
npm install

# Dependencias Python (RAG)
cd ai-service
python -m venv .venv
.venv/Scripts/activate        # En Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

## Variables de entorno

No hay `.env.example` en el repo — crea un `.env` en la raíz con:

| Variable | Obligatoria | Por defecto | Descripción |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Sí | — | Token del bot, entregado por BotFather |
| `RAG_URL` | No | `http://localhost:11400/chat` | Endpoint del servicio RAG |
| `PORT` | No | `4000` | Puerto del servidor Express |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Solo en producción | — | Conexión a Postgres (Supabase). En `development`, si falla la conexión, cae a SQLite persistente en `./data/dev.sqlite` |
| `NODE_ENV` | No | `development` | Controla el fallback de base de datos |
| `CORS_ORIGINS` / `CORS_ORIGIN` | No | `*` | Orígenes permitidos por CORS |

## Cómo levantar el proyecto

Los tres procesos se levantan por separado, en este orden:

```powershell
# 1. Ollama
ollama serve

# 2. Servicio RAG (en otra terminal)
cd ai-service
.venv/Scripts/Activate.ps1
uvicorn api:app --host 0.0.0.0 --port 11400

# 3. Backend + bot de Telegram (en otra terminal)
npm run dev      # o: npm start
```

### Indexar / re-indexar el corpus

El servicio RAG **no** indexa automáticamente al arrancar — es un paso manual
separado. Ejecutar cada vez que cambie algo en `ai-service/docs/sii/`:

```bash
cd ai-service
python ingest.py
```

Reconstruye `ai-service/chroma_db/` desde cero (la ingesta es idempotente:
borra y recrea la colección, no acumula duplicados). Este directorio **no**
está versionado — hay que correr `ingest.py` una vez después de cada `git pull`.

## Estructura del repo

```
ai-service/
  api.py              Servicio FastAPI: embedding de la query, retrieval
                       en ChromaDB, orquestación con Ollama
  ingest.py            Script de indexación del corpus
  docs/sii/             13 documentos .md — el corpus normativo (único
                       contenido que el bot puede citar)
  chroma_db/           Base vectorial (generada, no versionada)

src/
  index.js             Punto de entrada: DB + servidor HTTP + bot
  server.js             Express, healthcheck en /health
  bot.js                 Bot de Telegram (Telegraf), llama a RAG_URL
  config/db.js           Conexión Sequelize (Postgres con fallback SQLite)
  models/                Usuario, Chat, Mensaje

scripts/
  evaluar_banco.py      Corre el banco de preguntas contra el pipeline
                       completo; separa fallos de retrieval de fallos
                       de generación
  medir_retrieval.py     Mide recall@k sin invocar al LLM (segundos,
                       útil para iterar sobre chunking/embeddings)

tests/
  dataset/               Banco de 100 preguntas (50 con respaldo en el
                       corpus, 50 sin él — para medir alucinación)
  iteraciones/            Una carpeta por iteración experimental del RAG,
                       cada una con su plan_X.X.md y resultado_X.X.md
```

## Testing y evaluación del RAG

El proyecto sigue una metodología de iteración documentada en
[`METODOLOGIA_TESTING.md`](METODOLOGIA_TESTING.md): cada cambio al pipeline
RAG (chunking, modelo, prompt) se prueba en su propia rama contra el mismo
banco de 100 preguntas, y el resultado se registra en
`tests/iteraciones/iteracion_X.X_*/resultado_X.X.md` antes de fusionar.

```bash
# Evaluación completa (retrieval + generación), ~20-45 min según el modelo
python scripts/evaluar_banco.py <etiqueta> [modelo] [k] [num_predict]

# Pipeline de dos pasos: un juez binario decide si el contexto contiene la
# respuesta y solo entonces se llama al redactor (iteración 1.6)
python scripts/evaluar_banco.py dospasos_A --dos-pasos --juez llama3.2 --redactor llama3.2

# Solo retrieval, sin invocar al LLM (segundos)
python scripts/medir_retrieval.py

# Smoke test sobre las primeras N preguntas, sin pagar la corrida completa
python scripts/evaluar_banco.py prueba --limite 10
```

El estado de las líneas de investigación abiertas (qué se probó, qué falta,
qué se descartó y por qué) está en
[`ESTADO_INVESTIGACION.md`](ESTADO_INVESTIGACION.md), en la raíz del repositorio.

## Documentación relacionada

| Documento | Contenido |
|---|---|
| [`ESTADO_INVESTIGACION.md`](ESTADO_INVESTIGACION.md) | **Mapa del proyecto.** Líneas de investigación abiertas, qué se confirmó, qué se refutó y con qué evidencia |
| [`CLAUDE.md`](CLAUDE.md) | Orientación para asistentes de IA: reglas de trabajo, cómo se mide y trampas conocidas |
| [`CONTEXTO.md`](CONTEXTO.md) | Auditoría técnica detallada: inventario de archivos, configuración de Ollama/ChromaDB, seguridad, roadmap |
| [`Bitacora.md`](Bitacora.md) | Registro histórico de cambios de arquitectura, con pasos de rollback |
| [`METODOLOGIA_TESTING.md`](METODOLOGIA_TESTING.md) | Protocolo de evaluación del chatbot y estrategia de branching por iteración |
