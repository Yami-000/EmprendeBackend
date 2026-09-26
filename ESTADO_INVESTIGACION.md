# Estado de la investigación — pipeline RAG

**Este archivo es el mapa del proyecto.** Registra qué se probó, qué funcionó,
qué se descartó y con qué evidencia. Léelo antes de proponer cualquier cambio al
pipeline: buena parte de las ideas plausibles ya se midieron y fallaron, y están
documentadas abajo con el número que las refutó.

> **Regla de ubicación.** Vive en la raíz y se fusiona a `main` apenas se cierra
> una iteración, **por separado del código de esa iteración**. No debe volver a
> quedar dentro de `tests/iteraciones/iteracion_X.X_*/`: estuvo en la carpeta de
> la 1.0 y quedó atrapado en un PR sin fusionar, de modo que las ramas 1.6 y
> posteriores citaban oportunidades (OP-6) que no existían en su árbol.

**Última actualización:** 2026-09-25, al medir y descartar la Fase 1 de la 1.10. Las
métricas de abajo son las de la 1.8, que sigue siendo la última corrida completa:
la Fase 0, la B1 y el análisis del núcleo duro se resolvieron con pruebas
dirigidas de 8 a 29 preguntas.

> ## ⏭️ Punto de partida de la próxima sesión
>
> **Iteración 1.10, Fase 2 — declarar las relaciones como predicados en el
> corpus.** El plan está escrito y aprobado en
> `tests/iteraciones/iteracion_1.10_relaciones_explicitas/plan_1.10.md`. **No hay
> que rediseñarlo:** la Fase 1 ya se midió y su resultado lo refuerza.
>
> Rama: `iteracion_1.10_relaciones_explicitas` (ya creada, desde `main`).
>
> ### Qué pasó con la Fase 1, y por qué importa para la Fase 2
>
> Se quitó el aplanado de los saltos de línea en `_build_judge_prompt`. Resultado:
> **1 de 8 en el juez, 0 de 8 end-to-end.** No pasa el corte de 3 y **está
> revertido**. Detalle en
> [`resultado_fase1.md`](tests/iteraciones/iteracion_1.10_relaciones_explicitas/resultado_fase1.md).
>
> Lo que deja no es solo un número negativo: **PREG-088 sigue en `NO` con la tabla
> perfectamente formateada.** Era el caso que motivó el cambio —fila de tabla,
> columna "Rol"— y no cayó. Eso separa dos hipótesis que venían juntas: el
> problema **no es que la tabla sea ilegible**, es que la celda no contiene el
> verbo. Des-aplanar devuelve la estructura; no devuelve la relación.
>
> **La Fase 2 es ahora la única vía en pie**, y ataca exactamente eso.
>
> ### Qué hacer, en orden
>
> **Fase 2 — declarar las relaciones como predicados.** Agregar *"La Notaría
> elabora la escritura pública de constitución"* **sin borrar la fila de tabla**:
> 37 de las 50 citas son texto literal y `anclaje@k` las compara carácter a
> carácter. La frase va **antes** de la tabla, para caer dentro de los 256 tokens
> que lee el embedder. Solo los documentos del núcleo duro. Reconstruir el índice
> y correr `medir_retrieval.py` **antes** de gastar el end-to-end: si `recall@6`
> baja de 48/50 o `anclaje@6` de 29/37, se corta ahí.
>
> **Corte:** recuperar ≥ 4 de 8.
>
> **Si falla:** queda **B2** del plan 1.9 (descomponer la pregunta), con la
> expectativa ajustada — solo 3 de las 8 son compuestas.
>
> ### Candidato nuevo que dejó la Fase 1, para después
>
> En PREG-065 el juez dijo `SI`, el redactor corrió 18,3 s y **aun así abstuvo**.
> Por eso el end-to-end fue 0 y no 1. El redactor tiene su propia abstención y
> sigue leyendo contexto aplanado (`_build_system_prompt`, línea 96, intacta por
> diseño). **Es un segundo eslabón, y está sin medir.** No entra en la 1.10 para no
> mezclar variables.
>
> ### Los números de control
>
> ```
> núcleo duro (8 preguntas) .....  0 de 8 aprobadas   (Fase 1: 1 en el juez, 0 e2e)
> sensibilidad en las 29 .........  18/29
> especificidad ..................  50/50
> alucinación ....................  0/50
> recall@6 / anclaje@6 ...........  48/50  /  29/37     (28 chunks)
> ```
>
> El veredicto del juez es **determinista ante el mismo contexto**: dos corridas
> idénticas del núcleo duro dieron 0 vuelcos de 8. La banda de ±6 aplica a cambios
> *del* contexto, no a repetir una corrida.
>
> **Restricción que no se negocia:** nada entra si la especificidad baja de 48/50
> o la alucinación sube de 0%.
>
> ### Por qué 1.10 y no 2.0
>
> Las fases son incrementales, de una variable cada una. **El 2.0 debería ser
> llevar el pipeline de dos pasos a producción:** la 1.6 lo dejó solo en el arnés
> de evaluación y `api.py` todavía sirve `/chat` de un paso, que es el que alucina
> 34%. Esa es la deuda arquitectónica real.
>
> ### Herramientas disponibles
>
> `evaluar_banco.py --ids` corre un subconjunto por ID (lista con comas o
> `@archivo`); `subconjunto_dato_integro.py` y `subconjunto_sin_respaldo.py`
> generan los subconjuntos. Una prueba dirigida de 8 preguntas tarda ~3 min y una
> de 29 unos 15, contra 20-45 min de la corrida completa. La 1.9 se resolvió
> entera sin pagar una corrida completa.

