# Resultado B1 — Un juez más grande no mueve la sensibilidad

**Rama:** `iteracion_1.9_B1_juez_grande` · **Corrida:** 2026-09-25
**Plan:** [`plan_B1.md`](plan_B1.md) · **Datos:** `tests/iteraciones/resultados_b1_sens.json`

## Veredicto: refutada. No pasa la puerta 1, no se paga la puerta 2

```
                              control (llama3.2)   B1 (qwen2.5:7b)
sensibilidad en las 29            18/29  (62%)       18/29  (62%)
falsos NO                            11                 11
latencia media del juez            13,1 s             30,1 s   (2,3x)
```

El corte era **22/29**. Dio 18: exactamente el mismo número que el juez de 3B.
La hipótesis de que los 11 falsos `NO` son techo de capacidad del 3B **queda
refutada**.

No se corrió la puerta 2 (especificidad): sin ganancia de sensibilidad no hay
nada que justifique pagarla.

## El hallazgo no es el empate, es su composición

```
ambos NO (núcleo duro) ....  8    PREG-010, 064, 065, 075, 080, 084, 088, 115
recupera qwen  (NO -> SI) .  3    PREG-067, 068, 073
pierde qwen    (SI -> NO) .  3    PREG-083, 106, 114
```

**Ocho de los once falsos `NO` los comparten un modelo de 3B y uno de 7B.** Ese
núcleo duro es la evidencia útil de la corrida: si dos modelos con 2,3x de
diferencia de tamaño rechazan las mismas 8 preguntas teniendo el dato delante, el
problema no está en la capacidad del modelo. Está en la tarea que se le pide, o
en cómo le llega el dato.

**Y el intercambio de 3 por 3 da 6 discordantes** — exactamente la banda de ±6
que la 1.1-1.7 midió ante cambios cosméticos del contexto. Hasta ahora esa banda
se había medido **con el mismo modelo** y contexto distinto; esta corrida muestra
que **también aparece entre modelos distintos con el mismo contexto**. Es la misma
inestabilidad, y ahora tiene dos confirmaciones independientes.

## Hipótesis descartada en el análisis: el formato de la cita

La inspección de las 8 sugería que el juez falla cuando el dato está en una fila
de tabla markdown o en una definición en negrita. **Contado, no se sostiene:** la
tasa de `NO` es plana entre formatos —negrita 43%, tabla 33%, prosa 33%,
encabezado 50%, viñeta 0%— con 1-7 casos por celda. Era coincidencia sobre n
minúsculo. Se registra para no volver a proponerlo desde la misma observación.

## La latencia lo habría descartado igual

30,1 s por pregunta contra 13,1 s. El juez corre en **las 100 preguntas**, no solo
en el camino `SI`, así que una consulta respondida pasaría de ~28 s a ~53 s en la
GTX 1650. Para un bot de Telegram es inaceptable, y contradice de frente la
dirección del proyecto. **Aunque hubiera ganado 4 preguntas, no habría entrado.**

## Un detalle que conviene no perder

La cobertura de datos sube 54% → 68% sobre estas 29, con el **mismo redactor**. El
salto viene entero de PREG-067 y PREG-068, que pasan de cobertura 0,00 a 1,00: son
2 de 29, 14 puntos. Y las 3 que qwen pierde —PREG-083, 106, 114— ya tenían
**cobertura 0,00 con el control**: el juez de 3B las aprobaba y el redactor no
extraía el dato de todos modos.

O sea que en esas 3, el `NO` de qwen es más honesto que el `SI` de llama3.2. **La
sensibilidad del juez medida a secas cuenta como acierto un `SI` que no produce
respuesta útil.** Vale la pena medir la sensibilidad cruzada con la cobertura del
redactor, no sola.

## Consecuencias para el plan de la 1.9

- **B1 cerrado, negativo.** No se fusiona el cambio de modelo; sí la
  documentación y el arnés (`--ids`, los dos `subconjunto_*.py`), que son
  transversales.
- **Sube la prioridad de B2** (descomponer la pregunta). Es la lectura directa del
  núcleo duro: si no es capacidad, es la tarea. De las 8, tres son compuestas
  (PREG-010, 064, 115) — por debajo de la mitad, así que B2 explicaría parte y no
  todo.
- **Se mantiene OP-5 antes de B3**, sin cambios.
- **La vía A (cita que audita el camino `SI`) gana valor.** El detalle de
  PREG-083/106/114 muestra que hoy no se distingue un `SI` productivo de uno
  estéril, que es justo lo que la cita instrumentaría.

## Reproducir

```bash
python scripts/subconjunto_dato_integro.py > tests/dataset/dato_integro_k6.txt
python scripts/evaluar_banco.py b1_sens --dos-pasos --juez qwen2.5:7b \
    --redactor llama3.2 --ids @tests/dataset/dato_integro_k6.txt
```

El juez respondió `SI`/`NO` limpio en las 29: ningún veredicto viene de que
`parse_juicio` haya caído a su fail-safe por formato.
