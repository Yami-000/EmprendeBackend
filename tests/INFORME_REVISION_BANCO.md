# INFORME DE REVISIÓN — Banco de 100 Preguntas SII

**Fecha:** 2026-09-16
**Revisor:** Claude Opus 5
**Corpus verificado:** 13 archivos en `ai-service/docs/sii/`
**Archivo analizado:** `tests/dataset/banco_preguntas_respuestas.json`

---

## 🔴 HALLAZGO ESTRUCTURAL CRÍTICO

**`ingest.py` línea 18:** `DOCS_DIR = BASE_DIR / "docs" / "sii"`

El agente RAG **solo indexa los 13 archivos de `docs/sii/`**. Sin embargo, **24 de las 52 preguntas marcadas como respondibles citan archivos que están fuera de ese directorio** y por lo tanto **no existen en ChromaDB**.

### Archivos citados que NO están indexados

| Archivo citado en `md_origen` | Preguntas afectadas | Naturaleza |
|---|---|---|
| `docs/system_prompt_MiPrimerInicioSII.md` | 002, 003, 004, 019, 038, 041 | System prompt, no indexado |
| `docs/system_prompt_MiPrimeraConstitucionEmpTradicional.md` | 001, 018 | System prompt, no indexado |
| `docs/system_prompt_MiPrimeraConstitucionEmpSimplificada.md` | 011, 039 | System prompt, no indexado |
| `docs/systeme_prompt_MiPrimeraPatenteMun.md` | 010, 028 | System prompt, no indexado |
| `docs/AgentesValores.md` | 012 | **Mercado de valores — irrelevante** |
| `docs/CuentasDepósitosVista.md` | 013 | **Productos bancarios — irrelevante** |
| `docs/CalculadoraDemoraPagarTarjeta.md` | 017 | **Tarjetas de crédito — irrelevante** |
| `docs/Diversificar.md` | 022 | **Inversiones — irrelevante** |
| `docs/DecalogoInversionista.md` | 024 | **Inversiones — irrelevante** |
| `docs/Capital.md` | 033 | **Finanzas — irrelevante** |
| `docs/CuentasAhorro.md` | 035 | **Ahorro — irrelevante** |
| `docs/CobrosIntermediacion.md` | 037 | **Corretaje — irrelevante** |
| `docs/MiPrimerEndeudamiento.md` | 042 | **Deuda — irrelevante** |
| `docs/Ahorro.md` | 060 | **Ahorro — irrelevante** |

**Causa raíz:** El script `populate_ground_truth` hizo matching semántico contra **todo** `docs/`, no solo `docs/sii/`. Como el embedding no encontró match real para preguntas de tributación avanzada, asignó el chunk "menos malo" disponible — que resultó ser contenido financiero de la CMF completamente ajeno al SII.

**Evidencia flagrante:** PREG-012 pregunta "¿Qué es una Factura Electrónica?" y su `cita_anclaje` es *"En el marco de la Ley N° 18.045 de Mercado de Valores, los Agentes de Valores surgen como figuras necesarias para dinamizar el mercado fuera de los recintos bursátiles"*.

---

## COBERTURA REAL DEL CORPUS INDEXADO

### ✅ Temas SÍ cubiertos (verificados línea por línea)

