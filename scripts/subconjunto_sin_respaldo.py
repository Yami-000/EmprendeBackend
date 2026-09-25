"""Emite los IDs de las preguntas SIN respaldo en el corpus (mitad de control).

Son las que miden alucinacion y especificidad del juez: la respuesta correcta es
abstenerse. La clasificacion vive en el campo `md_origen` del ground truth (null
si la pregunta no tiene respaldo), no en el orden del array, asi que se lee de
ahi y no de un corte por indice.

No carga el modelo de embeddings ni el indice: es instantaneo.

Uso:
  python scripts/subconjunto_sin_respaldo.py > tests/dataset/sin_respaldo.txt
"""
import io, json, os, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANCO = os.path.join(RAIZ, "tests", "dataset", "banco_preguntas_respuestas.json")

d = json.load(io.open(BANCO, encoding="utf-8-sig"))
sin = [p["id"] for p in d if not p["ground_truth"]["md_origen"]]

sys.stderr.write("banco: %d preguntas | sin respaldo: %d\n" % (len(d), len(sin)))

print("# preguntas sin respaldo en el corpus (miden alucinacion y especificidad)")
print("# generado por scripts/subconjunto_sin_respaldo.py")
for pid in sin:
    print(pid)
