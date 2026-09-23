# Plan 1.3 — Modelo de generación

**Prioridad:** 🔴 Alta · **Origen:** OP-3 de `iteracion_1.0_baseline/analisis_y_bifurcaciones.md`

## Objetivo

Reducir la alucinación del 34% medido en el baseline sustituyendo `llama3.2` (3B)
por un modelo de 7–8B, sin perder la capacidad de responder cuando el dato sí
está en el contexto.

## Hipótesis

El modo de fallo dominante no es de recuperación ni de redacción del prompt, sino
de capacidad: un modelo de 3B no ejecuta de forma confiable la discriminación
*"¿este contexto responde la pregunta?"*. Ante fragmentos vagamente relacionados
asume que sí y fabrica una respuesta.

**Evidencia que sostiene la hipótesis:**

- Con retrieval al 88%, el modelo aún falla 22 de 31 veces por generación.
- PREG-017: el modelo tomó el "día 12" (vencimiento del F29, presente en el
  contexto por otra razón) y lo presentó como plazo de reclamo de facturas.
- PREG-007: inventó un umbral de 750 UF, un criterio incorrecto y una sigla
  inexistente ("Unidades Físicas").
- El experimento de prompt v2 empeoró la alucinación a 78%, descartando que el
  problema sea de formulación.

## Entorno de ejecución (verificado 2026-09-22)

| Recurso | Valor |
|---|---|
| GPU | NVIDIA GTX 1650, 4096 MiB VRAM (3414 MiB libres) |
| `llama3.1:latest` | Ya descargado, 8B, **Q4_K_M** — no requiere pull |
| `qwen2.5:7b` | No descargado, ~4,7 GB — requiere pull |
| Disco disponible | 206 GB — sin restricción |

Prueba de humo con `llama3.1:latest` (3 llamadas en régimen estable, modelo ya
cargado en memoria):

```
ollama ps  ->  58%/42% CPU/GPU   (no entra completo en 4 GB de VRAM)
eval: ~8 tok/s   ~9-10s por llamada (num_predict=300, ~73 tokens generados)
```

Es **comparable al baseline** (~10,5 s/pregunta con `llama3.2:3b`, que sí corre
100% en GPU). El reparto CPU/GPU no lo vuelve inviable para este volumen de
preguntas; una corrida de 100 debería tomar ~17-20 min, en línea con las
corridas v1 y v2 (1050 s y 1122 s).

## Pasos

1. `llama3.1:latest` ya está disponible — no requiere pull. Para el segundo
   candidato: `ollama pull qwen2.5:7b`.
2. Medir cada uno sin tocar nada más del pipeline:
   ```
   python scripts/evaluar_banco.py llama8b llama3.1:latest 6 300
   python scripts/evaluar_banco.py qwen7b  qwen2.5:7b      6 300
   ```
3. Registrar latencia (`total_duration` de la respuesta de Ollama) junto a las
   métricas de calidad — no hace falta instrumentar VRAM aparte, `ollama ps`
   alcanza para confirmar el reparto CPU/GPU.
4. Comparar contra `resultados_v1.json`.

## Métricas objetivo

| Métrica | Baseline v1 | Objetivo |
|---|---:|---:|
| Alucinación (no respondibles) | 34% | **≤ 15%** |
| Abstención indebida (respondibles) | 12/50 | ≤ 12/50 |
| Cobertura de datos verificables | 57% | ≥ 65% |
| Fallos de generación totales | 29 | **≤ 15** |

## Criterio de éxito

Fallos de generación ≤ 15 **y** alucinación ≤ 15%, con latencia por consulta que
siga siendo aceptable para un bot de Telegram (referencia: ~10,5 s por pregunta
en el baseline).

## Riesgos

- **VRAM.** Confirmado: un modelo de 8B no entra completo en los 4 GB de la GPU
  de desarrollo (`llama3.1:latest`, ya en Q4_K_M, corre 58%/42% CPU/GPU). No es
  un riesgo hipotético, es el estado real. No bloquea la medición porque la
  latencia resultante (~10s/llamada) sigue siendo comparable al baseline, pero
  sí importa para producción: la máquina donde corra el bot en el futuro debe
  dimensionarse con esto en mente, o aceptar el reparto CPU/GPU.
- **Latencia.** Si sube demasiado, evaluar si el bot tolera la espera o si
  conviene reducir `k` para acortar el prompt.
- **Regresión en terminología chilena.** El system prompt prohíbe explícitamente
  términos de otros países (DNI, NIT, RUC). Verificar que el modelo nuevo los
  respete: revisar las respuestas de PREG-113 (Cédula de Identidad vs "DNI").

## Si ningún modelo alcanza el objetivo

Escalar a OP-6 — discriminación en dos pasos
(`iteracion_1.6_dos_pasos/plan_1.6.md`): una llamada que juzgue si el contexto
contiene la respuesta y, solo si es afirmativa, una segunda que la redacte.
Desacopla la discriminación de la generación, que es precisamente lo que el
modelo pequeño no logra hacer en un solo paso, a costa de duplicar la latencia.