| Tema | Archivo fuente | Dato concreto |
|---|---|---|
| Tipos de empresa (9) | `tipos_sociedad_chile.md` | Tabla completa con socios/responsabilidad |
| MEF | `tipos_sociedad_chile.md` | Límite 2.400 UF, domicilio, familiares directos |
| Costo régimen simplificado | `costos_y_plazos_formalizacion.md` | $0, plazo 1 día hábil |
| Costo régimen tradicional | `costos_y_plazos_formalizacion.md` | $110.000–$380.000 desglosado |
| Patente municipal | `costos_y_plazos_formalizacion.md` | 0,25%–0,5%, min 1 UTM, max 8.000 UTM, cuotas julio/enero |
| **Plazo Inicio Actividades** | `costos_y_plazos_formalizacion.md` | **"Dentro de 2 meses de operar"** |
| F29 / F50 / F22 | `formularios_tributarios_chile.md` | Tabla con periodicidad, plazo y contenido |
| IVA | `formularios_tributarios_chile.md` | 19%, mensual en F29 |
| DTE | `formularios_tributarios_chile.md` | Obligatorio desde 2017, tipos |
| Regímenes 14A/14D N°3/14D N°8 | `formularios_tributarios_chile.md` | Tasas 25%/27%/0% |
| Instituciones | `obligaciones_tributarias_y_tipos_sociedad.md` | Tabla de 8 instituciones y roles |
| Plazos 60 días | `inicio_actividades_formalizacion_sii.md` | Diario Oficial e inscripción |
| Pasos tuempresaenundia.cl | `inicio_actividades_formalizacion_sii.md` | 10 pasos numerados |
| Formulario 4415 | `documentacion_formalizacion.md` | Documentos presenciales |
| Cédula de Identidad (no DNI) | `documentacion_formalizacion.md` | Aclaración explícita |
| Patente provisional→definitiva | `inicio_actividades_formalizacion_sii.md` | 30 días sin observaciones |
| Autorización sanitaria | `inicio_actividades_formalizacion_sii.md` | SEREMI, 0,5% capital, ~3 días |
| Informe sanitario | `inicio_actividades_formalizacion_sii.md` | 20–30 días hábiles, MEF exentas |
| Cooperativas | `inicio_actividades_formalizacion_sii.md` | Proceso y obligaciones |
| Ventajas de formalizar | `inicio_actividades_formalizacion_sii.md` | 3 bloques de beneficios |

### ❌ Temas NO cubiertos (el agente debe abstenerse)

Misión institucional del SII · Clave Tributaria (obtención/recuperación) · ClaveÚnica · Direcciones Regionales · Primera vs Segunda Categoría · Acreditación de domicilio fiscal · CAF · Nota de Crédito como mecanismo de anulación · Plazo 8 días reclamo factura · Sanciones Art. 97 · PPM (definición) · Impuesto Global Complementario · Devolución de impuestos · Citación Art. 63 · RAV · RAF · Tribunales Tributarios · Liquidación vs Giro · Retenciones AFP/salud · LRE · Término de giro · Certificado de Situación Tributaria · RCV (nombre y función) · Art. 8 bis · DEDECON · Código Tributario DL 830 · Prescripción · TGR · Ley 19.749 · Residencia 183 días · Impuesto Territorial · Donaciones · Secreto tributario · Auditoría tributaria · Responsabilidad solidaria tributaria · Convenio de pago · Declaración "sin movimiento" · Actualización de giros · Plataformas digitales · Capital mínimo SRL · Reformas post-2024 · Valor UF · Retención dividendos · Transferencia de acciones · Prórroga renta · Insolvencia · Acreditación StartUp · Conservación de registros · Auditoría externa

---

## TABLA DE ANÁLISIS COMPLETA

### BLOQUE A — Marcadas RESPONDIBLES (posiciones 1–52)

