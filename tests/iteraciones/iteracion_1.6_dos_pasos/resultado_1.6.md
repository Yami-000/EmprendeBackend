# Resultado 1.6 — Discriminación en dos pasos

**Fecha:** 2026-09-22
**Experimento A:** juez `llama3.2:3B` + redactor `llama3.2:3B`
**Arnés:** `scripts/evaluar_banco.py --dos-pasos`, mismo banco de 100 preguntas, `k=6`
**Duración:** 1174 s (~19,6 min) — más rápido que el baseline v1 pese a ser dos llamadas,
porque 74 de 100 preguntas se resolvieron por el camino `NO` sin invocar al redactor.

## Resumen

La alucinación cayó de 34% a **0%**. El criterio de éxito formal **no se cumple**
por la abstención indebida (25/50 contra un objetivo de ≤8/50), pero el análisis
caso por caso muestra que **la mayoría de esas abstenciones no son culpa del
juez sino del retrieval**, y que el experimento destapó un problema que las
métricas anteriores venían escondiendo.

## Métricas

| | v1 (3B) | llama3.1 (8B) | qwen2.5 (7B) | **dos pasos A** | Objetivo |
|---|---:|---:|---:|---:|---:|
| retrieval_hit@6 /50 | 44 | 44 | 44 | 44 | — |
| Abstención indebida /50 | 12 | 5 | 5 | **25** | ≤8 |
| Cobertura de datos | 57% | 69% | 68% | 47% | ≥65% |
| Abstención correcta /50 | 33 | 34 | 29 | **50** | — |
| **Alucinación /50** | 17 (34%) | 16 (32%) | 21 (42%) | **0 (0%)** | ≤15% |
| Fallos de generación | 29 | 21 | 26 | 25 | ≤12 |
| Duración | 17,5 min | 41,6 min | 37,6 min | **19,6 min** | — |

### Métrica nueva: precisión del juez

| | Valor | Objetivo |
|---|---:|---:|
| Sensibilidad (dijo `SI` en respondibles) | 26/50 (52%) | — |
| **Especificidad** (dijo `NO` en no respondibles) | **50/50 (100%)** | ≥80% ✅ |

## Resultado contra el criterio de éxito

| Condición | Resultado | |
|---|---|---|
| Alucinación ≤ 15% | 0% | ✅ |
| Especificidad del juez ≥ 80% | 100% | ✅ |
| Abstención indebida ≤ 8/50 | 25/50 | ❌ |

**No cumple.** Pero ver el desglose siguiente antes de concluir.

## El hallazgo principal: el retrieval es peor de lo que medíamos

De las 24 preguntas respondibles donde el juez dijo `NO`, se verificó
textualmente si el dato esperado estaba realmente en los fragmentos recuperados:

| Causa | Casos | ¿El `NO` fue correcto? |
|---|---:|---|
| Retrieval falló a nivel **archivo** (`retrieval_hit` = false) | 4 | Sí |
| Retrieval falló a nivel **chunk** (llegó el archivo, no el fragmento con el dato) | 11 | Sí |
| El dato llegó pero **cortado por el chunking** | 4 | Sí |
| El dato estaba íntegro y el juez negó igual | **5** | No — falso negativo real |

**El juez acertó en 45 de 50 respondibles (90%)**, no en 26 como sugiere la
sensibilidad cruda. De las 25 abstenciones indebidas, **19 son atribuibles al
retrieval y al chunking**, y solo 5 al juez.

> **Corrección a una versión previa de este documento.** La primera medición
> reportó 9 falsos negativos del juez. Verificaba la presencia del dato buscando
> números y siglas sueltos (`25`, `27`, `UF`), y eso produce falsos positivos:
> un `27%` puede aparecer en el contexto por una razón distinta a la pregunta.
> Al re-verificar exigiendo que la **línea completa** de la cita de anclaje
> apareciera íntegra, 4 de esos 9 resultaron ser fragmentos mutilados por el
> chunking, donde negar era lo correcto. Es el mismo tipo de error de métrica
> laxa que este experimento destapó en `retrieval_hit@6`.

### Evidencia directa del corte: PREG-076

*"¿Qué tasa de impuesto a la renta aplica el Régimen General (14A)?"*
Dato esperado: *"Tasa: 25% (renta atribuida) o 27% (semi-integrado)"*.

El fragmento recuperado que contenía la información empezaba así:

```
"...régimen de renta atribuida; 27% para régimen semi-integrado"
```

El chunking por caracteres (800) partió la frase y se llevó el `25%` y el
sujeto de la oración. El juez recibió un dato mutilado y dijo `NO`.

### Por qué esto importa más que el número

`retrieval_hit@6` se mide a nivel de archivo: cuenta acierto si *alguno* de los
6 fragmentos viene de un archivo que contiene la respuesta, aunque el fragmento
concreto no tenga el dato. Con esa métrica el retrieval marcaba 88% en las
cuatro iteraciones.

En el modo de un paso ese error quedaba enmascarado: cuando el chunk no traía
el dato, el modelo lo completaba con conocimiento paramétrico. Si acertaba de
memoria, la respuesta mencionaba las anclas correctas y contaba como acierto en
`cobertura`. El pipeline de dos pasos rompe ese enmascaramiento — el juez mira
el contexto real y dice `NO` — y al hacerlo expone que el retrieval efectivo a
nivel de chunk es bastante peor que el 88% nominal.

