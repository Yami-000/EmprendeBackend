# Plan B1 — Un modelo más grande solo para juzgar

**Rama:** `iteracion_1.9_B1_juez_grande` · **Abierta:** 2026-09-25
**Vía B1 del** [`plan_1.9.md`](../iteracion_1.9_juez_con_cita/plan_1.9.md)

```
juez qwen2.5:7b  +  redactor llama3.2 (3B)
```

## Hipótesis

El juez binario niega 11 de las 29 preguntas cuyo dato de anclaje **le llega
íntegro**. La hipótesis es que esos 11 falsos `NO` son techo de capacidad del 3B
*en la tarea de juzgar*, y que un modelo de 7B la resuelve.

**Por qué no está refutada ya.** La 1.3 midió que escalar no ayuda, pero midió
**generación en un paso**: el modelo grande tenía que decidir *y* redactar. El
experimento B de la 1.6 probó el reparto contrario (juez 3B + redactor 8B) y se
descartó porque el redactor ya responde en 25 de las 26 veces que se le habilita.
**Nadie ha medido un juez grande.** Es el hueco que esta rama cierra.

## La variable

Una sola: el modelo del juez, `llama3.2` → `qwen2.5:7b`. Todo lo demás queda fijo
—corpus 1.8, `k=6`, `--juez-prompt estricto`, `CHUNK_SIZE` 1400, redactor
`llama3.2`, `temperature=0.0`— para que el efecto sea atribuible.

## El control ya está medido: no se vuelve a correr

Los veredictos por pregunta de la 1.8 están en
`tests/iteraciones/resultados_claves_1.8_k6.json`, con `juez_dijo_si` por
pregunta. Sobre el subconjunto de 29:

```
control (juez llama3.2, 1.8) ......  18/29 SI   (62%)   11 falsos NO
```

Los 11 falsos `NO`: PREG-010, 064, 065, 067, 068, 073, 075, 080, 084, 088, 115.

Gastar una corrida en reproducirlo sería repetir una medición existente. El
smoke test de dos preguntas confirmó que el arnés sigue dando los mismos
veredictos (PREG-001 `SI`, PREG-010 `NO`).

## Dos puertas, la barata primero

**Puerta 1 — sensibilidad (~10 min, 29 preguntas).** Solo las preguntas cuyo dato
llega íntegro. Si el dato no está en el contexto, un `NO` es correcto y no dice
nada del juez; medir ahí contamina la señal con fallos de retrieval.

```bash
python scripts/subconjunto_dato_integro.py > tests/dataset/dato_integro_k6.txt
python scripts/evaluar_banco.py b1_sens --dos-pasos --juez qwen2.5:7b \
    --redactor llama3.2 --ids @tests/dataset/dato_integro_k6.txt
```

**Corte:** si `qwen2.5:7b` no supera **22/29** (control 18, banda del juez ±6),
la vía muere aquí y no se paga la puerta 2.

**Puerta 2 — especificidad (~20 min, 50 preguntas sin respaldo).** Solo si pasa
la 1. Es la restricción que no se negocia, y necesita la mitad no respondible
completa.

```bash
python scripts/subconjunto_sin_respaldo.py > tests/dataset/sin_respaldo.txt
python scripts/evaluar_banco.py b1_espe --dos-pasos --juez qwen2.5:7b \
    --redactor llama3.2 --ids @tests/dataset/sin_respaldo.txt
```

**Corte:** especificidad ≥ 48/50. Por debajo, se descarta aunque la
sensibilidad haya subido.

Solo si pasa las dos se paga la corrida completa de 100 preguntas para el número
comparable con las iteraciones anteriores.

## Criterio de éxito

| Métrica | Control | Objetivo |
|---|---|---|
| sensibilidad en las 29 de dato íntegro | 18/29 (62%) | **≥ 23/29** (79%) |
| especificidad | 50/50 | **≥ 48/50** |
| alucinación | 0/50 | **0/50** |

## Lo que hay que medir aunque el resultado sea bueno: la latencia

`qwen2.5:7b` es 2,4x el tamaño del redactor. El juez corre en **las 100
preguntas**, no solo en el camino `SI`, y el 98% de su costo es leer contexto.
Con el juez 3B a 12,7 s, un juez de 7B podría llevar la consulta respondida de
~28 s a ~45 s en la GTX 1650.

**Esto choca de frente con la dirección del proyecto** —hacer rendir al 3B
cambiando la arquitectura, no sustituirlo—. Si B1 funciona pero cuesta el doble
de latencia, el resultado no es "adoptar qwen de juez": es **evidencia de que la
tarea de juzgar sí tiene techo de capacidad**, y eso redirige el esfuerzo a
darle al 3B una tarea más fácil (B2: descomponer la pregunta) en vez de un
modelo más grande. Anotar los segundos por pregunta en el resultado, pase lo que
pase.

## Riesgos

- **`qwen2.5:7b` alucinó 42% en la 1.3**, el peor de los tres modelos probados,
  en generación de un paso. Es el argumento más fuerte contra esta vía. La
  puerta 2 existe justamente por eso.
- **El prompt del juez está calibrado para un 3B.** Lleva el sesgo *"ante
  cualquier duda responde NO"*, que en la 1.6 se midió necesario. Un 7B podría
  obedecerlo *más* y bajar la sensibilidad. Si pasa, no se toca el prompt en esta
  rama: sería una segunda variable.
- **`parse_juicio` es fail-safe hacia `NO`.** Un 7B que conteste "Sí, el
  contexto indica..." en vez de `SI` cuenta como `NO`. Con `num_predict=5` el
  riesgo es bajo, pero hay que revisar `juez_respuesta` en el JSON antes de creer
  un resultado malo.

## Cambios al arnés (no al pipeline)

Ninguno toca `api.py` ni `ingest.py`, así que no afectan lo que se mide:

- `scripts/evaluar_banco.py`: flag `--ids` (lista con comas o `@archivo`), para
  correr un subconjunto por ID. Excluyente con `--limite`. Los porcentajes ahora
  toleran que una de las dos mitades del banco quede vacía.
- `scripts/subconjunto_dato_integro.py`: recalcula el subconjunto desde el índice
  en vez de fijar los IDs en el código, porque depende de la ingesta vigente.
- `scripts/subconjunto_sin_respaldo.py`: la mitad de control, leída del campo
  `md_origen` del ground truth y no de un corte por índice.
- `scripts/medir_retrieval.py`: el informe pasa a `reporte()` bajo
  `if __name__ == "__main__"` para que el módulo sea importable. Salida verificada
  idéntica antes y después.
