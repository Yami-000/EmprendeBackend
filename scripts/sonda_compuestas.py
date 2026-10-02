# -*- coding: utf-8 -*-
"""Veredicto del juez ante preguntas COMPUESTAS, y que haria el veto de la 2.1.

POR QUE EXISTE
--------------
El fallo que origino la iteracion 2.1 llego desde Telegram: el bot se abstuvo
cuatro veces y a la quinta respondio inventando la mision del SII. La pregunta
que filtro era COMPUESTA ("¿Que es X y cual es su Y?").

Ni evaluar_banco.py ni evaluar_endpoint.py sirven para diagnosticar eso: el banco
no contiene esa pregunta, y desde el endpoint no se ve el veredicto del juez.
Esta sonda si: usa el retrieval REAL (k=3), pregunta al juez la compuesta y cada
mitad por separado, y dice si el veto actuaria.

QUE NO ES
---------
No es una metrica. Mide un punado de preguntas elegidas a mano para entender un
mecanismo. Lo que decide si un cambio entra sigue siendo el banco de 100.

Uso:  python scripts/sonda_compuestas.py [--reps N] [--pregunta "..."]
"""
import argparse
import asyncio
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "ai-service"))
import api  # noqa: E402

# Las 7 variantes con que se aislo la fuga. Las dos ultimas son controles: 'RUT'
# esta en el corpus y 'Tesoreria' no, y la forma sin tildes esta para exponer que
# la fuga depende de la ortografia de la pregunta.
CASOS = [
    "¿Qué es el SII?",
    "¿Cuál es su misión institucional?",
    "¿Qué es el SII y cuál es su misión institucional?",
    "¿Qué es el servicio de impuestos internos (SII) y cuál es su misión institucional?",
    "Que es el servicio de impuestos internos (SII) y cual es su mision institucional?",
    "¿Qué es el RUT y cuál es su misión?",
    "¿Qué es la Tesorería y cuál es su función?",
]

ap = argparse.ArgumentParser()
ap.add_argument("--reps", type=int, default=3,
                help="repeticiones por pregunta, para distinguir un veredicto "
                     "deterministico de un vuelco")
ap.add_argument("--pregunta", action="append",
                help="reemplaza la lista por una pregunta propia; repetible")
args = ap.parse_args()


async def main():
    # El endpoint carga el modelo y ChromaDB en su evento de arranque. Aca se
    # llama a mano porque esta sonda corre sin uvicorn.
    await api.startup_event()

    preguntas = args.pregunta or CASOS
    for q in preguntas:
        vec = await api._embed_text(q)
        frs = await api._query_chroma(vec, k=3)
        fuentes = [os.path.basename(f.get("metadata", {}).get("source", "?"))
                   for f in frs]

        veredictos = []
        for _ in range(args.reps):
            ok, _crudo = await api._juzgar(frs, q)
            veredictos.append("SI" if ok else "NO")

        mitades = api.partir_compuesta(q)
        vm = []
        for m in mitades:
            ok, _crudo = await api._juzgar(frs, m)
            vm.append("SI" if ok else "NO")

        print("-" * 74)
        print("P: %s" % q)
        print("   juez x%d: %s%s" % (
            args.reps, " ".join(veredictos),
            "   <-- VUELCA" if len(set(veredictos)) > 1 else "   (deterministico)"))
        if mitades:
            for v, m in zip(vm, mitades):
                print("   mitad    %s  %s" % (v, m))
            veta = veredictos[0] == "SI" and "SI" not in vm
            conj = veredictos[0] == "SI" and "NO" in vm
            print("   veto:    %s" % ("ANULA el SI" if veta else "no actua"))
            if conj and not veta:
                print("   (una conjuncion la rechazaria: el veto la conserva)")
        else:
            print("   mitad    no es una pregunta compuesta")
        print("   fuentes: %s" % ", ".join(fuentes))


if __name__ == "__main__":
    asyncio.run(main())
