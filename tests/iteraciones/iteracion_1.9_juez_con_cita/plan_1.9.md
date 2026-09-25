# Plan 1.9 — Juez con cita verificable

**Rama:** `iteracion_1.9_juez_con_cita`, creada desde `main`
**Acordado con Yami:** 2026-09-24, al cerrar la 1.8

## Por qué esto no es una octava hipótesis

Van **siete** hipótesis sobre el comportamiento del juez probadas y sin
confirmar: recalibrar su prompt (A2), descomponer el contexto fragmento por
fragmento (A3), escalar el modelo, el tipo de pregunta, las cabeceras del grafo
en el texto, la diversidad del top-6 y la saturación del contexto. Proponerlas de
una en una está dando refutaciones, no convergencia.

El problema de fondo no es *por qué* el juez se equivoca, sino que **su salida no
es verificable**. Un `SI` o un `NO` no se puede comprobar: hay que creerle. Y
medimos que su veredicto se mueve en ~6 de 50 preguntas ante cambios del contexto
que no alteran la información disponible, con `temperature=0`.

Esta iteración cambia el enfoque: en vez de seguir explicando la inestabilidad,
**elimina la necesidad de confiar**.

## La idea

El juez deja de emitir una opinión binaria y pasa a **transcribir la línea del
contexto donde está el dato**. El código comprueba que esa línea exista de verdad
en los fragmentos recuperados.

```
antes:   juez -> "SI"                      (hay que creerle)
después: juez -> "[3] Total estimado | $110.000 – $380.000"
                 ^^^ comprobable por código
```

Si la cita no aparece en el contexto, el modelo se la inventó y el pipeline
**devuelve la abstención**. El fail-safe sigue apuntando hacia callar, que es el
modo de fallo correcto para normativa tributaria.

## Lo que esto desbloquea

1. **La salida del juez se vuelve determinista de verificar.** No hay que confiar
   en que mantenga una opinión estable entre perturbaciones del contexto.
2. **Su decisión se vuelve comparable con `anclaje@k`.** Hoy son métricas
   incommensurables: `anclaje@k` mide si el dato llegó, y el veredicto del juez
   mide otra cosa. Con citas, ambas se miden contra el mismo ground truth y por
   primera vez se puede atribuir un fallo a uno u otro componente sin ambigüedad.
3. **Una cita inventada es detectable en el acto**, sin esperar una corrida
   completa de 30 minutos.
4. **La cita sirve al redactor.** Pasarle la línea exacta en vez del contexto
   entero podría subir la cobertura de datos, que hoy está en 48%. Queda fuera de
   esta iteración para no mezclar variables, pero se anota.

## Riesgo principal, y cómo se acota antes de invertir

**Un modelo de 3B puede no transcribir literalmente.** Si parafrasea, la
verificación falla y la sensibilidad se hunde. Eso haría inútil el enfoque, y hay
que saberlo **antes** de pagar una corrida completa.

**Fase 0 obligatoria — prueba de transcripción (~2 min, 10 preguntas).** Tomar 10
preguntas cuyo dato sabemos que llega íntegro al contexto y medir solo esto:

```
de 10 citas emitidas, cuántas aparecen literalmente en el contexto
```

- Si son **8 o más**, el enfoque es viable y se sigue.
- Si son **menos de 5**, se detiene aquí y se documenta. Alternativa a evaluar en
  ese caso: pedir solo el **número de fragmento** (`[3]`), que es mucho más fácil
  de emitir aunque solo verifica el rango, no el contenido.
- Entre 5 y 7, probar una variante del prompt antes de decidir.

## Pasos

1. **Fase 0.** La prueba de transcripción de arriba. No continuar sin superarla.
2. Añadir `JUEZ_PROMPT_BASES["cita"]` en `api.py`, junto a `estricto` y
   `flexible`, para poder reproducir la comparación sin reescribir código.
3. Implementar en `evaluar_banco.py` el parseo y la verificación de la cita, con
   la normalización ya usada en `medir_retrieval.py` —sin tildes, sin viñetas,
   espaciado colapsado—, que debe ser **la misma** o los números no serán
   comparables.
4. Subir `--num-predict-juez` de 5 a lo que la Fase 0 muestre necesario.
5. Corrida completa con `k=6` para aislar la variable.
6. Comparar la cita del juez contra la `cita_anclaje` del ground truth y calcular
   por primera vez la atribución sin ambigüedad.

## Métricas nuevas

| Métrica | Qué mide |
|---|---|
| `cita_valida` | la cita del juez existe literalmente en el contexto (determinista) |
| `cita_correcta` | además coincide con la `cita_anclaje` del ground truth |
| `cita_inventada` | el juez citó algo que no está: se fuerza abstención |

## Métricas objetivo

| Métrica | Actual (1.8) | Objetivo |
|---|---:|---:|
| Citas válidas sobre las emitidas | — | ≥ 90% |
| Sensibilidad del juez | 25/50 | ≥ 29/50 |
| Abstención indebida /50 | 25 | ≤ 21 |
| **Alucinación /50** | 0 | se mantiene en 0 |
| **Especificidad del juez** | 50/50 | ≥ 48/50 |
| Latencia del juez | 12,7 s | ≤ 16 s |

El objetivo de sensibilidad es 29/50 porque el anclaje está en 29/37: si el juez
aprobara toda pregunta cuyo dato llega íntegro, llegaría ahí. Es el techo que
marca la recuperación actual.

## Criterio de éxito

Al menos el 90% de las citas emitidas son verificables **y** la abstención
indebida baja, **sin** que la especificidad caiga por debajo de 48/50 ni que la
latencia del juez pase de 16 s.

## Riesgos secundarios

- **Latencia.** `num_predict` pasa de 5 a ~60. El 98% del costo del juez es leer
  el contexto y `eval` es ~0,1 s por 3 tokens, así que el añadido debería rondar
  los 2 s. Hay que medirlo, no suponerlo: ya fallé una estimación de tiempo por
  2,4x en la 1.3.
- **Citas parcialmente correctas.** El juez puede citar una línea real del
  contexto que no responde la pregunta. `cita_valida` daría positivo y
  `cita_correcta` negativo: por eso se miden las dos por separado.
- **El techo del banco.** 13 de las 50 citas del ground truth están
  parafraseadas y no existen literales en el corpus. Para esas preguntas
  `cita_correcta` no es medible, igual que `anclaje@k`. El techo sigue siendo 37.
