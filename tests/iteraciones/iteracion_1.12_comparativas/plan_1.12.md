# Plan 1.12 — La enumeración del prompt del juez no admite comparaciones

**Rama:** `iteracion_1.12_comparativas`, apilada sobre `iteracion_1.11_ventana_embedder`
**Abierta:** 2026-09-26 · **Origen:** las 3 preguntas que resistieron a la 1.10
**Leer antes:** [`resultado_fase2.md`](../iteracion_1.10_relaciones_explicitas/resultado_fase2.md)

## El problema

Tres preguntas del núcleo duro no se recuperan con predicados, **y no es
retrieval**: el predicado les llega al contexto, en el **puesto 1** en dos de ellas,
y el juez dice `NO` igual.

```
PREG-064  "¿Qué diferencia existe entre una SA Cerrada y una SA Abierta?"      puesto 5
PREG-084  "¿Cuál es la diferencia entre los tipos de socios...?"               puesto 1
PREG-010  "¿...se gestiona directamente en el SII o en otra institución?"      puesto 1
```

Dos son **comparativas** y una es **disyuntiva**.

## La hipótesis

Está en una línea del prompt `estricto`, en `api.py`:

```
Responde SI solo si el contexto menciona explícitamente el dato pedido
(cifra, plazo, nombre de institución, definición, procedimiento),
no solo un tema relacionado o parecido.
```

**La enumeración no incluye comparaciones ni delimitaciones.** Una *"diferencia
entre A y B"* no es una cifra, ni un plazo, ni un nombre de institución, ni una
definición, ni un procedimiento. Tampoco lo es *"en el SII o en otra institución"*,
que pide elegir entre dos alternativas.

**El juez está aplicando la lista al pie de la letra.** Es el mismo patrón que
explicó el núcleo duro en la 1.9: no es incapacidad, es obediencia a una
instrucción que excluye lo que la pregunta necesita.

Eso predice el detalle que más llama la atención de la 1.10: que el predicado esté
en el **puesto 1** y no sirva. Si el problema fuera de recuperación o de
legibilidad, el puesto 1 tendría que bastar. Si el problema es que el tipo de dato
no está en la lista de tipos admitidos, el puesto es irrelevante.

## Por qué esto NO es "aflojar el prompt del juez", que está refutado

Hay que ser explícito, porque a primera vista se parece al callejón sin salida.

La variante `flexible` (A2), refutada dos veces —1.6 y 1.9, recupera 1 de 8—
cambia **tres cosas** a la vez:

1. quita *"Ante cualquier duda, responde NO"*,
2. admite que el dato esté *"redactado con otras palabras"*,
3. admite que esté *"repartido entre varios fragmentos"*.

Esas tres aflojan el **umbral de certeza**, y eso es lo que destruye la
especificidad.

Esta iteración **no toca el umbral**. Conserva *"Ante cualquier duda, responde NO"*
y conserva la exigencia de mención explícita. Solo amplía la **taxonomía de tipos
de dato** para que incluya dos que el banco pregunta y la lista omite. El umbral
sigue siendo el mismo: el dato tiene que estar explícito, solo que ahora una
comparación explícita cuenta como dato.

**Si esta distinción no se sostiene en los números, la iteración falla y se
documenta como refuerzo del callejón.** Es exactamente lo que hay que medir.

## Variante única — `estricto_taxonomia`

Se agrega una entrada a `JUEZ_PROMPT_BASES` en `api.py`. **Una sola línea cambia**
respecto de `estricto`:

```
antes    (cifra, plazo, nombre de institución, definición, procedimiento)

después  (cifra, plazo, nombre de institución, definición, procedimiento,
          comparación entre dos figuras, o delimitación de qué organismo
          interviene y cuál no)
```

Todo lo demás, idéntico. Incluido el sesgo hacia `NO`.

`estricto` **no se modifica**: la variante nueva convive con ella y se selecciona
con `--juez-prompt estricto_taxonomia`, igual que `flexible`. Así el control se
puede volver a correr sin revertir nada.

## Medición

```bash
# 1) las 3 que resisten, ~1 min. Es la prueba mas barata posible.
python scripts/evaluar_banco.py v12_tres --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --juez-prompt estricto_taxonomia \
    --ids PREG-010,PREG-064,PREG-084

# 2) solo si recupera >=2 de 3: ESPECIFICIDAD PRIMERO, ~20 min.
#    Va antes de la sensibilidad a proposito: es la restriccion que no se
#    negocia y es el modo de fallo conocido de tocar este prompt.
python scripts/evaluar_banco.py v12_espe --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --juez-prompt estricto_taxonomia \
    --ids @tests/dataset/sin_respaldo.txt

# 3) solo si la especificidad aguanta: sensibilidad sobre los 29 congelados
python scripts/evaluar_banco.py v12_sens --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --juez-prompt estricto_taxonomia \
    --ids @tests/dataset/dato_integro_k6_control_1.9.txt
```

**El orden invierte el de las iteraciones anteriores, y es deliberado.** En la 1.10
la especificidad iba última porque el cambio era en el corpus y el riesgo era bajo.
Acá el cambio es en el prompt del juez, y la Fase 0 de la 1.9 ya mostró que tocar
ese prompt puede llevar la especificidad de 50/50 a 0/50. **No tiene sentido medir
la sensibilidad de una variante que no puede entrar.**

**Corte de la puerta 1:** recuperar ≥ 2 de 3.
**Corte de la puerta 2, que no se negocia:** especificidad ≥ 48/50 y alucinación 0%.

## Controles

Dependen de lo que resulte de la 1.11, que está midiéndose en paralelo. Se fijan al
abrir la medición, del `resultado` de la 1.11 o, si la 1.11 no entra, de la 1.10:

```
las 3 que resisten ....  0 de 3
especificidad .........  50/50
alucinacion ...........  0/50
sensibilidad ..........  23/29 (1.10) o el numero que deje la 1.11
```

## Riesgos

- **El principal: la especificidad.** Ampliar lo que cuenta como dato puede hacer
  que el juez acepte contextos que solo *rozan* la pregunta. Las 50 sin respaldo lo
  detectan y por eso van segundas.
- **Contaminación entre variables.** Si la 1.11 entra, esta iteración se mide encima
  de ella y hay que decir contra qué control se compara. Las ramas están apiladas
  precisamente para que eso quede trazable.
- **`temperature=0` no garantiza estabilidad ante cambios del prompt.** El juez es
  determinista ante el *mismo* contexto y prompt (0 vuelcos en dos corridas
  idénticas, 1.10 Fase 1), pero cambiar el prompt mueve ~6 veredictos. Decidir con
  las 3 dirigidas y la especificidad, no con diferencias de 1 en la sensibilidad.

## Si falla

Queda **B2** del plan 1.9: descomponer la pregunta en subpreguntas antes del juez.
La expectativa ya está ajustada — solo 3 de las 8 originales eran compuestas, y son
casualmente estas mismas. Es la vía natural si la taxonomía no alcanza, porque
*"¿cuál es la diferencia entre A y B?"* se descompone en *"¿qué caracteriza a A?"* y
*"¿qué caracteriza a B?"*, que sí son preguntas por definiciones — un tipo que la
lista **sí** admite.
