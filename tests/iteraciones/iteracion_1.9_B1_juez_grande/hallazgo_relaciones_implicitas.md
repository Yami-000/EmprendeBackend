# Hallazgo — El juez tiene que inferir relaciones que el corpus solo implica

**Fecha:** 2026-09-25 · **Rama:** `iteracion_1.9_B1_juez_grande`
**Origen:** análisis del núcleo duro de 8 preguntas que dejó la B1
**Datos:** `resultados_b1_sens.json`, `resultados_nucleo_flexible.json`

Este documento no es un experimento con criterio de éxito: es el diagnóstico que
salió de cruzar la B1 con dos pruebas dirigidas, y es lo que ordena la 1.10.

## El núcleo duro

8 preguntas con la cita de anclaje presente en el contexto, negadas por el juez:
PREG-010, 064, 065, 075, 080, 084, 088, 115.

## Las tres explicaciones candidatas, medidas

```
capacidad del modelo (llama3.2 3B -> qwen2.5:7b) ....  recupera 0 de 8
calibración del prompt (estricto -> flexible) .......  recupera 1 de 8
redacción de la pregunta ............................  refutada, ver abajo
```

**Capacidad: 0 de 8.** La B1. Un juez de 7B da el mismo 18/29 y comparte 8 de los
11 falsos `NO`.

**Prompt: 1 de 8.** El prompt `flexible` (A2) quita el sesgo *"ante cualquier duda
responde NO"* y dice explícitamente *"responde SI aunque el dato esté dentro de
una tabla"*. Recupera solo PREG-088. **Replica de forma independiente el "1 de 9"
que midió la 1.6**, ahora sobre el corpus de la 1.8. Y es inconsistente: recupera
PREG-088 (fila de tabla) pero **no** PREG-080, que es otra fila de la misma tabla
del mismo documento.

**Redacción de la pregunta: refutada por PREG-065.** La pregunta es *"¿Cuál es el
costo total de formalizar una empresa bajo el régimen simplificado (Tu Empresa en
un Día)?"*. Esto es lo que el juez recibe:

```
### Régimen Simplificado (Tu Empresa en un Día) - **Costo total: $0 (gratuito)** - Incluye...
```

La pregunta contiene **textualmente el encabezado del documento** y el dato viene
en la línea siguiente. No existe reescritura que la mejore. Un 3B y un 7B dicen
`NO` igual. **Ninguna técnica que opere sobre el texto de la pregunta puede
arreglar este caso.**

## El mecanismo: falta el verbo, no el sustantivo

Midiendo qué vocabulario de cada pregunta aparece textual en el contexto del juez:

```
PREG-064  60%   ausente: diferencia, existe
PREG-088  67%   ausente: responsable, elaboracion
PREG-115  67%   ausente: entrega, emite
PREG-010  75%   ausente: gestiona, otra
PREG-080  75%   ausente: inscribe
PREG-075  83%   ausente: mantener
PREG-084  83%   ausente: diferencia
PREG-065  89%   ausente: formalizar
```

**Todos los sustantivos de las 8 están en el contexto. Lo ausente es siempre el
verbo o la relación.** PREG-088 lo muestra entero. La pregunta es *"¿quién es
responsable de la elaboración de la escritura pública?"* y el contexto dice:

```
| Institución | Rol | |---|---| | SII (...) | RUT, Inicio de Actividades | |
Notaría | Escritura pública de constitución (régimen tradicional) | | ...
```

El corpus **nunca afirma que la Notaría elabore nada**. Codifica esa relación en
una columna llamada "Rol". El prompt pide decidir si el contexto *"menciona
explícitamente el dato pedido"* y prohíbe el *"tema relacionado o parecido"*.
Inferir `Rol: escritura pública ⇒ es responsable de elaborarla` es un paso que el
prompt le prohíbe dar. **El juez está siendo obediente, no incapaz.**

