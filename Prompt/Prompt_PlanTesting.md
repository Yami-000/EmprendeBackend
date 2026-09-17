# ROL Y OBJETIVO
Actúa como Ingeniero de Software Principal y Especialista en MLOps/QA. Tu tarea es formalizar e institucionalizar el protocolo de pruebas del chatbot en este repositorio.

Debes generar un documento maestro llamado `METODOLOGIA_TESTING.md`, crear la estructura de carpetas inicial bajo `tests/` y actualizar la documentación viva (`CONTEXTO.md` y `Bitacora.md`) para reflejar este marco de experimentación.

---

### ESPECIFICACIONES DE LA METODOLOGÍA A DOCUMENTAR

#### 1. Marco de Evaluación Multidimensional (Métricas Cuantitativas)
Cada respuesta evaluada se puntuará en una escala numérica de **1 a 10** (donde 1 es completamente inaceptable/pésimo y 10 es rendimiento óptimo/perfecto), además de las métricas duras de telemetría:

1. **Fidelidad al Contexto (Faithfulness) [Escala 1 - 10]:**
   - *1-3:* Alucinación crítica o contradicción directa del contexto recuperado.
   - *4-7:* Respuesta plausible pero incorpora afirmaciones externas no respaldadas por los `.md`.
   - *8-10:* Respaldo total y trazable contra los fragmentos de contexto inyectados (cero alucinación).

2. **Relevancia y Precisión (Answer Relevance) [Escala 1 - 10]:**
   - *1-3:* Respuesta evasiva, fuera de foco o ignora la consulta directa.
   - *4-7:* Responde parcialmente pero añade redundancias o divaga.
   - *8-10:* Respuesta directa, concisa y orientada a la necesidad del usuario.

3. **Recuperación Vectorial (Context Recall) [Escala 1 - 10]:**
   - *1-3:* ChromaDB trajo fragmentos irrelevantes que no contienen la respuesta esperada.
   - *4-7:* Trajo parte de la información, pero omitió fragmentos clave presentes en los `.md`.
   - *8-10:* Trajo exactamente los fragmentos necesarios dentro de los top-k.

4. **Rendimiento Operativo y Latencia:**
   - **Latencia Total por Respuesta:** Medida en segundos desde el envío en Telegram hasta el despacho del último carácter.
   - **Timeouts:** Umbral máximo de 60 segundos (peticiones superiores se marcan como fallo crítico).

5. **Consumo de Hardware del Host:**
   - **Pico y Promedio de RAM (MB):** Monitoreo agregado de Node.js, FastAPI y Ollama.
   - **Pico de VRAM (MB):** Monitoreo vía `nvidia-smi` (o memoria compartida en entornos sin GPU dedicada).

*Criterio de Aprobación Global (Gate de Calidad):* Promedio $\ge 8.0/10$ en las tres dimensiones de contenido, latencia media $< 15$ s y 0 timeouts.

---

#### 2. Protocolo de Pruebas Escalonado (3 Fases)
Ninguna prueba con usuarios reales se ejecuta sin validar primero la máquina:
- **Paso 1 (Benchmark Cuantitativo Congelado):** Ejecución estructurada contra `tests/dataset/banco_preguntas.json`. Solo las ramas que alcancen el Gate de Calidad avanzan.
- **Paso 2 (Casos de Uso Acotados):** Simulación de roles con evaluador siguiendo libretos estrictos (3 a 5 preguntas encadenadas) para verificar persistencia de contexto en SQLite.
- **Paso 3 (Test Humano Libre):** Interacción libre por Telegram para evaluar tono, lenguaje natural y casos límite. Base empírica para el informe cualitativo.

---

#### 3. Árbol de Experimentación Genealógico (Branching Strategy)
El ciclo parte siempre del **Resultado** y se bifurca en **Planes**:
- Un `Resultado_X.0` genera un diagnóstico que identifica múltiples oportunidades de mejora independientes (OP-1, OP-2, OP-3).
- Cada oportunidad da origen a una rama de Git hija y un plan específico (`Plan_X.1`, `Plan_X.2`, etc.).
- **Regla de Oro (Aislamiento de Variables):** Cada rama hija modifica una única variable (ej. solo chunking, solo prompt, solo parámetros de Ollama). Queda estrictamente prohibido mezclar cambios arquitectónicos en la misma rama.
- **Criterio de Fusión (Merge Gate):** Solo la rama hija con métricas cuantitativas superiores al Resultado Padre (`X.0`) se integra a `main`. Las ramas perdedoras se conservan documentadas pero no se fusionan.

---

#### 4. Topología de Archivos y Directorios
Diseña el árbol dentro de `tests/`:
```text
tests/
├── dataset/
│   └── banco_preguntas.json
└── iteraciones/
    ├── iteracion_1.0_baseline/
    │   ├── resultado_1.0.md
    │   └── analisis_y_bifurcaciones.md
    ├── iteracion_1.1_chunking/
    │   ├── plan_1.1.md
    │   └── resultado_1.1.md
    └── iteracion_1.2_sanitizacion/
        ├── plan_1.2.md
        └── resultado_1.2.md