## 🚨 Dos restricciones que invalidan supuestos previos

**1. El embedder solo lee los primeros 256 tokens de cada fragmento.**
`all-MiniLM-L6-v2` tiene `max_seq_length = 256`. Los fragmentos actuales tienen
mediana 402 tokens y máximo 496: **24 de 28 exceden la ventana y un 33% del
corpus es invisible para el recuperador**. Todo lo que esté más allá del token
256 no influye en si un fragmento se recupera — solo en lo que el juez lee
después. Esto explica por qué subir `CHUNK_SIZE` de 800 a 1400 en la 1.1 mejoró
el `anclaje` (más datos por fragmento) y casi no movió el `recall` (44 → 46).

**2. El veredicto del juez se mueve en ~6 de 50 preguntas ante cambios
cosméticos del contexto.** Medido entre la 1.1 y la 1.7: en 49 de 50 preguntas la
disponibilidad del dato no cambió y el juez cambió de opinión en 6. Con
`temperature=0.0`, así que no es aleatoriedad entre ejecuciones. **Las
diferencias menores a ~6 preguntas en las métricas end-to-end no son
distinguibles de esta sensibilidad.** La B1 le dio una segunda confirmación
independiente: cambiar el juez de `llama3.2` a `qwen2.5:7b` con el **mismo
contexto** movió exactamente 6 veredictos (3 en cada dirección) sin mover el
total. La banda aparece tanto entre contextos con el mismo modelo como entre
modelos con el mismo contexto. Decidir con `recall@k` y `anclaje@k`, que
son deterministas, y usar la corrida end-to-end como confirmación declarando la
banda.

---

## Estado actual del sistema

**Pipeline de dos pasos con `llama3.2` (3B) en ambos roles, chunking de 1400
caracteres y palabras clave derivadas en el texto indexado** (iteraciones 1.6,
1.1 y 1.8):

```
MÉTRICAS DETERMINISTAS  (deciden)
  retrieval_hit@6 ........ 48/50 (96%, medido por archivo)
  anclaje@6 .............. 29/37 (78%, medido por chunk)

MÉTRICAS END-TO-END     (confirman, con banda de ±6 preguntas)
  abstuvo indebidamente .. 25/50
  cobertura de datos ..... 48%
  ALUCINACIÓN ............  0/50 (0%)
  especificidad del juez . 50/50 (100%)

Duración .............................. 28,1 min   (juez 12,7 s/pregunta)
```

