# Resultado 2.1 — El veto de preguntas compuestas, y una abstención que ayuda

**Fecha:** 2026-09-30 · **Rama:** `iteracion_2.1_compuestas`

## Veredicto

**Entra.** Tapa una fuga de alucinación **reproducible y determinística** reportada desde
Telegram, y **no cuesta nada** en el banco: cero vuelcos en 100 preguntas.

```
                            control 2.0    v21_veto     diferencia
abstuvo indebidamente ....    14/50         14/50           0
ALUCINACION .............      0/50          0/50           0
errores de transporte ...         0             0            0
latencia por consulta ...       7,4 s         6,8 s       -0,6 s
```

**Cero vuelcos, pregunta por pregunta.** No es que el saldo empate ocultando una pérdida
y una ganancia: **ninguna de las 100 preguntas cambió de resultado**. Y el mecanismo lo
confirma por dentro — ver *"El veto se disparó 0 veces"* más abajo.

## El fallo que originó la iteración

Reportado desde Telegram. Cuatro abstenciones seguidas y a la quinta una respuesta
inventada:

```
"Que es el sii?"                        -> se abstiene   (correcto)
"¿Que es el servicio de impuestos       -> RESPONDE, e inventa
 internos (SII) y cual es su mision
 institucional?"
```

La respuesta afirmaba que el SII se encarga de *"la recaudación de los ingresos
públicos"*. Eso no está en el corpus **y además es falso**: el SII gira los impuestos, la
Tesorería los recauda. Es exactamente la confusión que PREG-045 testea.

**El diagnóstico fue el contrario de lo que parecía.** A primera vista el problema eran
las cuatro abstenciones —un juez demasiado severo— y la quinta respuesta parecía el
sistema por fin funcionando. Al revisarlo contra el corpus resultó que **las cuatro
abstenciones eran correctas** (ninguna de esas preguntas tiene respaldo) y **la única
falla era la quinta**.

Eso cambió la decisión de diseño: bajar la severidad del juez habría "arreglado" cuatro
aciertos y dejado la fuga intacta.

## El mecanismo, aislado

`scripts/sonda_compuestas.py` —nuevo— usa el retrieval real (k=3) y le pregunta al juez
la compuesta y cada mitad por separado. Con 3 repeticiones cada una:

```
pregunta                                                    juez x3
¿Qué es el SII?                                              NO NO NO
¿Cuál es su misión institucional?                            NO NO NO
¿Qué es el SII y cuál es su misión institucional?            NO NO NO
¿Qué es el servicio de impuestos internos (SII) y            SI SI SI   <- LA FUGA
 cuál es su misión institucional?
 ... la misma, escrita sin tildes                            NO NO NO
¿Qué es el RUT y cuál es su misión?                          NO NO NO
¿Qué es la Tesorería y cuál es su función?                    NO NO NO
```

**En una pregunta compuesta el juez puede aprobar el conjunto mientras rechaza las dos
mitades.** Es el espejo del caso comparativo de la 1.16: allí exigía las dos y fallaba;
aquí le basta una, y ni siquiera eso — aprueba el conjunto con **ambas** mitades en `NO`.

## Dos cosas que hay que decir sobre esta evidencia

**1. La fuga reproduce en 1 de 7 variantes, no en 4.** Una versión anterior del comentario
en `api.py` daba como fugas también la forma corta del SII y la variante con `RUT`. **No
reproducen.** El caso es determinístico —3 de 3— pero es **uno**: esto tapa una fuga
verificada, no una clase de fugas cuantificada. El comentario quedó corregido.

**2. La fuga depende de la ortografía de la pregunta.** Con el **mismo trío de documentos
recuperados**, la forma con tildes da `SI` y la misma sin tildes da `NO`. No es la
inestabilidad de ~6 de 50 ya documentada —cada variante es determinística por separado—
sino **sensibilidad al texto de la pregunta**. Queda como riesgo abierto: significa que
hay fugas equivalentes que no encontramos porque no escribimos la variante correcta.

## Por qué un veto y no una conjunción

Lo natural sería exigir que **las dos** mitades den `SI`. Arregla la fuga y **rompe una
pregunta legítima del banco**:

```
caso                      juez   mitades   conjuncion   veto
la fuga del SII            SI     NO, NO      NO         NO   arregla
PREG-019                   SI     SI, NO      NO !       SI   conserva
PREG-062/107/109/115       SI     SI, SI      SI         SI   conserva
```

**PREG-019** —*"¿Qué es el Formulario 29 (F29) y qué obligaciones tributarias principales
se declaran en él?"*— tiene una segunda mitad que no se sostiene sola y **hoy se responde
bien**. La conjunción la perdería.

El veto solo actúa cuando **ninguna** mitad se verifica, que es cuando la aprobación del
compuesto no se apoya en nada.

## El veto se disparó 0 veces en 100 preguntas

La traza del pipeline (`logs/traza.log`, nueva en esta iteración) permite auditar el
mecanismo por dentro, no solo el saldo:

```
consultas ................................ 100
el juez aprobo ............................ 35
de esas, compuestas ........................ 5
  con al menos una mitad verificable ....... 5   -> se conservan
  con las dos mitades en NO ................ 0   -> ninguna vetada
rescates por descomposicion comparativa .... 2
```

**Esto es lo que hace defendible el cambio.** El costo cero no es un empate de suerte: el
veto no tuvo ocasión de equivocarse porque las 5 compuestas que el juez aprobó tenían
respaldo real en al menos una mitad. Y de las 13 preguntas del banco que encajan en el
patrón, **las 6 sin respaldo ya se abstienen antes**, por el juez.