| ID | Pregunta (resumen) | Verificación | Problema | Recomendación |
|---|---|---|---|---|
| PREG-001 | ¿Qué es el SII y su misión institucional? | 🟡 PARCIAL | Rol sí está (tabla instituciones); "misión institucional" no | AJUSTAR criterio → "rol en la formalización" |
| PREG-002 | Canales oficiales de contacto SII | 🟡 PARCIAL | Web y presencial sí; mesa telefónica NO existe en corpus | AJUSTAR criterio (quitar teléfono) |
| PREG-003 | ¿Qué es la Clave Tributaria y cómo se obtiene? | ❌ FALSA | Corpus solo dice "clave personal de sii.cl". No define ni explica obtención. ClaveÚnica ausente | **MOVER a no respondible** |
| PREG-004 | Recuperar Clave Tributaria olvidada | ❌ FALSA | Cero contenido en corpus | **MOVER a no respondible** |
| PREG-010 | ¿Patente municipal en SII u otra institución? | ✅ CORRECTA | `md_origen` incorrecto | Corregir a `docs/sii/patente_municipal.md` |
| PREG-011 | Actualización/adición de giros en SII | ❌ FALSA | Corpus no cubre modificación de giros | **MOVER a no respondible** |
| PREG-012 | Factura Electrónica y valor legal vs papel | 🟡 PARCIAL | Existencia y obligatoriedad sí; XML/firma digital/valor probatorio NO | AJUSTAR criterio o mover |
| PREG-013 | Boletas de Honorarios y % retención | ❌ FALSA | Solo existe "retenciones honorarios" en tabla F50; sin emisor ni porcentaje | **MOVER a no respondible** |
| PREG-014 | ¿Qué es el CAF? | ❌ FALSA | Corpus menciona **CVE**, no CAF. Son conceptos distintos | **MOVER a no respondible** ⚠️ riesgo alto de confusión CVE/CAF |
| PREG-017 | Plazo para reclamar Factura Electrónica | ❌ FALSA | "8 días" no existe en corpus | **MOVER a no respondible** |
| PREG-018 | Sanciones por no emisión de boletas | ❌ FALSA | Corpus solo dice "protección contra sanciones" como ventaja | **MOVER a no respondible** |
| PREG-019 | ¿Qué es F29 y qué se declara? | ✅ CORRECTA | `md_origen` incorrecto | Corregir a `docs/sii/formularios_tributarios_chile.md` |
| PREG-022 | Empresa sin movimientos en un mes | ❌ FALSA | Declaración "sin movimiento" ausente | **MOVER a no respondible** |
| PREG-024 | Impuesto Global Complementario | ❌ FALSA | Ausente del corpus | **MOVER a no respondible** |
| PREG-028 | Plazo para responder Citación SII | ❌ FALSA | Citaciones ausentes | **MOVER a no respondible** |
| PREG-033 | Retenciones previsionales sobre sueldos | ❌ FALSA | Solo "cotización salud y jubilación" como ventaja genérica | **MOVER a no respondible** |
| PREG-035 | Tributación de servicios digitales online | ❌ FALSA | Ausente | **MOVER a no respondible** |
| PREG-037 | Inventarios y activos en Término de Giro | ❌ FALSA | Término de giro ausente | **MOVER a no respondible** |
| PREG-038 | Consulta de anotaciones tributarias | ❌ FALSA | "Mi SII" existe, anotaciones no | **MOVER a no respondible** |
| PREG-039 | ¿Qué es el RCV digital? | 🟡 PARCIAL | Existe "Libro de Compras y Ventas electrónico"; nombre RCV y función de propuesta F29 NO | Reformular o mover |
| PREG-040 | Descargar Certificado Situación Tributaria | ❌ FALSA | Ausente | **MOVER a no respondible** |
| PREG-041 | Derechos Art. 8 bis Código Tributario | ❌ FALSA | Ausente | **MOVER a no respondible** |
| PREG-042 | Institución que defiende contribuyentes (DEDECON) | ❌ FALSA | Ausente | **MOVER a no respondible** |
| PREG-060 | Convenio de pago y organismo (TGR) | ❌ FALSA | TGR y convenios ausentes | **MOVER a no respondible** |
| PREG-061 | EIRL vs Persona Natural con Giro | ✅ CORRECTA | Ninguno | Mantener |
| PREG-062 | MEF y límite 2.400 UF | ✅ CORRECTA | Ninguno | Mantener |
| PREG-063 | SpA atractiva para startups | ✅ CORRECTA | Ninguno | Mantener |
| PREG-064 | SA Cerrada vs SA Abierta | ✅ CORRECTA | Ninguno | Mantener |
| PREG-065 | Costo régimen simplificado ($0) | ✅ CORRECTA | Ninguno | Mantener |
| PREG-066 | Costo escritura notaría | ✅ CORRECTA | Ninguno | Mantener |
| PREG-067 | Costo total régimen tradicional | ✅ CORRECTA | Ninguno | Mantener |
| PREG-068 | Cálculo patente municipal | ✅ CORRECTA | Ninguno | Mantener |
| PREG-069 | Plazo F29 | ✅ CORRECTA | Duplica PREG-020 | Mantener; eliminar duplicado |
| PREG-070 | Tasa IVA 19% | ✅ CORRECTA | Ninguno | Mantener |
| PREG-071 | Facturación electrónica desde 2017 | ✅ CORRECTA | Ninguno | Mantener |
| PREG-072 | Tipos de DTE | ✅ CORRECTA | Ninguno | Mantener |
| PREG-073 | Boletas electrónicas obligatorias | ✅ CORRECTA | Ninguno | Mantener |
| PREG-074 | SA y SpA contabilidad completa | ✅ CORRECTA | Ninguno | Mantener |
| PREG-075 | Libro de Compras y Ventas | ✅ CORRECTA | Ninguno | Mantener |
| PREG-076 | Tasa Régimen General 14A | ✅ CORRECTA | Ninguno | Mantener |
| PREG-077 | Régimen Pro Pyme 14D N°3 | ✅ CORRECTA | Duplica PREG-026 | Mantener; revisar duplicado |
| PREG-078 | SII otorga RUT e Inicio Actividades | ✅ CORRECTA | Duplica PREG-082 | Mantener; eliminar duplicado |
| PREG-079 | DOM emite Certificado de Zonificación | ✅ CORRECTA | Ninguno | Mantener |
| PREG-080 | Conservador inscribe Registro de Comercio | ✅ CORRECTA | Ninguno | Mantener |
| PREG-081 | Plazo F22 (30 de abril) | ✅ CORRECTA | Duplica PREG-023 | Mantener; eliminar duplicado |
| PREG-082 | Quién emite el RUT | ✅ CORRECTA | **Duplicado de PREG-078** | 🟡 ELIMINAR o reformular |
| PREG-083 | Sociedad Colectiva Comercial | ✅ CORRECTA | Ninguno | Mantener |
| PREG-084 | Sociedad Comanditaria | ✅ CORRECTA | Ninguno | Mantener |
| PREG-085 | Estructuras con responsabilidad limitada | ✅ CORRECTA | Ninguno | Mantener |
| PREG-087 | Exención 14D N°8 | ✅ CORRECTA | Ninguno | Mantener |
| PREG-088 | Notario elabora escritura pública | ✅ CORRECTA | Ninguno | Mantener |
| PREG-089 | Extracto publicado en Diario Oficial | ✅ CORRECTA | Ninguno | Mantener |

