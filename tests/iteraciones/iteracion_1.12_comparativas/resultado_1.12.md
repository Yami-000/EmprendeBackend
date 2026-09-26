# Resultado 1.12 — La taxonomía del prompt no era la causa, y la descomposición sí sirve

**Fecha:** 2026-09-26 · **Rama:** `iteracion_1.12_comparativas`, apilada sobre la 1.10
**Plan:** [`plan_1.12.md`](plan_1.12.md)

## Veredicto

**La hipótesis de la iteración está refutada, y de la forma más limpia posible: el
cambio no tuvo *ningún* efecto.** Pero la sonda que se corrió para decidir qué
seguía dejó validada la premisa de **B2 (descomponer la pregunta)** en 2 de las 3.

```
ampliar la taxonomía del prompt del juez ....  0 de 3     corte >= 2   NO PASA
descomponer la pregunta (sonda) .............  2 de 3     premisa validada
```

No se corrieron las puertas de especificidad ni sensibilidad: el plan las
condiciona a la primera, y con 0 de 3 no hay nada que confirmar.

## Lo que se probó

Una entrada nueva en `JUEZ_PROMPT_BASES` de `api.py`, `estricto_taxonomia`.
**Verificado programáticamente: una sola línea difiere de `estricto`.**

```
antes    (cifra, plazo, nombre de institución, definición, procedimiento)

después  (cifra, plazo, nombre de institución, definición, procedimiento,
          comparación entre dos figuras, o delimitación de qué organismo
          interviene y cuál no)
```

`estricto` no se modificó. La variante convive con ella y se selecciona con
`--juez-prompt estricto_taxonomia`, así que el control se puede volver a correr sin
revertir nada.

## El resultado: efecto exactamente nulo

```
python scripts/evaluar_banco.py v12_tres --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --juez-prompt estricto_taxonomia \
    --ids PREG-010,PREG-064,PREG-084

sensibilidad: 0/3
```

Y la sonda de descomposición, corrida con **las dos** variantes del prompt, dio
**resultados idénticos en los 9 juicios**:

```
                                      estricto   estricto_taxonomia
PREG-010  original                       NO            NO
          "¿Qué institución otorga la patente municipal?"      SI            SI
          "¿Qué trámites se realizan en el SII?"               NO            NO
PREG-064  original                       NO            NO
          "¿Qué caracteriza a una SA Cerrada?"                 NO            NO
          "¿Qué caracteriza a una SA Abierta?"                 NO            NO
PREG-084  original                       NO            NO
          "¿Qué responsabilidad tienen los socios gestores?"   SI            SI
          "¿Qué responsabilidad tienen los socios comanditarios?" SI         SI
```

**No es que ampliar la lista sea insuficiente: es que el juez no está usando esa
lista para decidir.** Nueve juicios, dos prompts distintos, cero diferencias. Si la
enumeración pesara aunque fuera un poco, algo se habría movido.

Eso **refuta la hipótesis y refuerza el callejón sin salida**: tocar el texto del
prompt del juez no mueve estos casos. Ya son tres intentos independientes —
`flexible` (1 de 8), un juez de 7B (0 de 8), y ahora la taxonomía (0 de 3).

## Lo que sí quedó demostrado

**Con el MISMO contexto y el MISMO prompt, el juez aprueba las subpreguntas y
rechaza la pregunta compuesta.**

- **PREG-084: descomposición completa.** Las dos subpreguntas dan `SI`. Los dos
  datos están en el contexto y el juez los reconoce por separado; lo que no puede
  es responder *"¿cuál es la diferencia?"*.
- **PREG-010: descomposición parcial, pero en el lado que importa.** *"¿Qué
  institución otorga la patente municipal?"* da `SI`. La otra mitad (*"¿qué
  trámites se realizan en el SII?"*) da `NO`, que es correcto: el contexto
  recuperado con la pregunta original no trae la lista de trámites del SII.
- **PREG-064 no se arregla descomponiendo.** Y hay una explicación independiente:
  **su cita de anclaje cae fuera de la ventana de 256 tokens del embedder** (está en
  la lista de 14 de `medir_ventana_embedder.py`), así que el fragmento que la
  contiene se recupera por carambola y el tramo que el juez lee no es el que tiene
  el dato. **Es un problema de retrieval disfrazado de problema de juez.**

**El mecanismo, en una línea:** el juez de 3B puede verificar un hecho a la vez.
No puede verificar una relación entre dos hechos, aunque los dos estén delante y el
prompt se lo permita explícitamente. No es la instrucción: es la tarea.

## Qué hacer con esto

**B2 (descomponer la pregunta) tiene la premisa validada y vale implementarlo**,
pero no se hizo esta noche porque es un cambio de arquitectura y tiene un costo que
alguien tiene que aceptar:

- **Una llamada más al modelo por consulta.** El end-to-end de una consulta
  respondida ya está en ~28 s, y la latencia es una tensión abierta del proyecto.
- **Hay que decidir quién descompone.** Un modelo que genera subpreguntas es texto
  fuera del corpus, y eso es el modo de fallo que mató la Fase 0 de la 1.9. La
  variante segura es descomponer **solo para el juez**, no para el retrieval ni para
  el redactor, de modo que no pueda tocar la especificidad.
- **El techo es acotado y ya se sabe cuál es:** de las 8 del núcleo duro original,
  la 1.10 recuperó 5 y de las 3 restantes esta sonda dice que 2 responden a la
  descomposición. **Compra 2 preguntas por una llamada extra en las 100.**

**PREG-064 no entra en ese techo:** su problema es la ventana del embedder, y le
corresponde a la línea de la 1.11.

## Lo que NO hay que volver a proponer

- **Editar el texto del prompt del juez para estos casos.** Tres refutaciones
  independientes. La sonda con dos prompts dando 9 juicios idénticos es la más
  contundente: el prompt no es la variable.
- **Reformular la pregunta del usuario para que parezca otra cosa.** No es lo mismo
  que descomponer. Ya está refutado por PREG-065 en la 1.9, y la sonda no lo
  contradice: lo que funciona no es reescribir la pregunta, es **partirla en dos
  juicios independientes** y combinar los veredictos fuera del modelo.

## Reproducir

```bash
python scripts/evaluar_banco.py v12_tres --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --juez-prompt estricto_taxonomia \
    --ids PREG-010,PREG-064,PREG-084

python scripts/sonda_descomposicion.py estricto
python scripts/sonda_descomposicion.py estricto_taxonomia
```

La sonda recupera el contexto con la pregunta **original** y solo cambia lo que se
le pregunta al juez, de modo que aísla la forma de la pregunta del retrieval. Las
subpreguntas están escritas a mano en el script y **el banco no se toca**: son
instrumento de diagnóstico, no una versión nueva del conjunto de prueba.

## Nota de método

La corrida completa de la configuración 1.10 (`v110_full`) se lanzó desde esta
rama. `api.py` acá tiene la entrada `estricto_taxonomia` agregada, pero **una
corrida que selecciona `estricto` no puede verse afectada por una entrada de
diccionario que no lee**: el número es válido como control de la 1.10.
