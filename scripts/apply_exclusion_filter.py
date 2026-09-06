#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / 'tests' / 'dataset' / 'banco_preguntas.json'
OUTCSV = ROOT / 'tests' / 'dataset' / 'verificacion_ground_truth.csv'

# Basenames of documents to exclude as invalid sources for SII/tramites
EXCLUDED_BASENAMES = {
    'BancoCentral.md', 'AccionesSociedadesAnónimasAbiertas.md', 'BonosCorporativos.md',
    'Futuros.md', 'CuotasFondosMutuos.md', 'FondosInversion.md', 'InstrumentosIntermediacionFinanciera.md',
    'CuentaCorriente.md', 'CarteraInversion.md', 'IntermediatiosValores.md', 'InstrumentosFinancierosValores.md',
    'CuotasFondosInversion.md', 'GananciaCapital.md', 'BonosCorporativos.md'
}

def basename_in_excluded(path_str):
    if not path_str:
        return False
    from pathlib import Path
    try:
        name = Path(path_str).name
        return name in EXCLUDED_BASENAMES
    except Exception:
        return False

def main():
    if not DATASET.exists():
        print('Dataset not found:', DATASET)
        return
    with DATASET.open('r', encoding='utf-8') as f:
        qs = json.load(f)

    changed = 0
    for q in qs:
        gt = q.get('ground_truth')
        if not gt:
            continue
        md = gt.get('md_origen')
        if md and basename_in_excluded(md):
            # mark as not present
            q['ground_truth'] = {
                'presente_en_docs': False,
                'md_origen': None,
                'seccion': None,
                'cita_anclaje': None,
                'respuesta_esperada': 'Fuente excluida por política: documento financiero/inversiones.'
            }
            changed += 1

    with DATASET.open('w', encoding='utf-8') as f:
        json.dump(qs, f, ensure_ascii=False, indent=2)

    print('Applied exclusion filter. Items changed:', changed)

if __name__ == '__main__':
    main()
