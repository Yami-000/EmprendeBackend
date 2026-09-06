#!/usr/bin/env python3
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / 'tests' / 'dataset' / 'banco_preguntas.json'
OUTCSV = ROOT / 'tests' / 'dataset' / 'verificacion_ground_truth.csv'

def main():
    with DATASET.open('r', encoding='utf-8') as f:
        questions = json.load(f)

    with OUTCSV.open('w', encoding='utf-8', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['id','categoria','pregunta','md_origen','seccion','cita_anclaje'])
        for q in questions:
            gt = q.get('ground_truth', {})
            writer.writerow([
                q.get('id',''),
                q.get('categoria',''),
                q.get('pregunta','').replace('\n',' '),
                gt.get('md_origen') if gt.get('md_origen') is not None else '',
                gt.get('seccion') if gt.get('seccion') is not None else '',
                (gt.get('cita_anclaje') or '').replace('\n',' ')[:800]
            ])
    print('Wrote', OUTCSV)

if __name__ == '__main__':
    main()
