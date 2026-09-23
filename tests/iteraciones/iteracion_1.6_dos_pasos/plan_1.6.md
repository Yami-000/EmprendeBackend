# Plan 1.6 — Discriminación en dos pasos

**Prioridad:** 🟡 Media, mueve a Alta tras la iteración 1.3 · **Origen:** OP-6
**Depende de:** iteración 1.0 (baseline) e iteración 1.3 (modelo de generación) —
ver nota de dependencia al final.

## Objetivo

Reducir la alucinación separando en dos llamadas lo que hoy se le pide al
modelo en una sola: decidir si el contexto recuperado responde la pregunta
**y** redactar la respuesta.

## Hipótesis

El fallo no está en la redacción, está en la discriminación previa. La
iteración 1.3 midió tres modelos (3B, 7B, 8B) con el mismo arnés y el mismo
banco de 100 preguntas, y el patrón se repitió en los tres tamaños:

| | v1 (3B) | llama3.1 (8B) | qwen2.5 (7B) |
|---|---:|---:|---:|
| Alucinación | 34% | 32% | 42% |
| Fallos de generación | 29 | 21 | 26 |

Escalar el modelo mejoró la extracción cuando el modelo *sí* tenía el dato
(abstención indebida 12→5, cobertura +11-12 pts) pero no movió la alucinación
de forma consistente — en el peor caso (qwen 7B) la empeoró. Y no es el mismo
conjunto de preguntas el que falla: con cada modelo aparecen alucinaciones
nuevas que v1 no tenía (5 con el 8B, 11 con qwen).

Dos ejemplos concretos de la 1.3 ilustran el mecanismo:

- **qwen2.5 (7B), "¿Diferencia entre Liquidación y Giro?"** — responde que la
  liquidación *"la realiza la empresa"* (es al revés, la emite el SII) e
  inventa que un giro es *"un cambio temporal en la tasa impositiva"* (no
  existe ese concepto). Estructura y tono de respuesta técnica correcta,
  contenido falso en las dos mitades.
- **llama3.1 (8B), "¿Qué tribunal es competente...?"** — inventa una
  institución que no existe: *"Tribunal de Controversias Tributarias (TCT)"*.

En ningún caso el modelo "no supo redactar". En los dos casos decidió mal si
tenía la información, y hacia allá se dirige el remedio.

**Por qué separar el juicio ayuda:** juzgar "¿este contexto contiene la
respuesta a esta pregunta?" con salida binaria es una tarea mucho más simple
que juzgar y redactar a la vez. Un modelo de 3B, que falla en la tarea
combinada, puede ser suficientemente confiable en la tarea aislada.

## Diseño

Pipeline de dos llamadas:

1. **Juez** — recibe la pregunta y el contexto recuperado (los mismos 6
   fragmentos de siempre). Responde exclusivamente `SI` o `NO`, sin
   elaboración. `num_predict` bajo (≤5 tokens) para forzar la brevedad y
   reducir el costo de esta llamada casi a cero.
2. **Redactor** — solo se invoca si el juez dijo `SI`. Usa el
   `_build_system_prompt` actual de `api.py`, sin cambios.
   Si el juez dijo `NO`, se devuelve directo la frase canónica de abstención
   **sin** segunda llamada al modelo — más rápido que el pipeline actual en
   ese camino, no solo más seguro.

### Matriz de combinaciones a probar

| Experimento | Juez | Redactor | Por qué |
|---|---|---|---|
| A (principal) | `llama3.2:3B` | `llama3.2:3B` | Aísla el efecto de la arquitectura, sin cambiar tamaño de modelo — comparación limpia contra v1 |
| B (si A funciona) | `llama3.2:3B` | `llama3.1:8B` | Combina un juicio barato y rápido con la mejor capacidad de extracción medida en 1.3 |

Empezar por A. B solo si A reduce la alucinación de forma clara — si A no
funciona, el problema no es la arquitectura de dos pasos y B no lo va a
arreglar.

## Métrica nueva: precisión del juez

Además de las métricas de siempre (alucinación, fallos de generación,
abstención indebida, cobertura), esta iteración mide algo que las anteriores
no separaban:

