#!/usr/bin/env python3
import time
import json
import random
import subprocess
from pathlib import Path

try:
    import requests
except Exception:
    raise SystemExit('requests is required. Install with: pip install requests')

try:
    import psutil
except Exception:
    raise SystemExit('psutil is required. Install with: pip install psutil')


ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / 'tests' / 'dataset' / 'banco_preguntas.json'
OUTDIR = ROOT / 'tests' / 'iteraciones' / 'iteracion_1.0_baseline'
OUTDIR.mkdir(parents=True, exist_ok=True)
OUTFILE = OUTDIR / 'metricas_1.0.json'
REPORTMD = OUTDIR / 'resultado_1.0.md'

RAG_ENDPOINT = 'http://localhost:11400/chat'
TIMEOUT = 60


def sample_questions(qs, seed=42):
    random.seed(seed)
    true_qs = [q for q in qs if q.get('ground_truth', {}).get('presente_en_docs') is True]
    false_qs = [q for q in qs if q.get('ground_truth', {}).get('presente_en_docs') is not True]
    if len(true_qs) < 10 or len(false_qs) < 10:
        raise SystemExit('Not enough items to sample 10/10; found true=%d false=%d' % (len(true_qs), len(false_qs)))
    s_true = random.sample(true_qs, 10)
    s_false = random.sample(false_qs, 10)
    return s_true + s_false


def get_vram_usage():
    try:
        out = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], stderr=subprocess.DEVNULL)
        vals = [int(x) for x in out.decode().strip().splitlines() if x.strip()]
        return sum(vals)
    except Exception:
        return 'N/A'


def extract_chunks_from_response(resp):
    # Try several common keys
    if isinstance(resp, dict):
        for k in ('retrieved_chunks', 'chunks', 'docs', 'sources', 'retrieved'):
            if k in resp:
                return resp[k]
    return []


def run():
    with DATASET.open('r', encoding='utf-8') as f:
        qs = json.load(f)

    sample = sample_questions(qs)
    metrics = []

    for item in sample:
        qid = item.get('id') or item.get('question_id') or 'unknown'
        pregunta = item.get('pregunta') or item.get('question') or item.get('q') or item.get('text')
        presente = item.get('ground_truth', {}).get('presente_en_docs') is True

        payload = {'question': pregunta}

        start = time.perf_counter()
        timeout_flag = False
        resp_text = ''
        resp_json = None
        retrieved_chunks = []
        try:
            r = requests.post(RAG_ENDPOINT, json=payload, timeout=TIMEOUT)
            latency = time.perf_counter() - start
            try:
                resp_json = r.json()
                resp_text = resp_json.get('answer') or json.dumps(resp_json)[:1000]
            except Exception:
                resp_text = r.text[:1000]
        except requests.exceptions.Timeout:
            latency = time.perf_counter() - start
            timeout_flag = True
            resp_text = ''
        except Exception as e:
            latency = time.perf_counter() - start
            resp_text = f'ERROR: {e}'

        # Attempt to extract chunks
        if resp_json:
            retrieved_chunks = extract_chunks_from_response(resp_json)

        vm = psutil.virtual_memory()
        proc = psutil.Process()
        rss = proc.memory_info().rss

        vram = get_vram_usage()

        metric = {
            'id': qid,
            'pregunta': pregunta,
            'ground_truth_presente': presente,
            'latency_s': round(latency, 3),
            'timeout': timeout_flag,
            'response_snippet': resp_text[:500] if resp_text else '',
            'retrieved_chunks': retrieved_chunks,
            'host_ram_used': vm.used,
            'host_ram_total': vm.total,
            'process_rss': rss,
            'vram_used_mb': vram,
            'timestamp': time.time()
        }
        metrics.append(metric)
        print(f"[{qid}] latency={metric['latency_s']}s timeout={timeout_flag} vram={vram}")

    with OUTFILE.open('w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    # Print summary
    latencies = [m['latency_s'] for m in metrics]
    timeouts = sum(1 for m in metrics if m['timeout'])
    avg_latency = sum(latencies) / len(latencies) if latencies else None
    print('\n=== Summary ===')
    print('Total queries:', len(metrics))
    print('Timeouts:', timeouts)
    print('Average latency (s):', round(avg_latency, 3) if avg_latency else 'N/A')

    # Update report markdown
    with REPORTMD.open('w', encoding='utf-8') as f:
        f.write('# Resultado 1.0 — Baseline\n\n')
        f.write('Fecha: %s\n\n' % time.strftime('%Y-%m-%d %H:%M:%S'))
        f.write('Resumen: Prueba baseline con 20 preguntas (10 presentes, 10 ausentes).\n\n')
        f.write('- Total consultas: %d\n' % len(metrics))
        f.write('- Encontradas en docs: %d\n' % sum(1 for m in metrics if m['ground_truth_presente']))
        f.write('- Timeouts: %d\n' % timeouts)
        f.write('- Latencia media (s): %s\n\n' % (round(avg_latency,3) if avg_latency else 'N/A'))

        f.write('## Tabla de resultados\n\n')
        f.write('| id | presente_en_docs | latency_s | timeout | vram_mb | response_snippet |\n')
        f.write('|---|---:|---:|---:|---:|---|\n')
        for m in metrics:
            snippet = (m['response_snippet'].replace('\n',' ')[:80] + '...') if m['response_snippet'] else ''
            vram = m['vram_used_mb']
            f.write(f"| {m['id']} | {str(m['ground_truth_presente'])} | {m['latency_s']} | {m['timeout']} | {vram} | {snippet} |\n")

    print('\nMetrics saved to', OUTFILE)


if __name__ == '__main__':
    run()