**Las dos mitades del pipeline van en direcciones distintas.** La recuperación
avanzó de verdad: de `recall` 44/50 y `anclaje` 22/37 en el baseline a 48/50 y
29/37, con mediciones deterministas. La generación está bloqueada: la
sensibilidad del juez bajó 30 → 28 → 25 en las mismas tres iteraciones, y cuando
el dato le llega íntegro aprueba 18 de 29 (62%) contra 21 de 25 (84%) en la 1.1.

**El modo de fallo es el correcto para el dominio:** cero falsos positivos, así
que la alucinación se mantiene en 0% y la especificidad en 50/50. El sistema
calla de más, no inventa. Para normativa tributaria es preferible, pero limita
su utilidad.

**Tensión abierta:** cada mejora de calidad se ha pagado en latencia. El juez
pasó de 6,4 s a 12,3 s al agrandar los fragmentos, porque el 98% de su costo es
leer contexto. Una consulta respondida cuesta ~28 s en una GTX 1650. Para un bot
de Telegram eso ya es mucho, y `k=8` lo encarecería otra vez.

**Dirección estratégica:** hacer rendir al modelo de 3B cambiando la
arquitectura, no sustituirlo por uno más grande. Un sistema que corre en
hardware modesto es el objetivo del proyecto, no una limitación a superar.

---

## Las líneas de investigación

Empezaron siendo siete oportunidades numeradas (OP-1 a OP-7) de la auditoría. Las
que no llevan número salieron después, de iteraciones que abrieron mecanismos que
la auditoría no había visto.

| # | Línea | Estado | Evidencia |
|---|---|---|---|
| OP-3 | Modelo de generación | ❌ **Refutada** | 1.3 — escalar a 7-8B no baja la alucinación; B1 — tampoco ayuda escalar solo el juez |
| OP-6 | Discriminación en dos pasos | ✅ **Confirmada** | 1.6 — alucinación 34% a 0% |
| OP-1 | Chunking | ✅ **Parcial** | 1.1 — el tamaño era la causa; 25 → 21 abstenciones |
| OP-5 | Métrica de similitud | ⏳ Pendiente | sin medir, costo ~1 línea |
| OP-4 | Deduplicación del corpus | ⏳ Pendiente | incluido en el techo de retrieval |
| OP-7 | RAG basado en nodos | ◐ **Parcial** | 1.7 — declarar las aristas sirve, recorrerlas no |
| — | Palabras clave derivadas del corpus | ✅ **Confirmada** | 1.8 — anclaje 25 → 29, el mejor retrieval del proyecto |
| — | Reescritura estructurada del corpus | 🟠 **Candidata principal** | piloto: mejora el retrieval, no al juez. La 1.9 le da un mecanismo nuevo: declarar las relaciones como predicados. **Fase 2 de la 1.10, y ahora la única vía en pie**: la Fase 1 aisló el formato y no era el formato |
| — | Estabilidad del juez | 🔴 **Bloqueante** | domina toda mejora. Ni capacidad (B1: 0 de 8) ni prompt (`flexible`: 1 de 8) ni redacción de la pregunta (refutada). El diagnóstico vigente es la inferencia relacional |
| — | Presentación del contexto al juez | ❌ **Refutada** | Fase 1 de la 1.10 — des-aplanar las tablas recupera 1 de 8 y 0 end-to-end. PREG-088, el caso de tabla que motivó el cambio, sigue en `NO` con la tabla bien formateada |
| OP-2 | Sanitización de fragments | 🟢 Baja | 0 casos observados |

---

## Callejones sin salida — no repetir

Cada una de estas ideas se midió y no funcionó. Reintentarlas sin un argumento
nuevo es retrabajo.

