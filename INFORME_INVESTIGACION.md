# Ecia — Informe de investigación del pipeline RAG

**Última actualización:** 2026-09-27 · **Iteraciones cubiertas:** 1.0 a 1.16
**Estado del sistema:** ver la sección [Configuración óptima](#6-configuración-óptima)

Este documento es la **síntesis** de la investigación: qué se buscaba, cómo se midió,
qué se probó y qué quedó en pie. Está escrito para alguien que no participó de las
sesiones.

Complementa, no reemplaza, a los otros dos documentos vivos:

| Documento | Para qué |
|---|---|
| [`ESTADO_INVESTIGACION.md`](ESTADO_INVESTIGACION.md) | **El mapa operativo.** Dónde retomar, qué está abierto, callejones sin salida con su evidencia |
| [`CONTEXTO.md`](CONTEXTO.md) | **El código verificado.** Inventario, configuración, deuda técnica |
| Este archivo | **La síntesis.** Metodología, hipótesis, resultados, próximos pasos |

---

## 1. El problema y el objetivo

**Ecia** es un bot de Telegram que asesora sobre formalización de PYMEs y trámites del
Servicio de Impuestos Internos de Chile, con un pipeline RAG sobre un corpus normativo
propio.

El objetivo de la investigación **no es maximizar una métrica**: es lograr que un
modelo de **3B de parámetros** dé buen rendimiento **cambiando la arquitectura**, no
escalando el modelo.

> Un sistema que corre en hardware modesto es el objetivo del proyecto, no una
> limitación a superar. Haría accesible información del SII en máquinas básicas.

Esa premisa tiene consecuencias concretas en las decisiones: se descartó un embedder
de 2,2 GB que habría resuelto un problema con margen, porque contradice el propósito
(ver [hipótesis 14](#h14--cambiar-el-embedder)).

**El modo de fallo que importa es la alucinación.** En normativa tributaria una
respuesta inventada es peor que ninguna respuesta, así que el sistema debe **callar
cuando no sabe**. Esto gobierna todos los criterios de aceptación.

### Contexto material

```
corpus ........ 13 archivos .md, 26.245 caracteres, elaboración propia
indice ........ ChromaDB persistente, 28 fragmentos
modelo ........ llama3.2 (3,2B) en Ollama, local
embedder ...... multilingual-e5-small (384 dims, 512 tokens)
hardware ...... GPU GTX 1650
```

---

## 2. El instrumento de medición

Todo lo que sigue depende de esto, así que va antes de los resultados.

### El banco de preguntas

`tests/dataset/banco_preguntas_respuestas.json`: **100 preguntas**.

- Las **50 primeras son respondibles** con el corpus.
- Las **50 siguientes NO lo son** — esa mitad es la que mide alucinación.

La clasificación vive en **el orden del array**, no en un campo. Ocho tipos:
`normativa` (25), `factual` (21), `conceptual` (21), `procedimiento` (15),
`delimitacion` (9), `adversarial` (5), `sancion` (3), `tecnico` (1).

**Varias de las 50 sin respaldo son adversarias por diseño:** nombran al SII o un
trámite real para preguntar algo que el corpus no cubre. Es lo que las hace útiles y
también lo que hace que un retrieval *mejor* pueda empeorar la especificidad.

### Las métricas, y cuál decide

```
DETERMINISTAS  (deciden)
  recall@k    ¿alguno de los k fragmentos viene de un archivo con la respuesta?
              Se mide por ARCHIVO, así que es OPTIMISTA.
  anclaje@k   ¿la cita literal del ground truth aparece ÍNTEGRA en algún fragmento?
              Se mide por CHUNK. Es lo que realmente ve el juez.

END-TO-END     (confirman, con banda de ±6 preguntas)
  sensibilidad     el juez dice SI en una pregunta respondible
  especificidad    el juez dice NO en una pregunta sin respaldo
  alucinación      una respuesta sin respaldo LLEGÓ AL USUARIO
  abstención indebida  el sistema calló teniendo el dato
```

**Especificidad y alucinación no son lo mismo**, y confundirlas oculta fallos reales:
entre las dos está el redactor, que puede abstenerse pese al `SI` del juez. Hoy eso
está ocurriendo (ver [riesgos abiertos](#10-riesgos-abiertos)).

### La restricción que no se negocia

> **Nada entra si la especificidad baja de 48/50 o si la alucinación sube de 0%.**

No es una métrica más: es el criterio que hace al sistema apto para su dominio. Se
respetó en las 16 iteraciones.

---

## 3. La metodología de trabajo

Estas reglas no son burocracia: cada una se adoptó **después de que su ausencia
costara algo**.

### Un experimento, una variable

La iteración 1.1 cambió cinco cosas a la vez, el resultado empeoró y **no se pudo
atribuir a cuál**. Costó una corrida completa. Desde entonces se construyó
`scripts/ablacion_chunking.py`, que separa variables a ~10 s por variante.

El corolario práctico: cuando dos cambios tocan subsistemas distintos (retrieval y
juez), se miden **en secuencia**, no juntos — aunque apuren.

### Medir barato antes que caro

```
medir_retrieval.py .......... segundos, sin LLM
medir_ventana_embedder.py ... segundos, sin LLM
ablacion_chunking.py ........ ~10 s por variante, sin LLM
prueba dirigida (8 ids) ..... ~3 min
subconjunto (29 ids) ........ ~15 min
banco completo (100) ........ 20-45 min
```

**Diseñar las puertas en ese orden es lo que permitió cerrar hipótesis enteras sin
gastar una corrida.** La hipótesis 15 (`CHUNK_SIZE`) se refutó completa con **cero**
invocaciones al LLM.

### El orden de las puertas depende del riesgo

En cambios de corpus la especificidad va última: el riesgo es bajo. En cambios del
**prompt del juez** va **primera**, porque la Fase 0 de la 1.9 mostró que tocar ese
prompt puede llevar la especificidad de 50/50 a 0/50. **No tiene sentido medir la
sensibilidad de una variante que no puede entrar.**

### Documentar también lo que falla

Un experimento negativo bien registrado evita repetirlo. La tabla de
[callejones sin salida](#7-callejones-sin-salida) es, en volumen, el resultado
principal de la investigación.

### Ramas y fusión

Una rama por iteración. **No todas llegan a `main`:** solo se fusiona lo que mejora
una métrica o aporta documentación transversal. En dos casos se fusionó el hallazgo y
**se dejó el código afuera** deliberadamente.

### Congelar los subconjuntos de comparación

Los subconjuntos se derivan del índice. Si el índice cambia, el denominador se mueve y
la comparación con su propio control se rompe. Los 29 IDs del control de sensibilidad
están congelados en `tests/dataset/dato_integro_k6_control_1.9.txt`.

### No copiar lo que se puede importar

`evaluar_banco.py` importa los prompts, el descomponedor y el contrato del embedder
**desde `api.py` y `embedding.py`**, en vez de copiarlos. Una copia divergente mide
una versión que no es la que corre.

---

## 4. Cronología de resultados

Extraída de las 35 corridas registradas en `tests/iteraciones/`.

| Iteración | Configuración | juez `SI` | abst. indebida | especif. | ALUC |
|---|---|---|---|---|---|
| 1.0 | baseline, **un paso** | — | 12/50 | 50/50 | **17 (34%)** |
| — | prompt v2 (abstención al final) | — | 2/50 | 50/50 | **39 (78%)** |
| 1.3 | `llama3.1:8b`, un paso | — | 5/50 | 50/50 | 16 (32%) |
| 1.3 | `qwen2.5:7b`, un paso | — | 5/50 | 50/50 | 21 (42%) |
| **1.6** | **dos pasos (juez + redactor)** | 26/50 | 25/50 | 50/50 | **0** |
| 1.1 | chunking 1400 | 30/50 | 21/50 | 50/50 | 0 |
| 1.7 | grafo declarado | 28/50 | 24/50 | 50/50 | 0 |
| 1.8 | palabras clave derivadas | 25/50 | 25/50 | 50/50 | 0 |
| 1.10 | predicados en el corpus | 30/50 | 20/50 | 50/50 | 0 |
| 1.11 | promediar ventanas | 28/50 | 24/50 | 50/50 | 0 |
| 1.14 | e5-small, `k=6` | 38/50 | 13/50 | 49/50 | **1** |
| 1.14 | e5-small, `k=3` | 34/50 | 16/50 | 49/50 | 0 |
| **1.16** | **+ descomposición comparativa** | **37/50** | **13/50** | 49/50 | **0** |

**Retrieval en paralelo:**

| | recall@6 | anclaje@6 |
|---|---|---|
| baseline | 44/50 | 22/37 |
| 1.8 | 48/50 | 29/37 |
| 1.10 | 48/50 | 28/37 |
| **1.14 (e5)** | **49/50** | **36/37** |
| 1.14, `anclaje@8` | — | **37/37** (techo teórico) |

### Las dos inflexiones

**La 1.6 fue la arquitectónica.** Separar el juicio de la redacción llevó la
alucinación de 34% a **0%** sin cambiar de modelo, después de que la 1.3 demostrara
que escalar a 7-8B **no** la bajaba. Es la validación de la tesis del proyecto.

**La 1.14 fue la del instrumento.** Entre la 1.1 y la 1.8 el retrieval mejoraba y la
sensibilidad del juez **bajaba** (30 → 28 → 25). La causa resultó ser que el embedder
solo leía 256 tokens de fragmentos de 382: un tercio del corpus no influía en qué se
recuperaba, y las mejoras competían por un prefijo escaso.

---

## 5. Las hipótesis, una por una

### H1 — Chunking: el tamaño del fragmento ✅ *confirmada parcialmente*

**Iteración 1.1.** Subir el tope de 800 a 1400 caracteres sube el `anclaje` de 22/36 a
31/36 con `k=8`: con 800 el dato llegaba partido entre dos fragmentos.

**Cambió cinco variables a la vez** y el resultado neto empeoró. La ablación posterior
mostró que cuatro de las cinco estorbaban. Es el origen de la regla de una variable.

### H2 — Escalar el modelo de generación ❌ *refutada*

**Iteración 1.3.** `llama3.1:8b` deja la alucinación en 32% y `qwen2.5:7b` la **sube**
a 42%, contra 34% del 3B. Cuesta 2,4x el tiempo de corrida.

**Es la refutación que funda la dirección del proyecto:** si escalar no sirve, hay que
cambiar la arquitectura.

### H3 — Discriminación en dos pasos ✅ **confirmada, el mayor avance**

**Iteración 1.6.** Un juez binario decide si el contexto contiene la respuesta; solo
si aprueba se llama al redactor. **Alucinación de 34% a 0%**, con el mismo modelo de
3B.

Efecto lateral valioso: el camino `NO` **no llama al modelo**, así que es más rápido
que el pipeline de un paso.

### H4 — Reformular el system prompt ❌ *refutada, con daño*

Mover la regla de abstención a un cierre tras el contexto subió la alucinación de 34%
a **78%**. Reforzar "usa el contexto" justo antes de generar empuja al modelo a forzar
una respuesta.

**El orden del system prompt no es arbitrario.** Hay un comentario de advertencia en
`api.py`.

### H5 — RAG basado en nodos (grafo) ◐ *parcial*

**Iteración 1.7.** Declarar las aristas en la cabecera de cada documento **sirve**;
recorrerlas para expandir el retrieval **no**: el mejor de 9 configuraciones compra +1
pregunta por 45% más contexto, y la variante que desplaza a los peor rankeados degrada
hasta 36/50.

Con 28 fragmentos y `k=6`, la búsqueda vectorial ya ve el 21% del corpus.

### H6 — Palabras clave derivadas del corpus ✅ *confirmada*

**Iteración 1.8.** Un prefijo de 5 palabras clave por documento en el **texto
indexado** (no en el guardado) sube el `anclaje@6` de 25/37 a 29/37.

**Se derivan del corpus, no se eligen a mano:** elegirlas mirando el banco sería
ajustar al conjunto de prueba. Esta decisión metodológica fue la que después obligó a
auditar la 1.10 (ver H12).

### H7 — Un juez más grande ❌ *refutada*

**Iteración 1.9, vía B1.** `qwen2.5:7b` de juez da **18/29**, el mismo número que el
3B, y 8 de los 11 falsos `NO` son los mismos. Cuesta 2,3x de latencia.

**Si dos modelos con 2,3x de diferencia rechazan las mismas preguntas teniendo el dato
delante, no es capacidad.**

### H8 — Aflojar el prompt del juez ❌ *refutada dos veces*

La variante `flexible` recupera **1 de 8** casos difíciles. Medida en la 1.6 y
replicada en la 1.9 sobre otro corpus.

### H9 — Sustituir el `SI`/`NO` del juez por una cita verificable ❌ *refutada*

**Fase 0 de la 1.9.** El juez con cita **nunca dice `NO`**: 10 fugas de 10. Y 6 de
esas 10 citas son válidas pero irrelevantes, así que verificar que la cita exista no
protege. Llevaría la especificidad de 50/50 a 0/50.

**Dejó el modo de fallo más importante del proyecto:** hacer que el contexto *parezca*
pertinente empuja al juez a aprobar sin respaldo.

### H10 — La causa de los falsos `NO`: inferencia relacional 🔍 *diagnóstico*

**Iteración 1.9.** Ocho preguntas se negaban con el dato delante. Medidas las tres
explicaciones candidatas: capacidad del modelo (0 de 8), calibración del prompt (1 de
8), redacción de la pregunta (refutada — PREG-065 cita textual el encabezado del
documento).

Lo ausente del contexto era **siempre el verbo**. El corpus decía
`| Notaría | Escritura pública |` bajo una columna "Rol"; la pregunta pedía quién la
*elabora*; el prompt del juez veta el *"tema relacionado o parecido"*.

**La inferencia que hacía falta era justo la que el prompt prohibía. El juez era
obediente, no incapaz.**

### H11 — Declarar las relaciones como predicados ✅ *confirmada*

**Iteración 1.10, Fase 2.** Agregar *"La Notaría elabora la escritura pública de
constitución"* **antes** de la tabla, sin borrar la fila. **+11 líneas, 0 borradas.**

Núcleo duro de 0 a **5 de 8**; banco completo 25/50 → **30/50**; especificidad y
alucinación intactas. Cayó PREG-088, que había resistido al juez de 7B, al prompt
`flexible` y a la Fase 1.

**La fila de tabla no se borra:** 37 de las 50 citas son texto literal y `anclaje@k`
las compara carácter a carácter.

### H12 — ¿Los predicados eran sobreajuste al banco? ✅ *no lo eran*

**Iteración 1.13.** Los 6 predicados de la 1.10 **se escribieron mirando las 8
preguntas del banco**, lo que contradice el criterio de la 1.8.

Se construyó un generador con **plantillas derivadas de los encabezados de cada
tabla**, ciego al banco. Prueba directa: al quitar los predicados escritos a mano y
dejar solo las versiones mecánicas, **PREG-088 sigue aprobando**. La redacción elegida
no era necesaria.

Limpio en 1 de 2 casos comprobables, y ese caso sale a favor del mecanismo.

### H13 — Promediar ventanas del embedder ❌ *refutada, y superada*

**Iteración 1.11.** En vez de dejar que el embedder truncara a 256 tokens, promediar
ventanas: `anclaje@6` subió a **31/37**, el mejor del proyecto en ese momento, y la
**sensibilidad bajó** de 23/29 a 20/29.

**Es el resultado que enseñó que `anclaje@k` no es un proxy suficiente del juez.**
Mide si la cita está entre los k, **no qué más hay ahí**. La 1.14 la dejó además sin
objeto al subir la ventana.

### H14 — Cambiar el embedder ✅ **confirmada, resolvió el techo**

**Iteración 1.14.** `all-MiniLM-L6-v2` lee **256 tokens** y los fragmentos tenían
mediana 382: **22 de 28 excedían la ventana y el 32% del corpus no influía en el
retrieval.** Cuantificado: `anclaje@6` acertaba **91%** cuando la cita caía dentro de
la ventana y **50%** cuando caía fuera — 41 puntos de brecha.

`multilingual-e5-small`: 512 tokens, **384 dims** (no cambia el esquema del índice),
~470 MB.

```
anclaje@6 ...  28/37  ->  36/37  (97%)
anclaje@8 ...  30/37  ->  37/37  (100%, techo teórico)
recall@6 ....  48/50  ->  49/50
fragmentos fuera de la ventana:  22 de 28  ->  0 de 28
```

**Efecto no previsto:** el tokenizador de XLM-R es más eficiente en español. Los mismos
fragmentos pasan de mediana 382 tokens a **283**. La ventana no solo alcanza, sobra.

**Se descartó `bge-m3` (8192 tokens) a propósito:** pesa 2,2 GB contra 470 MB.
Contradice el propósito del proyecto.

**El precio:** con `k=6` el juez aprobó PREG-045 —*"¿qué organismo recauda los
impuestos girados por el SII?"*, cuya respuesta es la Tesorería General de la
República y no está en el corpus— y el bot contestó que el SII. **Una alucinación.**
Solo `k=3` la elimina, y resulta que `anclaje@3` con e5 (30/37) **supera al
`anclaje@6` de MiniLM** (28/37): mejor retrieval con la mitad del contexto, y la
latencia del juez baja de 12,7 s a **6,9 s**.

### H15 — Agrandar `CHUNK_SIZE` ❌ *refutada, sin gastar LLM*

**Iteración 1.15.** La 1.14 habilitó fragmentos más grandes sin volverlos invisibles.
Valía preguntarlo porque la comparación original (800 contra 1400) estaba
**confundida**: bajo MiniLM un fragmento de 1400 excedía la ventana.

```
hacia arriba   anclaje@3: 32 -> 32 -> 31 -> 30 -> 28   (1400 a 2200)
hacia abajo    anclaje@3: 27 -> 27 -> 30 -> 30 -> 32   (600 a 1400)
solape         200 es el mejor, por 1 punto
```

**1400/200 ya era el óptimo.** Fragmentos más grandes son menos específicos y el
correcto rankea peor. Refutada con **cero** invocaciones al LLM.

### H16 — La taxonomía del prompt del juez ❌ *refutada, efecto nulo*

**Iteración 1.12.** El prompt pide el *"dato pedido (cifra, plazo, nombre de
institución, definición, procedimiento)"* — y **esa lista no incluye comparaciones**.

Agregar *"comparación entre dos figuras"* y *"delimitación"*: **0 de 3**, y la sonda
de descomposición corrida con las dos variantes dio **9 juicios idénticos**. No es que
la lista sea insuficiente: **el juez no la está usando para decidir.**

Tercera refutación independiente de tocar el prompt del juez.

### H17 — El juez verifica un hecho a la vez 🔍 *diagnóstico*

**Iteración 1.12.** `scripts/sonda_descomposicion.py` recupera el contexto con la
pregunta **original** y luego le pregunta al juez la original y cada subpregunta,
aislando la forma de la pregunta del retrieval.

Con el **mismo** contexto y el **mismo** prompt:

```
PREG-084  "¿Cuál es la diferencia entre los tipos de socios?"   -> NO
          "¿Qué responsabilidad tienen los socios gestores?"    -> SI
          "¿Qué responsabilidad tienen los socios comanditarios?" -> SI
```

**No es la instrucción: es la tarea.** El juez de 3B puede verificar un hecho, no una
relación entre dos.

### H18 — Descomponer las comparativas para el juez ✅ **confirmada**

**Iteración 1.16.** Una **regla determinista** —no un modelo— parte
*"diferencia ... entre X y Y"* en dos preguntas por definición, y exige que **todas**
den `SI`.

```
                        sin B2    con B2
sensibilidad .......    34/50     37/50
abstuvo indebida ...    16/50     13/50
especificidad juez .    49/50     49/50
ALUCINACION ........     0/50      0/50
latencia juez ......     6,9 s     6,8 s
```

**3 ganadas, 0 perdidas.** Exactamente las tres respondibles que la regla apunta, y
las tres respuestas verificadas como correctas contra el criterio esperado.

Tres decisiones de diseño hacen que no tenga efectos colaterales:

1. **Solo se dispara cuando el juez ya dijo `NO`**, así que no puede convertir un `SI`
   en `NO` y el costo extra recae solo en los casos que hoy se pierden — por eso la
   latencia no se mueve.
2. **Exige que TODAS las subpreguntas den `SI`.** De las 5 preguntas que el patrón
   cubre, **dos son sin respaldo** (PREG-007 y 029); las dos dieron `NO` en ambas
   subpreguntas. Una comparación necesita los dos lados en el contexto, y esa
   conjunción es lo que protege la especificidad.
3. **No toca el retrieval ni el redactor.** Los dos reciben la pregunta original. Si
   la descomposición alimentara el retrieval podría traer contexto que hace parecer
   pertinente algo que no lo es — el modo de fallo de H9.

**Una regla, no un LLM:** generar subpreguntas con un modelo costaría una llamada más
por consulta y produciría texto fuera del corpus.

---

## 6. Configuración óptima

La medida al cierre. Todos los números son del banco completo de 100 preguntas.

```
EMBEDDER ...... intfloat/multilingual-e5-small   (384 dims, ventana 512 tokens)
                contrato único en ai-service/embedding.py
                prefijos query: / passage: (la familia E5 los exige)

MODELO ........ llama3.2 (3,2B) como juez Y como redactor
CHUNKING ...... 1400 caracteres, solape 200  -> 28 fragmentos
k ............. 3
PIPELINE ...... dos pasos: juez binario, y solo si aprueba se llama al redactor
                + descomposición de comparativas, solo para el juez
PROMPT JUEZ ... 'estricto' (el orden importa: no reordenar)
```

| Métrica | Valor | Contra baseline |
|---|---|---|
| **Alucinación** | **0/50 (0%)** | era 17/50 (34%) |
| Especificidad del juez | 49/50 (98%) | — |
| Sensibilidad | 37/50 (74%) | — |
| Abstención indebida | 13/50 (26%) | era 12/50 con 34% de alucinación |
| `recall@6` / `anclaje@6` | 49/50 / 36/37 | era 44/50 / 22/37 |
| `anclaje@3` (el k que corre) | 30/37 | — |
| Latencia del juez | 6,8 s | era 12,7 s |
| Consulta respondida | 10,3 s media, 23 s pico | era 17,5 s / 39 s |

### Por qué cada pieza

- **El pipeline de dos pasos** es lo único que lleva la alucinación a 0%.
- **El embedder de 512 tokens** es lo que rompió el techo del retrieval.
- **`k=3`** no es una concesión de rendimiento: con e5 recupera mejor que `k=6` con
  MiniLM, y de paso **parte la latencia en dos**.
- **La descomposición** suma 3 preguntas sin costo de latencia ni de especificidad.
- **Los predicados en el corpus** eliminan la inferencia que el prompt del juez veta.

### ⚠️ La advertencia más importante de este informe

**Nada de esto corre en producción.** `api.py` sirve `/chat` de **un paso**, que es el
que alucina 34%. Todas las métricas de arriba son del **arnés de evaluación**. Ver
[próximos pasos](#11-próximos-pasos).

---

## 7. Callejones sin salida

Cada una se midió y no funcionó. **Reintentarlas sin un argumento nuevo es
retrabajo.** La tabla completa, con la evidencia y el archivo de cada una, está en
`ESTADO_INVESTIGACION.md`.

| Idea | Qué pasó |
|---|---|
| Escalar el modelo de generación | 8B deja la alucinación en 32%, 7B la sube a 42%, contra 34% del 3B |
| Reformular el system prompt | Mover la abstención tras el contexto la subió a **78%** |
| Aflojar el prompt del juez | Recupera 1 de 8. Medido dos veces |
| Juzgar fragmento por fragmento | Recupera 2 de 9 |
| Un juez más grande | 7B da el mismo 18/29, con 2,3x de latencia |
| Ampliar la taxonomía del prompt del juez | **Efecto nulo:** 0 de 3 y 9 juicios idénticos |
| Sustituir el `SI`/`NO` por una cita | El juez nunca dice `NO`: 10 fugas de 10 |
| Un ejemplo en el prompt del juez | El 3B lo copia como respuesta: 3 de 10 citas eran el ejemplo |
| Reescribir la pregunta del usuario | Refutado por PREG-065, que ya cita el encabezado del documento |
| Recorrer el grafo para expandir | +1 pregunta por 45% más contexto; la variante agresiva degrada a 36/50 |
| Chunking por sección markdown | El anclaje cae de 22/36 a 18/36 |
| Agrandar o achicar `CHUNK_SIZE` | 1400 ya era el óptimo en las dos direcciones |
| Anteponer el título del documento | Empeora: recall 48 → 46 |
| Promediar ventanas del embedder | Mejor `anclaje` (31/37) y **peor** sensibilidad (20/29) |
| Métrica de similitud del índice (L2 → coseno) | **No-op:** los vectores son unitarios, top-6 idéntico en 50 de 50 |
| Deduplicar el corpus | Sin objeto: el techo que la justificaba ya no existe |
| Cambiar de motor vectorial | Con 28 fragmentos el motor no es el cuello de botella |

---

## 8. Advertencias de método

Las que un lector necesita para no malinterpretar los números.

### `anclaje@k` no es un proxy suficiente del juez

Mide si la cita está entre los k fragmentos, **no qué más hay ahí**. La 1.11 lo llevó
al mejor valor del proyecto y la sensibilidad bajó. **Si un cambio mejora `anclaje@k`,
confirmá la sensibilidad antes de celebrarlo.**

### El juez es determinista ante el mismo contexto, inestable ante cambios

Dos corridas idénticas dan **0 vuelcos**. Pero cambiar el contexto mueve **~6
veredictos**, con `temperature=0`. Consecuencia: repetir una corrida para "confirmar"
no aporta nada, y una diferencia neta menor a 6 no se puede afirmar.

**Lo que distingue señal de ruido es la asimetría, no la cantidad de vuelcos.** El
ruido mueve veredictos en las dos direcciones; un efecto real los mueve en una. La
1.14 dio 9 ganadas contra 1 perdida; la 1.11, 4 contra 6.

### Los dos recortes que no son el mismo

```
ventana del embedder ...  decide QUÉ fragmentos se recuperan
truncado de api.py .....  decide QUÉ lee el juez de cada fragmento recuperado
```

Confundirlos costó una iteración. Hoy la ventana es de 512 tokens y ningún fragmento
la excede, pero **si alguna vez se sube `CHUNK_SIZE` por encima de eso, el problema
vuelve.**

### `anclaje@k` exige adyacencia

Compara una subcadena **contigua**. Varias citas del banco abarcan dos o tres líneas
seguidas, así que **insertar texto entre las líneas de una cita la destruye**. Hay que
verificar que las citas siguen presentes **antes** de reingestar.

### Cualquier número medido antes de la 1.14 pertenece a otro régimen

Con MiniLM el 32% del corpus era invisible para el retrieval. Las comparaciones de
antes de ese cambio **no se comparan de frente** con las de ahora.

### Dos errores de instrumentación propios, encontrados y corregidos

Van acá porque el instrumento también se equivoca, y ocultarlo sería peor:

1. **`comparar_corridas.py` calculaba la especificidad desde `abstuvo`** en vez de
   `juez_dijo_si`. Reportaba 50/50 y **escondía** que el juez fallaba PREG-045 y que
   el 0% de alucinación dependía del redactor.
2. **Avisaba "no se distingue de la banda" solo por contar vuelcos**, y con eso
   desestimaba el resultado de la 1.14 (9 contra 1). Ahora avisa por asimetría.

3. **`ablacion_chunking.py` no aplicaba el prefijo de palabras clave** que `ingest.py`
   agrega, así que sus números absolutos no eran comparables con `medir_retrieval.py`.
   Solo servía para comparar variantes entre sí. Se le agregaron los prefijos de E5 y
   una columna con los fragmentos que exceden la ventana.

---

## 9. Limitaciones y amenazas a la validez

Lo que este informe **no** demuestra.

### El techo del banco no es 50

**13 de las 50 citas del ground truth están parafraseadas** y no existen literalmente
en ningún `.md`. Para esas preguntas ninguna técnica de chunking puede dar positivo,
así que `anclaje@k` se reporta **sobre 37**. Comparar contra 50 subestima el retrieval
en 26 puntos.

### `recall@k` es optimista por construcción

Se mide **por archivo**: cuenta acierto si alguno de los k fragmentos viene de un
archivo que contiene la respuesta, aunque ese fragmento no traiga el dato. Las
coberturas de las iteraciones 1.0 y 1.3 están infladas por esto.

### El corpus es chico

13 archivos, 26.245 caracteres, 28 fragmentos. Con `k=3` se está viendo el ~11% del
corpus en cada consulta. **Varias conclusiones podrían no escalar:** que el motor
vectorial no importe, que recorrer el grafo no sirva, que deduplicar no compre nada.

### El banco es de 100 preguntas y el ruido es de ±6

Cualquier diferencia neta menor a 6 preguntas no se puede afirmar con este
instrumento. Por eso las decisiones se toman con las métricas deterministas y el
end-to-end solo confirma.

### El corpus y el banco son de elaboración propia

No hay validación externa de que el ground truth sea correcto, más allá de una
revisión cruzada con NotebookLM registrada en la bitácora (99% de concordancia). Un
error en el ground truth se propaga a todas las métricas.

### Una sola configuración de hardware

Todas las latencias son de una GTX 1650. No hay medición en CPU pura, que es el caso
que el propósito del proyecto haría más relevante.

---

## 10. Riesgos abiertos

### El 0% de alucinación descansa en el redactor, no en el juez

**La especificidad del juez es 49/50**, no 50/50: aprueba PREG-045. Lo que evita que
la respuesta errónea llegue al usuario es que **el redactor abstiene**.

Y esa abstención está medida como **marginal y no controlada**: 6 de 185 casos
históricos (3,2%). Actúa acá como una red de seguridad que **nadie diseñó para eso**.

**Cumple la letra de la restricción, con una garantía más frágil que la de la 1.10.
Cualquier cambio que toque al redactor puede destapar esa fuga.**

### Dos piezas de código quedaron fuera de `main` por decisión

- El **promediado de ventanas** de la 1.11: sin objeto tras subir la ventana, y
  combinarlo con e5 daría una configuración que nadie midió.
- El **corpus convertido** de la 1.13: sus 20 predicados se midieron bajo un régimen
  de prefijo escaso que ya no existe.

Las dos están en el historial de su rama.

---

## 11. Próximos pasos

### 🔴 1. Llevar el pipeline de dos pasos a producción — *no es una hipótesis*

**Es lo más importante y no hay nada que medir: está medido.** `api.py` sirve `/chat`
de un paso, que alucina 34%. El bot que usa la gente **no tiene ninguna** de las
mejoras de 16 iteraciones.

El argumento que lo frenaba era la latencia, y la 1.14 la bajó de 39 s de pico a 23 s.

Qué implica, concretamente:

1. Mover la lógica de dos pasos de `evaluar_banco.py` a `api.py`.
2. **El camino `NO` no debe llamar al modelo:** devuelve `FRASE_ABSTENCION` directo.
   Es lo que lo hace más rápido que el de un paso.
3. **Cuidado con el *streaming*:** `/chat` devuelve SSE y el juez es una llamada
   bloqueante previa. El primer token va a tardar ~7 s más.
4. **Verificar con el banco a través del endpoint**, no del arnés. Es lo único que
   prueba que producción se comporta como lo medido — y es justamente lo que nunca se
   hizo, razón por la que esta deuda pasó desapercibida 16 iteraciones.

### 2. Endurecer la garantía de especificidad

Medir a propósito si la red de seguridad del redactor es sólida o casual: forzar `SI`
en las 50 sin respaldo y contar cuántas ataja. Hoy el 0% depende de un comportamiento
no caracterizado.

### 3. El grupo B: 9 preguntas cuyo dato no llega con `k=3`

Es el precio de haber elegido `k=3`. **No se ataca desde el chunking** (H15). Lo que
queda sin medir:

- **`k` variable**: una segunda pasada de retrieval con `k` mayor cuando el juez dice
  `NO`. No cambia el chunking.
- **Un reordenador (*reranker*)** sobre un `k` mayor, para quedarse con 3 eligiéndolos
  mejor. **Requeriría descargar otro modelo.**

### 4. Extender la descomposición

La regla actual cubre 5 de 100 preguntas: el patrón *"diferencia entre X y Y"*. Quedan
sin cubrir PREG-084 (*"entre los tipos de socios en una Sociedad Comanditaria"*, sin
dos lados separables), PREG-010 (disyuntiva) y las de tipo `normativa` del grupo A.

### 5. Remedir la 1.13 sobre el embedder nuevo

El generador de predicados está en `main` pero su corpus no: se midió bajo el prefijo
escaso. Si se decide incorporarlo, hay que **corregir la gramática** de las frases
generadas (*"La EIRL admite 1 socios"*) y medir ese arreglo aparte: es texto indexado.

### 6. Deuda técnica no experimental

Código muerto en `src/config/` y `src/graphql/`, dependencias declaradas sin uso,
sanitización de fragments contra prompt injection (prioridad baja: 0 casos
observados, corpus propio).

---

## 12. Reproducibilidad

```bash
# 1. Reconstruir el índice. OBLIGATORIO tras cualquier pull:
#    chroma_db/ no está versionado, y el corpus y el embedder cambian.
cd ai-service && python ingest.py && cd ..

# 2. Retrieval, en segundos y sin LLM
python scripts/medir_retrieval.py            # 28 chunks, k=6: 49/50 y 36/37
python scripts/medir_ventana_embedder.py     # 0 de 28 exceden la ventana

# 3. La configuración óptima, banco completo (~25 min)
python scripts/evaluar_banco.py v16_full --dos-pasos --descomponer \
    --juez llama3.2 --redactor llama3.2 llama3.2 3

# 4. Comparar dos corridas
python scripts/comparar_corridas.py v14_k3_full v16_full
```

La primera ejecución descarga el embedder (~470 MB) y queda en caché.

### Herramientas de diagnóstico

| Script | Para qué | Costo |
|---|---|---|
| `medir_retrieval.py` | `recall@k` y `anclaje@k` | segundos |
| `medir_ventana_embedder.py` | cuánto del corpus ve el embedder | segundos |
| `ablacion_chunking.py` | comparar configuraciones de chunking | ~10 s/variante |
| `comparar_corridas.py` | dos corridas pregunta por pregunta | instantáneo |
| `sonda_descomposicion.py` | aislar la forma de la pregunta del retrieval | ~1 min |
| `generar_predicados.py` | tablas a predicados, con regla ciega | instantáneo |
| `evaluar_banco.py` | el pipeline completo | 3-45 min según alcance |

### Trampas al reproducir

- **No regenerar los subconjuntos para comparar contra su control:** se derivan del
  índice. Los 29 IDs congelados están en `tests/dataset/dato_integro_k6_control_1.9.txt`.
- **Al redirigir la salida de los `subconjunto_*.py`, no usar `2>&1`:** imprimen una
  línea de resumen por stderr que `leer_ids` tomaría como IDs.
- **`k` es el tercer argumento posicional** de `evaluar_banco.py`, después de la
  etiqueta y el modelo.
