# -*- coding: utf-8 -*-
"""Convierte TODAS las filas de tabla del corpus en frases-predicado.

POR QUE EXISTE, Y POR QUE ES UN SCRIPT Y NO EDICION A MANO
----------------------------------------------------------
La 1.10 demostro que declarar una relacion en prosa antes de la tabla recupera
preguntas que el juez negaba con el dato delante. Pero esos 6 predicados se
escribieron MIRANDO LAS 8 PREGUNTAS DEL BANCO, y eso es ajustar al conjunto de
prueba: exactamente lo que la 1.8 evito al derivar las palabras clave del corpus
en vez de elegirlas a ojo.

Este script convierte las 33 filas de tabla del corpus SIN MIRAR EL BANCO. Las
plantillas son el aporte humano -una por tabla, derivada de los encabezados de
esa tabla- y las filas se convierten mecanicamente. Si el resultado de la 1.10
generaliza, esto deberia mejorar mas alla de las preguntas para las que se
escribieron los predicados. Si no generaliza, lo de la 1.10 era sobreajuste y
hay que decirlo.

REGLAS QUE RESPETA
------------------
- La fila de tabla NO se borra. 37 de las 50 citas del banco son texto literal y
  anclaje@k las compara caracter a caracter.
- La frase va ANTES de la tabla, para caer dentro de los 256 tokens que lee el
  embedder. Una frase mas alla de ese token es texto muerto para el retrieval
  (medido en la 1.10: el predicado de PREG-118 cayo en el token 313 y no movio
  nada).
- No se insertan frases ENTRE las lineas de una tabla ni de una lista: anclaje@k
  compara subcadenas CONTIGUAS y varias citas del banco abarcan varias lineas.
- No se renombra ningun archivo: el ground truth referencia por basename.

OJO CON EL CONTEO DE CHUNKS
---------------------------
Agregar texto puede empujar una seccion sobre el tope de 1400 caracteres y
partirla, y eso degrada el retrieval mas de lo que el predicado compra: en la
1.10, dos predicados de mas partieron tipos_sociedad_chile.md en 3 chunks y
bajaron recall@6 de 48/50 a 47/50. Correr medir_retrieval.py despues y mirar el
numero de chunks ANTES de gastar el end-to-end.

Uso:  python scripts/generar_predicados.py --ver      (imprime, no escribe)
      python scripts/generar_predicados.py --aplicar  (escribe los .md)
"""
import io, os, re, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(RAIZ, "ai-service", "docs", "sii")

MARCA = "<!-- predicados generados por scripts/generar_predicados.py -->"


def plantilla_costos(c):
    return "El trámite de %s cuesta %s y su plazo es: %s." % (c[0], c[1].lower(), c[2].lower())


def plantilla_formularios(c):
    return ("El formulario %s es la %s. Se presenta de forma %s, con plazo hasta el %s, "
            "y declara %s." % (c[0], c[1], c[2].lower(), c[3].lower(), c[4].lower()))


def plantilla_regimenes(c):
    return ("En cuanto a %s, el Régimen Simplificado usa %s y el Régimen Tradicional usa %s."
            % (c[0].lower(), c[1], c[2]))


def plantilla_natural_juridica(c):
    return ("En cuanto a %s, la Persona Natural tiene %s y la Persona Jurídica tiene %s."
            % (c[0].lower(), c[1].lower(), c[2].lower()))


def plantilla_sociedades(c):
    return ("La %s admite %s socios, su responsabilidad es %s, y %s."
            % (c[0], c[1], c[2].lower(), c[3].lower()))


def plantilla_instituciones(c):
    return "La institución %s se encarga de: %s." % (c[0], c[1].lower())


# Una entrada por tabla. La clave es la linea del encabezado, que identifica la
# tabla sin ambiguedad dentro de su archivo.
TABLAS = [
    ("costos_y_plazos_formalizacion.md", "| Trámite | Costo estimado (CLP) | Plazo |",
     plantilla_costos),
    ("formularios_tributarios_chile.md",
     "| Formulario | Nombre | Periodicidad | Plazo | Contenido |", plantilla_formularios),
    ("inicio_actividades_formalizacion_sii.md",
     "| Aspecto | Régimen Simplificado | Régimen Tradicional |", plantilla_regimenes),
    ("inicio_actividades_formalizacion_sii.md",
     "| Aspecto | Persona Natural | Persona Jurídica |", plantilla_natural_juridica),
    ("tipos_sociedad_chile.md", "| Tipo | Socios | Responsabilidad | Notas |",
     plantilla_sociedades),
    ("obligaciones_tributarias_y_tipos_sociedad.md", "| Institución | Rol |",
     plantilla_instituciones),
]