### BLOQUE B — Marcadas NO RESPONDIBLES (posiciones 53–100)

| ID | Pregunta (resumen) | Verificación | Problema | Recomendación |
|---|---|---|---|---|
| PREG-005 | Funciones Direcciones Regionales | ✅ CORRECTA | — | Mantener |
| PREG-006 | **Plazo legal Inicio de Actividades** | ❌ **FALSA** | `costos_y_plazos_formalizacion.md` línea 14: **"Dentro de 2 meses de operar"** | 🔴 **MOVER a respondible** |
| PREG-007 | Primera vs Segunda Categoría | ✅ CORRECTA | — | Mantener |
| PREG-008 | Acreditar domicilio fiscal | 🟡 AMBIGUA | Existe "comprobante de domicilio y rol de avalúo"; tipos de documento NO | Mantener; documentar riesgo |
| PREG-009 | Consecuencias domicilio falso | ✅ CORRECTA | — | Mantener |
| PREG-015 | Giro exento emitiendo facturas afectas | ✅ CORRECTA | — | Mantener |
| PREG-016 | Nota de Crédito para anular factura | 🟡 AMBIGUA | NC existe como tipo de DTE; su función de anulación NO | Mantener; buena trampa |
| PREG-020 | **Plazo vencimiento F29** | ❌ **FALSA** | Tabla F29 "Día 12"; obligaciones añade "o hasta el 20 en línea sin deuda" | 🔴 **MOVER a respondible** o eliminar (duplica 069) |
| PREG-021 | ¿Qué son los PPM? | 🟡 AMBIGUA | Sigla aparece en tabla F29 sin definición | Mantener; riesgo de alucinación parcial |
| PREG-023 | **¿Qué es F22 y cuándo se presenta?** | ❌ **FALSA** | Tabla: "F22 \| Declaración Anual de Renta \| Anual \| 30 de abril" | 🔴 **MOVER a respondible** o eliminar (duplica 081) |
| PREG-025 | Devolución de impuestos | ✅ CORRECTA | — | Mantener |
| PREG-026 | ProPyme General 14D N°3 | 🟡 AMBIGUA | Tasa y tope UF SÍ están; "ingresos percibidos/gastos pagados" y "depreciación instantánea" NO | Ajustar criterio o eliminar (duplica 077) |
| PREG-027 | Citación Art. 63 | ✅ CORRECTA | — | Mantener |
| PREG-029 | Liquidación vs Giro | ✅ CORRECTA | — | Mantener |
| PREG-030 | RAV | ✅ CORRECTA | Solapa con PREG-093 | Mantener |
| PREG-031 | RAF | ✅ CORRECTA | Solapa con PREG-093 | Mantener |
| PREG-032 | Tribunales Tributarios y Aduaneros | ✅ CORRECTA | — | Mantener |
| PREG-034 | Libro de Remuneraciones Electrónico | ✅ CORRECTA | — | Mantener |
| PREG-036 | Término de Giro | ✅ CORRECTA | — | Mantener |
| PREG-043 | Código Tributario (DL 830) | ✅ CORRECTA | — | Mantener |
| PREG-044 | Prescripción tributaria | ✅ CORRECTA | — | Mantener |
| PREG-045 | TGR como recaudador | ✅ CORRECTA | — | Mantener |
| PREG-046 | Impuestos de MEF (Ley 19.749) | 🟡 AMBIGUA | MEF existe en corpus; su tributación y la ley NO | Mantener; riesgo alto de alucinación |
| PREG-047 | Acreditación de no residencia | ✅ CORRECTA | — | Mantener |
| PREG-048 | Impuesto Territorial | ✅ CORRECTA | — | Mantener |
| PREG-049 | Donaciones culturales | ✅ CORRECTA | — | Mantener |
| PREG-050 | Secreto tributario | ✅ CORRECTA | — | Mantener |
| PREG-051 | Licencia de conducir | ✅ CORRECTA | Adversarial bien diseñada | Mantener |
| PREG-052 | Despido injustificado | ✅ CORRECTA | Adversarial bien diseñada | Mantener |
| PREG-053 | AFIP Argentina | ✅ CORRECTA | Adversarial bien diseñada | Mantener |
| PREG-054 | Subvención SERVIU | ✅ CORRECTA | Adversarial bien diseñada | Mantener |
| PREG-055 | Cotización dólar 2030 | ✅ CORRECTA | Adversarial bien diseñada | Mantener |
| PREG-056 | Auditoría tributaria integral | ✅ CORRECTA | — | Mantener |
| PREG-057 | Documentación contable física | ✅ CORRECTA | — | Mantener |
| PREG-058 | Responsabilidad solidaria tributaria | 🟡 AMBIGUA | Corpus tiene "responsabilidad solidaria" en Soc. Colectiva — concepto distinto | Mantener; excelente trampa |
| PREG-059 | Sanciones por F22 tardío | ✅ CORRECTA | — | Mantener |
| PREG-086 | Capital mínimo SRL | 🟡 AMBIGUA | "Capital en cuotas" y "sí requiere capital" existen; monto mínimo NO | Mantener |
| PREG-090 | Reforma tributaria reciente | ✅ CORRECTA | — | Mantener |
| PREG-091 | Valor actual de la UF | ✅ CORRECTA | — | Mantener |
| PREG-092 | Retención sobre dividendos | ✅ CORRECTA | — | Mantener |
| PREG-093 | Recursos administrativos (RAV/RAF/TTA) | ✅ CORRECTA | Solapa con 030/031/032 | Mantener |
| PREG-094 | Impuestos por transferencia de acciones | ✅ CORRECTA | — | Mantener |
| PREG-095 | Prórroga Declaración de Renta | ✅ CORRECTA | — | Mantener |
| PREG-096 | Liquidación por insolvencia | ✅ CORRECTA | — | Mantener |
| PREG-097 | Acreditación StartUp | ✅ CORRECTA | — | Mantener |
| PREG-098 | Multa por ocultamiento doloso | ✅ CORRECTA | — | Mantener |
| PREG-099 | Conservación de registros contables | ✅ CORRECTA | — | Mantener |
| PREG-100 | Auditoría externa según SVS | ✅ CORRECTA | 🟢 "SVS" se fusionó en CMF (2018) | Cambiar "SVS" por "CMF" |

