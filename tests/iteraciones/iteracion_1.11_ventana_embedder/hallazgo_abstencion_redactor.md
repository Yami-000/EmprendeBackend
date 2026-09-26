# Hallazgo — La abstención del redactor pese al `SI` del juez es marginal: 3,2%, y hoy 0%

**Fecha:** 2026-09-26 · **Rama:** `iteracion_1.11_ventana_embedder`
**Origen:** deuda que dejó la Fase 1 de la 1.10, nunca medida

La Fase 1 detectó que en PREG-065 el juez aprobó, el redactor corrió 18,3 s y **aun
así emitió la frase de abstención**. Quedó anotado como un segundo eslabón sin
medir, con la sospecha de que podía estar costando respuestas que ya habían pasado
la puerta del juez.

**Se midió, y no lo está.** No hizo falta una corrida nueva: el dato estaba en los
JSON de todas las iteraciones anteriores.

## El número

Cruzando `juez_dijo_si == True` con `abstuvo == True` en las 12 corridas
registradas:

```
corrida                juez SI   y abstuvo   ids
b1_sens                    18           0
chunking_1.1_k6            30           1    PREG-087
claves_1.8_k6              25           0
dospasos_A                 26           1    PREG-065
f1_nucleo                   1           1    PREG-065
f1_nucleo_rep               1           1    PREG-065
f2_nucleo                   5           0
f2_sens                    22           0
f2b_nucleo                  5           0
f2b_sens                   23           0
grafo_1.7_k6               28           2    PREG-071, PREG-085
nucleo_flexible             1           0

TOTAL                     185           6    (3,2%)
```

**Cuatro preguntas en total**, y PREG-065 aporta 3 de los 6 casos.

## Lo decisivo: en la configuración actual es 0

Las cuatro corridas de la 1.10 con predicados (`f2_nucleo`, `f2_sens`,
`f2b_nucleo`, `f2b_sens`) dan **0 abstenciones sobre 55 `SI` del juez**. Y PREG-065,
que era el caso que motivó la sospecha, **hoy responde correctamente**: *"El costo
total de formalizar una empresa bajo el régimen simplificado (Tu Empresa en un Día)
es $0"*.

Los predicados de la Fase 2 arreglaron el eslabón del redactor **de paso**. Tiene
sentido: el redactor abstenía cuando el contexto tenía el dato en una forma que no
podía afirmar —una celda de tabla bajo una columna "Rol"— exactamente el mismo
mecanismo que bloqueaba al juez. No eran dos problemas, era uno.

## Conclusión

**No amerita una iteración.** Un modo de fallo del 3,2% histórico y 0% en la
configuración vigente no es donde está el retorno. Queda anotado para que no se
vuelva a abrir como línea de trabajo, y queda la métrica para detectarlo si
reaparece.

**Sí conviene vigilarlo**, porque es un fallo silencioso: el juez aprueba, se paga
la segunda llamada al modelo y el usuario recibe una abstención igual. Un cambio
futuro que lo haga crecer no aparecería en `sensibilidad` —que mide el juez— sino
solo en `abstuvo indebidamente`.

## Reproducir

```bash
python - <<'EOF'
import json, io, glob, os
tot = ab = 0
for f in sorted(glob.glob('tests/iteraciones/resultados_*.json')):
    try: items = json.load(io.open(f, encoding='utf-8'))
    except Exception: continue
    if not isinstance(items, list) or not items or 'juez_dijo_si' not in items[0]:
        continue
    si = [r for r in items if r.get('juez_dijo_si')]
    mal = [r['id'] for r in si if r.get('abstuvo')]
    tot += len(si); ab += len(mal)
    if mal: print(os.path.basename(f), mal)
print('juez SI:', tot, '| redactor abstuvo:', ab)
EOF
```