SEP = re.compile(r"^\s*\|[\s|:-]+\|\s*$")


def celdas(linea):
    return [c.strip() for c in linea.strip().strip("|").split("|")]


def predicados_de(lineas, i_enc):
    """Frases para las filas de datos que siguen al encabezado en i_enc."""
    if i_enc + 1 >= len(lineas) or not SEP.match(lineas[i_enc + 1]):
        return None, None
    j = i_enc + 2
    filas = []
    while j < len(lineas) and lineas[j].strip().startswith("|"):
        filas.append(celdas(lineas[j]))
        j += 1
    return filas, j


def _chunker():
    """Presta _chunk_text de ingest.py sin ejecutar la ingesta.

    Se extrae por texto en vez de importar el modulo porque importar ingest.py
    arrastra chromadb y sentence_transformers, que tardan segundos en cargar y no
    hacen falta para contar fragmentos.
    """
    src = io.open(os.path.join(RAIZ, "ai-service", "ingest.py"), encoding="utf-8").read()
    i = src.index("def _chunk_text")
    j = src.index("\ndef ", i + 10)
    ns = {}
    exec("import re\nCHUNK_SIZE=1400\nCHUNK_OVERLAP=200\n" + src[i:j], ns)
    return ns["_chunk_text"]


def cabe(fn, lineas_nuevas, chunk):
    """La tabla convertida deja el archivo con el mismo numero de fragmentos?

    ESTA ES LA REGLA CIEGA de --solo-si-cabe, y la razon de que exista:
    un predicado que empuja su seccion sobre el tope de 1400 la parte en dos, y
    eso degrada el retrieval mas de lo que el predicado compra. Medido: aplicar
    las 6 tablas subio el indice de 28 a 31 fragmentos y bajo recall@6 de 48/50
    a 45/50.

    La regla decide por el CONTEO DE FRAGMENTOS, no por que preguntas mejoran:
    elegir tablas mirando el banco seria el sobreajuste que este script existe
    para evitar.
    """
    original = io.open(os.path.join(D, fn), encoding="utf-8").read()
    return len(chunk("\n".join(lineas_nuevas))) == len(chunk(original))


def procesar(aplicar, solo_si_cabe=False):
    chunk = _chunker() if solo_si_cabe else None
    total = omitidas = 0
    for fn, encabezado, plantilla in TABLAS:
        p = os.path.join(D, fn)
        texto = io.open(p, encoding="utf-8").read()
        lineas = texto.split("\n")
        if encabezado not in lineas:
            print("  !! no encontrado en %s: %s" % (fn, encabezado))
            continue
        i = lineas.index(encabezado)
        filas, _ = predicados_de(lineas, i)
        if not filas:
            print("  !! sin filas de datos: %s / %s" % (fn, encabezado))
            continue

        frases = []
        for c in filas:
            try:
                frases.append(plantilla(c))
            except IndexError:
                print("  !! fila con menos columnas de lo esperado en %s: %r" % (fn, c))
        if not frases:
            continue

        bloque = [MARCA] + frases + [""]
        nuevas = lineas[:i] + bloque + lineas[i:]

        if solo_si_cabe and not cabe(fn, nuevas, chunk):
            print("=" * 72)
            print("%s  <-  %s" % (fn, encabezado[:40]))
            print("   OMITIDA: partiria el archivo en mas fragmentos (%d frases)"
                  % len(frases))
            omitidas += len(frases)
            continue

        print("=" * 72)
        print("%s  <-  %s  (%d filas)" % (fn, encabezado[:40], len(frases)))
        for f in frases:
            print("   " + f)
        total += len(frases)

        if aplicar:
            io.open(p, "w", encoding="utf-8", newline="\r\n").write("\n".join(nuevas))

    print("\n%d predicados %s" % (total, "APLICADOS" if aplicar else "(solo vista)"))
    if solo_si_cabe:
        print("%d omitidos por partir su archivo" % omitidas)
    if aplicar:
        print("\nAhora, EN ESTE ORDEN:")
        print("  1) verificar que las citas del banco siguen intactas")
        print("  2) cd ai-service && python ingest.py")
        print("  3) python scripts/medir_retrieval.py  <- mirar el NUMERO DE CHUNKS")
        print("  4) solo si el retrieval no empeoro, gastar el end-to-end")


if __name__ == "__main__":
    cabe_solo = "--solo-si-cabe" in sys.argv
    if "--aplicar" in sys.argv:
        procesar(True, cabe_solo)
    elif "--ver" in sys.argv:
        procesar(False, cabe_solo)
    else:
        sys.exit(__doc__)
