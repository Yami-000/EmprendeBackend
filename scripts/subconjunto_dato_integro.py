"""Emite los IDs de las preguntas cuyo dato de anclaje llega INTEGRO al juez.

Es el subconjunto sobre el que se mide la *sensibilidad* del juez sin
contaminarla con fallos de retrieval: si la cita de anclaje no esta en el
contexto, un `NO` del juez es correcto y no dice nada sobre su calidad.

Con k=6 y el corpus de la 1.8 son 29 de las 37 preguntas verificables. El
numero depende del indice, asi que se recalcula en vez de fijarse en el codigo:
tras un `ingest.py` distinto puede cambiar.

Uso:
  python scripts/subconjunto_dato_integro.py > tests/dataset/dato_integro_k6.txt
  python scripts/evaluar_banco.py b1 --dos-pasos --juez qwen2.5:7b \
      --redactor llama3.2 --ids @tests/dataset/dato_integro_k6.txt
"""
import sys

from medir_retrieval import verificables, anclaje_presente

K = 6

integro = [p["id"] for p in verificables if anclaje_presente(p, K)]
fuera = [p["id"] for p in verificables if not anclaje_presente(p, K)]

sys.stderr.write("verificables: %d | dato integro con k=%d: %d | fuera: %d\n"
                 % (len(verificables), K, len(integro), len(fuera)))
sys.stderr.write("fuera: %s\n" % ", ".join(fuera))

print("# preguntas con el dato de anclaje integro en el top-%d" % K)
print("# generado por scripts/subconjunto_dato_integro.py")
for pid in integro:
    print(pid)
