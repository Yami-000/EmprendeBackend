# Plan 1.2 — Sanitización de fragments

Objetivo: Implementar filtros automáticos que limpien fragmentos recuperados antes de su inclusión en el `system` prompt para mitigar prompt injection.

Pasos:
1. Implementar función de sanitización que elimine líneas/directivas que comiencen con `You are`, `System:`, `Assistant:`, o patrones similares.
2. Añadir wrapper `SÓLO CONTEXTO:` al enviar fragments al LLM.
3. Ejecutar benchmark y medir cambios en Fidelity y Relevancia.

Criterio de éxito: Reducción comprobable de casos con Fidelity <= 3 en un 80%.
