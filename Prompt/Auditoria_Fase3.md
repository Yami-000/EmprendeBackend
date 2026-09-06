# ROL Y OBJETIVO
Actúa como Arquitecto de Software y Diseñador de Sistemas. Con el análisis completo de las Fases 1 y 2, tu tarea final es generar dos entregables:
1. `Diagramas.md`: Archivo de diagramas en Mermaid.js y especificaciones formales de flujo para que otra IA pueda interpretar o redibujar el sistema.
2. Cierre de `CONTEXTO.md` con el Roadmap de Refactorización Priorizado.

---

### ENTREGABLE 1: Archivo `Diagramas.md`
Genera el archivo completo con:

# ESPECIFICACIÓN Y DIAGRAMAS DEL SISTEMA

> **USO PARA MODELOS DE IA:** Este archivo contiene el modelo relacional y de flujo del sistema. Puedes renderizar los bloques Mermaid directamente o utilizar la especificación textual para recrear los diagramas en PlantUML, Draw.io o Graphviz.

## 1. Diagrama de Arquitectura Global (Mermaid `graph TD`)
- Representar: Usuario Telegram, Telegram Bot API, Servidor Backend, Pipeline RAG, Base de Conocimiento (`.md`), Servidor Ollama.
- Indicar visualmente los componentes del Frontend marcándolos como `[DEPRECADO / PENDIENTE DE REMOCIÓN]`.

## 2. Diagrama de Secuencia: Ciclo de Vida del Mensaje (Mermaid `sequenceDiagram`)
- Mapear el flujo exacto síncrono/asíncrono:
  Telegram User -> Polling/Webhook -> Handler -> Módulo RAG -> Inferencia Ollama -> Formateo de respuesta -> Telegram User.
- Incluir ramas alternativas para casos de error (ej. timeout de Ollama).

## 3. Diagrama de Flujo: Pipeline RAG (Mermaid `flowchart LR`)
- Flujo de datos: Archivos Markdown -> Extracción/Parsing -> Chunking (o falta de él) -> Vectorización -> Inyección en el System/User Prompt.

## 4. Especificación Estructural en Lenguaje Natural
- Desglose narrativo nodo por nodo y conexión por conexión para cada diagrama, explicando la semántica exacta de cada componente para procesamiento por otros LLMs.

---

### ENTREGABLE 2: Sección Final para `CONTEXTO.md`

## 8. Roadmap de Refactorización Priorizado (Plan de Acción para IAs y Desarrolladores)
Diseña un plan secuencial en 3 fases:
- **Paso 1: Limpieza Quirúrgica del Frontend:** Lista exacta de comandos/archivos a borrar y cambios en el backend para remover endpoints en desuso sin errores de importación.
- **Paso 2: Robustecimiento Operativo:** Implementación de timeouts para Ollama, variables de entorno seguras y persistencia del historial conversacional.
- **Paso 3: Modernización del RAG:** Plan concreto para reemplazar la lectura plana de `.md` por chunking con solapamiento, persistencia vectorial local eficiente (ej. ChromaDB/Qdrant/SQLite-vec) y manejo del contexto (`num_ctx`).