| Idea | Qué pasó | Dónde está |
|---|---|---|
| **Escalar el modelo de generación** | `llama3.1:8b` deja la alucinación en 32% y `qwen2.5:7b` la sube a 42%, contra 34% del 3B. Cuesta 2,4x el tiempo de corrida | `iteracion_1.3_modelo/resultado_1.3.md` |
| **Reformular el system prompt (v2)** | Mover la regla de abstención a un cierre tras el contexto subió la alucinación de 34% a **78%** | `experimento_prompt_v2.md` |
| **Recalibrar el prompt del juez (A2)** | Quitar el sesgo *"ante cualquier duda responde NO"* recupera **1 de 9** casos | `iteracion_1.6_dos_pasos/resultado_1.6.md` |
| **Juzgar fragmento por fragmento (A3)** | Descomponer el contexto en 6 juicios de ~220 tokens recupera **2 de 9** | `iteracion_1.6_dos_pasos/resultado_1.6.md` |
| **Reescribir la pregunta del usuario antes del pipeline** | Idea de un modelo "validador de consultas" que desglose y reformule la pregunta. Refutada por PREG-065: la pregunta ya contiene **textualmente el encabezado del documento** y el dato viene en la línea siguiente, y dos modelos dicen `NO` igual. El eslabón que falla está después de la pregunta. Además "agregar contexto" hace que un LLM genere texto fuera del corpus, que es lo que en la Fase 0 llevó al juez a no decir `NO` nunca | `iteracion_1.9_B1_juez_grande/hallazgo_relaciones_implicitas.md` |
| **Aflojar el prompt del juez (A2 `flexible`)** | Recupera **1 de 8** del núcleo duro, y de forma inconsistente: recupera PREG-088 pero no PREG-080, otra fila de la misma tabla. Replica el "1 de 9" de la 1.6 sobre el corpus de la 1.8. Medido dos veces | `iteracion_1.9_B1_juez_grande/hallazgo_relaciones_implicitas.md` |
| **Un modelo más grande solo para juzgar (B1)** | `qwen2.5:7b` de juez da **18/29**, el mismo número que el 3B, y 8 de los 11 falsos `NO` son los mismos. Cuesta 2,3x de latencia (13,1 → 30,1 s). Si dos modelos con 2,3x de diferencia rechazan las mismas 8 preguntas teniendo el dato delante, no es capacidad | `iteracion_1.9_B1_juez_grande/resultado_B1.md` |
| **El formato de la cita explica los falsos `NO`** | La tasa de `NO` es plana entre formatos: negrita 43%, tabla 33%, prosa 33%, encabezado 50%, viñeta 0%, con 1-7 casos por celda. Coincidencia sobre n minúsculo | `iteracion_1.9_B1_juez_grande/resultado_B1.md` |
| **Juez 3B + redactor 8B (experimento B)** | Descartado sin correr: el redactor ya responde en 25 de las 26 veces que se le habilita. El problema no está ahí | `iteracion_1.6_dos_pasos/resultado_1.6.md` |
| **Contaminación del índice con documentos de la CMF** | Nunca estuvieron indexados. `ingest.py` solo lee `docs/sii/`. El daño estaba en el ground truth, no en ChromaDB | `Bitacora.md` 2026-09-17 |
| **Chunks duplicados en ChromaDB** | 0 duplicados. La sospecha venía de que `collection.add()` acumulaba entre ingestas; ya es idempotente | `Bitacora.md` 2026-09-17 |
| **Desalineación de embeddings ingesta/consulta** | Ambos usan 384 dims. Era un riesgo real (`nomic-embed-text` con respaldo silencioso) pero coincidían por accidente. Ya está fijado | `Bitacora.md` 2026-09-17 |
| **Chunking estructural: un fragmento por sección markdown** | Implementado y medido en la 1.1: el anclaje cae de 22/36 a 18/36. Fragmentar más es PEOR. `_chunk_text` ya dividía por encabezados desde antes | `iteracion_1.1_chunking/resultado_1.1.md` |
| **Quitar el solape del chunking** | Neutro (22/36 → 22/36) a k=6 y negativo a k=10. El solape hace que los fragmentos empiecen a mitad de frase, pero su efecto neto es positivo: duplica los bordes y da una segunda oportunidad al dato | `iteracion_1.1_chunking/resultado_1.1.md` |
| **Recorrer el grafo para expandir el retrieval** | 1.7, barrido de 9 configuraciones: el mejor caso compra +1 pregunta por 45% más contexto. La variante que desplaza a los peor rankeados degrada siempre, hasta 36/50 de recall. Con 28 fragmentos y `k=6` la búsqueda vectorial ya ve el 21% del corpus | `iteracion_1.7_nodos/resultado_1.7.md` |
| **Que el top-6 se volviera más diverso y confundiera al juez** | 1.8: la diversidad *bajó* de 4,96 a 4,50 documentos distintos por consulta. Y el contexto no creció: 2028 → 2074 tokens | `iteracion_1.8_palabras_clave/resultado_1.8.md` |
| **Sustituir el `SI`/`NO` del juez por una cita verificable** | Fase 0 de la 1.9: el juez con cita **nunca dice NO**, 10 fugas de 10 en preguntas sin respaldo. Y 6 de esas 10 citas son válidas pero irrelevantes, así que verificar que la cita exista no protege. Llevaría la especificidad de 50/50 a 0/50 | `iteracion_1.9_juez_con_cita/resultado_fase0.md` |
| **Poner un ejemplo concreto en el prompt del juez** | El modelo de 3B lo copia como respuesta en vez de leer el contexto: 3 de 10 citas eran literalmente el ejemplo del prompt. Quitarlo sube las citas válidas de 60% a 100% | `iteracion_1.9_juez_con_cita/resultado_fase0.md` |
| **Des-aplanar los saltos de línea del contexto del juez** | Fase 1 de la 1.10: `doc.replace('\n',' ')[:1400]` a `doc[:1400]` recupera **1 de 8** del núcleo duro y **0 de 8** end-to-end. Determinista (0 vuelcos en dos corridas idénticas), así que el 1 es real y es uno solo. Lo decisivo: **PREG-088 sigue en `NO` con la tabla perfectamente formateada**, y era el caso que motivó el cambio. El contexto no crece —28415 caracteres en ambas versiones— así que tampoco hay nada que ganar optimizándolo | `iteracion_1.10_relaciones_explicitas/resultado_fase1.md` |
| **Anteponer el título del documento a cada fragmento** | Empeora: recall 48 → 46, anclaje 26 → 25. Repetir texto que el documento ya implica acerca sus fragmentos entre sí y diluye lo propio de cada uno | `iteracion_1.7_nodos/resultado_1.7.md` |
| **Quitar la cabecera del grafo del texto que lee el juez** | Recupera 1 de 4. La idea de separar texto indexado de texto mostrado sigue valiendo como principio, pero no explicaba la regresión de la 1.7 | `iteracion_1.7_nodos/resultado_1.7.md` |
| **Cambiar de motor de base vectorial** (Qdrant/FAISS/pgvector) | Con 48 fragmentos el motor no es el cuello de botella: cualquier implementación devuelve los mismos vecinos con el mismo embedding | ver OP-7, nota final |

