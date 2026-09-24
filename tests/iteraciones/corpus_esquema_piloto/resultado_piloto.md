# Piloto — Esquema estructurado del corpus

**Fecha:** 2026-09-24
**Idea original:** Yami — estandarizar los `.md` con un esquema fijo de cuatro
partes (institución / requisitos previos / de qué trata / siguiente paso), y
guardar la pertenencia a un nodo del grafo en el propio documento.
**Alcance:** 2 de los 13 documentos, en un corpus paralelo (`docs/sii_piloto/`)
para no tocar el vigente.

## Qué se probó

| Documento | Tipo aplicado | Objetivo |
|---|---|---|
| `patente_municipal.md` | trámite (4 partes) | PREG-010, falso negativo del juez |
| `tipos_sociedad_chile.md` | referencia | PREG-063 y PREG-064, fallos de retrieval |

Adaptaciones al esquema original, discutidas antes de implementar:

- **Dos tipos de documento, no uno.** Solo 3 de las 50 preguntas respondibles
  son de tipo `procedimiento`; 18 son `factual`, 12 `normativa` y 12
  `conceptual`. Forzar las cuatro partes procedimentales en todos los documentos
  habría generado decenas de "Requisitos previos: ninguno", texto repetido que
  acerca los vectores entre sí y empeora la discriminación.
- **La parte 3 se parte en dos:** "Qué es" y "Datos". Las cifras, plazos y
  formularios son lo que preguntan 40 de las 50 citas de anclaje; darles un
  lugar fijo hace que el juez las encuentre siempre en el mismo sitio.
- **Los datos del grafo van como campos del documento** (`Nodo`,
  `Requiere antes`, `Habilita después`), no como capa separada.

## Resultado: el retrieval mejora, y de forma atribuible

Con 2 de 13 documentos reescritos:

| | k=6 rec/anc | k=8 rec/anc |
|---|---|---|
| Corpus vigente | 46 / 25 | 48 / 31 |
| **Corpus piloto** | **47 / 26** | **48 / 33** |

Lo relevante es *dónde* se movió:

| Pregunta | Corpus vigente | Corpus piloto |
|---|---|---|
| PREG-063 (SpA / startups) | fuera del top-6 | **#4**, el dato llega |
| PREG-064 (SA Cerrada vs Abierta) | fuera del top-6 | **#1**, el dato llega |
| PREG-010, 062, 083, 084 | sin cambio | sin cambio |

Se movieron exactamente las dos preguntas a las que apuntaba la reescritura y
ninguna otra. **PREG-064 era uno de los 4 fallos de retrieval a nivel de archivo
que la 1.1 dio por irrecuperables** con chunking o con `k`.

## Resultado: el juez no se mueve

Se probó el veredicto del juez sobre las cuatro preguntas objetivo, con los dos
corpus, más cuatro no respondibles como control:

```
             vigente   piloto
PREG-010        NO       NO
PREG-084        NO       NO
PREG-063        NO       NO
PREG-064        NO       NO

control de especificidad: 0 fugas en ambos
```

**Ninguna cambió.** Incluso PREG-063 y PREG-064, donde el dato pasó de no llegar
a llegar, siguen recibiendo `NO`.

El instrumento está validado: reproduce 5 de 5 los veredictos de la corrida 1.1
sobre el índice real, así que el resultado negativo no es un artefacto.

Esto **refuta la parte de la hipótesis referida al juez**. Se había previsto que
una declaración explícita de institución —`patente_municipal.md` dice ahora
*"No la tramita el SII"*— convencería al juez en PREG-010, que pregunta
literalmente *"¿se gestiona en el SII o en otra institución?"*. No ocurrió.
También se añadió una frase de encuadre explícita en PREG-064 (*"La diferencia
entre una SA Cerrada y una SA Abierta está en si cotiza en bolsa…"*) sin efecto.

### Una hipótesis que tampoco se sostiene

Se comprobó si el juez falla sistemáticamente en preguntas de síntesis frente a
las de búsqueda de dato, sobre la corrida completa:

```
búsqueda de dato (factual + normativa)   19/30   63%
síntesis (conceptual + delimitación)      9/17   53%
```

Diez puntos sobre muestras pequeñas. **No alcanza para sostener la hipótesis.**
Las causas de los falsos negativos del juez siguen sin explicación, tras tres
intentos: recalibrar el prompt (A2), descomponer el contexto (A3) y ahora
explicitar el dato en el documento.

## El techo real del juez

Medido sobre la corrida 1.1, restringido a las preguntas donde el dato **sí
llegó íntegro** al contexto:

```
el juez aprobó 21 de 25   (84%)
```

Es el número que faltaba para dimensionar las dos vías:

- Mejorar el retrieval sigue valiendo la pena: cada pregunta cuyo dato se logre
  entregar se convierte en respuesta el 84% de las veces.
- Pero hay un 16% que no se recupera por esa vía. PREG-063 y PREG-064 cayeron
  justamente ahí — que fallen las dos, contra una tasa base de 84%, tiene una
  probabilidad de 2,6%: son difíciles para el juez, no mala suerte.

## Restricciones descubiertas al implementar

1. **Los nombres de archivo no se pueden cambiar.** La granularidad ideal para
   `tipos_sociedad_chile.md` sería un archivo por tipo de sociedad. No es
   posible: el ground truth referencia los documentos por nombre de archivo y
   `recall@k` compara basenames. Partir archivos invalidaría la medición de 8
   preguntas. La reestructuración debe ser **interna al archivo**.
2. **Hay citas que exigen adyacencia.** La de PREG-064 son dos líneas que deben
   quedar seguidas y en ese orden. Verificado: el techo del anclaje se mantiene
   en 37, sin pérdidas.
3. **Con el tope de 1400 las secciones se vuelven a juntar.** Los documentos son
   pequeños, así que dividirlos en más secciones no cambia los fragmentos. Lo
   que movió la aguja **no fue la estructura sino el vocabulario**: los
   encabezados y frases puente que usan los términos de las preguntas
   (*"SpA — Sociedad por Acciones, la opción de startups"*). Es un matiz
   importante: la estructura ayuda a escribir mejor, pero el efecto medible vino
   del contenido.

## Conclusión

**Media confirmación.** La reescritura del corpus es una vía real para el
retrieval, con efecto medible y atribuible usando 2 documentos de 13. No es una
vía para el juez.

Lo que decide si conviene extenderla a los 13 documentos es el costo: son
documentos que hay que escribir a mano preservando las líneas con datos palabra
por palabra. El piloto tomó dos y ganó dos preguntas de retrieval.

## Lo que queda por probar de la idea original

El grafo. Los campos `Nodo`, `Requiere antes` y `Habilita después` están escritos
en los dos documentos del piloto pero **todavía no se usan**: haría falta
llevarlos a la metadata del chunk en `ingest.py` y expandir el resultado del
retrieval con los vecinos. Es la parte de la idea con más potencial y la menos
probada — y ahora es barata, porque las aristas están declaradas en vez de tener
que extraerse.
