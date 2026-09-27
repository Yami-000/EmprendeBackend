# Resultado 1.13 — El mecanismo no era sobreajuste, y el presupuesto de 256 tokens es el techo

**Fecha:** 2026-09-26 · **Rama:** `iteracion_1.13_predicados_sistematicos`
**Plan:** [`plan_1.13.md`](plan_1.13.md) (leer el addendum: hubo un desvío del diseño)

## Veredicto

**Pasa el corte, y responde la pregunta que motivó la iteración: el mecanismo de la
1.10 no depende de haber elegido las palabras mirando el banco.**

```
                  control (1.10)   1.13        corte
nucleo duro .....  5 de 8          5 de 8      --
sensibilidad ....  23/29           23/29       no bajar    PASA
especificidad ...  50/50           50/50       >= 48/50    PASA
alucinacion .....  0/50            0/50        0%          PASA
recall@6 ........  48/50           47/50       no bajar    -1
anclaje@6 .......  28/37           27/37       --          -1
anclaje@1 .......  12/37           13/37       --          +1
```

## La pregunta de método que resolvía

Los 6 predicados de la 1.10 **se escribieron mirando las 8 preguntas del banco.**
Eso es ajustar al conjunto de prueba, y la 1.8 lo había evitado a propósito
(*"elegirlas mirando el banco de preguntas sería ajustar al conjunto de prueba"*,
en `ingest.py`).

Hacía falta saber si el +5 de la 1.10 era el **mecanismo** —declarar la relación—
o **haber acertado las palabras**.

## Lo que se hizo

`scripts/generar_predicados.py` convierte filas de tabla en frases-predicado con
plantillas derivadas de los **encabezados de cada tabla**, nunca del banco. Las
frases quedan como salen, torpes incluidas —*"La EIRL admite 1 socios"*, *"El
trámite de Total estimado cuesta"*— porque retocarlas mirando qué se pregunta sería
volver al cherry-picking.

**Dos pasadas, y la segunda es un desvío del plan (ver addendum):**

| pasada | predicados | índice | recall@6 | decisión |
|---|---|---|---|---|
| las 33 filas | 33 | **31 chunks** | **45/50** | cortada sin gastar end-to-end |
| `--solo-si-cabe` | 20 | 28 chunks | 47/50 | medida completa |

La regla `--solo-si-cabe` aplica la conversión a una tabla **solo si el archivo
conserva su número de fragmentos**. Decide por el **conteo de fragmentos**, nunca
por qué preguntas mejoran, así que sigue siendo ciega al banco. Selecciona 20 y
omite 13.

## Resultado 1 — los predicados ciegos son neutros

**Sensibilidad 23/29, idéntica a la 1.10.** Agregar 18 predicados mecánicos más (2
de los 20 duplican relaciones que la 1.10 ya declaraba) **no ayuda ni daña**.

Eso responde la mitad de la pregunta: **el mecanismo tolera aplicarse a ciegas y en
escala.** No mejora porque ninguna de las preguntas que aún fallan necesita esas
relaciones — las que fallan son las comparativas y las que tienen la cita fuera de
la ventana del embedder.

## Resultado 2 — la prueba directa del sobreajuste

La mitad que faltaba: **¿sirven los predicados porque declaran la relación, o porque
elegí las palabras?**

Se quitaron los **2 predicados escritos a mano** para PREG-080 y PREG-088, dejando
solo las versiones **mecánicas** de esas mismas filas de tabla:

```
a mano      La Notaría elabora la escritura pública de constitución del régimen
            tradicional: el notario público es el responsable de su elaboración.

mecánico    La institución Notaría se encarga de: escritura pública de
            constitución (régimen tradicional).
```

```
            1.13   sin las escritas a mano   retrieval_hit@6
PREG-088     SI            SI                     True
PREG-080     SI            NO                     False   <- no llega el documento
```

**PREG-088 sigue aprobando con solo el predicado mecánico.** La redacción elegida a
mano **no era necesaria**: alcanza con que el corpus afirme la relación en alguna
forma. Es la evidencia más directa de que el mecanismo no era sobreajuste.

