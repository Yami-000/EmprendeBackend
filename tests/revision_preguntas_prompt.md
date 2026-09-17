# PROMPT DE REVISIÓN - Banco de Preguntas SII (100 preguntas)

## CONTEXTO Y OBJETIVO

Se ha creado un banco de 100 preguntas para evaluar un agente RAG (Retrieval Augmented Generation) que asesora sobre formalización de empresas y trámites tributarios ante el SII (Servicio de Impuestos Internos) de Chile.

**Objetivo de tu análisis:** Verificar si la clasificación de cada pregunta es correcta:
- **Respondibles (primeras 52):** Deben poder contestarse con información disponible en los documentos
- **No respondibles (últimas 48):** No deben poder contestarse con información disponible (diseñadas para detectar alucinaciones)

---

## DOCUMENTOS DISPONIBLES PARA EL AGENTE

El agente tiene acceso ÚNICAMENTE a estos 13 documentos en `ai-service/docs/sii/`:

1. `tipos_sociedad_chile.md` — 9 tipos de empresa (EIRL, SRL, SpA, SA, etc.) con tabla comparativa
2. `obligaciones_tributarias_y_tipos_sociedad.md` — Combinado: tipos, costos, obligaciones, regímenes
3. `constitucion_empresa_simplificada.md` — Régimen simplificado (Tu Empresa en un Día)
4. `constitucion_empresa_tradicional.md` — Régimen tradicional con notaría
5. `costos_y_plazos_formalizacion.md` — Costos en CLP y plazos de trámites
6. `documentacion_formalizacion.md` — Documentos requeridos por tipo de empresa
7. `formularios_tributarios_chile.md` — F29, F50, F22, DTE
8. `inicio_actividades_formalizacion_sii.md` — Proceso de inicio de actividades
9. `inicio_actividades_sii.md` — Detalles del trámite en línea
10. `patente_municipal.md` — Patente municipal y municipalidad
11. `permisos_complementarios.md` — Permisos sanitarios, bomberos, etc.
12. `planificacion_formalizacion.md` — Decisiones previas a formalizar
13. `tipos_empresa_decision.md` — Cuadro comparativo para elegir estructura

**NO tiene acceso a:**
- Código Tributario completo
- Leyes específicas (Ley 19.749, 21.234, etc.)
- Procedimientos administrativos avanzados (RAV, RAF)
- Tasas de retención específicas
- Información económica dinámica (UF, cotizaciones)
- Cambios normativos post-2024

---

## ESTRUCTURA DE CADA PREGUNTA EN EL ARCHIVO

```json
{
  "id": "PREG-001",
  "categoria": "informacion_general",
  "pregunta": "¿Qué es el Servicio de Impuestos Internos (SII)?",
  "criterio_esperado": "Debe mencionar que es...",
  "tipo": "factual|conceptual|procedimiento|normativa|sancion|delimitacion|adversarial|tecnico",
  "ground_truth": {
    "md_origen": "nombre del archivo .md donde se encuentra",
    "seccion": "Sección del documento donde está la información",
    "cita_anclaje": "Fragmento exacto del documento",
    "respuesta_esperada": "Lo que el agente debe responder"
  }
}
```

---

## TAREA PARA TI

Analiza TODAS las 100 preguntas y verifica:

### Para cada pregunta (hazlo pregunta por pregunta):

1. **Verificación de presencia en documentos:**
   - ¿La información para responder esta pregunta existe realmente en los documentos listados arriba?
   - ¿La `cita_anclaje` proporcionada es relevante para la pregunta?
   - ¿O está la información en un documento que no fue incluido?

2. **Evaluación de clasificación:**
   - ¿Una pregunta está marcada como "respondible" (primeras 52) pero NO tiene información disponible?
   - ¿Una pregunta está marcada como "no respondible" (últimas 48) pero SÍ tiene información disponible?

3. **Criterios de respondibilidad:**
   - Para que sea **RESPONDIBLE**: El agente debe poder encontrar información específica y concreta en los documentos
   - Para que sea **NO RESPONDIBLE**: Requiere información que no está en los documentos disponibles
   - **Caso gris**: Si la pregunta puede ser parcialmente contestada o requiere inferencia, marca como "AMBIGUA"

4. **Recomendaciones:**
   - Si hay error en la clasificación, sugiere moverla a la otra categoría
   - Si la pregunta está bien formulada pero el `criterio_esperado` es incorrecto, sugiérelo
   - Si la `cita_anclaje` no es relevante, proporciona una alternativa

---

## FORMATO DE SALIDA ESPERADO

Crea una tabla con este formato:

| ID | Pregunta (resumen) | Clasificación Actual | Verificación | Problema Identificado | Recomendación |
|---|---|---|---|---|---|
| PREG-001 | ¿Qué es el SII? | Respondible | ✅ Correcta | Ninguno | Mantener |
| PREG-055 | ¿Cotización 2030? | No respondible | ✅ Correcta | Ninguno | Mantener |
| PREG-XXX | [Ejemplo malo] | Respondible | ❌ FALSA | Info no está en docs | MOVER a No respondible |

---

## SECCIONES A CUBRIR

### Resumen ejecutivo (al final):
- Total preguntas verificadas: 100
- Preguntas correctamente clasificadas: X
- Preguntas con error de clasificación: Y
- Preguntas ambiguas que requieren ajuste: Z
- % de precisión actual: (100-Y)/100

### Por categoría (agrupa por `categoria`):
- Información General
- Tipos de Empresa
- Formalización y Costos
- Obligaciones Tributarias
- Facturación Electrónica
- Contabilidad
- Instituciones
- Normativa General
- Gestión Interna
- Out of Scope

---

## INSTRUCCIONES FINALES

1. Analiza pregunta por pregunta (todas 100)
2. Sé riguroso: si hay duda, revisa el documento completo
3. Identifica patrones de error (si hay categorías con más errores)
4. Proporciona cambios específicos, no solo comentarios
5. Al final, clasifica cada problema encontrado por **severidad**:
   - 🔴 CRÍTICO: Pregunta totalmente mal clasificada
   - 🟡 MEDIO: Clasificación parcialmente correcta pero criterio débil
   - 🟢 MENOR: Pequeño ajuste en redacción

**Entrega:** Lista completa de análisis + tabla resumen + recomendaciones por severidad.
