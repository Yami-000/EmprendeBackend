# METODOLOGÍA DE TESTING PARA EL CHATBOT (RAG)

Objetivo: Formalizar el protocolo de pruebas automatizadas y manuales para validar fidelidad, relevancia, recuperación vectorial y performance del pipeline RAG antes de cualquier prueba con usuarios reales.

1) Marco de Evaluación
- Escalas cuantitativas (1-10) para: Fidelity (Faithfulness), Relevancia, Recuperación (Context Recall).
- Métricas operativas: Latencia total por respuesta (s), Timeouts (umbral 60s), RAM/VRAM pico y promedio.
- Gate de Aprobación: Promedio >= 8.0/10 en las tres dimensiones de contenido, latencia media < 15s, 0 timeouts.

2) Protocolo escalonado
- Fase 1 — Benchmark Cuantitativo Congelado:
  - Ejecutar tests estructurados contra `tests/dataset/banco_preguntas.json`.
  - Cada caso define: `id`, `pregunta`, `respuesta_esperada` (o palabras clave), `categoria`.
  - Resultados y puntuaciones almacenadas en `tests/iteraciones/iteracion_1.0_baseline/resultado_1.0.md`.

- Fase 2 — Casos de Uso Acotados:
  - Escenarios de 3–5 preguntas encadenadas que validan persistencia de contexto, completitud y estabilidad en SQLite.
  - Scripts de simulación deben registrar latencias y matrices de similitud.

- Fase 3 — Test Humano Libre:
  - Interacciones por Telegram con evaluadores humanos; recolectar métricas cualitativas y ejemplos de fallo.

3) Branching Strategy experimental
- Flujo: Resultado_X.0 -> OP-1, OP-2 -> Plan_X.1, Plan_X.2 (una variable por rama).
- Merge Gate: Solo ramas con métricas cuantitativas superiores al padre se fusionan a `main`.

4) Topología mínima de archivos (creada en este commit)
```
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
```

5) Procedimiento de ejecución (resumen)
- Preparar entorno: `pip install -r ai-service/requirements.txt && npm ci`
- Levantar servicios: `uvicorn ai-service.api:app --host 0.0.0.0 --port 11400` y `npm start` para backend Node.
- Ejecutar el runner de tests (por ahora manual): iterar sobre `tests/dataset/banco_preguntas.json`, enviar cada `pregunta` al endpoint RAG (`RAG_URL`) y medir: latencia, conteo de fragments recuperados, score heurístico por coincidencia con `respuesta_esperada`.

6) Plantillas y artefactos esperados
- Cada `resultado_X.Y.md` debe contener: métricas globales (promedios), tabla por caso (Fidelity, Relevancia, Recall, Latencia), lista de timeouts y recomendaciones operacionales (OP-N).
- `analisis_y_bifurcaciones.md` documenta oportunidades y ramas hijas propuestas con número de cambio aislado.

7) Requisitos SRE/Infra
- Añadir endpoints `/health` y `/metrics` (Prometheus) si no existen; instrumentar latencias en Node y FastAPI.
- Guardar logs de evaluación en `tests/iteraciones/logs/` con formatos JSON para ingest en dashboards.

8) Próximos pasos (inmediatos)
- Ejecutar un primer benchmark automático con `tests/dataset/banco_preguntas.json` y publicar `resultado_1.0.md`.
- Implementar scripts de runner e integración CI en iteración subsiguiente.

Documento generado automáticamente como parte del plan de testing.