### Advertencias de método

- **`retrieval_hit@k` se mide a nivel de archivo y es optimista.** Cuenta acierto
  si alguno de los 6 fragmentos viene de un archivo que contiene la respuesta,
  aunque ese fragmento concreto no traiga el dato. El 88% nominal esconde un
  recall a nivel de *chunk* bastante peor. Las coberturas de las iteraciones 1.0
  y 1.3 (57%, 69%, 68%) están infladas por la misma razón: en modo de un paso el
  modelo completaba con memoria paramétrica lo que el chunk no traía.
- **Verificar la presencia de un dato buscando cifras sueltas produce falsos
  positivos.** Un `27%` puede aparecer en el contexto por otra razón. Exigir que
  la línea completa de la cita aparezca íntegra cambió el diagnóstico de la 1.6
  de 9 falsos negativos del juez a 5.
- **Un experimento, una variable.** El prompt v2 cambió dos cosas a la vez y
  costó una corrida entera poder atribuir el efecto. La 1.1 repitió el error con
  cinco variables juntas; la ablación (`scripts/ablacion_chunking.py`, ~10 s por
  variante) las separó y mostró que cuatro de las cinco estorbaban.
- **`anclaje@k` tiene techo 37, no 50.** 13 de las 50 citas del banco están
  parafraseadas y no existen literales en ningún `.md`, así que ninguna técnica
  de chunking puede darles positivo. Comparar contra 50 subestima el retrieval en
  26 puntos. El normalizador debe ignorar tildes **y marcadores de lista**: sin
  lo segundo el techo daba 36 y PREG-064 contaba como no verificable pese a estar
  textual en el corpus.
