# Resultado Fase 1 — No aplanar los saltos de línea: **negativo**

**Fecha:** 2026-09-25 · **Rama:** `iteracion_1.10_relaciones_explicitas`
**Plan:** [`plan_1.10.md`](plan_1.10.md) · **Diagnóstico de origen:**
[`hallazgo_relaciones_implicitas.md`](../iteracion_1.9_B1_juez_grande/hallazgo_relaciones_implicitas.md)

## Veredicto

**No pasa la puerta 1.** El corte era recuperar ≥ 3 de las 8 del núcleo duro. Se
recuperó **1 de 8** en el juez y **0 de 8** end-to-end. No se corrieron las
puertas 2 (las 29) ni 3 (las 50 sin respaldo): el plan las condiciona a esta.

**El cambio no entra al pipeline.** Se revierte en esta misma rama, en el commit
siguiente al que lo mide. La especificidad nunca se midió, así que la restricción
que no se negocia —nada entra si baja de 48/50— no está satisfecha ni podría
estarlo con una ganancia de 1 pregunta.

## La variable

Una línea en `_build_judge_prompt` de `ai-service/api.py`:

```python
snippet = doc.replace('
', ' ')[:1400]   # antes
snippet = doc[:1400]                       # después
```

**Solo el juez.** `_build_system_prompt` (línea 96) y los dos fallbacks de error
de Ollama (líneas 223 y 244) tienen la misma línea y **no** se tocaron: son el
redactor y un camino de error, y serían variables adicionales.

`evaluar_banco.py` importa `_build_judge_prompt` desde `api.py`, así que el arnés
mide la versión modificada y no una copia.

## Índice verificado antes de medir

```
indice ......... 28 chunks
recall@6 ....... 48/50  (96%)
anclaje@6 ...... 29/37  (78%)
```

Idéntico a los controles, así que los números de abajo son comparables. No hubo
que reconstruir el índice.

## Resultado sobre el núcleo duro

Las 8: PREG-010, 064, 065, 075, 080, 084, 088, 115.

| Corrida | Juez dice `SI` | Cuál | Abstenciones | Latencia juez |
|---|---|---|---|---|
| **control** (1.8, `estricto`, aplanado) | **0 de 8** | — | 8 de 8 | 13,1 s |
| B1 (`qwen2.5:7b`, aplanado) | 0 de 8 | — | 8 de 8 | 28,5 s |
| A2 (`flexible`, aplanado) | 1 de 8 | PREG-088 | 7 de 8 | 14,1 s |
| **Fase 1** (`estricto`, **sin aplanar**) | **1 de 8** | **PREG-065** | **8 de 8** | 13,6 s |

`resultados_f1_nucleo.json`, `resultados_f1_nucleo_rep.json`.

## Tres cosas que sí quedaron medidas

**1. El veredicto del juez es determinista, y el 1 de 8 es real.** Se repitió la
corrida idéntica: **0 vuelcos de 8**, mismo `SI` en PREG-065. La ganancia no es
ruido de corrida — es reproducible y es de una sola pregunta. Esto acota la
inestabilidad conocida del juez: ante el *mismo* contexto no se mueve; lo que se
mueve es *cuál* pregunta recupera cada intervención.

**2. Cada intervención recupera una pregunta distinta, y arbitraria.** `flexible`
recupera PREG-088 y no PREG-080, otra fila de la misma tabla. La Fase 1 recupera
PREG-065 y **no** PREG-088, que es justamente el caso de tabla que el diagnóstico
usó para motivar este cambio. Si des-aplanar las tablas fuera el mecanismo,
PREG-088 tendría que haber caído primero. **No cayó.** Eso es evidencia en contra
de la legibilidad de la tabla como causa, no solo una ganancia insuficiente.

**3. El `SI` del juez no llega al usuario.** En PREG-065 el juez dijo `SI`, el
redactor corrió (18,3 s) y **aun así** emitió la frase de abstención. Por eso el
end-to-end es 0 de 8 y no 1 de 8. El redactor sigue leyendo contexto aplanado —
línea 96, intacta por diseño— y tiene su propia abstención. **Es un eslabón
distinto del que esta fase midió, y está sin medir.**

**4. La causalidad está confirmada por el revert.** Tras revertir la línea, se
volvieron a correr PREG-065 y PREG-088: **0 de 2**, PREG-065 de vuelta en `NO`,
latencia del juez 13,1 s — el control exacto. El `SI` de PREG-065 lo produjo el
cambio y nada más.

## El riesgo de crecimiento del contexto queda refutado

El plan advertía que al volver los `
` el contexto crecería y encarecería al
juez, que gasta el 98% de su costo leyendo contexto. Medido sobre los 28 chunks:

```
caracteres, aplanado ......... 28415
caracteres, estructurado ..... 28415   <- idéntico
```

Es exacto, no aproximado: `replace('
', ' ')` sustituye un carácter por otro, no
agrega ni quita. El truncado a 1400 recorta lo mismo en ambos casos (máximo real
1378, mediana 1066), así que **ninguna cita se pierde en ninguna de las dos
versiones**. El costo real es de tokenización: vuelven 660 saltos de línea, 23,6
por chunk, unos **+141 tokens** en un prompt de 6 fragmentos.

La latencia no permite concluir nada: 13,6 s en frío contra 5,0 s en la réplica en
caliente, sobre un control de 13,1 s. El calentamiento del modelo domina la
diferencia.

## Por qué falla, y qué dice del diagnóstico

El diagnóstico de la 1.9 sostenía que al juez le falta **el verbo**: el corpus
codifica `| Notaría | Escritura pública |` bajo una columna "Rol" y la pregunta
pide quién la *elabora*. Des-aplanar devuelve la **estructura** de la tabla, pero
no agrega el verbo: la celda sigue sin decir "elabora". Que PREG-088 siga en `NO`
con la tabla perfectamente formateada es la confirmación más limpia de que **el
problema no es la legibilidad del formato sino la ausencia de la relación**.

Eso **refuerza** la Fase 2, que es la que ataca el verbo directamente: agregar
*"La Notaría elabora la escritura pública de constitución"* antes de la tabla, sin
borrar la fila.

## Reproducir

```bash
python scripts/medir_retrieval.py    # 28 chunks, 48/50, 29/37
python scripts/evaluar_banco.py f1_nucleo --dos-pasos --juez llama3.2     --redactor llama3.2     --ids PREG-010,PREG-064,PREG-065,PREG-075,PREG-080,PREG-084,PREG-088,PREG-115
```

Los 8 veredictos fueron `SI`/`NO` limpios, así que ninguno viene del fail-safe de
`parse_juicio`.

## Qué sigue

**Fase 2 del plan 1.10**, sin cambios de diseño: declarar las relaciones como
predicados en los documentos del núcleo duro, conservando las filas de tabla
palabra por palabra. Corte: ≥ 4 de 8, sin que `recall@6` baje de 48/50 ni
`anclaje@6` de 29/37.

**Candidato nuevo que dejó esta fase, para después y como variable separada:** la
abstención del redactor pese al `SI` del juez (punto 3). No entra en la 1.10 para
no mezclar variables.
