# Plan 1.6 — Discriminación en dos pasos

**Prioridad:** 🟡 Media, mueve a Alta tras la iteración 1.3 · **Origen:** OP-6
**Depende de:** iteración 1.0 (baseline) e iteración 1.3 (modelo de generación) —
ver nota de dependencia al final.

## Objetivo

Reducir la alucinación separando en dos llamadas lo que hoy se le pide al
modelo en una sola: decidir si el contexto recuperado responde la pregunta
**y** redactar la respuesta.

## Hipótesis

El fallo no está en la redacción, está en la discriminación previa. La
iteración 1.3 midió tres modelos (3B, 7B, 8B) con el mismo arnés y el mismo
banco de 100 preguntas, y el patrón se repitió en los tres tamaños:

| | v1 (3B) | llama3.1 (8B) | qwen2.5 (7B) |
|---|---:|---:|---:|
| Alucinación | 34% | 32% | 42% |
| Fallos de generación | 29 | 21 | 26 |

Escalar el modelo mejoró la extracción cuando el modelo *sí* tenía el dato
(abstención indebida 12→5, cobertura +11-12 pts) pero no movió la alucinación
de forma consistente — en el peor caso (qwen 7B) la empeoró. Y no es el mismo
conjunto de preguntas el que falla: con cada modelo aparecen alucinaciones
nuevas que v1 no tenía (5 con el 8B, 11 con qwen).

Dos ejemplos concretos de la 1.3 ilustran el mecanismo:

- **qwen2.5 (7B), "¿Diferencia entre Liquidación y Giro?"** — responde que la
  liquidación *"la realiza la empresa"* (es al revés, la emite el SII) e
  inventa que un giro es *"un cambio temporal en la tasa impositiva"* (no
  existe ese concepto). Estructura y tono de respuesta técnica correcta,
  contenido falso en las dos mitades.
- **llama3.1 (8B), "¿Qué tribunal es competente...?"** — inventa una
  institución que no existe: *"Tribunal de Controversias Tributarias (TCT)"*.

En ningún caso el modelo "no supo redactar". En los dos casos decidió mal si
tenía la información, y hacia allá se dirige el remedio.

**Por qué separar el juicio ayuda:** juzgar "¿este contexto contiene la
respuesta a esta pregunta?" con salida binaria es una tarea mucho más simple
que juzgar y redactar a la vez. Un modelo de 3B, que falla en la tarea
combinada, puede ser suficientemente confiable en la tarea aislada.

## Diseño

Pipeline de dos llamadas:

1. **Juez** — recibe la pregunta y el contexto recuperado (los mismos 6
   fragmentos de siempre). Responde exclusivamente `SI` o `NO`, sin
   elaboración. `num_predict` bajo (≤5 tokens) para forzar la brevedad y
   reducir el costo de esta llamada casi a cero.
2. **Redactor** — solo se invoca si el juez dijo `SI`. Usa el
   `_build_system_prompt` actual de `api.py`, sin cambios.
   Si el juez dijo `NO`, se devuelve directo la frase canónica de abstención
   **sin** segunda llamada al modelo — más rápido que el pipeline actual en
   ese camino, no solo más seguro.

### Matriz de combinaciones a probar

| Experimento | Juez | Redactor | Por qué |
|---|---|---|---|
| A (principal) | `llama3.2:3B` | `llama3.2:3B` | Aísla el efecto de la arquitectura, sin cambiar tamaño de modelo — comparación limpia contra v1 |
| B (si A funciona) | `llama3.2:3B` | `llama3.1:8B` | Combina un juicio barato y rápido con la mejor capacidad de extracción medida en 1.3 |

Empezar por A. B solo si A reduce la alucinación de forma clara — si A no
funciona, el problema no es la arquitectura de dos pasos y B no lo va a
arreglar.

## Especificación técnica de implementación

Esta sección va antes de "Pasos" porque los reemplaza en detalle: firmas de
función, formato de datos y orden de trabajo ya definidos, para implementar
sin tener que rediseñar nada.

