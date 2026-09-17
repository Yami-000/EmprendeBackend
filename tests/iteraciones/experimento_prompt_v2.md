# Experimento — Prompt v2 (regla de abstención al final)

**Fecha:** 2026-09-17
**Resultado:** ❌ Fallido. Revertido.

## Hipótesis

Un modelo pequeño atiende más lo último que lee. Mover la regla de abstención
desde la posición #3 de 4 (antes del contexto) a un cierre después de los
fragmentos debería reducir la alucinación del 34% medida en el baseline.

## Cambios aplicados

1. Regla de abstención extraída de `REGLAS ABSOLUTAS` y convertida en cierre tras el contexto:

```
--- FIN DEL CONTEXTO ---

Antes de responder, verifica: ¿la respuesta está literalmente en el contexto de arriba?
- SI: responde usando solo esa información.
- NO: responde EXACTAMENTE esta frase y nada más:
"Lo siento, mi base de conocimientos actual no incluye esa información..."

No uses conocimiento propio. Si el contexto no lo dice, no lo sabes.
```

2. `num_predict`: 300 → 150.

## Resultado

| Métrica | v1 | v2 | Δ |
|---|---:|---:|---:|
| retrieval_hit@6 /50 | 44 | 44 | 0 |
| Abstención indebida (respondibles) /50 | 12 | **2** | −10 ✅ |
| Cobertura de datos verificables | 57% | **64%** | +7 ✅ |
| Abstención correcta (no respondibles) /50 | 33 | 11 | −22 🔴 |
| **Alucinación** | **34%** | **78%** | +44 🔴 |
| Fallos de generación totales | **29** | 41 | +12 🔴 |

**Neto: −12 preguntas.** La hipótesis era incorrecta.

## Por qué falló

El cierre no reforzó la abstención: reforzó el *uso del contexto*. Al colocar
"responde usando solo esa información" inmediatamente antes de generar, el
modelo empezó a **forzar** respuestas con los fragmentos que tuviera a mano.

Evidencia directa:

```
PREG-017  ¿Plazo para reclamar una Factura Electrónica?
  v1 → "Lo siento, mi base de conocimientos actual no incluye..."
  v2 → "El plazo es hasta el día 12 del mes siguiente al recibimiento."
```

El "día 12" es el vencimiento del **F29**, presente en el contexto recuperado por
otra razón. El modelo tomó un dato disponible y lo aplicó a una pregunta donde no
corresponde.

```
PREG-007  ¿Primera vs Segunda Categoría?
  v2 → "Primera Categoría son aquellos con ingresos hasta 750 UF
        (Unidades Físicas)..."
```

Umbral inventado, criterio inventado (la distinción real es capital vs. trabajo,
no monto) y sigla inventada — "Unidades Físicas" no existe.

Efecto colateral de `num_predict=150`: **12 de 100 respuestas quedaron cortadas a
media frase**.

## Errores de método

1. **Dos variables cambiadas a la vez.** No se puede atribuir el efecto al prompt
   o a `num_predict` por separado.
2. **Verificación mal escrita.** El chequeo de posición usaba
   `p.index('Contexto recuperado')`, que matchea primero la mención dentro de la
   regla #1, no el encabezado real. Para verificar posiciones hay que usar el
   marcador único `"\nContexto recuperado:"`.

## Conclusión

El modo de fallo no es de redacción del prompt. `llama3.2` (3B) no ejecuta de
forma confiable la discriminación "¿este contexto responde la pregunta?": ante
fragmentos vagamente relacionados asume que sí y fabrica. Eso es una limitación
de capacidad, y ninguna reformulación del prompt la elimina.

**Siguiente paso recomendado:** Fase 4 — modelo de 7–8B, midiendo con el mismo
arnés contra el baseline v1.

## Si se reintenta algo de prompt

Lo único que rescató valor fue la mejora en respondibles (−10 abstenciones
indebidas, +7 pts de cobertura). Si se quisiera recuperar eso sin la regresión,
probar **una sola** variable: invertir el orden de las ramas (poner primero el
caso "NO está en el contexto") y mantener `num_predict=300`.
