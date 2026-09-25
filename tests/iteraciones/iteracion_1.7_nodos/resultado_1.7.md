# Resultado 1.7 — RAG basado en nodos

**Fecha:** 2026-09-24
**Cambio bajo prueba:** aristas del grafo declaradas en la cabecera de los 13
documentos, más expansión del retrieval por vecinos
**Arnés:** `scripts/evaluar_banco.py --dos-pasos`, `llama3.2` (3B) en ambos roles, `k=6`
**Duración:** 1796 s (~29,9 min)

## Resumen

La iteración **no cumple su criterio de éxito**, pero el hallazgo principal no
es sobre el grafo: es que **el veredicto del juez se mueve en ~6 de 50 preguntas
ante cambios del contexto que no alteran la información disponible**. Esa
sensibilidad es mayor que el efecto que esta iteración intentaba medir.

## Métricas

| | 1.1 | **1.7** | Objetivo |
|---|---:|---:|---:|
| retrieval_hit@6 /50 | 46 | **48** | ≥ 48 ✅ |
| anclaje@6 /37 | 25 | **26** | ≥ 29 ❌ |
| Abstención indebida /50 | 21 | **24** | ≤ 17 ❌ |
| Cobertura de datos | 57% | **50%** | — |
| Sensibilidad del juez | 30/50 | **28/50** | — |
| **Especificidad del juez** | 50/50 | **50/50** | ≥ 48/50 ✅ |
| **Alucinación /50** | 0 | **0** | 0% ✅ |
| Latencia media del juez | 12,3 s | **13,1 s** | ≤ 15 s ✅ |
| Duración | 28,2 min | 29,9 min | — |

El retrieval mejoró y el resultado end-to-end empeoró. Es la primera vez que
ocurre, y contradice el modelo que veníamos usando: *"si el dato llega, el juez
lo aprueba el 84% de las veces"*.

## El hallazgo: el juez es inestable ante perturbaciones cosméticas

Entre la 1.1 y la 1.7 el juez ganó 2 preguntas y perdió 4. Se verificó, para las
50 respondibles, si la **disponibilidad del dato** había cambiado entre ambos
índices:

```
en 49 de 50 preguntas la disponibilidad del dato NO cambió
   -> el juez cambió de opinión en 6 de ellas   (12%)

en 1 pregunta sí cambió
   -> el juez no cambió de opinión
```

El modelo corre con `temperature=0.0`, así que no es aleatoriedad entre
ejecuciones: es **sensibilidad a perturbaciones del texto** que no alteran la
información. Tres líneas de cabecera en documentos que ni siquiera son los
relevantes bastan para dar vuelta un veredicto.

### Consecuencia metodológica

**Las diferencias menores a ~6 preguntas en las métricas end-to-end no son
distinguibles de esta sensibilidad.** Eso obliga a releer los resultados
anteriores:

- La "regresión" de esta iteración (21 → 24 abstenciones) **está dentro de la
  banda**. No es evidencia de que el grafo haya empeorado nada.
- La mejora de la 1.1 (25 → 21) **también está dentro de la banda**. Se sostiene
  igualmente, pero por la evidencia independiente y determinista que la
  acompañaba: el anclaje subió 23 → 25 y la atribución mostró que los fallos a
  nivel de chunk bajaron de 11 a 8. El número end-to-end por sí solo no habría
  bastado.

**Regla que se adopta:** decidir con las métricas de retrieval —`recall@k` y
`anclaje@k` son deterministas y reproducibles— y usar la corrida end-to-end como
confirmación, siempre declarando la banda de ±6.

## El grafo: qué funciona y qué no

Medido con `scripts/medir_grafo.py`, sin invocar al modelo:

```
                  recall   anclaje   frag/pregunta
base                46       25        6.0
cabecera            48       26        6.0     <- gratis
sumar (mejor)       48       27        8.7     <- +45% contexto por +1 pregunta
desplazar (mejor)   46       23        6.0     <- siempre peor
```