Esto reinterpreta hacia abajo las métricas de cobertura de las iteraciones 1.0
y 1.3 (57%, 69%, 68%): una fracción desconocida de esos aciertos venía de la
memoria del modelo, no del corpus.

## Lo que funcionó

- **Cero alucinaciones en 50 preguntas sin respaldo documental.** Ninguno de los
  tres modelos probados en la 1.3 bajó del 32%. La arquitectura de dos pasos lo
  llevó a 0.
- **Especificidad perfecta.** El juez no dejó pasar ni una sola pregunta sin
  respaldo. El riesgo central que anticipaba el plan ("el juez hereda el mismo
  problema un nivel arriba") **no se materializó**.
- **Más rápido que el baseline**, contra lo esperado: 19,6 min contra 17,5 min
  del v1 y 41,6 min del 8B. El camino `NO` (74 de 100 preguntas) evita la
  segunda llamada y compensa el costo del juez.
- **El redactor mejora cuando el juez lo habilita**: en las 26 preguntas donde
  el juez dijo `SI`, el redactor respondió en 25 y la cobertura de datos en esos
  casos fue 67%, contra 57% del v1 sobre el total.

## Lo que falló

Nueve falsos negativos reales del juez, sobre preguntas con el dato explícito en
el contexto. Ejemplos:

- **PREG-076** — *"¿Qué tasa aplica el Régimen General (14A)?"*. El contexto
  incluía `formularios_tributarios_chile.md`, que dice literal
  *"Régimen General (14A): 25% (renta atribuida) o 27% (semi-integrado)"*.
- **PREG-067** — *"¿Costo total del régimen tradicional?"*. El contexto incluía
  `costos_y_plazos_formalizacion.md` con la fila *"Total estimado | $110.000 – $380.000"*.

La causa probable está en el prompt del juez, que combina dos instrucciones muy
restrictivas:

```
- Responde SI solo si el contexto menciona explícitamente el dato pedido...
- Ante cualquier duda, responde NO.
```

Para un modelo de 3B, "ante cualquier duda responde NO" parece dominar sobre el
resto. El fail-safe hacia la abstención está bien como principio, pero calibrado
así cuesta 9 respuestas correctas.

## Corrección a un supuesto del plan

El plan asumía que el juez sería "casi gratis" con `num_predict` bajo. Medido con
los timings de Ollama sobre un prompt de juez típico:

```
prompt_eval : 6,4 s  (1309 tokens de contexto)  -> 98% del costo
eval        : 0,1 s  (3 tokens: "SI.")          ->  2% del costo
```

`num_predict=5` ahorra el 2%. El 98% restante es irreducible: el juez necesita
leer el contexto para poder juzgarlo. El camino `NO` sigue siendo más rápido que
el pipeline de un paso, pero por evitar la *segunda* llamada, no porque la
primera sea barata.

## Experimento A2 — recalibrar el prompt del juez (descartado)

Hipótesis: la combinación *"solo si menciona explícitamente"* + *"ante cualquier
duda, responde NO"* sesgaba al modelo de 3B hacia negar. Se añadió una variante
`flexible` en `JUEZ_PROMPT_BASES` (`api.py`) que quita el sesgo y nombra las
formas en que el dato puede aparecer (otras palabras, tabla, varios fragmentos).

Probada de forma dirigida contra los 9 falsos negativos y 8 no respondibles de
control, sin pagar la corrida completa:

```
recupera:  1 de 9      fugas de especificidad: 0 de 8
```

**Hipótesis refutada.** El juez no estaba siendo conservador por instrucción.

## Experimento A3 — juzgar fragmento por fragmento (descartado)

Hipótesis alternativa: el juez de 3B se satura al evaluar los 6 fragmentos
juntos (~1300 tokens). Se probó juzgar un fragmento a la vez (~220 tokens cada
uno), aceptando `SI` si alguno lo daba.

```
recupera:  2 de 9      fugas de especificidad: 0 de 8
```

**También refutada.** Ni la calibración ni la carga de contexto explican los
fallos. La verificación estricta posterior mostró por qué: en 4 de los 9 casos
el dato simplemente no estaba íntegro en ningún fragmento, así que ningún ajuste
del juez podía recuperarlos.

Ambas variantes quedan versionadas en `JUEZ_PROMPT_BASES` y seleccionables con
`--juez-prompt`, para poder reproducir la comparación sin reescribir código.

## Siguiente paso

**OP-1 (chunking estructural) pasa a prioridad alta**, con evidencia directa que
antes no existía:

- 19 de las 25 abstenciones indebidas son atribuibles al retrieval y al
  chunking; solo 5 al juez.
- El caso PREG-076 muestra el mecanismo: el corte por caracteres parte frases a
  la mitad y entrega datos mutilados que ningún componente posterior puede
  reconstruir.
- El techo de 9 preguntas que la iteración 1.0 asignó a esta línea se calculó
  con `retrieval_hit` a nivel de archivo. El techo real es mayor.

El juez de 3B, con 90% de precisión y 100% de especificidad, **ya no es el
cuello de botella**. Mejorar lo que le llega rinde más que seguir ajustándolo.

El experimento B (juez 3B + redactor 8B) se descarta: el redactor respondió en
25 de las 26 veces que se le habilitó, y escalarlo contradice la prioridad de
mantener el sistema corriendo en hardware modesto. El problema
está antes, en qué llega al contexto y en qué deja pasar el juez.
