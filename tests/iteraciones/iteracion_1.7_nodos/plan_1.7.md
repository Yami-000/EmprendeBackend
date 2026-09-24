# Plan 1.7 — RAG basado en nodos

**Origen:** OP-7 de `ESTADO_INVESTIGACION.md` · **Rama:** `iteracion_1.7_nodos`, a crear desde `main`
**Estado:** siguiente paso acordado con Yami el 2026-09-24

> **Punto de partida.** El piloto de reescritura del corpus
> (`corpus_esquema_piloto/resultado_piloto.md`) dejó las aristas del grafo ya
> escritas en dos documentos, pero **sin usar**. Esta iteración las conecta.

## Por qué ahora

Esta línea estaba marcada como "la de mayor costo del conjunto" porque exigía
extraer entidades y relaciones del corpus automáticamente. El piloto mostró que
**las aristas se pueden declarar a mano**, como campos del documento:

```markdown
**Nodo:** patente_municipal
**Requiere antes:** inicio_actividades_sii, certificado_de_zonificacion
**Habilita después:** operacion_del_local
```

Deja de ser un proyecto de NLP y pasa a ser redacción más una expansión del
retrieval. Es lo que hace viable la línea.

## Hipótesis

Hay preguntas cuyo dato vive en un documento que el embedding denso nunca
privilegia, porque la pregunta no comparte vocabulario con él sino con su
vecino. Si el documento recuperado declara sus vecinos, traerlos al contexto
resuelve esas preguntas **por estructura y no por similitud**.

## Evidencia que la respalda

- Quedan **4 fallos de retrieval a nivel de archivo** tras la 1.1: PREG-006,
  PREG-064, PREG-075, PREG-116. Ni el chunking ni subir `k` los mueve. El piloto
  ya recuperó PREG-064 por reescritura; quedan 3.
- El banco tiene una categoría `delimitacion` (5 preguntas) de tipo "¿esto lo
  hace el SII o la municipalidad?". Su sensibilidad es la más baja de todas:
  **2 de 5 (40%)**. Son exactamente preguntas de arista.
- PREG-078 y PREG-089, fallos históricos del baseline, son de ese tipo: el dato
  vive en una tabla de instituciones que la prosa temáticamente parecida le gana.

## Techo de esta vía

Lo fija el juez, medido en la 1.1 sobre las preguntas donde el dato **sí** llegó
íntegro al contexto:

```
el juez aprobó 21 de 25   (84%)
```

Cada pregunta cuyo dato el grafo logre entregar se convierte en respuesta el 84%
de las veces. **No más que eso**, y conviene tenerlo presente antes de invertir:
si el grafo recupera 6 preguntas a nivel de retrieval, se traducen en ~5
respuestas.

## Pasos

### Fase 1 — Llevar las aristas a la metadata (barato, sin LLM)

1. En `ingest.py`, parsear los campos `Nodo`, `Requiere antes` y
   `Habilita después` de la cabecera del documento y guardarlos en la metadata
   de cada fragmento de ese documento.
2. Verificar que la metadata llega a ChromaDB y que `evaluar_banco.py` sigue
   corriendo sin cambios (solo lee `source`).

### Fase 2 — Expandir el retrieval con los vecinos

3. Tras la consulta vectorial, para cada fragmento recuperado, traer los
   fragmentos de sus nodos vecinos que no estén ya en el resultado.
4. **Decisión de diseño a tomar con medición, no a priori:** si los vecinos se
   suman a los `k` existentes (más contexto, juez más lento) o si desplazan a
   los peor rankeados (mismo contexto, se puede perder algo). Medir las dos.
5. Medir con `scripts/medir_retrieval.py`. Segundos, sin invocar al modelo.

### Fase 3 — Extender las aristas al resto del corpus

6. Solo si la Fase 2 muestra ganancia. Declarar `Nodo` / `Requiere antes` /
   `Habilita después` en los 11 documentos restantes, respetando las tres
   restricciones del piloto (no cambiar nombres de archivo, conservar las líneas
   con datos palabra por palabra, mantener las adyacencias que exigen las citas).

### Fase 4 — Validar end-to-end

7. `evaluar_banco.py --dos-pasos` con `k=6` para aislar la variable.
   ~30 min con el chunking actual.

## Métricas objetivo

| Métrica | Actual (1.1) | Objetivo |
|---|---:|---:|
| recall@6 | 46/50 | ≥ 48/50 |
| anclaje@6 | 25/37 | ≥ 29/37 |
| Sensibilidad en preguntas `delimitacion` | 2/5 | ≥ 4/5 |
| Abstención indebida | 21/50 | ≤ 17/50 |
| Alucinación | 0% | se mantiene en 0% |
| Especificidad del juez | 50/50 | ≥ 48/50 |

## Criterio de éxito

`anclaje@6` sube **y** la sensibilidad en `delimitacion` mejora, **sin** que la
especificidad del juez caiga por debajo de 48/50 ni que la latencia del juez
supere los 15 s por pregunta.

## Riesgos

- **La consulta, no la extracción.** Mapear una pregunta a un nodo es otra tarea
  que un modelo de 3B puede errar. Por eso la Fase 2 usa el grafo para
  *expandir* el resultado vectorial, no para reemplazarlo: si el grafo no aporta,
  el sistema degrada al comportamiento actual en vez de romperse.
- **Latencia.** El juez ya está en 12,3 s por pregunta y el 98% de su costo es
  leer contexto. Traer vecinos lo encarece. Si la opción de "sumar a los `k`"
  gana en calidad pero sube el juez por encima de 15 s, preferir la de
  "desplazar".
- **Aristas mal declaradas.** Son texto escrito a mano; un `Requiere antes` con
  un id que no existe debe fallar visiblemente en la ingesta, no en silencio.

## Pendientes de otras iteraciones que NO entran aquí

Se dejan fuera para no mezclar variables. Ambos están medidos a nivel de
retrieval y son de una constante:

- `k` de 6 a 8: anclaje 25/37 → 31/37. Encarece al juez.
- `CHUNK_OVERLAP` de 200 a 150: anclaje 25/37 → 27/37 con `k=6`.