Eso explica por qué el tamaño del modelo no cambia nada: no es una tarea de
capacidad, es una instrucción que excluye la inferencia que hace falta.

## Dos correcciones a lo que se creyó durante el análisis

**1. El dato no se pierde por truncado ni por aplanado.** Se sospechó que
`snippet = doc.replace('\n', ' ')[:1400]` en `_build_judge_prompt` dejaba citas
fuera. Verificado: ningún chunk del índice supera los 1400 caracteres (máx. 1378,
mediana 1071), y con una normalización que ignora marcadores de lista y de tabla,
**las 8 citas están presentes en lo que el juez lee**. La primera comprobación dio
dos pérdidas (PREG-064, 065) por un artefacto: el normalizador de
`medir_retrieval.py` quita las viñetas solo al **inicio de línea**, y al aplanar
los `\n` esas viñetas quedan en medio del texto.

**2. El formato de la cita no explica los falsos `NO`.** La tasa de `NO` es plana
entre formatos —negrita 43%, tabla 33%, prosa 33%, encabezado 50%, viñeta 0%— con
1-7 casos por celda. Se propuso a partir de inspeccionar las 8 y se descartó al
contarlo.

## Lo que queda en pie y no está medido

**El aplanado sí destruye la estructura, aunque no borre el dato.** La tabla de
PREG-088 llega al juez como una fila de pipes sin saltos de línea. `anclaje@k` se
mide sobre texto **estructurado** y el juez lee texto **plano**: no es una
diferencia de contenido, pero sí de legibilidad, y nadie ha medido si importa. Es
un cambio de una línea.

**El corpus puede declarar las relaciones como predicados.** Convertir
`| Notaría | Escritura pública de constitución |` en *"La Notaría elabora la
escritura pública de constitución"* elimina la inferencia prohibida en vez de
pedirle al juez que la haga. Cuesta cero latencia y cae dentro de la ventana de
256 tokens del embedder. Es la línea de reescritura estructurada del corpus, que
estaba en ◐ media por otras razones.

## Reproducir

```bash
python scripts/evaluar_banco.py nucleo_flexible --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --juez-prompt flexible \
    --ids PREG-010,PREG-064,PREG-065,PREG-075,PREG-080,PREG-084,PREG-088,PREG-115
```

El juez respondió `SI`/`NO` limpio en las 8, así que ningún veredicto viene del
fail-safe de `parse_juicio`.

## Descartado con esto: reescritor de consultas antes del juez

Idea evaluada el 2026-09-25: un modelo "validador" que desglose la pregunta del
usuario y la reescriba mejor redactada y con más contexto, antes del pipeline.

No se implementa, por cuatro razones:

1. **No ataca el mecanismo.** El eslabón que falla está después de la pregunta. Un
   reescritor que no conoce el corpus no puede saber que allí "responsable de
   elaborar" se dice "Rol"; uno que sí lo conoce es el juez con dos llamadas más.
   Y PREG-065 ya está redactada de forma óptima.
2. **Riesgo sobre la especificidad, que es lo que no se negocia.** "Más contexto"
   significa que un LLM genera texto que no está en el corpus. En las 50 preguntas
   sin respaldo eso hace que el contexto parezca pertinente y empuja al juez a
   `SI`. Es el modo de fallo que mató la Fase 0 de la 1.9.
3. **Rompe el instrumento.** Cambia el retrieval y la entrada del juez a la vez —
   dos variables — y el subconjunto de 29 deja de ser comparable con su control.
4. **Latencia.** Una tercera llamada en las 100 consultas, sobre un end-to-end que
   ya está en ~28 s.

**Dónde sí sería viable:** como expansión de consulta **solo para el retrieval**,
evaluada con `medir_retrieval.py` en segundos y sin invocar al juez, de modo que no
puede tocar la especificidad. La objeción honesta es el techo: el recall ya está en
96% y el anclaje en 78%.
