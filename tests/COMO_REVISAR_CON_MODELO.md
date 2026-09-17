# Cómo Revisar el Banco de Preguntas con un Modelo Pesado

## Resumen

Se han preparado dos archivos para que hagas una revisión exhaustiva del banco de 100 preguntas:

1. **`revision_preguntas_prompt.md`** — Prompt completo y estructura de análisis
2. **`preguntas_para_revision.txt`** — Listado legible de las 100 preguntas

## Paso 1: Prepara el contexto

Reúne estos documentos que el modelo necesitará consultar:

```
ai-service/docs/sii/
├── tipos_sociedad_chile.md
├── obligaciones_tributarias_y_tipos_sociedad.md
├── constitucion_empresa_simplificada.md
├── constitucion_empresa_tradicional.md
├── costos_y_plazos_formalizacion.md
├── documentacion_formalizacion.md
├── formularios_tributarios_chile.md
├── inicio_actividades_formalizacion_sii.md
├── inicio_actividades_sii.md
├── patente_municipal.md
├── permisos_complementarios.md
├── planificacion_formalizacion.md
└── tipos_empresa_decision.md
```

Estos 13 archivos SON los únicos que el agente RAG tiene disponibles. El modelo pesado debe verificar si las preguntas pueden realmente contestarse con esta información.

## Paso 2: Ejecuta la revisión en etapas

### Opción A: Revisión en paralelo (MÁS RÁPIDO)

Divide el banco en 5 grupos:

```
# Grupo 1: PREG-001 a PREG-020
# Grupo 2: PREG-021 a PREG-040
# Grupo 3: PREG-041 a PREG-060
# Grupo 4: PREG-061 a PREG-080
# Grupo 5: PREG-081 a PREG-100
```

Para cada grupo, usa este prompt:

```
[Incluye el contenido de revision_preguntas_prompt.md]

AHORA ANALIZA SOLO ESTAS PREGUNTAS:
PREG-001 a PREG-020

[Proporciona el contenido de preguntas_para_revision.txt filtrado a este rango]
```

### Opción B: Revisión completa en una pasada (MÁS EXHAUSTIVO)

1. Proporciona `revision_preguntas_prompt.md` al modelo
2. Proporciona `preguntas_para_revision.txt` completo
3. Proporciona el contenido de los 13 archivos .md
4. Ejecuta en modelo con contexto extendido (Opus o Sonnet)

## Paso 3: Espera el resultado esperado

El modelo debe entregar:

### 1. Tabla de análisis (CSV o Markdown):

```
| ID | Pregunta | Clasificación Actual | Verificación | Problema | Recomendación |
|----|----------|----------------------|--------------|----------|----------------|
```

### 2. Resumen por categoría:

```
## Información General (5 preguntas)
- Respondible: 4/5
- No respondible: 1/5
- Errores encontrados: 0
```

### 3. Listado de problemas críticos:

```
🔴 CRÍTICOS (Mover entre categorías):
- PREG-XXX: Está marcada como Respondible pero info no existe
- PREG-YYY: Está marcada como No respondible pero info SÍ existe

🟡 MEDIOS (Ajustar criterios):
- PREG-ZZZ: Criterio demasiado amplio/específico
```

### 4. Estadísticas:

```
- Total verificadas: 100
- Correctas: 95
- Con error: 5
- Ambiguas: 2
- % Precisión: 95%
```

## Paso 4: Aplica cambios

Una vez recibas el análisis:

1. **Para problemas CRÍTICOS:** Remueve la pregunta o cámbiala de categoría
2. **Para problemas MEDIOS:** Ajusta el criterio_esperado
3. **Para problemas MENORES:** Mejora la redacción

## Recursos útiles

- **Archivo JSON completo:** `tests/dataset/banco_preguntas_respuestas.json`
- **Documentos a consultar:** `ai-service/docs/sii/`
- **Archivos de prueba:** `tests/dataset/banco_preguntas.json` (solo id + pregunta)

## Modelos recomendados

- ✅ **Claude Opus 5** (mejor opción, máximo contexto)
- ✅ **Claude Sonnet 5** (equilibrio speed/quality)
- ✅ **GPT-4 Turbo** (alternativa)
- ❌ Evita: modelos pequeños (<70B parámetros) para esta tarea

## Ejemplo de entrada para el modelo

```
[Incluir contenido de revision_preguntas_prompt.md]

[Incluir listado de preguntas de preguntas_para_revision.txt]

Archivos disponibles para el agente:
1. tipos_sociedad_chile.md — [contenido]
2. obligaciones_tributarias_y_tipos_sociedad.md — [contenido]
... (los 13 archivos)

Por favor, analiza TODAS las preguntas y verifica si están correctamente clasificadas.
```

## Tiempo estimado

- Revisión completa (100 preguntas, 13 documentos): **15-20 minutos** con Opus
- Revisión en 5 grupos paralelos: **5-8 minutos** por grupo

## Próximos pasos después de la revisión

1. Consolidar cambios en `banco_preguntas_respuestas.json`
2. Regenerar `banco_preguntas.json` (solo id + pregunta)
3. Ejecutar las 100 preguntas contra el agente RAG
4. Comparar resultados vs. clasificación revisada