> ⚠️ **Estos cinco números salen de la traza, y la traza no se versiona** (`logs/` está
> en `.gitignore`). La medición de registro es
> `tests/iteraciones/resultados_endpoint_v21_veto.json`, que sí está en el repositorio y
> es la que sostiene los cero vuelcos. Para reconstruir el desglose hay que volver a
> correr `evaluar_endpoint.py` con el servicio arriba y contar sobre `logs/traza.log`:
>
> ```bash
> grep -c "es compuesta: se comprueba" logs/traza.log   # compuestas aprobadas
> grep -c "VETO" logs/traza.log                         # vetadas
> ```

## Lo que entró, y dónde

| Cambio | Archivo | Por qué ahí |
|---|---|---|
| `partir_compuesta()` + veto | `ai-service/api.py` | lógica de decisión, junto al juez |
| `AYUDA_ABSTENCION` | `ai-service/api.py` (endpoint) | **no** en el system prompt: es presentación |
| `es_saludo()` / `BIENVENIDA` | `ai-service/api.py` | corta antes del retrieval |
| Traza legible | `ai-service/traza.py` | ventana en vivo, la abre `iniciar.bat` |
| Sonda de compuestas | `scripts/sonda_compuestas.py` | reproduce el aislamiento |

### La abstención ahora dice qué sí se puede preguntar

El texto de ayuda va **como sufijo** de `FRASE_ABSTENCION`, no en su lugar. Es
deliberado: `abstuvo()` detecta un fragmento de esa frase, y **sobre ese detector se
calculan la alucinación y la abstención indebida de las 19 iteraciones**. Reemplazar la
frase habría roto la comparabilidad de todo el histórico.

Y va en el **endpoint**, no en el system prompt: meterlo en el prompt cambiaría lo que el
redactor genera, que es una variable medida.

### Los saludos no consultan al modelo

`"hola"` costaba ~7 s de juez para nada y respondía con la frase de abstención, que es la
peor primera impresión posible. La comparación es sobre el **texto completo** normalizado,
no por subcadena: `"hola"` saluda, pero `"hola, cuánto cuesta una SpA?"` sigue al pipeline.
Verificado que **ninguna de las 100 preguntas del banco** cae en la lista.

## Tres errores propios, y cómo se detectaron

**1. Se invalidó una medición desde dentro.** Se reinició uvicorn **en medio** de la corrida
del banco para cargar la traza. Las consultas que cayeron en esa ventana dieron error de
conexión, y `evaluar_endpoint.py` **cuenta un error de transporte como abstención**. Los
números habrían salido sesgados hacia el lado bueno sin que se notara. Se descartó y se
relanzó limpia. El campo `errores de transporte = 0` de la corrida buena es lo que lo
certifica.

**2. La traza se entrelazaba.** Con dos consultas en vuelo las líneas de ambas se mezclaban.
Se reescribió para acumular cada consulta y volcarla **entera** al cerrarse. El costo es que
el bloque aparece cuando la consulta termina. Los identificadores, además, se derivaban de
la hora en milisegundos y colisionaban — justo el caso que el id existe para distinguir.

**3. El `TIEMPO` de la traza mentía justo en el caso que importa.** Se cerraba antes de
llamar al redactor, así que una consulta **respondida** reportaba solo lo que tardó en
*decidir* y dejaba fuera la redacción, que es la parte lenta. Una consulta medida en 31,8 s
reales aparecía como 15 s. Se detectó comparando la traza contra el tiempo de pared desde
el cliente, no leyéndola: la traza sola era internamente coherente y no tenía con qué
delatarse. Ahora se cierra dentro del *stream* y la última línea dice cómo terminó —
`LISTO`, `ABSTIENE`, `SALUDO`, `FALLBACK` o `ERROR`.

El `FALLBACK` es el que más interesa vigilar: es el camino en que Ollama falla y el
usuario recibe **el contexto recuperado en crudo**. Es deuda anterior a la 2.0 y hasta
ahora era invisible.

## Reproducir

```bash
cd ai-service && python ingest.py && cd ..
cd ai-service && uvicorn api:app --host 0.0.0.0 --port 11400   # dejar corriendo

python scripts/sonda_compuestas.py --reps 3          # el mecanismo, ~1 min
python scripts/evaluar_endpoint.py v21_veto          # el banco, ~11 min
```

La sonda debe dar `SI SI SI` **solo** en la forma larga con tildes, y `veto: ANULA el SI`.

## Lo que queda abierto

- **La fuga sensible a la ortografía.** Hay probablemente más variantes que aprueban el
  compuesto y no encontramos. El veto las cubriría a todas *si* encajan en el patrón
  `" y " + interrogativo`; las que no, no.
- **El patrón es léxico.** Una compuesta unida por coma, punto y coma o `"además"` no se
  parte. No se midió cuántas hay porque el banco tiene 13 y todas usan `" y "`.
- **La especificidad del juez sigue en 49/50** y el 0% de alucinación sigue descansando en
  que el redactor abstiene en PREG-045. El veto **no toca eso**.
- **El historial no llega al juez.** Sigue sin medirse si una pregunta que depende del
  historial se juzga peor por eso. La conversación de Telegram que originó esto tenía
  cuatro turnos previos, y el juez no los vio: **no se puede descartar que el historial
  influyera en la respuesta del redactor**, aunque el veredicto sí se reprodujo sin él.
- **La traza escribe la pregunta del usuario en claro** a un archivo local. Sirve para
  desarrollar. Con usuarios reales hay que decidir qué se guarda y por cuánto tiempo.