- **`anclaje@k` se mide sobre texto estructurado y el juez lee texto plano, y
  eso ya está medido: no importa.** `_build_judge_prompt` hace
  `doc.replace('\n', ' ')[:1400]`, así que las tablas llegan al modelo como una
  fila de pipes. La Fase 1 de la 1.10 quitó el aplanado y recuperó **1 de 8** del
  núcleo duro, 0 end-to-end. **El dato no se pierde y el contexto tampoco crece:**
  28415 caracteres en ambas versiones —`replace` cambia un carácter por otro— y
  ningún chunk supera los 1400 (máx. 1378, mediana 1066). Cuidado al verificarlo
  a mano: el normalizador de `medir_retrieval.py` quita las viñetas solo al
  **inicio de línea**, y sobre texto aplanado quedan en medio, lo que produce
  falsas "pérdidas" de cita.

- **El tope del chunking está acoplado al truncado de `api.py`** (1400
  caracteres por fragmento). Subir uno sin el otro anula la mejora: el recorte
  vuelve a partir el dato justo antes de que el modelo lo lea.

---

## Detalle por línea

### OP-1 — Chunking ✅ **CONFIRMADA PARCIALMENTE**

Rama: `iteracion_1.1_chunking` · Plan y resultado en esa carpeta

**La causa era el tamaño del fragmento, no la estructura.** Con un tope de 800
caracteres la mayoría de las secciones del corpus no cabía entera y el dato
pedido quedaba partido entre dos fragmentos.

El cambio adoptado son dos constantes en `ingest.py`: `CHUNK_SIZE` 800 → 1400 y
`CHUNK_OVERLAP` 150 → 200.

```
                 antes    después
recall@6         44/50     46/50
anclaje@6        23/37     25/37
abstención ind.  25/50     21/50
alucinación       0/50      0/50
```

Primera iteración del proyecto que cumple su criterio de éxito. Recuperó **3 de
los 11** fallos a nivel de chunk, que es exactamente donde se esperaba que
actuara, sin mover las otras categorías de fallo.

Dos hipótesis previas quedaron **refutadas** en el camino (ver la tabla de
callejones sin salida): el chunking estructural por sección, y la eliminación
del solape.

**Lo que queda, ambos de una constante y sin medir end-to-end:**

- `k=8` sube el anclaje de 25/37 a 31/37.
- `CHUNK_OVERLAP` 200 → **150** sube a 27/37 con `k=6` y a 32/37 con `k=8`. Se
  adoptó 200 con un normalizador que invertía el orden de las dos opciones.

Los dos encarecen o mantienen el costo del juez, que ya está en 12,3 s por
pregunta. Medir antes de adoptar.

### OP-6 — Discriminación en dos pasos ✅ **CONFIRMADA**

Rama: `iteracion_1.6_dos_pasos` · Resultado: `iteracion_1.6_dos_pasos/resultado_1.6.md`

Separar en dos llamadas lo que el modelo no logra en una: primero un juez binario
decide si el contexto contiene la respuesta, y solo si dice `SI` se invoca al
redactor.