### Declarar las aristas sí sirve

Solo escribir la cabecera —sin recorrer nada— recupera **2 preguntas sin perder
ninguna y sin un token extra de contexto**:

```
GANA  PREG-064  ¿Qué diferencia existe entre una SA Cerrada y una SA Abierta?
GANA  PREG-075  ¿Qué registro electrónico deben mantener todas las empresas?
```

PREG-075 era uno de los 4 fallos de retrieval a nivel de archivo que la 1.1 dio
por irrecuperables con chunking o con `k`.

El mecanismo no es el grafo: los nombres de los nodos vecinos funcionan como
**palabras clave** que enriquecen el vector del documento. Es el mismo efecto
que el piloto de ayer, donde lo que movió la aguja fue el vocabulario y no la
estructura.

### Recorrer las aristas no sirve

Barrido de 9 configuraciones (`--desde` 1-3 × `--max-vecinos` 2-6). El mejor caso
de `sumar` compra **+1 pregunta a cambio de 45% más contexto**, que llevaría al
juez de 13,1 s a unos 18 s. `desplazar` degrada siempre, y mucho: hasta 36/50 de
recall y 13/37 de anclaje cuando se toman muchos vecinos.

**Explicación probable:** el corpus tiene 28 fragmentos y `k=6` ya recupera el
**21% del total**. El grafo no puede aportar cuando la búsqueda vectorial ya ve
una quinta parte de todo. La expansión por vecinos debería pagar en un corpus
grande; en este no hay margen.

## Una hipótesis intermedia, también refutada

Ante la regresión se propuso que la cabecera, al viajar en el texto del
fragmento, estorbaba al juez: ve `**Requiere antes:** constitucion_empresa_simplificada`,
identificadores para la máquina que son ruido para el modelo.

Primera evidencia: las 4 preguntas perdidas tenían cabeceras en su contexto. **Esa
evidencia no valía nada** — la tasa base es 50 de 50, así que cualquier pregunta
la habría cumplido.

Prueba directa, quitando las cabeceras del texto mostrado al juez y dejándolas en
el indexado:

```
recupera 1 de 4      fugas de especificidad: 0 de 4
```

**Refutada.** La idea de separar *texto indexado* de *texto mostrado* sigue
siendo razonable como principio de diseño, pero no explica esta regresión.

## Lo que queda decidido y lo que no

**Decidido:** no se implementa la expansión por vecinos. El costo en contexto no
se justifica con este tamaño de corpus.

**Sin decidir:** si conservar las cabeceras en el corpus. A favor, las métricas
deterministas: `recall@6` 46 → 48 y `anclaje@6` 25 → 26, sin costo de contexto.
En contra, que el end-to-end no lo confirma — aunque tampoco puede, porque el
efecto es menor que la banda de ruido del juez.

`validar_grafo()` queda en `ingest.py` en cualquier caso: rompe la ingesta si una
arista apunta a un nodo inexistente, y las aristas son texto escrito a mano.

## Siguiente paso propuesto

**La inestabilidad del juez pasa a ser el problema principal.** Mientras el
veredicto se mueva en 6 de 50 preguntas por cambios cosméticos, no se pueden
medir mejoras de esa magnitud, que son casi todas las que quedan.

Ideas a evaluar, en orden de costo:

1. **Medir la banda con precisión.** Repetir una corrida con perturbaciones
   controladas del contexto (reordenar los fragmentos, por ejemplo) para separar
   la sensibilidad al orden de la sensibilidad al contenido.
2. **Autoconsistencia del juez:** varias pasadas y voto por mayoría. Multiplica
   la latencia, que ya es el cuello de botella.
3. **Sustituir el juicio binario por algo menos frágil**, como pedirle que cite
   el fragmento donde está el dato. Una cita verificable es comprobable por
   código y no depende de que el modelo mantenga una opinión estable.
