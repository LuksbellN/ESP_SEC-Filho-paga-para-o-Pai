"""Detector didático de candidatos a CPFP em blocos JSON do arquivo da disciplina."""
import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
import tarfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

KS = (1.5, 2.0, 3.0)


def coinbase(tx):
    ins = tx['inputs']
    return len(ins) == 1 and ins[0]['prev_out'].get('n') == 4294967295


def transaction_metrics(tx: dict) -> dict:
    """Valores em satoshis; tamanho virtual conforme peso, nunca tamanho bruto."""
    ins, outs = tx['inputs'], tx['out']
    if not ins or not outs:
        raise ValueError('Transação sem entradas ou saídas')
    values = [i['prev_out']['value'] for i in ins] + [o['value'] for o in outs]
    if any(type(v) is not int or v < 0 for v in values):
        raise ValueError('Valor monetário inválido')
    fee = sum(i['prev_out']['value'] for i in ins) - sum(o['value'] for o in outs)
    weight = tx['weight']
    if fee < 0 or tx.get('fee', fee) != fee:
        raise ValueError('Taxa incompatível com entradas e saídas')
    if type(weight) is not int or weight <= 0:
        raise ValueError('Peso inválido')
    vsize = (weight + 3) // 4
    return dict(fee_sat=fee, vsize=vsize, rate=fee / vsize)


def rejection_reasons(fp, vp, fc, vc, median_rate, k=2.0):
    rp, rc = fp / vp, fc / vc
    conditions = (
        ('pai_abaixo_mediana', rp < median_rate),
        ('filho_taxa_absoluta_maior', fc > fp),
        ('filho_taxa_relativa_maior', rc > rp and rc >= k * rp),
        ('conjunto_alcanca_mediana',
         (fp + fc) / (vp + vc) >= median_rate),
    )
    return [name for name, valid in conditions if not valid]


def is_candidate(fp: int, vp: int, fc: int, vc: int,
                 median_rate: float, k: float = 2.0) -> bool:
    return not rejection_reasons(fp, vp, fc, vc, median_rate, k)


def analyze_block(block: dict) -> dict:
    txs = block['tx']
    if block['n_tx'] != len(txs):
        raise ValueError('Contagem de transações inconsistente')
    index, positions, metrics, outputs = {}, {}, {}, {}
    hashes = set()
    for pos, tx in enumerate(txs):
        idx = tx['tx_index']
        if idx in index or tx['hash'] in hashes:
            raise ValueError('Identificador de transação duplicado')
        index[idx], positions[idx] = tx, pos
        hashes.add(tx['hash'])
        outmap = {o['n']: o for o in tx['out']}
        if len(outmap) != len(tx['out']):
            raise ValueError('Índice de saída duplicado')
        outputs[idx] = outmap
        if not coinbase(tx):
            metrics[idx] = transaction_metrics(tx)
    median = statistics.median(m['rate'] for m in metrics.values()) if metrics else 0
    edges, adjacent, spent = {}, defaultdict(set), set()
    for child, tx in index.items():
        if child not in metrics:
            continue
        for item in tx['inputs']:
            prev = item['prev_out']
            parent, n = prev['tx_index'], prev['n']
            key = parent, n
            if key in spent:
                raise ValueError('Saída consumida mais de uma vez no bloco')
            spent.add(key)
            if parent not in index:
                continue
            if parent not in metrics or positions[parent] >= positions[child]:
                raise ValueError('Pai interno inválido ou fora de ordem')
            output = outputs[parent].get(n)
            if output is None or output['value'] != prev['value']:
                raise ValueError('Saída interna inexistente ou valor divergente')
            edges.setdefault((parent, child), []).append(dict(
                n=n, value=output['value'], address=output.get('addr')))
            adjacent[parent].add(child)
            adjacent[child].add(parent)
    visited, simple, complex_sizes = set(), [], []
    for start in adjacent:
        if start in visited:
            continue
        stack, component = [start], set()
        visited.add(start)
        while stack:
            node = stack.pop()
            component.add(node)
            for neighbor in adjacent[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        if len(component) == 2:
            a, b = sorted(component, key=positions.get)
            simple.append((a, b))
        else:
            complex_sizes.append(len(component))
    pairs = []
    for parent, child in simple:
        p, c = metrics[parent], metrics[child]
        fp, vp, fc, vc = p['fee_sat'], p['vsize'], c['fee_sat'], c['vsize']
        row = dict(height=block['height'], parent=index[parent]['hash'],
                   child=index[child]['hash'], parent_fee=fp, child_fee=fc,
                   parent_vsize=vp, child_vsize=vc, parent_rate=p['rate'],
                   child_rate=c['rate'], median_rate=median,
                   package_rate=(fp + fc) / (vp + vc),
                   consumed_sat=sum(o['value'] for o in edges[parent, child]),
                   consumed_outputs=edges[parent, child])
        row['uplift'] = row['package_rate'] - row['parent_rate']
        for k in KS:
            row[f'candidate_{k}'] = is_candidate(fp, vp, fc, vc, median, k)
        row['reasons'] = '|'.join(rejection_reasons(fp, vp, fc, vc, median))
        pairs.append(row)
    info = dict(height=block['height'], hash=block['hash'], time=block['time'],
                normal_transactions=len(metrics), coinbase=len(txs)-len(metrics),
                median_rate=median, edges=len(edges), simple_pairs=len(pairs),
                complex_components=len(complex_sizes),
                complex_transactions=sum(complex_sizes),
                candidates=sum(p['candidate_2.0'] for p in pairs))
    return dict(block_row=info, pairs=pairs, complex_components=complex_sizes)


def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, list)
                             else v for k, v in row.items()})


