# Resultado Fase 0 — 1.9, juez con cita verificable

**Fecha:** 2026-09-24
**Costo:** ~40 llamadas al juez, ~12 min. Ninguna corrida completa.

La Fase 0 era la puerta del plan: comprobar que un modelo de 3B puede transcribir
literalmente antes de invertir en la iteración. **La superó, y acto seguido
reveló un fallo que invalida el diseño.**

## Puerta 1: ¿transcribe literalmente? Sí, 10 de 10

| prompt | citas válidas |
|---|---:|
| con un ejemplo concreto | 6/10 (60%) |
| con formato esquemático | 9/10 (90%) |
| **solo reglas, sin ejemplo** | **10/10 (100%)** |

El criterio del plan era ≥8 de 10. **Cumple.**

### Un error de diseño propio, detectado a tiempo

La primera medición dio 60%, y tres de las cuatro citas fallidas eran **la misma
cadena exacta**:

```
PREG-019   [3] | Total estimado | $110.000 - $380.000 |
PREG-067   [3] | Total estimado | $110.000 - $380.000 |
PREG-068   [3] | Total estimado | $110.000 - $380.000 |
```

Era literalmente el ejemplo puesto en el prompt. El modelo lo copiaba en vez de
leer el contexto. El 60% no medía la capacidad del modelo sino un defecto del
prompt: **en un modelo pequeño, un ejemplo concreto de few-shot se convierte en la
respuesta**. Quitarlo llevó el resultado a 100%.

Queda como advertencia de método: no poner ejemplos concretos en los prompts del
juez.

## Puerta 2: ¿mantiene la especificidad? No. 10 fugas de 10

Sobre 10 preguntas **sin respaldo documental**, donde el juez debe negar:

```
fugas: 10 de 10     (el juez binario actual: 0 de 50)
```

**El juez con cita nunca dice NO.** Siempre encuentra algo que citar. Y lo peor:
**6 de esas 10 citas son válidas** —existen literalmente en el contexto— pero no
responden la pregunta.

## Por qué esto invalida el diseño

La verificación por código comprueba que la cita **exista**, no que **responda**.
Contra una cita válida pero irrelevante, la verificación no protege:

```
PREG-067  (¿costo total del régimen tradicional?)
  -> "[2] limitada entre socios. - **Sociedad Comanditaria..."     cita válida
PREG-065  (otra pregunta)          -> la misma cadena
PREG-068  (otra pregunta)          -> la misma cadena
```

Tres preguntas distintas, la misma cita. El modelo copia *algo* para cumplir el
formato.

Adoptar esto llevaría la especificidad de **50/50 a 0/50** y devolvería la
alucinación, destruyendo el único logro sólido del proyecto. El fallo es del tipo
peor posible: sustituye "callar de más" por "afirmar sin respaldo", en un
asistente sobre normativa tributaria.

**Verificar la existencia de una cita no sustituye al juicio.** Decidir si una
línea responde una pregunta *es* el juicio, y es exactamente lo que no sabemos
hacer de forma estable.

## Rediseño propuesto: la cita audita, no reemplaza

El binario tiene especificidad perfecta (50/50 en tres iteraciones). La cita es
verificable. Combinarlos en vez de sustituir uno por otro:

```
paso 1   juez binario  ->  SI / NO        (conserva la especificidad)
paso 2   solo si dijo SI: "cita la línea"  (hace auditable ese SI)
paso 3   redactor, solo si la cita es relevante
```

Lo que se gana:

- **La especificidad queda intacta**, porque el binario sigue siendo el que
  decide negar.
- **El camino `SI` se vuelve auditable.** Hoy no se puede saber si un `SI` está
  justificado sin revisarlo a mano; con cita, el código lo comprueba contra la
  `cita_anclaje` del ground truth.
- **Se consigue la atribución determinista que buscaba la iteración**, que era la
  mitad del objetivo, sin arriesgar la otra mitad.
- **Costo acotado:** solo se pide cita en las ~25 preguntas del camino `SI`, no en
  las 100.

Lo que **no** se consigue: subir la sensibilidad. El binario seguirá negando 11 de
29 preguntas cuyo dato tiene delante. Esta vía mide el problema con precisión,
pero no lo resuelve.

## Estado

**El plan 1.9 original queda descartado.** No se implementa el reemplazo del
binario por la cita.

Antes de seguir con el rediseño conviene que Yami decida, porque cambia el
objetivo de la iteración: de *"mejorar la sensibilidad del juez"* a *"hacer
medible su decisión"*.
