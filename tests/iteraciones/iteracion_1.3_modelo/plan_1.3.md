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

## Pasos

1. Descargar candidatos: `ollama pull qwen2.5:7b` y `ollama pull llama3.1:8b`.
   Ambos tienen mejor desempeño documentado en español que `llama3.2:3b`.
2. Medir cada uno sin tocar nada más del pipeline:
   ```
   python scripts/evaluar_banco.py qwen7b   qwen2.5:7b  6 300
   python scripts/evaluar_banco.py llama8b  llama3.1:8b 6 300
   ```
3. Registrar latencia y consumo de VRAM junto a las métricas de calidad.
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

- **VRAM.** Un modelo de 7–8B puede no caber en la máquina de desarrollo. Si
  ocurre, medir con cuantización `q4_K_M` antes de descartar.
- **Latencia.** Si sube demasiado, evaluar si el bot tolera la espera o si
  conviene reducir `k` para acortar el prompt.
- **Regresión en terminología chilena.** El system prompt prohíbe explícitamente
  términos de otros países (DNI, NIT, RUC). Verificar que el modelo nuevo los
  respete: revisar las respuestas de PREG-113 (Cédula de Identidad vs "DNI").

## Si ningún modelo alcanza el objetivo

Escalar a un enfoque de dos pasos: una llamada que juzgue si el contexto contiene
la respuesta y, solo si la respuesta es afirmativa, una segunda que la redacte.
Duplica la latencia pero desacopla la discriminación de la generación, que es
precisamente lo que el modelo pequeño no logra hacer en un solo paso.
