# -*- coding: utf-8 -*-
"""Compara dos corridas de evaluar_banco.py pregunta por pregunta.

Existe porque comparar a mano dos JSON de 100 preguntas es donde se cuelan los
errores de lectura, y porque el numero que importa casi nunca es el total: son
las preguntas que se dieron vuelta y en que direccion.

Compara solo la INTERSECCION de ids, asi que sirve igual para dos corridas
completas o para dos subconjuntos que se solapan en parte.

OJO CON LA BANDA: el juez es determinista ante el mismo contexto y el mismo
prompt (0 vuelcos en dos corridas identicas, 1.10 Fase 1), pero cambiar el
contexto mueve ~6 veredictos. Si el total se mueve menos que la cantidad de
vuelcos, el cambio neto probablemente no se distingue de esa banda: mirar la
columna de vuelcos, no solo el total.

Uso:  python scripts/comparar_corridas.py <etiqueta_control> <etiqueta_nueva>
      python scripts/comparar_corridas.py claves_1.8_k6 v11a_full
"""
import json, io, os, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITER = os.path.join(RAIZ, "tests", "iteraciones")


def cargar(etiqueta):
    p = os.path.join(ITER, "resultados_%s.json" % etiqueta)
    if not os.path.exists(p):
        sys.exit("no existe: %s" % p)
    return {r["id"]: r for r in json.load(io.open(p, encoding="utf-8"))}


def resumen(D, ids):
    """Cuenta lo que importa sobre el subconjunto comparable."""
    sub = [D[i] for i in ids]
    resp = [r for r in sub if r.get("respondible")]
    nores = [r for r in sub if not r.get("respondible")]
    return {
        "n": len(sub),
        "respondibles": len(resp),
        "juez_si": sum(1 for r in resp if r.get("juez_dijo_si")),
        "abstuvo_mal": sum(1 for r in resp if r.get("abstuvo")),
        "sin_respaldo": len(nores),
        "especificidad": sum(1 for r in nores if r.get("abstuvo")),
        "alucino": sum(1 for r in nores if not r.get("abstuvo")),
    }


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    ctl_n, new_n = sys.argv[1], sys.argv[2]
    ctl, new = cargar(ctl_n), cargar(new_n)
    ids = sorted(set(ctl) & set(new))
    if not ids:
        sys.exit("las dos corridas no comparten ningun id")
    print("comparando %d preguntas en comun (%s: %d, %s: %d)\n"
          % (len(ids), ctl_n, len(ctl), new_n, len(new)))

    a, b = resumen(ctl, ids), resumen(new, ids)
    filas = [
        ("respondibles", "respondibles", None),
        ("juez dice SI", "juez_si", "respondibles"),
        ("abstuvo indebidamente", "abstuvo_mal", "respondibles"),
        ("sin respaldo", "sin_respaldo", None),
        ("especificidad", "especificidad", "sin_respaldo"),
        ("ALUCINO", "alucino", "sin_respaldo"),
    ]
    print("%-24s %14s %14s" % ("", ctl_n[:14], new_n[:14]))
    for etiq, k, den in filas:
        va, vb = a[k], b[k]
        if den:
            sa, sb = "%d/%d" % (va, a[den]), "%d/%d" % (vb, b[den])
        else:
            sa, sb = str(va), str(vb)
        flecha = ""
        if den and va != vb:
            flecha = "  <-- " + ("mejora" if (vb > va) != (k in ("abstuvo_mal", "alucino")) else "empeora")
        print("%-24s %14s %14s%s" % (etiq, sa, sb, flecha))

    # lo que de verdad importa: los vuelcos
    gan = [i for i in ids if ctl[i].get("respondible")
           and not ctl[i].get("juez_dijo_si") and new[i].get("juez_dijo_si")]
    per = [i for i in ids if ctl[i].get("respondible")
           and ctl[i].get("juez_dijo_si") and not new[i].get("juez_dijo_si")]
    fug = [i for i in ids if not ctl[i].get("respondible")
           and ctl[i].get("abstuvo") and not new[i].get("abstuvo")]
    print("\nvuelcos del juez en respondibles: %d  (ganadas %d, perdidas %d)"
          % (len(gan) + len(per), len(gan), len(per)))
    print("  ganadas:  %s" % (", ".join(gan) or "ninguna"))
    print("  perdidas: %s" % (", ".join(per) or "ninguna"))
    if fug:
        print("\nFUGAS NUEVAS en preguntas sin respaldo (esto no se negocia): %s"
              % ", ".join(fug))
    neto = a["juez_si"] - b["juez_si"]
    if len(gan) + len(per) > abs(neto):
        print("\nAVISO: %d vuelcos para un cambio neto de %+d. El neto no se distingue"
              % (len(gan) + len(per), -neto))
        print("de la banda de inestabilidad del juez (~6 ante cambios del contexto).")
        print("No concluir de este numero solo: mirar tambien recall@k y anclaje@k,")
        print("que son deterministas.")


if __name__ == "__main__":
    main()
