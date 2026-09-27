# Metodología de testing del pipeline RAG

**Última actualización:** 2026-09-27 · **Refleja:** el protocolo realmente usado en las iteraciones 1.0 a 1.16

Este documento es el **protocolo operativo**: cómo se mide, con qué se decide y cómo se
organiza el trabajo. El *por qué* de cada regla, con la evidencia que la motivó, está en
[`INFORME_INVESTIGACION.md`](INFORME_INVESTIGACION.md).

> **Nota histórica.** La primera versión de este archivo (2026-09-06) proponía un marco
> de escalas 1-10 para *Fidelity*, *Relevancia* y *Recall*, con un gate de "promedio ≥
> 8,0/10". **Ese marco nunca se usó** y fue reemplazado por métricas binarias y
> deterministas. La razón está al final, en
> [Lo que se descartó del plan original](#lo-que-se-descartó-del-plan-original).

---

## 1. El conjunto de prueba

**`tests/dataset/banco_preguntas_respuestas.json`** — 100 preguntas.

- Las **50 primeras son respondibles** con el corpus.
- Las **50 siguientes NO lo son**. Esa mitad es la que mide alucinación, y varias son
  **adversarias por diseño**: nombran al SII o un trámite real para preguntar algo que
  el corpus no cubre.
- La clasificación vive en **el orden del array**, no en un campo.

Cada caso trae `id`, `pregunta`, `categoria`, `tipo`, `criterio_esperado` y un
`ground_truth` con `md_origen`, `seccion`, `cita_anclaje` y `respuesta_esperada`.

> **Cuidado con los archivos vecinos.** `tests/dataset/banco_preguntas.json` existe pero
> **no es el que se usa**: solo tiene `id` y `pregunta`, sin ground truth. Y
> `banco_preguntas_respuestas.backup.json` es una copia previa a la corrección del
> ground truth del 2026-09-17. **El único banco válido es
> `banco_preguntas_respuestas.json`.**

---

## 2. Las métricas y el criterio de decisión

Descripción completa de cada una en
[`INFORME_INVESTIGACION.md`](INFORME_INVESTIGACION.md), sección 2.

```
DETERMINISTAS  (deciden)
  recall@k     retrieval a nivel de archivo. OPTIMISTA.
  anclaje@k    retrieval a nivel de chunk. Techo 37, no 50.

END-TO-END     (confirman, con banda de +-6 preguntas)
  sensibilidad del juez         especificidad del juez
  abstencion indebida          ALUCINACION
  cobertura de datos           latencia
```

**Se decide con las deterministas.** El juez mueve ~6 veredictos ante cambios del
contexto aunque corra con `temperature=0`, así que con un banco de 100 **una diferencia
neta menor a 6 preguntas no se puede afirmar**.

**Lo que distingue señal de ruido es la asimetría de los vuelcos, no su cantidad:** el
ruido mueve veredictos en las dos direcciones, un efecto real los mueve en una.
`scripts/comparar_corridas.py` lo reporta.

### El gate que no se negocia

> **Nada entra si la especificidad baja de 48/50 o si la alucinación sube de 0%.**

No es un promedio ni un umbral blando. El dominio es normativa tributaria: una
respuesta inventada es peor que ninguna respuesta.

---

## 3. Protocolo escalonado: medir barato antes que caro

**El orden importa más que las herramientas.** Diseñar las puertas de menor a mayor
costo permitió cerrar hipótesis completas sin gastar una corrida de LLM — la iteración
1.15 se refutó entera con **cero** invocaciones al modelo.

| Puerta | Herramienta | Costo | Qué decide |
|---|---|---|---|
| 0 | `medir_ventana_embedder.py` | segundos | ¿el embedder ve todo el corpus? |
| 1 | `medir_retrieval.py` | segundos | `recall@k` y `anclaje@k` |
| 1b | `ablacion_chunking.py` | ~10 s/variante | comparar configuraciones de chunking sin tocar el índice |
| 2 | `evaluar_banco.py --ids` (8 ids) | ~3 min | prueba dirigida a un subconjunto |
| 3 | `evaluar_banco.py --ids @archivo` (29) | ~15 min | sensibilidad sobre dato íntegro |
| 4 | `evaluar_banco.py --ids @sin_respaldo` (50) | ~20 min | **especificidad y alucinación** |
| 5 | `evaluar_banco.py` (100) | 25-45 min | todo junto, comparable entre iteraciones |

### El orden de las puertas 3 y 4 depende del riesgo

- **Cambios de corpus:** la especificidad va **última**. El riesgo es bajo.
- **Cambios del prompt del juez:** la especificidad va **primera**. La Fase 0 de la
  iteración 1.9 mostró que tocar ese prompt puede llevarla de 50/50 a **0/50**. **No
  tiene sentido medir la sensibilidad de una variante que no puede entrar.**

---

## 4. Reglas de experimentación

### Un experimento, una variable

La iteración 1.1 cambió cinco cosas a la vez, el resultado empeoró y **no se pudo
atribuir a cuál**. Costó una corrida completa.

Cuando dos cambios tocan subsistemas distintos (retrieval y juez), se miden **en
secuencia**, no juntos. El costo extra suele ser nulo: la puerta del cambio de retrieval
se resuelve sin LLM.

### Verificar que un refactor sea neutro antes de cambiar el comportamiento

Al cambiar el embedder (1.14) primero se centralizó el contrato **manteniendo el modelo
anterior**, y se comprobó que los números salieran **idénticos** al control. Sin ese
paso, cualquier cambio posterior habría sido inatribuible entre el refactor y el modelo.

### Congelar los subconjuntos de comparación

Los `subconjunto_*.py` se derivan del índice. **Si el índice cambia, el denominador se
mueve y la comparación con su propio control se rompe.** Los 29 IDs del control de
sensibilidad están congelados en `tests/dataset/dato_integro_k6_control_1.9.txt`.

### No copiar lo que se puede importar

`evaluar_banco.py` importa de `api.py` y `embedding.py` los prompts, el descomponedor y
el contrato del embedder. **Una copia divergente mide una versión que no es la que
corre.**

### Documentar también lo que falla

Cada iteración deja un `resultado_X.Y.md` con lo medido, **incluidos los resultados
negativos**. La tabla de callejones sin salida de `ESTADO_INVESTIGACION.md` es, en
volumen, el resultado principal de la investigación: evita repetir trabajo.

---

## 5. Estrategia de ramas

- **Una rama por iteración**, creada desde `main`.
- **No todas llegan a `main`:** solo se fusiona lo que mejora una métrica o aporta
  documentación transversal. En dos casos se fusionó el hallazgo y **se dejó el código
  afuera** a propósito.
- **`ESTADO_INVESTIGACION.md` vive en la raíz** y se fusiona apenas cierra una
  iteración, **por separado del código**. Estuvo dentro de `tests/iteraciones/` y quedó
  atrapado en un PR sin fusionar, de modo que ramas posteriores citaban oportunidades
  que no existían en su árbol.

### Estructura de artefactos

```
tests/
├── dataset/
│   ├── banco_preguntas_respuestas.json      <- el unico banco valido
│   └── dato_integro_k6_control_1.9.txt      <- subconjunto congelado
└── iteraciones/
    ├── resultados_<etiqueta>.json           <- una por corrida, 35 al cierre
    ├── triaje_hipotesis_2026-09-27.md
    └── iteracion_X.Y_<nombre>/
        ├── plan_X.Y.md                      <- escrito ANTES de medir
        └── resultado_X.Y.md                 <- con los numeros, negativos incluidos
```

**El plan se escribe antes de medir** y declara el corte. Si la ejecución obliga a
desviarse, el desvío se anota como **addendum en el plan**, no se reescribe el plan —
así se distingue una predicción cumplida de una segunda pasada.

---

## 6. Ejecución

```bash
# entorno
pip install -r ai-service/requirements.txt
npm ci

# OBLIGATORIO tras cualquier pull: chroma_db/ no esta versionado
cd ai-service && python ingest.py && cd ..

# puertas baratas
python scripts/medir_retrieval.py
python scripts/medir_ventana_embedder.py

# la configuracion vigente, banco completo
python scripts/evaluar_banco.py <etiqueta> --dos-pasos --descomponer \
    --juez llama3.2 --redactor llama3.2 llama3.2 3

# comparar contra un control
python scripts/comparar_corridas.py <control> <etiqueta>
```

`k` es el **tercer argumento posicional**, después de la etiqueta y el modelo.

**Al redirigir la salida de los `subconjunto_*.py`, no usar `2>&1`:** imprimen una línea
de resumen por stderr que `leer_ids` tomaría como IDs. Ya costó un relanzamiento.

### Servicios, solo para pruebas manuales

```bash
ollama serve
cd ai-service && uvicorn api:app --host 0.0.0.0 --port 11400
npm start
```

**El arnés no necesita nada de esto** salvo Ollama: consulta ChromaDB directamente. Ver
la limitación en la sección siguiente.

---

## 7. La limitación más importante de este protocolo

**El arnés no mide a través del endpoint.** `evaluar_banco.py` consulta ChromaDB y
Ollama directamente, replicando la lógica del pipeline con los prompts importados de
`api.py`.

Eso fue deliberado —es más rápido y aísla variables— pero tiene una consecuencia que
**pasó desapercibida durante 16 iteraciones**: el pipeline de dos pasos, que lleva la
alucinación de 34% a 0%, **nunca se implementó en `api.py`**. Producción sigue sirviendo
`/chat` de un paso.

**Todas las métricas de este proyecto son del arnés, no del sistema que usa la gente.**

Por eso, cuando el pipeline de dos pasos se porte a producción, **la verificación tiene
que hacerse a través del endpoint**, no del arnés. Es lo único que prueba que producción
se comporta como lo medido.

---

## Lo que se descartó del plan original

El plan de 2026-09-06 proponía cosas que la práctica descartó. Se registran para no
reintentarlas sin argumento nuevo.

| Propuesta original | Qué pasó |
|---|---|
| **Escalas 1-10 de Fidelity, Relevancia y Recall** | Reemplazadas por métricas **binarias y deterministas**. Una puntuación subjetiva de 1-10 no permite decidir si un cambio de una variable sirvió |
| **Gate de "promedio ≥ 8,0/10"** | Reemplazado por el gate que no se negocia. Un promedio permite compensar alucinación con fluidez, y en este dominio eso es inaceptable |
| **Un LLM juez que puntúe la calidad de la redacción** | Descartado con evidencia: el proyecto midió que un juez LLM es **inestable en ~6 de 50** preguntas ante cambios cosméticos del contexto. Usarlo como métrica agregaría el ruido que se quiere medir. La corrección se verifica **a mano** contra `criterio_esperado` |
| **Fase 2: casos de uso encadenados** | No ejecutada. La investigación se concentró en el fallo dominante, que era de una sola consulta |
| **Fase 3: test humano libre por Telegram** | No ejecutada, y con el hallazgo de la sección 7 **sería engañosa**: probaría el pipeline de un paso, que no es el que se midió |
| **Endpoints `/metrics` (Prometheus) y logs en `tests/iteraciones/logs/`** | No implementados. `/health` sí existe, en `src/server.js`. Las latencias se registran por corrida en los `resultados_*.json` |
| **Runner manual contra `RAG_URL`** | Reemplazado por `scripts/evaluar_banco.py` y seis herramientas más. Ninguna pasa por el endpoint — ver sección 7 |
