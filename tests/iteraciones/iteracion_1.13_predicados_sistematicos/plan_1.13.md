# Plan 1.13 — ¿El resultado de la 1.10 generaliza, o era sobreajuste al banco?

**Rama:** `iteracion_1.13_predicados_sistematicos`, apilada sobre
`iteracion_1.10_relaciones_explicitas`
**Abierta:** 2026-09-26

## El problema de método que hay que resolver

La 1.10 recuperó 5 de 8 preguntas agregando 6 frases-predicado al corpus. **Esas 6
frases se escribieron mirando las 8 preguntas del banco.** Se eligió qué relación
declarar, y con qué palabras, sabiendo exactamente qué se iba a preguntar.

Eso es **ajustar al conjunto de prueba**, y es justo lo que la 1.8 evitó a
propósito. Su comentario en `ingest.py` lo dice sin ambigüedad:

> *"POR QUÉ SE DERIVAN Y NO SE ESCRIBEN A MANO: elegirlas mirando el banco de
> preguntas sería ajustar al conjunto de prueba. Estas salen solo del corpus."*

**No invalida la 1.10**, pero la evidencia a favor de que generaliza es **más débil
de lo que parecía a primera vista.** Entre las 7 preguntas que ganó están PREG-068 y
PREG-073, que no tienen predicado propio — pero **las dos están en
`obligaciones_tributarias_y_tipos_sociedad.md`, que recibió 4 predicados.** Su
ganancia no es independiente: puede ser el mecanismo del predicado o el
re-chunking de ese archivo, y **con lo medido no se puede atribuir.**

Así que no se sabe cuánto del +5 es mecanismo y cuánto es haber acertado las
palabras mirando las preguntas.

## La hipótesis

**Si declarar relaciones funciona como mecanismo, convertir las relaciones del
corpus de forma sistemática y ciega al banco debería mejorar también.** Si solo
funciona cuando se eligen las frases mirando las preguntas, la 1.10 era
sobreajuste y hay que decirlo en la documentación antes de construir encima.

## La variable

`scripts/generar_predicados.py` convierte **las 33 filas de tabla del corpus** en
frases-predicado. El script es la garantía metodológica:

- **Las plantillas son el aporte humano**, una por tabla, derivada de los
  **encabezados de esa tabla**. No se mira el banco para escribirlas.
- **Las filas se convierten mecánicamente.** Todas, sin elegir.
- **Las frases quedan como salen.** Varias son torpes —*"La EIRL admite 1 socios"*,
  *"El trámite de Total estimado cuesta"*— y **no se retocan a mano**: retocarlas
  mirando qué se pregunta sería volver al cherry-picking. La torpeza es el costo
  honesto de una regla ciega, y si el mecanismo es real debe funcionar igual.

**Reglas que respeta, heredadas y verificadas por el script:**

1. La fila de tabla **no se borra**: 37 de las 50 citas son texto literal.
2. La frase va **antes** de la tabla, dentro de los 256 tokens del embedder. Más
   allá de ese token es texto muerto — medido en la 1.10, el predicado de PREG-118
   cayó en el token 313 y no movió nada.
3. **No se inserta nada entre las líneas de una tabla o lista:** `anclaje@k` compara
   subcadenas contiguas.
4. No se renombra ningún archivo.

## El riesgo principal, que ya costó una vez

**Agregar 33 frases va a mover el chunking.** En la 1.10, dos predicados de más
partieron `tipos_sociedad_chile.md` en 3 chunks, bajaron `recall@6` de 48/50 a
47/50 y **bajaron** la sensibilidad de 23/29 a 22/29.

Acá se agregan ~3300 caracteres repartidos en 5 archivos. Es muy probable que
varias secciones se partan. **Por eso el orden de medición no se negocia:**