| | Definición |
|---|---|
| Sensibilidad del juez | De las 50 respondibles, ¿en cuántas dijo `SI`? |
| Especificidad del juez | De las 50 no respondibles, ¿en cuántas dijo `NO`? |

Esto expone directamente si el juez resuelve la discriminación mejor que el
modelo combinado, independiente de cómo redacte después.

## Pasos

1. Extender `scripts/evaluar_banco.py` con un modo de dos llamadas: función
   `juzgar(pregunta, fragmentos)` que llama a Ollama con `num_predict` bajo y
   parsea `SI`/`NO`; si `SI`, procede con la llamada de redacción existente;
   si `NO`, no llama al modelo de nuevo.
2. Correr experimento A: `python scripts/evaluar_banco.py dospasos_A --juez llama3.2 --redactor llama3.2`
   (la interfaz exacta de argumentos se define al implementar).
3. Medir sensibilidad/especificidad del juez por separado, antes de mirar el
   resultado end-to-end.
4. Si el juez es confiable (especificidad alta) pero la alucinación
   end-to-end no baja tanto como se esperaba, revisar si el redactor sigue
   fallando en casos donde el juez erró por poco (falsos positivos del juez).
5. Comparar contra `resultados_v1.json` y, si aplica, contra `resultados_llama8b.json` / `resultados_qwen7b.json`.
6. Si el experimento A cumple el objetivo, portar la lógica de dos pasos a
   `ai-service/api.py` (el endpoint de producción), no solo al arnés de
   evaluación.

## Métricas objetivo

| Métrica | Baseline v1 | Objetivo |
|---|---:|---:|
| Alucinación | 34% | **≤ 15%** |
| Especificidad del juez | — (no medida antes) | **≥ 80%** |
| Abstención indebida | 12/50 | **≤ 8/50** |
| Fallos de generación totales | 29 | **≤ 12** |

El objetivo de abstención indebida es más exigente que el de la iteración 1.3
(≤12) porque un juez confiable no debería sacrificar respondibles para
reducir alucinación — si lo hace, está siendo conservador en vez de preciso,
y eso hay que verlo en la métrica de sensibilidad, no ocultarlo detrás de un
buen número de alucinación.

## Criterio de éxito

Alucinación ≤ 15% **y** especificidad del juez ≥ 80% **y** abstención
indebida ≤ 8/50, con latencia total (dos llamadas cuando el juez dice `SI`,
una cuando dice `NO`) que siga siendo aceptable para un bot de Telegram.

## Riesgos

- **El juez hereda el mismo problema, un nivel arriba.** Si el juez también
  falla en discriminar (dice `SI` a contexto irrelevante), el pipeline de dos
  pasos no gana nada sobre el actual. Es el riesgo central de esta hipótesis
  y la razón de medir sensibilidad/especificidad por separado en vez de
  confiar solo en el número end-to-end.
- **Latencia variable.** El camino `NO` es más rápido que hoy (sin segunda
  llamada); el camino `SI` es más lento (dos llamadas en serie). El promedio
  depende de la proporción real de preguntas respondibles que reciba el bot
  en producción, no solo del banco de prueba (que es 50/50 por diseño).
- **Parseo de la salida del juez.** Forzar `SI`/`NO` estricto con un LLM no
  es 100% confiable — puede responder con texto adicional pese a
  `num_predict` bajo. Definir un parseo tolerante (buscar `SI`/`NO` al inicio
  de la respuesta, tratar ambigüedad como `NO` por seguridad — fallar hacia
  la abstención, no hacia la alucinación).

## Nota de dependencia

Esta rama se creó desde `main` sin el merge de la iteración 1.3 todavía
pendiente. Antes de ejecutar el paso 2 (correr el experimento), verificar que
`scripts/evaluar_banco.py` tenga las dos correcciones hechas en 1.3:

1. Guard `if __name__ == "__main__":` (si falta, importar el módulo dispara
   una corrida completa sin querer).
2. Lista `ABST` con las frases de rechazo razonado (`"no se especifica"`, etc.),
   sin las cuales el juez de esta iteración también quedaría mal contado.

Si el PR de 1.3 no se ha mergeado a `main` cuando se llegue a este punto,
traer esos dos cambios a esta rama antes de medir.
