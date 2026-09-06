#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / 'tests' / 'dataset' / 'banco_preguntas.json'
DOCS_DIR = ROOT / 'ai-service' / 'docs'

STOPWORDS = set(["de","la","el","que","y","en","del","los","las","con","por","para","al","se","su","sus","es","una","un","lo","como","o"])

def split_sentences(text):
    # naive sentence splitter
    parts = re.split(r'(?<=[\.!?])\s+', text.replace('\r','\n'))
    return [p.strip() for p in parts if p.strip()]

def extract_heading_and_fragment(lines, line_idx, match_text):
    # find nearest preceding header
    for i in range(line_idx, -1, -1):
        if lines[i].strip().startswith('#'):
            return lines[i].strip(), None
    return None, None

def find_in_file(content, question, keywords):
    lc = content.lower()
    qlc = question.lower()
    # first try exact question match
    if qlc in lc:
        idx = lc.find(qlc)
        # find line index
        lines = content.splitlines()
        cum = 0
        for i,l in enumerate(lines):
            cum += len(l)+1
            if cum > idx:
                # find sentence containing match
                sents = split_sentences(l)
                if sents:
                    frag = None
                    for s in sents:
                        if qlc in s.lower():
                            frag = s
                            break
                    if not frag:
                        frag = l.strip()
                else:
                    frag = l.strip()
                # find nearest header
                header = None
                for j in range(i, -1, -1):
                    if lines[j].strip().startswith('#'):
                        header = lines[j].strip()
                        break
                return True, header, frag
    # second: keyword-based search (require >=2 keyword matches in a sentence)
    sents = split_sentences(content)
    for s in sents:
        lw = s.lower()
        cnt = sum(1 for k in keywords if k in lw)
        if cnt >= 2:
            # find header by locating sentence position in lines
            # approximate: find s in content then line
            idx = lc.find(s.lower())
            lines = content.splitlines()
            cum = 0
            for i,l in enumerate(lines):
                cum += len(l)+1
                if cum > idx:
                    header = None
                    for j in range(i, -1, -1):
                        if lines[j].strip().startswith('#'):
                            header = lines[j].strip()
                            break
                    return True, header, s.strip()
    return False, None, None

def extract_keywords(question):
    words = re.findall(r"[\wáéíóúñÁÉÍÓÚÑ]+", question.lower())
    kws = [w for w in words if len(w) >= 4 and w not in STOPWORDS]
    # dedupe
    seen = set()
    out = []
    for w in kws:
        if w not in seen:
            out.append(w)
            seen.add(w)
    return out

def main():
    if not DATASET.exists():
        print('Dataset not found:', DATASET)
        return
    # read dataset
    with DATASET.open('r', encoding='utf-8') as f:
        questions = json.load(f)

    # index docs
    docs = list(DOCS_DIR.rglob('*.md'))
    docs = [p for p in docs if p.is_file()]
    docs_content = {}
    for p in docs:
        try:
            docs_content[str(p)] = p.read_text(encoding='utf-8')
        except Exception as e:
            docs_content[str(p)] = ''

    updated = 0
    missing = 0

    for q in questions:
        question = q.get('pregunta','')
        kws = extract_keywords(question)
        found = False
        for p,content in docs_content.items():
            ok, header, frag = find_in_file(content, question, kws)
            if ok:
                # build ground_truth
                respuesta = frag
                # shorten respuesta to max 2 sentences
                sents = split_sentences(respuesta)
                respuesta_short = ' '.join(sents[:2]) if sents else respuesta
                q['ground_truth'] = {
                    'presente_en_docs': True,
                    'md_origen': str(Path(p).as_posix()),
                    'seccion': header,
                    'cita_anclaje': frag,
                    'respuesta_esperada': respuesta_short
                }
                updated += 1
                found = True
                break
        if not found:
            q['ground_truth'] = {
                'presente_en_docs': False,
                'md_origen': None,
                'seccion': None,
                'cita_anclaje': None,
                'respuesta_esperada': 'Información no disponible en la colección de documentos.'
            }
            missing += 1

    # write back
    with DATASET.open('w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

    print(f'Processed {len(questions)} questions: found={updated}, missing={missing}')

if __name__ == '__main__':
    main()