**PREG-080 no es concluyente**, y hay que decirlo: su `retrieval_hit@6` es `False`,
es decir **el documento no se recupera**. Es un fallo de retrieval, no del juez, y
no se puede atribuir a la redacción del predicado.

**Conclusión honesta: la prueba es limpia en 1 de 2 casos, y en ese caso sale a
favor del mecanismo.** Solo esas dos se podían probar así, porque los otros cuatro
predicados de la 1.10 no son filas de tabla y el generador no los cubre.

## Resultado 3 — el techo real: el prefijo de 256 tokens es un presupuesto escaso

**El retrieval baja 1 punto aunque el chunking no se rompa**, y quitar dos frases lo
baja **2 puntos más**:

```
                                      recall@6   anclaje@6
1.10 (6 predicados) ................   48/50      28/37
1.13 (20 predicados, 28 chunks) ....   47/50      27/37
1.13 sin las 2 escritas a mano .....   45/50      25/37
```

Que **quitar** texto también empeore descarta la explicación fácil ("más texto
diluye"). El mecanismo es otro: **los predicados van al inicio de cada sección, que
es exactamente el espacio que la 1.8 usa para las palabras clave.** Los primeros 256
tokens de cada fragmento son un presupuesto fijo, y ahora hay dos inquilinos
compitiendo por él. Mover cualquier cosa ahí reordena lo que el embedder ve.

Eso conecta las tres iteraciones de la noche en un solo diagnóstico:

- **1.10** ganó metiendo relaciones en ese prefijo.
- **1.11** intentó eliminar la escasez promediando ventanas: el retrieval mejoró
  (`anclaje@6` 31/37, el mejor del proyecto) y el juez empeoró.
- **1.13** muestra que, mientras el prefijo siga siendo escaso, **cada cosa que se
  agregue cuesta algo que ya estaba ahí.**

**El presupuesto de 256 tokens es el techo estructural del retrieval de este
proyecto**, y las tres iteraciones chocaron con él por caminos distintos.

## Lo que no se midió

- **La corrida completa de 100 preguntas** de esta configuración. Las tres puertas
  alcanzan para la decisión de fusión y la noche se terminó.
- **Corregir la gramática de las frases torpes.** Si esto se fusiona, el corpus lo
  leen personas además del modelo y *"La EIRL admite 1 socios"* es mala prosa.
  Arreglarlo es **una variable más** y hay que medirlo aparte: el texto que cambia
  es texto indexado.

## Reproducir

```bash
python scripts/generar_predicados.py --ver --solo-si-cabe    # revisar
python scripts/generar_predicados.py --aplicar --solo-si-cabe

cd ai-service && python ingest.py && cd ..
python scripts/medir_retrieval.py       # 28 chunks, 47/50, 27/37

python scripts/evaluar_banco.py v13_nucleo --dos-pasos --juez llama3.2 \
    --redactor llama3.2 \
    --ids PREG-010,PREG-064,PREG-065,PREG-075,PREG-080,PREG-084,PREG-088,PREG-115
python scripts/evaluar_banco.py v13_sens --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --ids @tests/dataset/dato_integro_k6_control_1.9.txt
python scripts/evaluar_banco.py v13_espe --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --ids @tests/dataset/sin_respaldo.txt
```

La prueba de sobreajuste (`resultados_v13_sinmano.json`) se corrió quitando a mano
las dos frases de la sección *Instituciones* en
`obligaciones_tributarias_y_tipos_sociedad.md` y reingestando. **Esa configuración
no está en la rama**: se revirtió, porque baja el retrieval 2 puntos.

## Qué decidir

**Si fusionar esto es opcional, y la razón es interesante.** No mejora ninguna
métrica: empata la sensibilidad y baja `recall@6` en 1. Lo que aporta es
**metodológico** — deja demostrado que la 1.10 no era sobreajuste — y **el corpus
queda más completo** para preguntas que el banco no hace.

Contra fusionarlo: `recall@6` baja 1 punto y las frases están mal redactadas.

**La recomendación es fusionar el script y la documentación, y decidir aparte si
entra el corpus convertido.** El valor de esta iteración es haber medido, no el
texto que generó.