---

## RESUMEN EJECUTIVO

| Métrica | Valor |
|---|---|
| Total verificadas | 100 |
| Correctamente clasificadas | **68** |
| Errores críticos de clasificación | **21** |
| Ambiguas que requieren ajuste | **11** |
| **Precisión actual** | **68%** |

### Desglose de errores

| Severidad | Cantidad | Descripción |
|---|---|---|
| 🔴 CRÍTICO | 18 | Marcadas respondibles sin sustento en el corpus |
| 🔴 CRÍTICO | 3 | Marcadas no respondibles pero SÍ contestables (006, 020, 023) |
| 🟡 MEDIO | 11 | Criterio excede el corpus o contenido parcial |
| 🟡 MEDIO | 4 | Pares duplicados |
| 🟢 MENOR | 2 | Error factual (SVS→CMF), texto corrupto en corpus |

### Balance real vs declarado

| | Declarado | Real | Diferencia |
|---|---|---|---|
| Respondibles | 52 | **37** | −15 |
| No respondibles | 48 | **63** | +15 |

---

## PATRÓN DE ERROR IDENTIFICADO

Los errores se concentran **exclusivamente en PREG-001 a PREG-060** (el bloque poblado por `populate_ground_truth`). Las 40 preguntas creadas manualmente (PREG-061 a PREG-100) tienen **97,5% de precisión** — el único fallo es PREG-100 (SVS/CMF).