### 0. Prerrequisito — traer los fixes de la 1.3 a esta rama

Esta rama sale de `main` **sin** el PR #3 (iteración 1.3) mergeado todavía.
`scripts/evaluar_banco.py` aquí tiene los dos bugs que se corrigieron allá:

1. `main()` se ejecuta al importar el módulo, sin guard.
2. La lista `ABST` no reconoce rechazos razonados ("no se especifica en el
   contexto"), solo la frase canónica.

**No cherry-pickear el commit `1642f1f`** — trae mezclados los resultados de
los modelos 8B/qwen de la 1.3, que no pertenecen a esta rama. Reaplicar los
dos fixes a mano, son ~10 líneas:

```python
# Al final del archivo, reemplazar la llamada suelta a main():
if __name__ == "__main__":
    main()
```

```python
# En la lista ABST, agregar:
        "no se especifica", "no se menciona", "no se indica",
        "no está especificado", "no se detalla", "no proporciona"
```

### 1. Cambios en `ai-service/api.py`

**1.1 — Extraer la frase de abstención a una constante.**

Hoy vive hardcodeada dentro de la regla #3 de `_build_system_prompt`. El
camino "el juez dijo NO" de esta iteración necesita la frase exacta, sin
mantener una segunda copia que pueda divergir:

```python
FRASE_ABSTENCION = (
    "Lo siento, mi base de conocimientos actual no incluye esa información "
    "específica sobre las normativas del SII."
)
```

Y en `_build_system_prompt`, la regla #3 pasa a interpolar la constante en vez
de tener el texto suelto:

```python
3. Si la respuesta NO está en el contexto, di EXACTAMENTE: "{FRASE_ABSTENCION}"
```

Debe producir el system prompt **byte-idéntico** al actual para el modo de un
paso — es un refactor de extracción, no un cambio de comportamiento. Verificar
con un diff de `_build_system_prompt(frags)` antes/después sobre el mismo
input.

**1.2 — Nueva función `_build_judge_prompt(fragments)`.**

Mismo patrón que `_build_system_prompt`: recibe los fragmentos ya recuperados
(no vuelve a consultar ChromaDB), arma un prompt de juicio binario, estricto y
sin la carga de reglas de terminología chilena (esas son del redactor, no del
juez — un prompt más corto reduce la superficie de fallo del juez mismo).

```python
def _build_judge_prompt(fragments):
    base = ("Eres un verificador estricto. Tu única tarea es decidir si el "
            "CONTEXTO de abajo contiene la información necesaria para "
            "responder la PREGUNTA de forma completa y específica.\n\n"
            "Reglas:\n"
            "- Responde con UNA sola palabra: SI o NO.\n"
            "- Responde SI solo si el contexto menciona explícitamente el "
            "dato pedido (cifra, plazo, nombre de institución, definición, "
            "procedimiento), no solo un tema relacionado o parecido.\n"
            "- Responde NO si el contexto trata un tema similar pero no "
            "contiene el dato específico que pide la pregunta.\n"
            "- Ante cualquier duda, responde NO.\n"
            "- No expliques tu respuesta. No agregues nada más que SI o NO.")
    ctx_lines = ["\nCONTEXTO:"]
    for i, f in enumerate(fragments, 1):
        src = f.get("metadata", {}).get("source", "")
        doc = f.get("document", f.get("page_content", ""))
        snippet = doc.replace("\n", " ")[:1400]
        ctx_lines.append("[%d] Fuente: %s\n%s\n" % (i, src, snippet))
    return base + "\n" + "\n".join(ctx_lines)
```

La pregunta del usuario se manda igual que hoy, como mensaje `user` separado
del `system` — no hace falta meterla dentro del prompt.

Exportar ambos símbolos nuevos junto al existente:
```python
from api import _build_system_prompt, _build_judge_prompt, FRASE_ABSTENCION
```

### 2. Cambios en `scripts/evaluar_banco.py`

**2.1 — CLI.** El actual es posicional (`etiqueta modelo k num_predict`) y ya
está al límite de lo que un `sys.argv` posicional puede manejar con claridad.
Pasar a `argparse`, manteniendo compatibilidad: `python evaluar_banco.py v1`
solo (sin flags) debe comportarse exactamente igual que hoy.

```python
import argparse

ap = argparse.ArgumentParser()
ap.add_argument("etiqueta")
ap.add_argument("--modelo", default="llama3.2", help="modelo unico (modo un paso)")
ap.add_argument("--k", type=int, default=6)
ap.add_argument("--num-predict", type=int, default=300)
ap.add_argument("--dos-pasos", action="store_true", help="activa el pipeline juez+redactor")
ap.add_argument("--juez", default=None, help="modelo juez (default: --modelo si no se especifica)")
ap.add_argument("--redactor", default=None, help="modelo redactor (default: --modelo si no se especifica)")
ap.add_argument("--num-predict-juez", type=int, default=5)
args = ap.parse_args()
```

**2.2 — Helper `llamar_ollama`.** Hoy el bloque `httpx.post(...)` con su
try/except está escrito una sola vez porque solo hay una llamada por pregunta.
Con dos pasos se repite tres veces (un paso / juez / redactor) — extraer:

```python
def llamar_ollama(modelo, system_prompt, pregunta, num_predict):
    t0 = time.time()
    try:
        r = httpx.post(OLLAMA, timeout=180, json={
            "model": modelo, "stream": False,
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": pregunta}],
            "options": {"temperature": 0.0, "top_p": 0.1,
                        "num_predict": num_predict, "num_ctx": 4096}})
        texto = r.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        texto = "<<ERROR: %s>>" % e
    return texto, time.time() - t0
```

**2.3 — Parseo del juicio.** Fail-safe hacia NO (abstención), nunca hacia SI
(alucinación) ante ambigüedad — es el mismo principio que ya rige el resto del
arnés:

```python
def parse_juicio(texto):
    t = texto.strip().upper()
    if re.match(r"^\s*(SI|SÍ)\b", t):
        return True
    return False   # NO, vacio, error o ambiguo -> tratar como NO
```

**2.4 — Rama de dos pasos en el loop principal.** Dentro del `for i, p in
enumerate(d, 1):`, después de obtener `frags`/`got` (sin cambios en
retrieval):

```python
if args.dos_pasos:
    juez_modelo = args.juez or args.modelo
    redactor_modelo = args.redactor or args.modelo

    juicio_txt, juez_lat = llamar_ollama(
        juez_modelo, _build_judge_prompt(frags), p["pregunta"], args.num_predict_juez)
    dijo_si = parse_juicio(juicio_txt)

    if dijo_si:
        ans, redactor_lat = llamar_ollama(
            redactor_modelo, _build_system_prompt(frags), p["pregunta"], args.num_predict)
    else:
        ans, redactor_lat = FRASE_ABSTENCION, 0.0
else:
    ans, _lat = llamar_ollama(args.modelo, _build_system_prompt(frags), p["pregunta"], args.num_predict)
    juicio_txt = dijo_si = juez_lat = redactor_lat = None
```

**2.5 — Campos nuevos en el registro por pregunta.** Se agregan sin romper los
que ya existen (todo lo demás igual: `id`, `pregunta`, `respondible`,
`esperado`, `recuperado`, `retrieval_hit`, `abstuvo`, `anclas`, `anclas_ok`,
`cobertura`, `respuesta`):

```python
res.append({
    # ...campos existentes sin cambios...
    "modo": "dos_pasos" if args.dos_pasos else "un_paso",
    "juez_respuesta": juicio_txt,
    "juez_dijo_si": dijo_si,
    "juez_latencia_s": round(juez_lat, 2) if juez_lat is not None else None,
    "redactor_latencia_s": round(redactor_lat, 2) if redactor_lat is not None else None,
})
```

`abstuvo` se sigue calculando igual (`abstuvo(ans)`) — cuando el juez dijo NO,
`ans` es literalmente `FRASE_ABSTENCION`, así que `abstuvo()` la reconoce sin
cambios.

**2.6 — Reporte agregado.** Agregar después del bloque de impresión actual,
solo si `args.dos_pasos`:

```python
if args.dos_pasos:
    sens = sum(1 for x in R if x["juez_dijo_si"]) / len(R)          # sensibilidad
    espe = sum(1 for x in N if not x["juez_dijo_si"]) / len(N)      # especificidad
    lat_juez = [x["juez_latencia_s"] for x in res if x["juez_latencia_s"] is not None]
    lat_red = [x["redactor_latencia_s"] for x in res if x["redactor_latencia_s"]]
    print()
    print("JUEZ")
    print("  sensibilidad (SI en respondibles) .... %3.0f%%" % (100*sens))
    print("  especificidad (NO en no-respondibles) . %3.0f%%" % (100*espe))
    print("  latencia media juez ................... %.1fs" % (sum(lat_juez)/len(lat_juez)))
    if lat_red:
        print("  latencia media redactor (camino SI) ... %.1fs" % (sum(lat_red)/len(lat_red)))
```

### 3. Plan de pruebas antes de correr el banco completo

Las corridas completas de la 1.3 tomaron 37-42 min cada una. Antes de lanzar
cualquiera de las dos completas:

1. **Prueba unitaria de `parse_juicio`** — sin tocar Ollama: casos
   `"SI"`, `"Sí, el contexto..."`, `"no"`, `"No estoy seguro"`, `""`,
   `"<<ERROR: ...>>"` → confirmar que solo los dos primeros dan `True`.
2. **Diff de `_build_system_prompt`** antes/después del refactor 1.1, mismo
   input, para confirmar que es byte-idéntico.
3. **Smoke test de 5 preguntas** (2-3 respondibles, 2-3 no respondibles),
   revisando a mano `juez_respuesta` y `respuesta` de cada una antes de
   comprometerse a una corrida de 100.
4. Recién ahí, correr el experimento A completo:
   ```bash
   python scripts/evaluar_banco.py dospasos_A --dos-pasos --juez llama3.2 --redactor llama3.2
   ```

### 4. Checklist de archivos

- [ ] `scripts/evaluar_banco.py` — fixes de la 1.3 reaplicados (paso 0)
- [ ] `ai-service/api.py` — `FRASE_ABSTENCION`, `_build_judge_prompt`
- [ ] `scripts/evaluar_banco.py` — argparse, `llamar_ollama`, `parse_juicio`, rama de dos pasos, campos nuevos, reporte de sensibilidad/especificidad
- [ ] Prueba unitaria de `parse_juicio` (puede ser un script suelto en el scratchpad, no hace falta un framework de tests para esto)
- [ ] Smoke test de 5 preguntas revisado a mano
- [ ] Corrida completa experimento A → `resultados_dospasos_A.json`
- [ ] `tests/iteraciones/iteracion_1.6_dos_pasos/resultado_1.6.md` con el mismo formato que `resultado_1.3.md`

No se toca `ai-service/ingest.py` ni el chunking/retrieval en ninguna parte de
esta iteración — la hipótesis es puramente sobre la etapa de generación, y
mantener retrieval sin cambios es lo que permite comparar `retrieval_hit@6`
1:1 contra v1, 8B y qwen7B de la 1.3.

## Métrica nueva: precisión del juez

Además de las métricas de siempre (alucinación, fallos de generación,
abstención indebida, cobertura), esta iteración mide algo que las anteriores
no separaban:

| | Definición |
|---|---|
| Sensibilidad del juez | De las 50 respondibles, ¿en cuántas dijo `SI`? |
| Especificidad del juez | De las 50 no respondibles, ¿en cuántas dijo `NO`? |

Esto expone directamente si el juez resuelve la discriminación mejor que el
modelo combinado, independiente de cómo redacte después.

## Pasos

Ver "Especificación técnica de implementación" más arriba para el detalle
completo (firmas de función, CLI, formato de datos, orden de trabajo). Resumen
de alto nivel:

1. Implementar el pipeline de dos llamadas (secciones 0-2 de la especificación).
2. Probar (sección 3): unitario de `parse_juicio`, diff del prompt refactorizado,
   smoke test de 5 preguntas.
3. Correr experimento A completo y medir sensibilidad/especificidad del juez
   **por separado** del resultado end-to-end — no solo el número agregado, es
   lo que va a decir si el pipeline resuelve la discriminación o la esconde.
4. Si el juez es confiable pero la alucinación end-to-end no baja tanto como
   se esperaba, revisar si el redactor sigue fallando en casos donde el juez
   acertó (el redactor tiene sus propios problemas, medidos en la 1.3).
5. Comparar contra `resultados_v1.json`, `resultados_llama8b.json` y
   `resultados_qwen7b.json`.
6. Si el experimento A cumple el objetivo, correr experimento B (juez 3B +
   redactor 8B) y, si también cumple, portar la lógica de dos pasos a
   `ai-service/api.py` — el endpoint de producción, no solo el arnés de
   evaluación. Este paso 6 queda fuera del alcance de la especificación técnica
   de arriba porque es condicional a los resultados, no parte del diseño base.

## Métricas objetivo

| Métrica | Baseline v1 | Objetivo |
|---|---:|---:|
| Alucinación | 34% | **≤ 15%** |
| Especificidad del juez | — (no medida antes) | **≥ 80%** |
| Abstención indebida | 12/50 | **≤ 8/50** |
| Fallos de generación totales | 29 | **≤ 12** |

El objetivo de abstención indebida es más exigente que el de la iteración 1.3
(≤12) porque un juez confiable no debería sacrificar respondibles para
reducir alucinación — si lo hace, está siendo conservador en vez de preciso,
y eso hay que verlo en la métrica de sensibilidad, no ocultarlo detrás de un
buen número de alucinación.

## Criterio de éxito

Alucinación ≤ 15% **y** especificidad del juez ≥ 80% **y** abstención
indebida ≤ 8/50, con latencia total (dos llamadas cuando el juez dice `SI`,
una cuando dice `NO`) que siga siendo aceptable para un bot de Telegram.

## Riesgos

- **El juez hereda el mismo problema, un nivel arriba.** Si el juez también
  falla en discriminar (dice `SI` a contexto irrelevante), el pipeline de dos
  pasos no gana nada sobre el actual. Es el riesgo central de esta hipótesis
  y la razón de medir sensibilidad/especificidad por separado en vez de
  confiar solo en el número end-to-end.
- **Latencia variable.** El camino `NO` es más rápido que hoy (sin segunda
  llamada); el camino `SI` es más lento (dos llamadas en serie). El promedio
  depende de la proporción real de preguntas respondibles que reciba el bot
  en producción, no solo del banco de prueba (que es 50/50 por diseño).
- **Parseo de la salida del juez.** Forzar `SI`/`NO` estricto con un LLM no
  es 100% confiable — puede responder con texto adicional pese a
  `num_predict` bajo. Definir un parseo tolerante (buscar `SI`/`NO` al inicio
  de la respuesta, tratar ambigüedad como `NO` por seguridad — fallar hacia
  la abstención, no hacia la alucinación).

## Nota de dependencia

Detalle exacto y bloque de código listo para reaplicar en la sección
"0. Prerrequisito" de la especificación técnica, más arriba. Resumen: esta
rama salió de `main` sin el PR #3 (iteración 1.3) mergeado, así que
`scripts/evaluar_banco.py` aquí no tiene el guard de `main()` ni el detector
de abstención con las frases de rechazo razonado. Verificar el estado del PR
antes de ejecutar cualquier medición — no antes de implementar el diseño.
