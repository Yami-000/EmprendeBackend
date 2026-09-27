# Resultado 1.11 — Promediar ventanas: el mejor retrieval del proyecto, y el juez aprueba menos

**Fecha:** 2026-09-26 · **Rama:** `iteracion_1.11_ventana_embedder`
**Plan:** [`plan_1.11.md`](plan_1.11.md)
**Origen:** [`hallazgo_ventana_embedder.md`](../iteracion_1.10_relaciones_explicitas/hallazgo_ventana_embedder.md)

## Veredicto

**La Variante A hace exactamente lo que prometía en retrieval, y el end-to-end va
en la dirección contraria.** No la fusiono por mi cuenta: la decisión depende de
qué métrica se considera la que manda, y eso es una decisión de proyecto, no una
lectura de los números.

```
                  control (1.10)   1.11A      corte del plan
anclaje@6 .......  28/37           31/37      >= 30/37      PASA
recall@6 ........  48/50           48/50      >= 48/50      PASA
cobertura datos .  61%             77%        --            mejora
especificidad ...  50/50           50/50      >= 48/50      PASA
alucinacion .....  0/50            0/50       0%            PASA
nucleo duro .....  5 de 8          4 de 8     --            EMPEORA
sensibilidad ....  23/29           20/29      --            EMPEORA
```

## La variable

Una función nueva en `ingest.py`. El vector de cada fragmento pasa de ser
`embed(primeros 256 tokens)` a `normalizar(media(embed(ventana)))` sobre ventanas
de ≤240 tokens con solape de 40.

**Nada del camino de consulta cambió.** Sigue habiendo un vector por fragmento, así
que `api.py`, `medir_retrieval.py` y `evaluar_banco.py` funcionan sin tocarse y
`k=6` sigue devolviendo seis fragmentos distintos. Eso es lo que permite comparar
contra el control sin ningún asterisco.

## Retrieval: funcionó, y de forma limpia

```
            recall (archivo)          anclaje (chunk)
  k         1.10   ->  1.11A          1.10   ->  1.11A
  1          26/50  ->  27/50         12/37  ->  12/37
  3          41/50  ->  42/50         22/37  ->  28/37   <- +6
  6          48/50  ->  48/50         28/37  ->  31/37   <- +3
  8          48/50  ->  48/50         30/37  ->  33/37
 10          48/50  ->  48/50         30/37  ->  34/37
```

**`anclaje@6` en 31/37 (84%) es el mejor del proyecto**, contra un máximo previo de
29/37. Y `anclaje@3` sube 6 puntos, que es el salto más grande medido en esa
métrica.

**La brecha de la ventana se cerró y se dio vuelta:**

```
anclaje@6 segun donde cae la cita      1.10        1.11A
  dentro de la ventana                 21/23 (91%)  19/23 (83%)
  fuera de la ventana                   7/14 (50%)  12/14 (86%)
```

El grupo que estaba ciego pasó de 50% a 86% —recuperó 5 preguntas: PREG-104, 105,
111, 117 y 118— y el grupo que ya veía cayó 8 puntos, perdiendo 2. **Es el
intercambio que el plan anticipó**, con saldo +3. Promediar difumina: un fragmento
que toca tres temas queda con un vector que no se parece mucho a ninguno.

**PREG-118 se recuperó**, que era la deuda abierta de la 1.10 y el punto que le
faltaba a `anclaje@6`.

## End-to-end: la dirección contraria

**Sensibilidad 23/29 → 20/29**, sobre los 29 IDs congelados del control.

```
ganadas (2) ... PREG-070, PREG-118
perdidas (5) .. PREG-073, PREG-074, PREG-075, PREG-083, PREG-114
```

**Y la cobertura de datos SUBIÓ de 0,61 a 0,77.** Llega más dato al contexto y el
juez aprueba menos. PREG-075 lo muestra sin ambigüedad: `cobertura 1,0` en las dos
configuraciones, y pasa de `SI` a `NO`.

**Núcleo duro 5 de 8 → 4 de 8**, perdiendo PREG-075.

**Especificidad 50/50 y alucinación 0/50**, intactas. La restricción que no se
negocia aguanta.

