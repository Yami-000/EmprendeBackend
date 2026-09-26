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

- **El embedder solo lee 256 tokens, y está cuantificado.** `all-MiniLM-L6-v2`
  tiene `max_seq_length = 256` y los fragmentos tienen mediana 382 tokens: **32%
  del corpus es invisible para el retrieval**, aunque el juez sí lo lea. Medido con
  `scripts/medir_ventana_embedder.py`: cuando la cita cae dentro de la ventana,
  `anclaje@6` acierta **21/23 (91%)**; cuando cae fuera, **7/14 (50%)**. Lo que se
  agregue al corpus para mejorar la recuperación tiene que caer dentro de esa
  ventana, o es **texto muerto**: así falló el arreglo de PREG-118, cuyo predicado
  quedó en el token 313. **No confundir con el truncado de `api.py` (1400
  caracteres):** ese decide qué lee el juez, la ventana decide qué se recupera.
- **El juez es inestable en ~6 de 50 preguntas** ante cambios cosméticos del
  contexto, con `temperature=0`. Decidir con `recall@k` y `anclaje@k`, que son
  deterministas; el end-to-end solo confirma, y con banda de ±6.
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
- **El juez lee las tablas aplanadas, y ya está medido que no importa.**
  `_build_judge_prompt` hace `doc.replace('\n', ' ')[:1400]`, así que una tabla
  markdown llega al modelo como una fila de pipes. La Fase 1 de la 1.10 quitó el
  aplanado: recupera **1 de 8** del núcleo duro y **0 end-to-end**, y está
  revertido. **No volver a proponerlo sin un argumento nuevo.** El dato no se
  pierde y el contexto no crece: 28415 caracteres en ambas versiones, ningún chunk
  supera los 1400 (máx. 1378). Al verificarlo a mano, ojo: el normalizador de
  `medir_retrieval.py` quita las viñetas solo al inicio de línea, y sobre texto
  aplanado quedan en medio, lo que produce falsas "pérdidas" de cita.
- **El veredicto del juez es determinista ante el mismo contexto.** Dos corridas
  idénticas del núcleo duro dan 0 vuelcos de 8. La inestabilidad de ~6 de 50
  aplica a cambios *del* contexto, no a repetir una corrida.

- **El juez negaba 8 preguntas con el dato delante, y la 1.10 recuperó 5.** La
  causa era que el corpus codificaba las relaciones como columnas de tabla
  (`| Notaría | Escritura pública |`) mientras el prompt del juez veta la
  inferencia necesaria para leerlas. La solución **no** fue tocar el modelo ni el
  prompt: fue **declarar la relación en prosa antes de la tabla** —*"La Notaría
  elabora la escritura pública de constitución"*— sin borrar la fila. Núcleo duro
  0 → 5 de 8, sensibilidad 18/29 → 23/29, especificidad y alucinación intactas.
- **Lo que resiste son las preguntas comparativas y disyuntivas.** PREG-010, 064 y
  084 reciben el predicado en el contexto —en el **puesto 1** dos de ellas— y el
  juez dice `NO` igual. Piden una **relación entre dos datos**, no un dato. Es el
  trabajo de la 1.11 y hace falta un mecanismo nuevo: más prosa del mismo tipo es
  retrabajo.
- **Los primeros 256 tokens de cada fragmento son un presupuesto escaso con dos
  inquilinos.** Las palabras clave (1.8) y las frases-predicado (1.10) viven ahí, y
  **compiten**: la 1.13 midió que agregar 14 predicados más baja `recall@6` en 1, y
  que **quitar** dos frases lo baja 2 más. No es que "más texto diluya": es que mover
  cualquier cosa en ese prefijo reordena lo que el embedder ve. **Es el techo
  estructural del retrieval de este proyecto.**
- **Los predicados no dependen de la redacción elegida.** Probado en la 1.13:
  PREG-088 sigue aprobando con el predicado **mecánico** (*"La institución Notaría se
  encarga de: escritura pública de constitución"*) en vez del escrito a mano. No hace
  falta acertar las palabras, alcanza con que el corpus afirme la relación.
- **Al agregar texto al corpus, vigilar el conteo de chunks.** Dos frases de más
  partieron `tipos_sociedad_chile.md` en 3 chunks, bajaron `recall@6` de 48/50 a
  47/50 y *bajaron* la sensibilidad de 23/29 a 22/29. Un predicado que parte una
  sección cuesta más de lo que compra.
- **`anclaje@k` exige adyacencia.** Compara `cita in norm(doc)`, una subcadena
  contigua. Varias citas abarcan dos o tres líneas seguidas, así que **insertar
  texto entre las líneas de una cita la destruye**. Verificar que las citas siguen
  presentes **antes** de reingestar.
- **No regenerar un subconjunto para compararlo con su propio control.** Se derivan
  del índice; si el corpus cambió, el denominador se mueve. Los 29 IDs del control
  están congelados en `tests/dataset/dato_integro_k6_control_1.9.txt`. Y al
  redirigirlos, **no usar `2>&1`**: la línea de resumen de stderr se colaría como ID.
- **El chunking ya divide por encabezados markdown.** Lo que rompe los
  fragmentos es el solape por caracteres (`chunk[-150:]`), que hace que el 62%
  empiece a mitad de frase. Ver la sección 5 de `CONTEXTO.md`.

## Idioma

Documentación, commits y pull requests en **español**, salvo tecnicismos.