**Resultado: alucinación de 34% a 0%**, con especificidad perfecta (50/50) y
*más rápido* que el baseline de un paso (19,6 min contra 17,5), porque 74 de 100
preguntas se resuelven por el camino `NO` sin segunda llamada.

El riesgo que anticipaba el plan — que el juez heredara el mismo problema un
nivel arriba — no se materializó. La hipótesis de que duplicaría la latencia
tampoco: el juez cuesta ~6,4 s, de los cuales el 98% es leer el contexto, pero
evitar la segunda llamada compensa de sobra.

Queda implementado **solo en el arnés de evaluación**. `api.py` conserva el
endpoint `/chat` de un paso: llevarlo a producción es trabajo pendiente.

### OP-3 — Modelo de generación ❌ **REFUTADA**

Rama: `iteracion_1.3_modelo` · Resultado: `iteracion_1.3_modelo/resultado_1.3.md`

La hipótesis era que `llama3.2` (3B) no discrimina si el contexto responde la
pregunta por techo de capacidad, y que un modelo de 7-8B lo resolvería.

Escalar mejora la **extracción** cuando el modelo sí tiene la información
(cobertura 57% a 69%) y reduce la abstención indebida (12 a 5), pero **no
resuelve la alucinación**: 32% con `llama3.1:8b`, 42% con `qwen2.5:7b`. Ninguno
cumplió el criterio de éxito.

Lo que sí dejó esta iteración: la evidencia de que el problema es arquitectónico
y no de capacidad, que es justamente lo que la 1.6 confirmó.

### OP-5 — Métrica de similitud del índice ⏳ **PENDIENTE**

Rama: `iteracion_1.5_similitud` · Plan: pendiente

La colección se crea sin especificar `hnsw:space`, así que ChromaDB usa **L2** por
defecto. `sentence-transformers.encode()` **no normaliza** salvo que se le pase
`normalize_embeddings=True`, y sin normalizar L2 y coseno **no producen el mismo
ranking**: L2 penaliza diferencias de magnitud que en un embedding semántico no
representan diferencia de significado.

Mejor relación costo/beneficio del conjunto: el cambio es de una línea y
`medir_retrieval.py` lo evalúa en segundos.

**Métrica objetivo:** recall@6 ≥ 90% (actual 88%).
**Riesgo:** ninguno relevante. Si no mejora, se revierte y al menos queda
documentado qué métrica usa el índice — deuda que la auditoría dejó abierta.

### OP-4 — Deduplicación del corpus ⏳ **PENDIENTE**

Rama: `iteracion_1.4_corpus` · Plan: `iteracion_1.4_corpus/plan_1.4.md`

Dos documentos "paraguas" duplican contenido de otros cuatro y se llevan la mitad
del retrieval. Explica mejor el problema histórico de
"`tipos_sociedad_chile.md` no aparece en top-3" que la hipótesis de embeddings.

Se solapa con OP-1: conviene medir el chunking estructural primero y re-evaluar
cuánto queda de este efecto después.

### Reescritura estructurada del corpus ◐ **CONFIRMADA A MEDIAS**

Rama: `corpus_esquema_piloto` · Resultado: `corpus_esquema_piloto/resultado_piloto.md`

Idea de Yami: estandarizar los `.md` con un esquema fijo (institución,
requisitos previos, de qué trata, siguiente paso) y declarar en el documento su
pertenencia a un nodo del grafo.

Piloto sobre **2 de los 13 documentos**, en un corpus paralelo:

```
                  k=6 rec/anc    k=8 rec/anc
corpus vigente      46 / 25        48 / 31
corpus piloto       47 / 26        48 / 33
```

- ✅ **Mejora el retrieval, de forma atribuible.** PREG-063 y PREG-064 pasan de
  estar fuera del top-6 a las posiciones 4 y 1, con el dato llegando íntegro, y
  ninguna otra pregunta se mueve. PREG-064 era uno de los cuatro fallos que la
  1.1 dio por irrecuperables con chunking o con `k`.
- ❌ **No mueve al juez.** Ninguna de las cuatro preguntas objetivo cambia de
  veredicto, ni siquiera las dos donde el dato pasó a llegar.

