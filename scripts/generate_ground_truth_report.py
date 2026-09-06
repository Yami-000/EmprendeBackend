#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / 'tests' / 'dataset' / 'banco_preguntas.json'

def main():
    with DATASET.open('r', encoding='utf-8') as f:
        questions = json.load(f)

    missing = [q for q in questions if not q.get('ground_truth', {}).get('presente_en_docs', False)]
    found = [q for q in questions if q.get('ground_truth', {}).get('presente_en_docs', False)]

    print('# Reporte de Auditoría: Ground Truth')
    print('## Preguntas sin evidencia (presente_en_docs: false)')
    print()
    if not missing:
        print('Ninguna. Todos los items tienen evidencia encontrada.')
    else:
        for q in missing:
            print(f'- {q.get("id")} | {q.get("categoria")} | {q.get("pregunta")}')

    print('\n## Resumen de matches encontrados (parcial)')
    print()
    print('| id | pregunta | md_origen | seccion |')
    print('|---|---|---|---|')
    for q in found:
        gt = q.get('ground_truth', {})
        md = gt.get('md_origen')
        sec = gt.get('seccion')
        # sanitize
        question = q.get('pregunta','').replace('\n',' ')[:120]
        md = md if md is not None else ''
        sec = sec if sec is not None else ''
        print(f'| {q.get("id")} | {question} | {md} | {sec} |')

    print(f'\nTotal preguntas: {len(questions)}; encontradas: {len(found)}; faltantes: {len(missing)}')

if __name__ == '__main__':
    main()
