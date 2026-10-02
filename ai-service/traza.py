# -*- coding: utf-8 -*-
"""Traza legible de como el pipeline decide, para mirarla en vivo.

POR QUE EXISTE
--------------
El pipeline de dos pasos toma decisiones que no se ven en la respuesta: el juez
aprueba o rechaza, la descomposicion rescata o no, el veto de compuestas anula
una aprobacion. Desde Telegram solo se ve el resultado, y cuando el bot abstiene
no hay forma de saber si fue porque el retrieval no trajo nada, porque el juez
dijo NO, o porque el veto anulo un SI.

Esta traza muestra ese camino. No reemplaza a las metricas: sirve para entender
UN caso, no para medir.

DONDE SE VE
-----------
  - En la ventana del ai-service (va a stdout).
  - En la ventana "Ecia - traza", que sigue el archivo logs/traza.log.
    iniciar.bat la abre.

NO ES UN LOG DE PRODUCCION. Escribe la pregunta del usuario en claro a un archivo
local: sirve para desarrollar y depurar. Si algun dia esto corre con usuarios
reales, hay que decidir que se guarda y por cuanto tiempo.
"""
import io
import itertools
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / "logs" / "traza.log"

_ANCHO = 66

# Contador para el id de cada consulta. Se uso primero la hora en milisegundos y
# dos consultas creadas en la misma milesima colisionaban, que es justo el caso
# que el id existe para distinguir.
_CONTADOR = itertools.count(1)


def _abrir():
    """Crea logs/ y el archivo si no existen.

    Se crea al importar y no al primer uso para que la ventana que sigue el
    archivo con Get-Content -Wait tenga algo que seguir desde el arranque: si el
    archivo no existe, ese comando falla y la ventana queda inutil.
    """
    try:
        ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
        if not ARCHIVO.exists():
            io.open(ARCHIVO, "w", encoding="utf-8").write(
                "traza del pipeline. Se llena cuando llega una consulta.\n")
    except Exception:
        pass


_abrir()


class Consulta:
    """Acumula la traza de una consulta y la escribe ENTERA al cerrarse.

    POR QUE SE ACUMULA EN VEZ DE ESCRIBIR LINEA A LINEA: con dos consultas en
    vuelo al mismo tiempo, escribir en el momento intercala las lineas de las dos
    y la traza queda ilegible. Paso de verdad al probar esto mientras corria una
    medicion del banco contra el mismo endpoint.

    El costo es que el bloque aparece cuando la consulta TERMINA, no mientras
    ocurre. Para un usuario en Telegram eso son los ~10 s de la respuesta, y a
    cambio cada bloque se lee de corrido.

    Uso:
        t = Consulta(pregunta)
        t.paso("JUEZ", "SI", 6.8)
        t.cerrar("REDACTOR", "...")     <- aca se escribe todo
    """

    def __init__(self, pregunta):
        self.t0 = time.time()
        # Un id corto y unico, para poder seguir dos consultas si aun asi se
        # cruzan en la ventana.
        self.id = "%03d" % (next(_CONTADOR) % 1000)
        self.lineas = [
            "",
            "=" * _ANCHO,
            "%s  [%s]  %s" % (time.strftime("%H:%M:%S"), self.id,
                              _corto(pregunta, _ANCHO - 20)),
            "-" * _ANCHO,
        ]
        self.cerrada = False

    def paso(self, etiqueta, detalle="", segundos=None):
        t = "  %-9s %s" % (etiqueta, detalle)
        if segundos is not None:
            t += "   (%.1f s)" % segundos
        self.lineas.append(t)

    def sub(self, detalle):
        """Una linea sangrada, para listas: fuentes, subpreguntas, mitades."""
        self.lineas.append("            %s" % detalle)

    def cerrar(self, etiqueta, detalle=""):
        """Escribe el bloque completo. Idempotente: llamarla dos veces no duplica."""
        if self.cerrada:
            return
        self.cerrada = True
        self.paso(etiqueta, _corto(detalle, _ANCHO - 14))
        self.paso("TIEMPO", "%.1f s en total" % (time.time() - self.t0))
        volcar(self.lineas)


def volcar(lineas):
    """Escribe un bloque entero, al archivo y a stdout.

    Nunca levanta: una traza que rompe el endpoint es peor que no tener traza.
    """
    texto = "\n".join(lineas) + "\n"
    try:
        sys.stdout.write(texto)
        sys.stdout.flush()
    except Exception:
        pass
    try:
        with io.open(ARCHIVO, "a", encoding="utf-8") as f:
            f.write(texto)
    except Exception:
        pass


def _corto(t, n):
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[:n - 1] + "…"