**Lo que de verdad movió la aguja no fue la estructura sino el vocabulario.** Con
el tope de 1400 las secciones se vuelven a juntar en el mismo fragmento, así que
dividir en más partes no cambió nada; el efecto vino de los encabezados y frases
puente que usan los términos de las preguntas (*"SpA — Sociedad por Acciones, la
opción de startups"*).

**Restricciones para extenderlo a los 13 documentos:**

1. **Los nombres de archivo no se pueden cambiar.** El ground truth referencia
   los documentos por basename y `recall@k` compara basenames. Partir un archivo
   en varios invalidaría la medición de las preguntas que lo citan. La
   reestructuración debe ser interna al archivo.
2. **Las líneas con datos se conservan palabra por palabra.** 37 de las 50 citas
   de anclaje son texto literal del corpus; reescribirlas deja el banco sin
   instrumento de medición.
3. **Hay citas que exigen adyacencia** entre dos líneas, en un orden concreto
   (PREG-064).

Dos adaptaciones al esquema original, ya validadas en el piloto: **dos tipos de
documento** (`trámite` y `referencia`), porque solo 3 de las 50 preguntas son de
procedimiento; y la tercera parte partida en **"Qué es"** y **"Datos"**, porque
40 de las 50 citas son cifras, plazos y formularios.

### OP-7 — RAG basado en nodos ◐ **PARCIAL**

Rama: `iteracion_1.7_nodos` · Resultado: `iteracion_1.7_nodos/resultado_1.7.md`

**Declarar las aristas sirve. Recorrerlas no.**

```
                  recall   anclaje   frag/pregunta
base                46       25        6.0
cabecera            48       26        6.0     <- adoptado
sumar (mejor)       48       27        8.7     <- +45% contexto por +1 pregunta
desplazar (mejor)   46       23        6.0     <- siempre peor
```

Escribir `Requiere antes` / `Habilita después` en la cabecera recupera **2
preguntas sin costo de contexto**, incluida PREG-075, que la 1.1 dio por
irrecuperable. El mecanismo no es el grafo: los nombres de los nodos vecinos
funcionan como **palabras clave** que enriquecen el vector del documento. Es el
mismo efecto que el piloto del corpus, y lo que motivó la iteración 1.8.

La expansión por vecinos **no se implementa**. Explicación probable: el corpus
tiene 28 fragmentos y `k=6` ya recupera el 21% del total. Debería pagar en un
corpus grande; en este no hay margen.

`ingest.py` conserva el parseo de la cabecera, la propagación a la metadata del
fragmento y `validar_grafo()`, que rompe la ingesta si una arista apunta a un
nodo inexistente. La infraestructura queda lista si el corpus crece.

**La 1.7 no cumplió su criterio de éxito end-to-end** (abstención 21 → 24), pero
esa diferencia está dentro de la banda de ±6 del juez. No es evidencia de que el
cambio empeore nada, ni de que mejore.

### OP-2 — Sanitización de fragments 🟢 **PRIORIDAD BAJA**

Rama: `iteracion_1.2_sanitizacion` · Plan: `iteracion_1.2_sanitizacion/plan_1.2.md`

Mitiga prompt injection desde los documentos. No se observaron casos porque el
corpus es de elaboración propia. Medida preventiva, valiosa si en el futuro se
ingestan documentos de terceros, pero no mueve ninguna métrica actual.

---

## Criterio transversal de fusión

Toda rama hija debe:

1. Medir con `scripts/evaluar_banco.py` contra el mismo banco de 100 preguntas.
2. Comparar contra el baseline v1 (`tests/iteraciones/resultados_v1.json`).
3. Documentar el resultado **aunque sea negativo** — ver `experimento_prompt_v2.md`
   como referencia de experimento fallido bien registrado.
4. No fusionar si los fallos de generación totales suben respecto al baseline.
5. Actualizar este archivo y `Bitacora.md` antes de cerrar la rama.