def stats(values):
    return dict(count=len(values), minimum=min(values) if values else None,
                median=statistics.median(values) if values else None,
                maximum=max(values) if values else None, total=sum(values))


def run_analysis(archive: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with archive.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    blocks, pairs, seen_blocks, seen_heights, seen_txs = [], [], set(), set(), set()
    with tarfile.open(archive, 'r|gz') as tar:
        for member in tar:
            if not member.isfile():
                continue
            block = json.load(tar.extractfile(member))
            if block['hash'] in seen_blocks or block['height'] in seen_heights:
                raise ValueError('Bloco duplicado')
            if Path(member.name).name != block['hash']:
                raise ValueError('Nome do arquivo não corresponde ao hash do bloco')
            seen_blocks.add(block['hash'])
            seen_heights.add(block['height'])
            for tx in block['tx']:
                if tx['hash'] in seen_txs:
                    raise ValueError('Transação repetida entre blocos')
                seen_txs.add(tx['hash'])
            result = analyze_block(block)
            blocks.append(result['block_row'])
            pairs.extend(result['pairs'])
            print(f"Bloco {block['height']}: {len(result['pairs'])} pares; "
                  f"{result['block_row']['candidates']} candidatos", flush=True)
    if not blocks:
        raise ValueError('Arquivo sem blocos')
    blocks.sort(key=lambda b: b['height'])
    pairs.sort(key=lambda p: (p['height'], p['parent']))
    candidates = [p for p in pairs if p['candidate_2.0']]
    address_rows = {}
    for pair in candidates:
        by_address = defaultdict(int)
        for out in pair['consumed_outputs']:
            by_address[out['address'] or '(ausente)'] += out['value']
        for address, value in by_address.items():
            a = address_rows.setdefault(address, dict(address=address, pairs=0, value_sat=0))
            a['pairs'] += 1
            a['value_sat'] += value
    addresses = sorted(address_rows.values(), key=lambda a: (-a['pairs'], a['address']))
    first = sorted(candidates, key=lambda p: (-p['uplift'], p['height'], p['parent']))[:1]
    rest = sorted([p for p in candidates if p not in first],
                  key=lambda p: (p['parent_rate'], p['height'], p['parent']))[:1]
    examples = first + rest if candidates else pairs[:1]
    normal = sum(b['normal_transactions'] for b in blocks)
    metrics = ['parent_fee', 'child_fee', 'parent_rate', 'child_rate',
               'package_rate', 'consumed_sat', 'uplift']
    summary = dict(
        archive_sha256=digest, archive_bytes=archive.stat().st_size,
        python=platform.python_version(), parameters=dict(k=2.0, sensitivity=list(KS)),
        blocks=len(blocks), height_min=blocks[0]['height'], height_max=blocks[-1]['height'],
        start_utc=datetime.fromtimestamp(min(b['time'] for b in blocks), timezone.utc).isoformat(),
        end_utc=datetime.fromtimestamp(max(b['time'] for b in blocks), timezone.utc).isoformat(),
        normal_transactions=normal, coinbase=sum(b['coinbase'] for b in blocks),
        direct_dependencies=sum(b['edges'] for b in blocks), simple_pairs=len(pairs),
        complex_components=sum(b['complex_components'] for b in blocks),
        complex_transactions=sum(b['complex_transactions'] for b in blocks),
        candidates=len(candidates), unique_parents=len({p['parent'] for p in candidates}),
        unique_children=len({p['child'] for p in candidates}),
        blocks_with_candidates=sum(b['candidates'] > 0 for b in blocks),
        candidate_fraction_pairs=len(candidates)/len(pairs) if pairs else None,
        candidate_fraction_transactions=len(candidates)/normal if normal else None,
        zero_fee_parents=sum(p['parent_fee'] == 0 for p in candidates),
        sensitivity={str(k): sum(p[f'candidate_{k}'] for p in pairs) for k in KS},
        metrics={name: stats([p[name] for p in candidates]) for name in metrics},
        unique_addresses=sum(a['address'] != '(ausente)' for a in addresses),
        missing_address_outputs=sum(o['address'] is None for p in candidates
                                    for o in p['consumed_outputs']),
        consumed_outputs=sum(len(p['consumed_outputs']) for p in candidates),
        top_addresses=addresses[:5], examples=examples, anomalies=0,
    )
    # Componentes simples são disjuntos: taxas e valores não duplicam transações.
    summary['unique_fee_total_sat'] = sum(p['parent_fee'] + p['child_fee'] for p in candidates)
    fields = list(pairs[0]) if pairs else [
        'height', 'parent', 'child', 'parent_fee', 'child_fee', 'parent_vsize',
        'child_vsize', 'parent_rate', 'child_rate', 'median_rate', 'package_rate',
        'consumed_sat', 'consumed_outputs', 'uplift', 'candidate_1.5',
        'candidate_2.0', 'candidate_3.0', 'reasons']
    write_csv(output/'pairs.csv', pairs, fields)
    write_csv(output/'blocks.csv', blocks, list(blocks[0]))
    write_csv(output/'addresses.csv', addresses, ['address', 'pairs', 'value_sat'])
    (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ['blocks', 'normal_transactions',
          'direct_dependencies', 'simple_pairs', 'complex_components', 'candidates', 'sensitivity']}, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=Path('../blocos.tgz'))
    parser.add_argument('--output', type=Path, default=Path('results'))
    args = parser.parse_args()
    run_analysis(args.archive, args.output)
