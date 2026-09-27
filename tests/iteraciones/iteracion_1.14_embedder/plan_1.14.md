# Plan 1.14 — Cambiar el embedder: atacar el techo en vez de administrarlo

**Rama:** `iteracion_1.14_embedder`, apilada sobre `iteracion_1.10_relaciones_explicitas`
**Abierta:** 2026-09-26 · **Autorizado por el usuario:** descargar un modelo
**Leer antes:** [`hallazgo_ventana_embedder.md`](../iteracion_1.10_relaciones_explicitas/hallazgo_ventana_embedder.md)
y [`resultado_1.13.md`](../iteracion_1.13_predicados_sistematicos/resultado_1.13.md)

## Por qué esta iteración

Tres iteraciones chocaron con el mismo techo por caminos distintos:

- **1.10** ganó metiendo relaciones en los primeros 256 tokens de cada fragmento.
- **1.11** intentó eliminar la escasez promediando ventanas: `anclaje@6` llegó a
  31/37, el mejor del proyecto, y **el juez empeoró**.
- **1.13** mostró que mientras el prefijo siga escaso, **cada cosa que se agrega
  cuesta algo que ya estaba ahí** — y que *quitar* dos frases también empeora el
  retrieval.

`all-MiniLM-L6-v2` lee **256 tokens** y los fragmentos tienen mediana **382**: el
32% del corpus no influía en qué se recupera. Las palabras clave de la 1.8 y los
predicados de la 1.10 competían por el mismo espacio.

**Administrar un presupuesto escaso tiene límite. Esta iteración lo agranda.**

## El modelo, y por qué ese

`intfloat/multilingual-e5-small`.

| | MiniLM-L6-v2 | e5-small | bge-m3 |
|---|---|---|---|
| ventana | 256 tokens | **512** | 8192 |
| dimensiones | 384 | **384** | 1024 |
| tamaño | ~90 MB | **~470 MB** | ~2,2 GB |
| `trust_remote_code` | no | **no** | no |

**Las 384 dimensiones son la razón principal.** No cambia el esquema del índice, y
la divergencia de dimensiones entre indexación y consulta es una trampa que ya
costó un incidente en este proyecto.

**No se eligió el de ventana mayor a propósito.** `bge-m3` resolvería el problema
con margen enorme, pero pesa 4,7 veces más. **Correr en hardware modesto es el
objetivo del proyecto, no una restricción a superar** — un sistema que necesita
2,2 GB de embedder deja de hacer accesible la información del SII en máquinas
básicas, que es el punto.

## Los prefijos no son opcionales

La familia E5 se entrenó con prefijos asimétricos: `query: ` para lo que se busca y
`passage: ` para lo indexado. Sin ellos el modelo rinde peor porque nunca vio texto
sin prefijo. **Y usar el prefijo equivocado es peor que no usar ninguno:** invierte
la asimetría aprendida.

## Primero un refactor, y hay que verificar que sea neutro

El nombre del modelo estaba escrito a mano en **siete archivos**: `ingest.py`,
`api.py` y cinco scripts de medición. Eso es la trampa de divergencia que
`CLAUDE.md` documenta, y ya ocurrió una vez (`ingest.py` intentaba
`nomic-embed-text` con respaldo silencioso a MiniLM mientras `api.py` usaba
siempre MiniLM, coincidiendo por accidente).

Se centraliza en `ai-service/embedding.py`: el modelo y las dos funciones de
prefijo.

**El refactor va en dos pasos, y el primero es una verificación:**

1. Conectar los siete sitios al módulo, con `MODEL_NAME` en **MiniLM** y prefijos
   vacíos. Reingestar y medir. **Los números tienen que salir idénticos**
   (28 chunks, `recall@6` 48/50, `anclaje@6` 28/37). Si cambian, el refactor
   introdujo algo y no se puede atribuir nada de lo que venga después.
2. Solo entonces cambiar `MODEL_NAME` a e5-small y medir de nuevo.

Sin el paso 1, un cambio en los números sería inatribuible entre el refactor y el
modelo. **Son dos variables y hay que separarlas.**

## Medición

```bash
cd ai-service && python ingest.py && cd ..
python scripts/medir_retrieval.py
python scripts/medir_ventana_embedder.py    # la brecha debe cerrarse

python scripts/evaluar_banco.py v14_nucleo --dos-pasos --juez llama3.2 \
    --redactor llama3.2 \
    --ids PREG-010,PREG-064,PREG-065,PREG-075,PREG-080,PREG-084,PREG-088,PREG-115
python scripts/evaluar_banco.py v14_sens --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --ids @tests/dataset/dato_integro_k6_control_1.9.txt
python scripts/evaluar_banco.py v14_full --dos-pasos --juez llama3.2 --redactor llama3.2
```

**El banco completo va incluido** porque da especificidad y alucinación sobre las
50 sin respaldo en la misma corrida, y porque ya hay tres corridas completas
comparables (1.8: 25/50, 1.10: 30/50, 1.11A: 28/50).

## Controles y cortes

```
recall@6 ........  48/50
anclaje@6 .......  28/37
sensibilidad ....  30/50 (banco completo) / 23/29 (subconjunto congelado)
especificidad ...  50/50
alucinacion .....  0/50
```

**Corte:** `anclaje@6` ≥ 32/37. Es exigente a propósito: si agrandar la ventana no
mueve el retrieval de forma clara, el modelo no vale el cambio.

**Restricción que no se negocia:** nada entra si la especificidad baja de 48/50 o
la alucinación sube de 0%.

## El riesgo, y la lección de la 1.11

**Mejor retrieval no implica mejor juez.** La 1.11 lo midió: `anclaje@6` 31/37, el
mejor del proyecto, y la sensibilidad **bajó** 3 puntos con la cobertura de datos
subiendo de 61% a 77%.

**Y hay un riesgo peor, específico de las 50 sin respaldo.** La Fase 0 de la 1.9
mostró que **hacer que el contexto parezca más pertinente empuja al juez a decir
`SI` en preguntas que no tienen respaldo.** Un embedder mejor recupera contenido
más relacionado semánticamente, y varias de esas 50 son adversarias por diseño:
nombran al SII o a un trámite real para preguntar algo que el corpus no cubre.

**Ahí es donde hay que mirar primero.** La sensibilidad puede subir mucho y la
iteración fallar igual por una sola fuga.

## Lo que NO cambia esta iteración

- **El chunking.** Sigue en 1400 caracteres, acoplado al truncado de `api.py`. Una
  ventana de 512 tokens permitiría fragmentos más grandes, pero eso es otra
  variable.
- **El corpus.** Los 6 predicados de la 1.10 quedan como están.
- **El prompt del juez.** Refutado tres veces.
- **`k`.** Sigue en 6.
