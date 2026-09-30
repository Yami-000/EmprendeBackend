# Resultado 2.0 — El pipeline de dos pasos en producción, verificado por el endpoint

**Fecha:** 2026-09-30 · **Rama:** `iteracion_2.0_dos_pasos_produccion`

## Veredicto

**Portado y verificado.** `/chat` sirve el pipeline de dos pasos, y **la verificación se
hizo a través del endpoint**, que es lo que nunca se había hecho en 16 iteraciones.

```
                            arnes      endpoint     diferencia
abstuvo indebidamente ....  13/50       14/50          1
ALUCINACION .............    0/50        0/50          0
errores de transporte ...      --           0
latencia por consulta ...      --       7,4 s de media, 17,6 s de pico
```

**99 de 100 preguntas dan el mismo resultado.** La única que difiere es PREG-117, y es
honesto decir cuál: una de las tres que solo pasan por la **descomposición**, o sea el
mecanismo más nuevo y más marginal. Está dentro de la banda de ±6 del juez.

## Por qué esta iteración existía

Todo lo medido en 16 iteraciones era del **arnés de evaluación**. `api.py` servía `/chat`
de un paso, que alucina **34%**. El bot que usaba la gente no tenía el juez, ni la
abstención, ni el 0% de alucinación.

Y la razón por la que pasó desapercibido tanto tiempo está en el propio método:
`evaluar_banco.py` **replicaba** el pipeline consultando ChromaDB y Ollama directamente,
en vez de hablar con el endpoint. Medía una implementación paralela.

## Lo que se agregó a `api.py`

```
NUM_PREDICT_JUEZ = 5          el juez solo dice SI o NO
parse_juicio()                el veredicto, con fail-safe hacia NO
_juzgar()                     una llamada NO streameada al juez
decidir_si_responder()        el juez + la descomposicion como segunda oportunidad
_sse_texto()                  un texto suelto con la forma que el bot ya parsea
```

Y en `chat_endpoint`, antes de construir el prompt del redactor:

```python
if not await decidir_si_responder(fragments, payload.query):
    # el camino NO no llama al modelo
    return StreamingResponse(solo_abstencion(), media_type="text/event-stream")
```

## Cuatro decisiones de diseño

**1. El bot no se tocó.** Se leyó primero el contrato de *streaming* de `src/bot.js`:
separa por líneas, quita el prefijo `data: `, intenta `JSON.parse` y usa
`message.content`, con *fallback* a texto plano. El camino de abstención emite **ese
mismo sobre**, así que para el bot se ve igual que una respuesta — solo que sin modelo
detrás.

**2. El camino `NO` no llama al modelo.** Devuelve `FRASE_ABSTENCION` directo. Es lo que
hace al pipeline de dos pasos **más rápido** que el de un paso cuando rechaza, y se ve en
la latencia medida: 7,4 s de media contra los ~10,3 s que daba el cálculo del arnés,
porque las 64 preguntas que se abstienen cuestan una sola llamada.

**3. El juez falla hacia la abstención.** Si Ollama se cae o da error en la llamada del
juez, `decidir_si_responder` devuelve `False`. En normativa tributaria callar es el fallo
aceptable; responder sin haber verificado, no.

**4. Timeout propio para el juez, más corto.** Emite 5 tokens: si tarda más de 60 s algo
está mal, y conviene abstenerse antes de que el bot llegue a su propio timeout y muestre
*"el servicio no respondió"*.

## Dos duplicaciones eliminadas, y por qué importaban

Al portar el juez aparecieron dos funciones **en `api.py` y en el arnés a la vez**:

- **`parse_juicio`** — el criterio con que se lee el veredicto.
- **`abstuvo` y su lista `ABST`** — el detector sobre el que se calculan la alucinación y
  la abstención indebida.

**Si esas copias divergieran, el arnés mediría un criterio distinto del que usa
producción para decidir** — exactamente el problema que esta iteración corrige. Ahora
viven en `api.py` y el arnés las importa. `abstuvo` quedó junto a `FRASE_ABSTENCION`
porque depende de ella: la primera entrada de la lista es un fragmento de esa frase.

## La herramienta que faltaba desde el principio

**`scripts/evaluar_endpoint.py`** mide el banco **hablando HTTP con `/chat`**, y parsea el
SSE **replicando el parseo de `src/bot.js`**. Si el endpoint emitiera algo que el bot no
entiende, este script lo vería igual que el bot.

Es explícito sobre su límite: **no puede medir sensibilidad ni especificidad del juez**,
porque desde afuera no se distingue *"el juez dijo `NO`"* de *"el juez dijo `SI` y el
redactor abstuvo igual"*. Para eso sigue haciendo falta el arnés. **Son complementarias,
no sustitutas.**

## Reproducir

```bash
cd ai-service && python ingest.py && cd ..

# dejar el endpoint corriendo
cd ai-service && uvicorn api:app --host 0.0.0.0 --port 11400

# en otra terminal
python scripts/evaluar_endpoint.py prod_2.0
python scripts/evaluar_banco.py v16_full --dos-pasos --descomponer \
    --juez llama3.2 --redactor llama3.2 llama3.2 3
```

Las dos corridas deberían coincidir en alucinación y diferir a lo sumo en un par de
preguntas en abstención indebida.

## Lo que queda

- **La especificidad del juez sigue en 49/50**, y el 0% de alucinación descansa en que el
  redactor abstiene en PREG-045. Portar el pipeline **no cambió eso**: sigue siendo la
  garantía más frágil del sistema.
- **El fallback ante fallo de Ollama** todavía devuelve el contexto recuperado en crudo al
  usuario, no una respuesta. Es deuda anterior a esta iteración y sigue abierta.
- **Historial:** el redactor recibe el historial que manda el bot (6 mensajes), pero **el
  juez no**. Es deliberado —juzga el contexto contra la pregunta actual— pero no se midió
  si una pregunta que depende del historial se juzga peor por eso.
