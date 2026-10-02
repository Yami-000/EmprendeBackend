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

Si necesitas el panorama completo y no solo el próximo paso,
[`INFORME_INVESTIGACION.md`](INFORME_INVESTIGACION.md) es la síntesis: metodología,
las 18 hipótesis con su resultado, la configuración óptima, limitaciones y riesgos
abiertos.

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

# lo que recibe el usuario: requiere el endpoint corriendo (~11 min)
python scripts/evaluar_endpoint.py <etiqueta>

# diagnosticar un caso suelto: el juez ante una compuesta y sus mitades
python scripts/sonda_compuestas.py --reps 3
```

`evaluar_banco.py` importa los prompts desde `ai-service/api.py` en vez de
copiarlos, para no medir una versión divergente de la que corre en producción.

## Trampas conocidas

- **El embedder es `multilingual-e5-small` y su ventana ya no es el techo.** Lee
  **512 tokens** y los fragmentos tienen mediana 283, así que **0 de 28 exceden la
  ventana**: todo el corpus influye en el retrieval. Antes, con `all-MiniLM-L6-v2`
  (256 tokens), el 32% era invisible y eso era el techo del proyecto. Verificable con
  `scripts/medir_ventana_embedder.py`.
- **El contrato del embedder vive en `ai-service/embedding.py`, en un solo lugar.**
  El modelo y los prefijos. Estaba escrito a mano en siete archivos y eso ya causó un
  incidente. **No volver a escribir el nombre del modelo en ningún otro sitio.**
- **Los prefijos `query:` y `passage:` no son opcionales.** La familia E5 se entrenó
  con esa asimetría: sin prefijo rinde peor, y con el prefijo cambiado rinde **peor
  que sin ninguno**. Usar `para_consulta()` para lo que se busca y `para_pasaje()`
  para lo que se indexa.
- **`k=3` en producción, y es el embedder lo que lo permite.** `anclaje@3` con e5 es
  30/37, mejor que el 28/37 que daba MiniLM con `k=6`. Con `k=6` el juez filtra
  PREG-045 (pregunta quién recauda los impuestos girados por el SII: la Tesorería, que
  no está en el corpus) y el redactor contesta mal. Bajar el contexto a la mitad
  también bajó la latencia del juez de 12,7 s a 6,9 s.
- **La especificidad del juez es 49/50, no 50/50, y el 0% de alucinación descansa en
  el redactor.** El juez aprueba PREG-045 y el redactor abstiene igual. Cumple la
  restricción, pero es una garantía más frágil que la de la 1.10: **cualquier cambio
  que toque al redactor puede destapar esa fuga.**
- **El juez es inestable en ~6 de 50 preguntas** ante cambios cosméticos del
  contexto, con `temperature=0`. Decidir con `recall@k` y `anclaje@k`, que son
  deterministas; el end-to-end solo confirma, y con banda de ±6.
- **`retrieval_hit@k` se mide por archivo, no por chunk** — es optimista. Ver
  las advertencias de método en `ESTADO_INVESTIGACION.md`.
- **El modelo de embeddings debe coincidir** entre indexación y consulta
  (`multilingual-e5-small`, 384 dims). Ya hubo un caso en que divergían y coincidían
  por accidente. **Desde la 1.14 eso ya no depende de la disciplina:** el nombre vive
  solo en `ai-service/embedding.py` y todo lo demás lo importa.
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
- **El juez de 3B verifica un hecho a la vez, no una relación entre dos.** Con el
  mismo contexto y el mismo prompt, PREG-084 da `NO` como *"¿cuál es la diferencia
  entre los tipos de socios?"* y `SI` a las dos subpreguntas por separado
  (`scripts/sonda_descomposicion.py`). No es la instrucción: es la tarea.
- **Eso ya está explotado, y la solución fue una regla, no un modelo.**
  `descomponer_comparativa()` en `api.py` parte *"diferencia entre X y Y"* en dos
  preguntas por definición y **exige que TODAS den `SI`**. Suma 3 preguntas (34/50 a
  37/50) sin costo de latencia ni de especificidad. Tres cosas la hacen segura y hay
  que preservarlas: **solo se dispara cuando el juez ya dijo `NO`**, **exige la
  conjunción** —de las 5 preguntas que el patrón cubre, 2 son sin respaldo y la
  conjunción es lo que las protege— y **no toca el retrieval ni el redactor**, que
  reciben la pregunta original.
- **No editar el texto del prompt del juez para esos casos.** Tres refutaciones
  independientes: `flexible` (1 de 8), un juez de 7B (0 de 8) y ampliar la
  enumeración de tipos de dato (1.12, **0 de 3** y 9 juicios idénticos con las dos
  variantes). Lo que queda en pie es **partir la pregunta en dos juicios y combinar
  los veredictos fuera del modelo** (B2), con premisa validada en 2 de 3 y un techo
  de 2 preguntas por una llamada extra.
- **`anclaje@k` no es un proxy suficiente del juez.** La 1.11A lo subió de 28 a
  31/37 —el mejor del proyecto— y la **sensibilidad bajó** de 23/29 a 20/29, con la
  cobertura de datos subiendo de 61% a 77%. Mide si la cita está entre los k, no
  **qué más** hay ahí. Si un cambio mejora `anclaje@k`, confirmá la sensibilidad
  antes de celebrarlo.
- **HISTÓRICO, ya no aplica: el prefijo de 256 tokens era un presupuesto escaso con
  dos inquilinos.** Con `all-MiniLM-L6-v2` las palabras clave (1.8) y las
  frases-predicado (1.10) competían por ese espacio, y la 1.13 lo midió: agregar 14
  predicados bajaba `recall@6` en 1, y **quitar** dos frases lo bajaba 2 más. **La
  1.14 lo dejó sin efecto** al pasar a una ventana de 512 tokens. Queda anotado por
  dos razones: explica por qué los números de la 1.13 salieron como salieron, y
  **cualquier número medido antes de la 1.14 pertenece a ese régimen** y no se puede
  comparar de frente con uno de ahora.
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

- **El juez aprueba una pregunta compuesta con las DOS mitades en `NO`, y eso filtró
  una alucinación real.** *«¿Qué es el servicio de impuestos internos (SII) y cuál es
  su misión institucional?»* recibe `SI` mientras cada mitad por separado recibe `NO`.
  Es el espejo del caso comparativo de la 1.16: allí exigía las dos y fallaba, aquí no
  exige ninguna. La 2.1 lo tapó con `partir_compuesta()` + **veto**, a costo cero.
  **Es un veto y no una conjunción a propósito:** exigir que las dos mitades den `SI`
  rechazaría PREG-019, que hoy se responde bien. Reproducible con
  `scripts/sonda_compuestas.py`.
- **El veredicto del juez depende de la ORTOGRAFÍA de la pregunta.** Con el mismo trío
  de documentos recuperados, la pregunta de arriba **con tildes** da `SI` y **sin
  tildes** da `NO`, y cada una es determinística (3 de 3). No es la banda de ~6 de 50,
  que es sensibilidad al *contexto*. **Consecuencia de método: un caso que no reproduce
  no prueba que la fuga no exista.** Un comentario en `api.py` llegó a afirmar cuatro
  fugas reproducibles y al remedirlas solo reproducía **una**.
- **No bajes la severidad del juez para "arreglar" abstenciones.** La 2.1 midió el caso
  reportado desde Telegram al revés de lo que parecía: de cinco respuestas, **cuatro
  abstenciones eran correctas** y la falla era la quinta. Bajar el umbral habría roto
  cuatro aciertos y dejado la fuga intacta.
- **`AYUDA_ABSTENCION` va como SUFIJO de `FRASE_ABSTENCION` y vive en el endpoint.**
  No la reemplaces: `abstuvo()` detecta un fragmento de esa frase y sobre él se calculan
  la alucinación y la abstención indebida de **19 iteraciones**. Y no la muevas al system
  prompt: eso cambia lo que el redactor genera, que es una variable medida.
- **Hay dos arneses y miden cosas distintas.** `evaluar_banco.py` replica el pipeline y
  es el único que ve el veredicto del juez (sensibilidad, especificidad).
  `evaluar_endpoint.py` habla HTTP con `/chat` y es el único que prueba lo que recibe el
  usuario. **Una lógica que vive en el endpoint —el veto, el saludo— el arnés no la
  ejecuta.** No son sustitutas.
- **No reinicies uvicorn mientras corre una medición por el endpoint.** Las consultas que
  caen en esa ventana dan error de conexión y `evaluar_endpoint.py` **cuenta un error de
  transporte como abstención**: los números salen sesgados hacia el lado bueno sin que se
  note. Ya invalidó una corrida. Mirar `errores de transporte` antes de creerle a una.

- **No propongas cambiar la métrica de similitud del índice (OP-5).** Es un no-op:
  los vectores son unitarios porque el modelo trae capa `Normalize`, y para vectores
  unitarios el orden por L2 y por coseno es el mismo. Verificado: top-6 idéntico en
  **50 de 50** preguntas.
- **Las hipótesis del pipeline están cerradas.** `CHUNK_SIZE` se midió óptimo en las dos
  direcciones (1.15) y B2 se confirmó (1.16). Lo que queda es **ingeniería**, y está
  priorizado en el bloque de arranque de `ESTADO_INVESTIGACION.md`: endurecer la
  especificidad, el *fallback* que devuelve el contexto en crudo, el historial que no
  llega al juez y qué guarda la traza. Ver
  `tests/iteraciones/triaje_hipotesis_2026-09-27.md` antes de proponer otra cosa.

## Idioma

Documentación, commits y pull requests en **español**, salvo tecnicismos.