```bash
python scripts/generar_predicados.py --ver        # revisar antes de escribir
python scripts/generar_predicados.py --aplicar

# 1) las citas del banco siguen intactas? el techo debe seguir en 37 de 50
# 2) reconstruir el indice
cd ai-service && python ingest.py && cd ..
# 3) MIRAR EL NUMERO DE CHUNKS antes que cualquier otra cosa
python scripts/medir_retrieval.py
```

**Si el conteo de chunks sube mucho y `recall@6` baja de 48/50, se corta ahí** y el
resultado es que el mecanismo no sobrevive a aplicarse en escala. Eso también es un
hallazgo, y es barato: segundos, sin LLM.

## Si el retrieval aguanta

```bash
python scripts/evaluar_banco.py v13_nucleo --dos-pasos --juez llama3.2 \
    --redactor llama3.2 \
    --ids PREG-010,PREG-064,PREG-065,PREG-075,PREG-080,PREG-084,PREG-088,PREG-115
python scripts/evaluar_banco.py v13_sens --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --ids @tests/dataset/dato_integro_k6_control_1.9.txt
python scripts/evaluar_banco.py v13_espe --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --ids @tests/dataset/sin_respaldo.txt
```

## Controles y cortes

```
recall@6 ........  48/50     piso: no bajar
anclaje@6 .......  28/37
nucleo duro .....  5 de 8
sensibilidad ....  23/29
especificidad ...  50/50     no se negocia
alucinacion .....  0/50      no se negocia
```

**Corte:** la sensibilidad **no baja** de 23/29. No se pide que suba: la pregunta de
esta iteración no es *"¿mejora más?"* sino *"¿el mecanismo sobrevive sin mirar el
banco?"*. Que se mantenga ya responde que sí.

**Lectura de un resultado negativo:** si baja, hay dos explicaciones posibles y hay
que distinguirlas con el conteo de chunks —
**(a)** el chunking se rompió, que es mecánico y arreglable, o
**(b)** los predicados solo servían porque estaban escritos para esas preguntas, que
es sobreajuste y obliga a rebajar la conclusión de la 1.10 en
`ESTADO_INVESTIGACION.md`.

## Lo que este experimento NO prueba

**No prueba que las frases torpes sean buena documentación.** El corpus lo leen
personas además del modelo, y *"La EIRL admite 1 socios"* es mala prosa. Si la
iteración sale positiva, la versión que se fusione debería **corregir la gramática
sin cambiar el contenido**, y eso es un cambio de una variable más, medible aparte.

---

## Addendum — desvío del diseño, anotado el 2026-09-26 durante la ejecución

Este plan se escribió antes de medir. Lo que pasó al ejecutarlo obligó a un
desvío, y queda acá para que se vea que el diseño original **no** contemplaba la
segunda pasada.

**Primera pasada, las 33 filas:** el índice subió de **28 a 31 fragmentos** y
`recall@6` cayó de 48/50 a **45/50**. Se cortó ahí, como el plan indicaba, sin
gastar el end-to-end. Pero eso deja el experimento **confundido**: rompió el
chunking, así que no responde la pregunta de la iteración.

**Segunda pasada, con una regla nueva.** Se agregó `--solo-si-cabe` al generador:
aplica la conversión a una tabla **solo si el archivo conserva su número de
fragmentos**. La regla decide por el **conteo de fragmentos**, nunca por qué
preguntas mejoran, así que sigue siendo ciega al banco. Selecciona 20 predicados
y omite 13.

**Por qué el desvío es legítimo y no es ajustar hasta que salga:** la regla no
mira el banco. Separa un fallo **mecánico** —el tope de 1400 caracteres— de la
pregunta que importa, que es si el mecanismo del predicado generaliza. Si se
hubieran elegido las tablas por las preguntas que mejoran, sería el sobreajuste
que esta iteración existe para detectar.

**Lo que el desvío cuesta en credibilidad:** son dos pasadas sobre el mismo banco,
y la segunda se diseñó sabiendo cómo falló la primera. El resultado hay que leerlo
como lo que es — una segunda pasada, no una predicción cumplida.