## La tensión, planteada sin resolver

**Siete vuelcos en total: 5 pérdidas y 2 ganancias.** La banda de inestabilidad del
juez ante cambios del contexto está documentada en **~6 preguntas**, y este es un
cambio del contexto: el conjunto de 6 fragmentos que recibe el juez es distinto.

Eso deja dos lecturas legítimas, y no son equivalentes:

**Lectura A — la metodología del proyecto.** `CLAUDE.md` dice: *"Decidir con
`recall@k` y `anclaje@k`, que son deterministas; el end-to-end solo confirma, y con
banda de ±6."* Bajo esa regla, 1.11A **entra**: `anclaje@6` sube 3 puntos de forma
determinista, `recall@6` no se mueve, la especificidad y la alucinación quedan
perfectas, y el −3 del end-to-end está dentro de la banda.

**Lectura B — el resultado para el usuario.** La sensibilidad es lo que el usuario
experimenta: 3 preguntas más que el bot se niega a responder teniendo el dato. Bajo
esa lectura 1.11A **no entra**, por bueno que sea el retrieval.

**No es una duda sobre los números: es una duda sobre cuál métrica manda cuando se
contradicen.** Es la primera vez en el proyecto que `anclaje@k` y la sensibilidad
apuntan en direcciones opuestas, y eso por sí solo es un resultado: **`anclaje@k`
no es un proxy suficiente del rendimiento del juez.**

Para reducir la incertidumbre con el instrumento más grande disponible se corrió el
**banco completo de 100 preguntas** en las dos configuraciones. Los números están en
[`comparacion_full.md`](comparacion_full.md).

## Lo que este resultado le enseña al proyecto

**Mejorar el retrieval medido por `anclaje@k` puede empeorar al juez.** El mecanismo
plausible: `anclaje@k` solo pregunta *"¿está la cita en alguno de los 6?"*, y no
mira **qué más** hay en esos 6. Promediar ventanas trae la cita, pero también trae
fragmentos que hacen *match* por su promedio difuso sin ser pertinentes, y el juez
—que sí lee todo el contexto— tiene más de qué dudar.

Eso sugiere una métrica que falta: **la precisión del contexto**, no solo su
cobertura. Un `anclaje@6` de 31/37 con 6 fragmentos ruidosos puede valer menos que
un 28/37 con 6 fragmentos limpios.

## Variante B, que queda sin probar

El diagnóstico apunta directo a ella: si el problema es que el promedio **difumina**,
la corrección es un **máximo** en vez de una media. Indexar una entrada por ventana,
todas apuntando al mismo fragmento, y quedarse con el mejor resultado de cada
fragmente preserva la precisión en vez de diluirla.

**Cuesta más y no se alcanzó a medir:** hay que deduplicar por fragmento padre en
`api.py::_query_chroma`, `medir_retrieval.py` y `evaluar_banco.py`, y mientras los
tres no estén alineados los números no son comparables. Es el candidato natural si
se decide seguir esta línea.

## Pendiente que requiere tu decisión

**Un embedder con ventana más grande resolvería el problema de raíz** —`all-MiniLM-L6-v2`
lee 256 tokens y los fragmentos tienen mediana 382— pero **requiere descargar un
modelo**, y eso está fuera de lo que puedo hacer sin aprobación. Queda anotado, no
ejecutado.

## Reproducir

```bash
cd ai-service && python ingest.py && cd ..
python scripts/medir_retrieval.py            # 28 chunks, 48/50, 31/37
python scripts/medir_ventana_embedder.py     # la brecha cerrada: 83% vs 86%

python scripts/evaluar_banco.py v11a_nucleo --dos-pasos --juez llama3.2 \
    --redactor llama3.2 \
    --ids PREG-010,PREG-064,PREG-065,PREG-075,PREG-080,PREG-084,PREG-088,PREG-115
python scripts/evaluar_banco.py v11a_sens --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --ids @tests/dataset/dato_integro_k6_control_1.9.txt
python scripts/evaluar_banco.py v11a_espe --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --ids @tests/dataset/sin_respaldo.txt
```