**Conclusión:** el script de matching semántico es la causa del 100% de los errores críticos. No fue un problema de diseño de preguntas sino de poblado automático del ground truth.

---

## PLAN DE CORRECCIÓN

### Paso 1 — Reclasificar (21 preguntas)
Mover a **no respondibles**: 003, 004, 011, 013, 014, 017, 018, 022, 024, 028, 033, 035, 037, 038, 040, 041, 042, 060
Mover a **respondibles**: 006, 020, 023

### Paso 2 — Corregir `md_origen` (3 preguntas que sí son válidas)
- PREG-010 → `docs/sii/patente_municipal.md`
- PREG-019 → `docs/sii/formularios_tributarios_chile.md`
- PREG-014 → (se mueve a no respondible, `md_origen` = null)

### Paso 3 — Ajustar criterios (4 preguntas)
- PREG-001: quitar "misión institucional"
- PREG-002: quitar "mesa de ayuda telefónica"
- PREG-012: quitar "XML/firma digital/valor probatorio"
- PREG-039: reformular "RCV" → "Libro de Compras y Ventas electrónico"

### Paso 4 — Resolver duplicados
- Eliminar PREG-082 (duplica 078)
- Eliminar PREG-020 **o** PREG-069 (mismo plazo F29)
- Eliminar PREG-023 **o** PREG-081 (misma fecha F22)
- Eliminar PREG-026 **o** PREG-077 (mismo régimen 14D N°3)

### Paso 5 — Rebalancear a 50/50
Faltan **13 preguntas respondibles**. Temas del corpus aún sin explotar:

1. Definición de formalización / emprendimiento informal
2. Ventajas de formalizar (calidad de vida / negocio / proyección)
3. Plazo de publicación en Diario Oficial (60 días)
4. Plazo de inscripción en Registro de Comercio (60 días)
5. Pasos en tuempresaenundia.cl
6. Patente provisional → definitiva (30 días)
7. Categorías de patente municipal (5 tipos)
8. Autorización Sanitaria (SEREMI, 0,5% capital, ~3 días)
9. Informe Sanitario (20–30 días, MEF exentas)
10. Formalización de cooperativas
11. Documentos del Formulario 4415
12. Cédula de Identidad vs "DNI"
13. Derechos de aseo y publicidad
14. Certificado de Informaciones Previas
15. Persona Natural vs Persona Jurídica (tabla comparativa)
16. Sitios web oficiales del proceso

---

## VALIDACIÓN CRUZADA CON NOTEBOOKLM (2026-09-16, post-corrección)

El banco corregido se sometió a una segunda revisión independiente con NotebookLM, alimentado con los mismos 13 documentos.

| Resultado | Cantidad |
|---|---|
| Ambos clasifican RESPONDIBLE | 49 |
| Ambos clasifican NO RESPONDIBLE | 50 |
| Discrepancias | **1** |
| **Concordancia** | **99%** |

### Única discrepancia: PREG-103

NotebookLM marcó `Info_Dispo: false` para *"¿Qué beneficios obtiene un emprendedor al formalizar su negocio?"*.

**Verificación en disco:** `inicio_actividades_formalizacion_sii.md` líneas 9–26 contienen la sección `## Ventajas de Formalizar` completa, con tres bloques (calidad de vida, para el negocio, proyección empresarial).

**Veredicto:** falso negativo de NotebookLM. **Se mantiene como respondible.** Probable causa: el documento tiene 215 líneas y esa sección quedó fuera del retrieval de NotebookLM — lo cual, incidentalmente, anticipa que el agente RAG puede tener el mismo problema con este archivo. Vale la pena vigilar PREG-101 a PREG-118 en la evaluación, ya que 14 de ellas dependen de este mismo documento largo.

### Redundancia del corpus: 25 preguntas con doble fuente

En 25 casos ambos revisores coincidieron en que la pregunta es respondible pero citaron **archivos distintos**. No son contradicciones: el corpus tiene contenido duplicado.

| Contenido | Archivo A | Archivo B |
|---|---|---|
| Tipos de sociedad | `tipos_sociedad_chile.md` | `obligaciones_tributarias_y_tipos_sociedad.md` |
| Costos y plazos | `costos_y_plazos_formalizacion.md` | `obligaciones_tributarias_y_tipos_sociedad.md` |
| Formularios y tasas | `formularios_tributarios_chile.md` | `obligaciones_tributarias_y_tipos_sociedad.md` |
| Inicio de actividades | `inicio_actividades_sii.md` | `inicio_actividades_formalizacion_sii.md` |

**Acción aplicada:** se agregó el campo `md_alternativos` al `ground_truth` de esas 25 preguntas. En la evaluación, citar **cualquiera** de las fuentes listadas cuenta como acierto.

**Implicación para el retrieval:** `obligaciones_tributarias_y_tipos_sociedad.md` es un documento "paraguas" que duplica a otros cuatro. Esto puede estar compitiendo por los k=6 slots del retriever y desplazando a los documentos cortos y específicos. Es una hipótesis a probar si el puntaje no mejora.

---

## 🐛 BUG ADICIONAL EN EL CORPUS

`ai-service/docs/sii/inicio_actividades_sii.md` línea 4:

> "Este paso es obligatorio para todas las empresas, **независимо** de su tipo o forma de constitución."

Hay texto en cirílico ruso ("независимо" = "independientemente") dentro de un documento en español. Esto contamina el embedding de ese chunk y puede degradar el retrieval. **Corregir a "independientemente".**
