# Plan 1.10 — Declarar las relaciones en vez de pedirle al juez que las infiera

**Rama a crear:** `iteracion_1.10_relaciones_explicitas`, desde `main`
**Abierta:** 2026-09-25 · **Origen:** el hallazgo de la 1.9
**Leer antes:** [`hallazgo_relaciones_implicitas.md`](../iteracion_1.9_B1_juez_grande/hallazgo_relaciones_implicitas.md)

## Por qué 1.10 y no 2.0

Las dos fases de abajo son cambios incrementales de una variable cada uno: una
línea de `api.py` y una reescritura interna de documentos. No cambian la
arquitectura del pipeline.

**El 2.0 debería reservarse para llevar el pipeline de dos pasos a producción.**
La 1.6 lo dejó implementado **solo en el arnés de evaluación**: `api.py` todavía
sirve `/chat` de un paso, que es el que alucina 34%. Eso es deuda arquitectónica
real y es el candidato natural a 2.0.

## El diagnóstico que hay que atacar

Las 8 preguntas que el juez niega con el dato delante no se explican por el
tamaño del modelo (0 de 8) ni por la calibración del prompt (1 de 8), y no se
pueden arreglar reescribiendo la pregunta (PREG-065 ya cita el encabezado del
documento). Lo que falta en el contexto es **siempre el verbo**: `inscribe`,
`emite`, `elabora`, `mantener`, `diferencia`.

El corpus dice `| Notaría | Escritura pública de constitución |` bajo una columna
"Rol". La pregunta pide *quién es responsable de elaborarla*. El prompt del juez
prohíbe el *"tema relacionado o parecido"*. **La inferencia que hace falta es
justo la que el prompt veta.** No hay que aflojar el prompt: hay que quitar la
necesidad de inferir.

## Fase 1 — No aplanar los saltos de línea (barata, primero)

**Variable única:** en `_build_judge_prompt` de `ai-service/api.py`,
`doc.replace('\n', ' ')[:1400]` → `doc[:1400]`.

**Por qué.** El juez recibe las tablas como una fila de pipes sin estructura. El
dato está —verificado, no se pierde nada por el aplanado ni por el truncado— pero
la tabla deja de ser una tabla. `anclaje@k` se mide sobre texto estructurado y el
juez lee texto plano. Nadie ha medido si esa diferencia importa.

**Señal de que puede importar:** el prompt `flexible`, que nombra las tablas
explícitamente, recupera PREG-088 pero no PREG-080 — otra fila de la *misma*
tabla. Un comportamiento inconsistente sobre el mismo formato es lo que se espera
si el modelo está leyendo una sopa de pipes.

**No tocar:** `_build_system_prompt` (línea 96) en la misma pasada. Es el redactor,
no el juez, y serían dos variables. Si la fase 1 funciona, el redactor va después
como cambio separado.

```bash
# 1) medición dirigida sobre el núcleo duro: 8 preguntas, ~3 min
python scripts/evaluar_banco.py f1_nucleo --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --ids PREG-010,PREG-064,PREG-065,PREG-075,PREG-080,PREG-084,PREG-088,PREG-115

# 2) solo si recupera >=3 de 8: las 29 de dato integro, ~15 min
python scripts/subconjunto_dato_integro.py > tests/dataset/dato_integro_k6.txt
python scripts/evaluar_banco.py f1_sens --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --ids @tests/dataset/dato_integro_k6.txt

# 3) solo si la sensibilidad sube: especificidad, ~20 min
python scripts/subconjunto_sin_respaldo.py > tests/dataset/sin_respaldo.txt
python scripts/evaluar_banco.py f1_espe --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --ids @tests/dataset/sin_respaldo.txt
```

**Controles:** núcleo duro 0 de 8 · sensibilidad 18/29 · especificidad 50/50.
**Corte de la puerta 1:** recuperar ≥ 3 de 8. Menos que eso queda dentro del
ruido y no justifica las puertas siguientes.

**Riesgo:** el contexto crece en caracteres (vuelven los `\n`) y el 98% del costo
del juez es leer contexto. Medir la latencia. También puede *bajar* la
sensibilidad: más tokens de estructura, menos densidad de dato por token leído.

## Fase 2 — Declarar las relaciones como predicados en el corpus

**Variable única:** el texto de los `.md`, en un corpus paralelo. Sin tocar
`api.py` ni `ingest.py`.

Convertir las relaciones implícitas en afirmaciones. Sobre las filas de tabla del
núcleo duro:

```
antes   | Notaría | Escritura pública de constitución (régimen tradicional) |
después La Notaría elabora la escritura pública de constitución del régimen
        tradicional.
        | Notaría | Escritura pública de constitución (régimen tradicional) |
```

**La fila se conserva.** Es requisito, no elegancia: 37 de las 50 citas de
anclaje son texto literal del corpus y `anclaje@k` las compara carácter a
carácter. Reescribir una fila que una cita referencia deja al banco sin
instrumento. **La frase se agrega, no reemplaza.**

**Restricciones heredadas del piloto de corpus, todas vigentes:**

1. **No cambiar nombres de archivo.** El ground truth referencia por basename y
   `recall@k` compara basenames. La reestructuración es interna al archivo.
2. **Las líneas con datos se conservan palabra por palabra.**
3. **Hay citas que exigen adyacencia** entre dos líneas en un orden concreto
   (PREG-064).
4. **La frase agregada tiene que caer dentro de los primeros 256 tokens del
   fragmento**, o el embedder no la lee para el retrieval. Ponerla antes de la
   tabla, no después.

**Alcance:** solo los documentos que tocan las 8 del núcleo duro. Medir, y
extender después si funciona.

```bash
cd ai-service && python ingest.py && cd ..
python scripts/medir_retrieval.py          # que recall y anclaje no bajen
python scripts/evaluar_banco.py f2_nucleo --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --ids PREG-010,PREG-064,PREG-065,PREG-075,PREG-080,PREG-084,PREG-088,PREG-115
```

**Corte:** recuperar ≥ 4 de 8 sin que `recall@6` baje de 48/50 ni `anclaje@6` de
29/37.

**Riesgo documentado:** anteponer el título del documento a cada fragmento
**empeoró** el retrieval en la 1.7 (recall 48 → 46), porque repetir texto que el
documento ya implica acerca los fragmentos entre sí. Una frase-predicado es texto
nuevo, no repetido, así que el mecanismo es distinto — pero hay que vigilar el
`recall` en `medir_retrieval.py` **antes** de gastar el end-to-end.

## Orden y criterio

1. **Fase 1** primero: una línea, 3 min de medición, no toca el corpus.
2. **Fase 2** después, y solo sobre los documentos del núcleo duro.
3. Si ambas fallan, el candidato que queda es **B2** del plan 1.9 (descomponer la
   pregunta), con la expectativa ya ajustada: solo 3 de las 8 son compuestas.

**Lo que no se negocia, igual que siempre:** nada entra si la especificidad baja
de 48/50 o si la alucinación sube de 0%.

## Lo que NO hay que volver a proponer

Está todo en la tabla de callejones sin salida de `ESTADO_INVESTIGACION.md`, pero
estos tres son los que esta iteración invita a repetir por error:

- **Escalar el modelo del juez.** B1: 0 de 8, y 2,3x de latencia.
- **Aflojar el prompt del juez.** `flexible` recupera 1 de 8. Ya está medido dos
  veces (1.6 y 1.9).
- **Reescribir la pregunta del usuario.** Refutado por PREG-065, que ya contiene
  el encabezado del documento textual. Ver la sección final del hallazgo.
