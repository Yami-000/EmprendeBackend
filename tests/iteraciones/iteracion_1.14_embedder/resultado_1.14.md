# Resultado 1.14 — El embedder era el techo. Con `k=3` es la mejor configuración del proyecto

**Fecha:** 2026-09-27 · **Rama:** `iteracion_1.14_embedder`
**Plan:** [`plan_1.14.md`](plan_1.14.md)

## Veredicto

**El retrieval pasa de ser el cuello de botella a estar prácticamente resuelto.** La
configuración que se recomienda es **`multilingual-e5-small` con `k=3`**: mejora la
sensibilidad, respeta las dos restricciones que no se negocian, y **corta la latencia
casi a la mitad**.

```
                        1.10        e5 k=6      e5 k=3      restriccion
sensibilidad .......   30/50       38/50       34/50
abstuvo indebido ...   20/50       13/50       16/50
especificidad (juez)   50/50       49/50       49/50       >= 48/50   PASA
ALUCINACION ........    0/50        1/50        0/50       0%         k=6 NO PASA
latencia juez ......   12,7 s      13,0 s       6,9 s
consulta respondida    17,5 s      19,6 s      10,3 s      (media)
                       39 s pico   40 s pico   23 s pico
```

## El retrieval, resuelto

```
                        1.10      e5-small
anclaje@6 ..........   28/37      36/37   (97%)
anclaje@8 ..........   30/37      37/37   (100%, el techo teorico)
recall@6 ...........   48/50      49/50
anclaje@3 ..........   22/37      30/37   <- con k=3 ya supera al 1.10 con k=6

chunks que exceden la ventana ....  22 de 28  ->  0 de 28
tokens fuera de la ventana .......  32%       ->  0%
citas de anclaje fuera ...........  14 de 37  ->  0 de 37
```

**`anclaje@8` toca el techo teórico: 37 de 37.** Todas las citas literales del banco
llegan al contexto.

**Un efecto que no estaba previsto y juega a favor:** el tokenizador de XLM-R es más
eficiente en español que el de MiniLM. Los mismos fragmentos pasan de mediana **382
tokens a 283** y de máximo **495 a 380**. La ventana de 512 no solo alcanza: sobra.
El problema no queda mitigado, queda cerrado.

## El juez sí siguió al retrieval, y esta vez se puede afirmar

Era la duda después de la 1.11, donde `anclaje@6` llegó a 31/37 y la sensibilidad
**bajó**. Acá subió, y la diferencia está en la forma del efecto:

```
1.10 -> e5 k=6 ....  10 vuelcos:  9 ganadas,  1 perdida    asimetrico
1.10 -> e5 k=3 ....   8 vuelcos:  6 ganadas,  2 perdidas   asimetrico
1.10 -> 1.11A .....  10 vuelcos:  4 ganadas,  6 perdidas   parejo
```

**La inestabilidad del juez mueve veredictos en las dos direcciones; un efecto real
los mueve en una.** Nueve contra uno no es la banda de ±6.

Esto obligó a **corregir `comparar_corridas.py`**, que avisaba "no se distingue de la
banda" solo por contar más vuelcos que cambio neto, y con eso desestimaba este
resultado. Ahora reporta el reparto y solo avisa cuando están casi parejos.

## La fuga con `k=6`, y por qué `k=3`

Con `k=6` el juez aprobó **PREG-045**: *"¿Qué organismo público es responsable
directo de recaudar y cobrar los impuestos girados por el SII?"*. El bot respondió
que el SII. **La respuesta correcta es la Tesorería General de la República** — el
SII gira, la Tesorería cobra.

La pregunta está entre las 50 sin respaldo porque el corpus no cubre a la Tesorería,
y es **adversaria por diseño**: nombra al SII, así que el retrieval trae documentos
del SII y el juez ve *"impuestos"* y *"declaración de impuestos"* y aprueba.

**Es exactamente el modo de fallo que documentó la Fase 0 de la 1.9:** hacer que el
contexto parezca más pertinente empuja al juez a decir `SI` sin respaldo. Un embedder
mejor recupera contenido más relacionado semánticamente, y eso corta para los dos
lados.

**Bajar `k` se probó pregunta por pregunta:**

```
k=3  abstiene correctamente
k=4  fuga
k=5  fuga
k=6  fuga
```

Solo `k=3` la elimina. Y ahí apareció algo mejor de lo que se buscaba: **`anclaje@3`
con e5 es 30/37, que supera al 28/37 de la 1.10 con `k=6`.** Mejor retrieval con la
mitad del contexto.

Como el **98% del costo del juez es leer contexto**, eso se traduce en latencia:
**6,9 s contra 12,7 s** en el juez, y una consulta respondida baja de 17,5 s a
**10,3 s** de media, con el pico de 39 s a 23 s. Para un bot de Telegram eso no es un
detalle: la latencia era una tensión abierta del proyecto desde la 1.1.

## Lo que hay que mirar con incomodidad

**La especificidad del juez bajó a 49/50 en las DOS configuraciones de e5.** El juez
aprueba PREG-045 tanto con `k=6` como con `k=3`. La diferencia es que con `k=3` **el
redactor abstuvo igual** y la respuesta errónea no llegó al usuario.

