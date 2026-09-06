# ROL Y OBJETIVO
Actúa como un Ingeniero de Software Principal y Arquitecto de Sistemas de IA. Tu objetivo es iniciar la auditoría profunda de este repositorio para crear la base de conocimiento técnico que consumirán otros modelos de IA para programar en él.

En esta Fase 1, analizarás exhaustivamente el repositorio y generarás dos artefactos:
1. `CONTEXTO.md` (Secciones 1 a 4: Visión, Código, Memoria de Sesión y Configuración de Inferencia).
2. `Bitacora.md` (Documento vivo para registrar el ciclo de vida, deuda técnica y cambios del proyecto).

---

### CONTEXTO DEL SISTEMA (KNOWN STATE)
- **Propósito:** Chatbot conversacional impulsado por LLMs locales/remotos vía Ollama.
- **Canal de entrada activo:** Bot de Telegram.
- **Frontend residual:** Código de frontend descartado y en desuso que debe inventariarse para ser eliminado.
- **RAG arcaico:** Pipeline rudimentario basado en múltiples archivos `.md` e incrustaciones.

---

### DIRECTIVAS DE EJECUCIÓN
- Cero suposiciones: si una variable, timeout o función no aparece en el código, marca explícitamente `[NO DETECTADO EN EL REPOSITORIO]`.
- Nombra archivos con rutas relativas reales, clases y funciones literales.

---

### ENTREGABLE 1: Archivo `CONTEXTO.md` (Parte 1)
Genera el archivo con la siguiente estructura exacta:

# CONTEXTO TÉCNICO DEL SISTEMA

## 1. Visión General y Stack Tecnológico Real
- Propósito central del sistema.
- Lista exhaustiva de tecnologías analizando manifests (`requirements.txt`, `package.json`, etc.): lenguajes, frameworks, librerías cliente y dependencias de sistema.

## 2. Inventario Exhaustivo de Archivos y Responsabilidades
Tabla Markdown con las columnas:
| Ruta Relativa del Archivo | Responsabilidad Principal | Módulos / Servicios que Importa | Archivos / Componentes que lo Consumen |

## 3. Configuración del Motor LLM (Ollama)
- Nombres de modelos declarados para inferencia y embeddings (ej. `llama3`, `nomic-embed-text`).
- Parámetros de inferencia detectados: `temperature`, `top_p`, `num_ctx` (context window), timeouts y URL del host.
- Identificar si `num_ctx` está fijado explícitamente o corre bajo el valor por defecto de Ollama (2048 tokens).

## 4. Gestión de Estado y Sesión en Telegram
- Mecanismo de seguimiento del `chat_id`: ¿dónde vive el historial de conversación (memoria RAM volátil, SQLite, Redis o sin persistencia)?
- Impacto técnico ante un reinicio del servicio backend (¿se pierde el contexto del usuario?).

---

### ENTREGABLE 2: Archivo `Bitacora.md` (Documento Vivo)
Inicializa este documento que servirá como registro evolutivo continuo. La regla de este archivo es mantenerse "vivo" y actualizarse con cada refactorización o cambio de arquitectura:

# BITÁCORA DE EVOLUCIÓN Y CAMBIOS DEL PROYECTO

> **REGLA PARA ASISTENTES IA Y DESARROLLADORES:** Este documento es dinámico y obligatorio. Cada vez que se realice un cambio de arquitectura, refactorización, eliminación de código muerto, actualización de librerías o corrección de bugs, se DEBE agregar una entrada a este archivo antes de cerrar la tarea.

## Registro Histórico de Cambios
| Fecha (YYYY-MM-DD) | Módulo / Archivo | Tipo de Cambio (Fix/Refactor/Feature/Docs) | Resumen del Cambio | Impacto / Dependencias Afectadas |
|---|---|---|---|---|
| [Fecha Actual] | Repositorio Completo | Docs | Inicio de auditoría técnica y creación de documentación viva | Generación de `CONTEXTO.md`, `Diagramas.md` y `Bitacora.md` |

## Deuda Técnica Inicial Detectada (Línea Base)
- [ ] Eliminar código residual y dependencias del frontend descartado.
- [ ] Modernizar el pipeline RAG basado en archivos `.md`.
- [ ] [Agregar otros ítems de deuda técnica detectados en la Fase 1].