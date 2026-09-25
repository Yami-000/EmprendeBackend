# Resultado 1.8 — Palabras clave en el corpus

**Fecha:** 2026-09-24
**Idea original:** Yami
**Cambio:** 5 palabras clave por documento, derivadas del corpus, antepuestas al
texto **indexado** de cada fragmento y no al guardado
**Arnés:** `evaluar_banco.py --dos-pasos`, `llama3.2` (3B) en ambos roles, `k=6`
**Duración:** 1687 s (~28,1 min)

## Resumen

**Cumple el criterio de éxito**, que estaba definido sobre métricas
deterministas. El mejor resultado de retrieval del proyecto hasta la fecha.

El end-to-end volvió a no seguir, por tercera iteración consecutiva. Eso, más que
esta iteración, es lo que hay que atacar ahora.

## Métricas deterministas — el criterio

| prefijo (compite por la ventana de 256 tokens) | recall@6 | anclaje@6 |
|---|---:|---:|
| ninguno | 46/50 | 25/37 |
| cabeceras del grafo (1.7) | 48/50 | 26/37 |
| **palabras clave (1.8)** | **48/50** | **29/37** |
| ambos | 47/50 | 28/37 |

> `anclaje@6` sube al menos 4 preguntas sin que baje el `recall@6`.

**Cumple**: 25 → 29 y el recall sube de 46 a 48.

Dos cosas que no se esperaban:

- **29/37 a `k=6` es casi lo que antes daba `k=10`** (31-32). Se obtiene la misma
  calidad de contexto sin pagar la latencia de más fragmentos.
- **Las palabras clave y las cabeceras del grafo compiten por la misma ventana**
  y juntas rinden menos que las palabras clave solas. Se retiran las cabeceras
  del corpus; el parseo y `validar_grafo()` se conservan para cuando crezca.

## Cómo se eligieron las palabras clave

Elegirlas a mano habría sido inválido: quien las escribiera lleva días leyendo el
banco de preguntas y las elegiría, aun sin querer, para que el banco acierte. Es
ajuste al conjunto de prueba, el mismo error que el ground truth poblado por
script.

Se derivan mecánicamente, alternando dos fuentes que **solo miran el corpus**:

| fuente | qué aporta | anclaje@6 |
|---|---|---:|
| TF-IDF contra los otros 12 documentos | términos sueltos discriminativos (`patente`, `cédula`, `comuna`) | 27/37 |
| Encabezados y **negritas** | frases que el autor marcó (`Para Patente Municipal`, `Impuesto a la Renta — Tasas`) | 27/37 |
| **Las dos alternadas** | | **29/37** |

Por separado rinden igual; juntas, más. Las preguntas usan las dos formas.

## El desacople: texto indexado ≠ texto guardado

```
indexado   ->  "Palabras clave: ..." + el fragmento    (para el embedder)
guardado   ->  el fragmento limpio                     (para el juez)
```

Existe por la ventana de 256 tokens: el prefijo es un presupuesto escaso y hay
que gastarlo en lo que mejor rinda. Y evita el problema de la 1.7, donde el mismo
texto servía a dos consumidores con necesidades opuestas.

A nivel de retrieval las dos variantes miden **idéntico** (48/50 y 29/37), como
debe ser: el texto indexado es el mismo. Se elige la desacoplada porque no altera
lo que el modelo lee.

## End-to-end: no sigue

| | 1.1 | 1.7 | **1.8** |
|---|---:|---:|---:|
| anclaje@6 /37 | 25 | 26 | **29** |
| Sensibilidad del juez | 30/50 | 28/50 | **25/50** |
| Abstención indebida /50 | 21 | 24 | **25** |
| Cobertura de datos | 57% | 50% | **48%** |
| **Alucinación /50** | 0 | 0 | **0** |
| **Especificidad del juez** | 50/50 | 50/50 | **50/50** |
| Latencia del juez | 12,3 s | 13,1 s | 12,7 s |

Tres iteraciones seguidas: el anclaje sube, la sensibilidad baja. Cada paso
individual cabe en la banda de ±6 del juez, pero la tendencia ya no parece ruido.

### El juez se volvió más conservador, no más preciso

Cruzando su veredicto con si el dato realmente llegaba al contexto:

```
                     juez dice SI   juez dice NO
  dato LLEGA             18             11
  dato NO llega           0              8
```

```
aprueba con el dato presente : 18/29 (62%)   <- era 21/25 (84%) en la 1.1
dice SI sin el dato          :  0/8  (0%)
```

**Cero falsos positivos**, que es la razón por la que la alucinación sigue en 0%
y la especificidad en 50/50. Pero rechaza 11 de 29 preguntas cuyo dato tiene
delante, y en términos absolutos aprueba menos que antes (18 contra 21) pese a
que ahora llega más información.

### Tres hipótesis probadas y descartadas en esta iteración

| Hipótesis | Resultado |
|---|---|
| El prefijo mete ruido en el texto que lee el juez | No aplica: el desacople ya lo evita, el juez ve el fragmento limpio |
| El top-6 se volvió más diverso y el juez niega ante fragmentos heterogéneos | **Refutada.** La diversidad *bajó*: 4,96 → 4,50 documentos distintos por consulta |
| El contexto creció y lo satura | **Refutada.** 2028 → 2074 tokens, prácticamente igual |

Sumadas a las anteriores —recalibrar el prompt (A2), descomponer el contexto
(A3), tipo de pregunta, cabeceras en el texto— van **siete hipótesis** sobre el
comportamiento del juez sin confirmar.

## Conclusión honesta

No hay mecanismo identificado. Seguir proponiendo hipótesis una a una está dando
refutaciones, no convergencia.

Lo que sí está establecido:

- **La mitad de recuperación del pipeline avanzó de verdad.** De `recall` 44/50 y
  `anclaje` 22/37 en el baseline a **48/50 y 29/37**, con mediciones
  deterministas y reproducibles.
- **La mitad de generación está bloqueada por la inestabilidad del juez**, que
  domina cualquier mejora del tamaño que podemos conseguir.
- **El modo de fallo es el correcto para el dominio:** el sistema se abstiene de
  más, no inventa. Alucinación 0% y especificidad 50/50 en las tres iteraciones.
  Para un asistente sobre normativa tributaria, callar de más es preferible a
  afirmar de menos — pero limita su utilidad.

## Siguiente paso

**Sustituir el `SI`/`NO` del juez por una cita verificable**, como se acordó con
Yami. El juez pasa de emitir una opinión binaria a **transcribir el fragmento
donde está el dato**, y el código comprueba que esa cita exista de verdad en el
contexto.

Por qué ataca el problema de raíz:

- Una cita es **verificable por código**. No hay que confiar en que el modelo
  mantenga una opinión estable entre perturbaciones del contexto.
- Convierte la métrica en determinista: hoy `anclaje@k` mide si el dato llegó y
  el veredicto del juez mide otra cosa. Con citas, ambas miden lo mismo y son
  comparables.
- Si el modelo cita algo que no está, es detectable en el acto — no se necesita
  una corrida completa para saberlo.

Riesgo a medir: transcribir cuesta más tokens de salida que decir `SI`, y la
latencia ya es el cuello de botella. Pero `num_predict` del juez está en 5, así
que hay margen antes de que la generación compita con la lectura de contexto, que
es el 98% de su costo.