```
                        e5 k=6     e5 k=3
especificidad (juez)    49/50      49/50     <- el mismo fallo
atajadas por redactor    0/50       1/50
ALUCINACION              1/50       0/50
```

**El 0% de alucinación con `k=3` depende de que el redactor abstenga, no de que el
juez acierte.** Y esa abstención está medida como **marginal y no controlada**: 6 de
185 casos históricos (3,2%), documentada en
[`hallazgo_abstencion_redactor.md`](../iteracion_1.11_ventana_embedder/hallazgo_abstencion_redactor.md)
como algo que *no amerita iteración*. Acá actuó como red de seguridad que **nadie
diseñó para eso**.

Cumple la letra de la restricción. **Pero la garantía es más frágil que en la 1.10,
donde el juez no fallaba ninguna.** Quien decida fusionar tiene que saberlo.

Eso también obligó a **corregir `comparar_corridas.py`**: calculaba la especificidad
desde `abstuvo` en vez de desde `juez_dijo_si`, reportaba 50/50 y **escondía este
fallo**. Ahora separa tres cosas: especificidad del juez, atajadas por el redactor, y
alucinación que llegó al usuario.

## El modelo, y por qué el chico

`intfloat/multilingual-e5-small`: 512 tokens de ventana, **384 dimensiones** (las
mismas que MiniLM, así que no cambia el esquema del índice), ~470 MB, sin
`trust_remote_code`.

**Se descartó `bge-m3` a propósito** aunque tiene 8192 tokens: pesa 2,2 GB, 4,7 veces
más. Correr en hardware modesto es el objetivo del proyecto, no una restricción a
superar — un embedder de 2,2 GB deja de hacer accesible la información del SII en
máquinas básicas, que es el punto.

**Los prefijos `query:` y `passage:` no son opcionales.** La familia E5 se entrenó con
esa asimetría y usar el prefijo equivocado es peor que no usar ninguno.

## El refactor que vino antes, y su verificación

El nombre del embedder estaba escrito a mano en **siete archivos**: `ingest.py`,
`api.py` y cinco scripts. Esa es la trampa de divergencia que ya costó un incidente
en este proyecto. Ahora vive en `ai-service/embedding.py`.

**Se verificó que el refactor fuera neutro antes de cambiar el modelo:** con el módulo
conectado y `MODEL_NAME` en MiniLM, la medición dio 28 chunks, `recall@6` 48/50 y
`anclaje@6` 28/37 — **idéntico al control**. Sin ese paso, cualquier cambio posterior
habría sido inatribuible entre el refactor y el modelo.

## Lo que este resultado le hace al resto de la investigación

**Vuelve obsoletas dos iteraciones de la misma sesión:**

- **La 1.11** (promediar ventanas) existía para exprimir una ventana de 256 tokens.
  Con 512 y cero fragmentos excedidos, **no tiene objeto**. Su hallazgo sigue
  valiendo como diagnóstico; su código no.
- **La 1.13** (predicados sistemáticos) medía la competencia por un prefijo escaso.
  **El prefijo ya no es escaso.** Habría que volver a medirla sobre e5 antes de
  concluir nada de sus números.

**Y reabre una pregunta que estaba cerrada:** el `CHUNK_SIZE` de 1400 caracteres se
fijó en la 1.1 para que el dato llegara íntegro al juez, y quedó acoplado al truncado
de `api.py`. Con 512 tokens de ventana **los fragmentos podrían ser más grandes sin
volverse invisibles**. Es una variable nueva y no se tocó.

## Reproducir

```bash
cd ai-service && python ingest.py && cd ..
python scripts/medir_retrieval.py            # 28 chunks, k=6: 49/50 y 36/37
python scripts/medir_ventana_embedder.py     # 0 de 28 chunks exceden la ventana

# la configuracion recomendada: k=3
python scripts/evaluar_banco.py v14_k3_full --dos-pasos --juez llama3.2 \
    --redactor llama3.2 llama3.2 3

# la variante k=6, que filtra PREG-045
python scripts/evaluar_banco.py v14_full --dos-pasos --juez llama3.2 --redactor llama3.2

python scripts/comparar_corridas.py v110_full v14_k3_full
```

`k` es el tercer argumento posicional de `evaluar_banco.py`, después de la etiqueta y
el modelo.

## Qué decidir

**La recomendación es fusionar con `k=3`.** Es la mejor configuración medida: +4 de
sensibilidad, 0 de alucinación, y la mitad de la latencia.

**Pero `k` es un valor de producción que vive en `api.py`** (`_query_chroma(query_vec,
k=6)`), y esta rama **no lo cambió**: las corridas con `k=3` se hicieron con el
argumento del arnés. **Si se fusiona, hay que bajarlo también en `api.py`, o
producción seguiría corriendo el `k=6` que filtra.**

Las tres cosas a decidir, en orden:

1. **`k=3` o `k=6`.** Con 6 la sensibilidad es 38/50 pero hay una alucinación. Con 3
   es 34/50 y ninguna.
2. **Si la garantía de `k=3` alcanza**, sabiendo que descansa en la abstención del
   redactor y no en el juez.
3. **Bajar `k` en `api.py`** si se elige 3.
