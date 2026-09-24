# Instrucciones para asistentes de IA

## Qué es este proyecto

**Ecia** — bot de Telegram con pipeline RAG que asesora sobre formalización de
PYMEs y trámites del SII (Chile). Node.js (bot + API) + Python (`ai-service`:
FastAPI + ChromaDB + Ollama).

La investigación en curso busca que un modelo de **3B de parámetros** dé buen
rendimiento **cambiando la arquitectura**, no escalando el modelo. Un sistema
que corre en hardware modesto es el objetivo del proyecto, no una limitación a
superar: haría accesible información del SII en máquinas básicas.

## Dónde retomar

El punto de partida acordado está al inicio de
[`ESTADO_INVESTIGACION.md`](ESTADO_INVESTIGACION.md), en el bloque
"Punto de partida de la próxima sesión". Léelo antes que nada.

## Antes de proponer cambios al pipeline RAG

**Lee [`ESTADO_INVESTIGACION.md`](ESTADO_INVESTIGACION.md).** Contiene las siete
líneas de investigación abiertas con su estado, y una sección de *callejones sin
salida* con lo que ya se midió y falló. Varias ideas plausibles —escalar el
modelo, reformular el prompt, recalibrar el juez— ya están refutadas con
números. Proponerlas de nuevo sin un argumento nuevo es retrabajo.

Ese archivo vive en la raíz y se fusiona a `main` apenas cierra una iteración,
para que esté disponible en **todas** las ramas. Si lo actualizas, no lo muevas
dentro de `tests/iteraciones/`.

## Reglas de trabajo

- **Ramas.** Una por iteración, siempre creada desde `main`. No todas llegan a
  `main`: solo se fusiona lo que mejora una métrica o aporta documentación
  transversal.
- **Documentar también lo que falla.** Un experimento negativo bien registrado
  evita repetirlo. Ver `tests/iteraciones/experimento_prompt_v2.md` como modelo.
- **Un experimento, una variable.** Cambiar dos cosas a la vez ya costó una
  corrida completa que no se pudo atribuir.
- **Mantener la documentación al día en el mismo turno** en que cambia el
  proyecto: `ESTADO_INVESTIGACION.md`, `Bitacora.md`, `README.md` y `CONTEXTO.md`.
- **Medir barato antes que caro.** `scripts/medir_retrieval.py` evalúa retrieval
  en segundos sin invocar al LLM; `evaluar_banco.py --limite N` hace un smoke
  test. La corrida completa tarda 20-45 min según el modelo.

## Cómo se mide

Banco de 100 preguntas en `tests/dataset/banco_preguntas_respuestas.json`: las
**50 primeras son respondibles** con el corpus, las 50 siguientes **no** — esa
segunda mitad es la que mide alucinación. La clasificación vive en el orden del
array, no en un campo.

```bash
python scripts/evaluar_banco.py <etiqueta> [modelo] [k] [num_predict]
python scripts/evaluar_banco.py dospasos_A --dos-pasos --juez llama3.2 --redactor llama3.2
python scripts/medir_retrieval.py
```

`evaluar_banco.py` importa los prompts desde `ai-service/api.py` en vez de
copiarlos, para no medir una versión divergente de la que corre en producción.

## Trampas conocidas

- **`retrieval_hit@k` se mide por archivo, no por chunk** — es optimista. Ver
  las advertencias de método en `ESTADO_INVESTIGACION.md`.
- **El modelo de embeddings debe coincidir** entre `ingest.py` y `api.py`
  (`all-MiniLM-L6-v2`, 384 dims). Ya hubo un caso en que divergían y coincidían
  por accidente.
- **Tras un `pull` hay que reconstruir el índice**: `cd ai-service && python ingest.py`.
  `chroma_db/` no está versionado.
- **El orden del system prompt no es arbitrario.** Mover la regla de abstención
  tras el contexto subió la alucinación de 34% a 78%. Hay un comentario de
  advertencia en `api.py`.
- **El chunking ya divide por encabezados markdown.** Lo que rompe los
  fragmentos es el solape por caracteres (`chunk[-150:]`), que hace que el 62%
  empiece a mitad de frase. Ver la sección 5 de `CONTEXTO.md`.

## Idioma

Documentación, commits y pull requests en **español**, salvo tecnicismos.
