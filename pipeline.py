"""Reproducible educational test analytics; Python standard library only."""
import argparse
import csv
import html
import json
import math
from pathlib import Path
import random
import sqlite3
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent
FIELDS = ['lot_id', 'wafer_id', 'device_id', 'temperature_c', 'voltage_v',
          'current_ma', 'leakage_ua', 'gain_db', 'test_timestamp']
LIMITS = {'leakage_ua_max': 10.0, 'current_ma_max': 60.0, 'gain_db_min': 18.0}
NUMERIC = ['temperature_c', 'voltage_v', 'current_ma', 'leakage_ua', 'gain_db']


def generate(seed=42):
    """One test condition per unique device; conditions are NOT repeated sweeps."""
    rng = random.Random(seed)
    rows = []
    start = datetime(2026, 1, 1, 9)
    for lot in range(1, 13):
        drift = max(0, lot - 8) * 0.36
        for wafer in range(1, 5):
            wafer_offset = rng.gauss(0, 0.06)
            for die in range(250):
                temp = rng.choice([-40, 25, 85])
                voltage = rng.choice([3.0, 3.3, 3.6])
                leakage = 2.5 * math.exp(0.008*(temp-25) + drift + wafer_offset + rng.gauss(0, .2))
                current = 44 + 4*(voltage-3.3) + .045*(temp-25) + rng.gauss(0, 2.5)
                gain = 20.4 - .008*(temp-25) + .3*(voltage-3.3) + rng.gauss(0, .4)
                if rng.random() < .025:
                    defect = rng.choice(['leakage', 'current', 'gain'])
                    if defect == 'leakage':
                        leakage *= 5
                    elif defect == 'current':
                        current += 25
                    else:
                        gain -= 4
                idx = len(rows)
                rows.append(dict(zip(FIELDS, [f'L{lot:02}', f'L{lot:02}-W{wafer:02}',
                    f'D{idx+1:05}', temp, voltage, round(current, 4),
                    round(leakage, 4), round(gain, 4),
                    (start + timedelta(minutes=idx)).isoformat()])))
    # Known corruptions are separate from valid electrical failures.
    for i in range(25):
        rows[i]['leakage_ua'] = ''
        rows[i+25]['current_ma'] = 'instrument_error'
        rows[i+50]['leakage_ua'] = -1
        rows[i+75]['temperature_c'] = 999
    rows.extend(dict(r) for r in rows[100:120])  # Exact duplicate exports.
    return rows


def classify(row):
    """Inclusive spec boundaries; a device may fail several limits."""
    modes = []
    if row['leakage_ua'] > LIMITS['leakage_ua_max']:
        modes.append('HIGH_LEAKAGE')
    if row['current_ma'] > LIMITS['current_ma_max']:
        modes.append('OVER_CURRENT')
    if row['gain_db'] < LIMITS['gain_db_min']:
        modes.append('LOW_GAIN')
    return ('FAIL' if modes else 'PASS', '|'.join(modes) or 'NORMAL')


def validate(rows):
    valid, rejected, seen = [], [], set()
    for index, raw in enumerate(rows, start=2):
        row, reasons = dict(raw), []
        key = str(row.get('device_id', '')).strip()
        for name in ['lot_id', 'wafer_id', 'device_id', 'test_timestamp']:
            if not str(row.get(name, '')).strip():
                reasons.append(f'missing_{name}')
        if key and key in seen:
            reasons.append('duplicate_device_record')
        if key:
            seen.add(key)
        for name in NUMERIC:
            try:
                row[name] = float(row[name])
                if not math.isfinite(row[name]):
                    raise ValueError('nonfinite')
            except (ValueError, TypeError, KeyError):
                reasons.append(f'invalid_{name}')
        if not any(r.startswith('invalid_') for r in reasons):
            if row['temperature_c'] not in [-40, 25, 85]:
                reasons.append('unsupported_temperature_setpoint')
            if row['voltage_v'] not in [3.0, 3.3, 3.6]:
                reasons.append('unsupported_voltage_setpoint')
            for name in ['current_ma', 'leakage_ua']:
                if row[name] < 0:
                    reasons.append(f'negative_{name}')
        try:
            datetime.fromisoformat(str(row.get('test_timestamp', '')))
        except ValueError:
            reasons.append('invalid_timestamp')
        if reasons:
            rejected.append({**raw, 'source_row': index, 'rejection_reason': '|'.join(reasons)})
        else:
            row['test_result'], row['failure_modes'] = classify(row)
            row['dc_power_mw'] = round(row['voltage_v'] * row['current_ma'], 4)
            valid.append(row)
    return valid, rejected


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def analyze(valid):
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    connection.execute('''CREATE TABLE tests (
        lot_id TEXT, wafer_id TEXT, device_id TEXT PRIMARY KEY,
        temperature_c REAL, voltage_v REAL, current_ma REAL,
        leakage_ua REAL, gain_db REAL, test_timestamp TEXT,
        test_result TEXT, failure_modes TEXT, dc_power_mw REAL)''')
    columns = FIELDS + ['test_result', 'failure_modes', 'dc_power_mw']
    connection.executemany('INSERT INTO tests VALUES (' + ','.join('?' for _ in columns) + ')',
                           [[row[c] for c in columns] for row in valid])
    query_text = (ROOT / 'sql' / 'analytics.sql').read_text(encoding='utf-8')
    results = {}
    for block in query_text.split('-- QUERY: ')[1:]:
        name, query = block.split('\n', 1)
        results[name.strip()] = [dict(row) for row in connection.execute(query.strip())]
    connection.commit()
    return connection, results


def report(summary, results):
    worst = min(results['lot_yield'], key=lambda r: r['yield_percent'])
    overall = results['overall'][0]
    finding = (f"{worst['lot_id']} has the lowest observed valid-device yield "
               f"({worst['yield_percent']:.2f}%). Compare its leakage distribution "
               "with earlier lots at the same temperature and voltage. Check instrument "
               "calibration and repeat measurements before investigating a process change.")
    table = ''.join('<tr>' + ''.join(f'<td>{html.escape(str(r[c]))}</td>' for c in
        ['lot_id', 'devices_tested', 'devices_passed', 'yield_percent', 'mean_leakage_ua']) + '</tr>'
        for r in results['lot_yield'])
    bars = ''.join(f'<div class="barrow"><b>{r["lot_id"]}</b><div class="track"><div class="bar" '
        f'style="width:{r["yield_percent"]}%"></div></div><span>{r["yield_percent"]:.2f}%</span></div>'
        for r in results['lot_yield'])
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1"><title>Semiconductor Test Analytics</title>
    <style>body{{font:16px/1.6 system-ui;background:#f4f7fa;color:#182a3d;max-width:1080px;margin:40px auto;padding:24px}}
    h1{{font-size:36px;line-height:1.15}}small{{color:#536a80}}.cards{{display:flex;gap:18px;flex-wrap:wrap}}
    .card,section{{background:white;border:1px solid #dce5ed;border-radius:14px;padding:22px;margin:16px 0}}
    .card b{{display:block;font-size:30px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;text-align:left;border-bottom:1px solid #ddd}}
    .barrow{{display:flex;gap:14px;align-items:center;margin:8px 0}}.track{{flex:1;background:#edf1f5;height:18px;border-radius:5px}}
    .bar{{background:#087e8b;height:18px;border-radius:5px}}.barrow span{{width:75px;text-align:right}}</style>
    <small>EDUCATIONAL SIMULATION · PYTHON + SQL</small><h1>Semiconductor Test<br>Yield & Failure Analysis</h1>
    <p>Synthetic device measurements. Illustrative limits; no company data or product specifications.</p>
    <div class="cards"><div class="card">Valid devices<b>{overall['devices_tested']:,}</b></div>
    <div class="card">Observed yield<b>{overall['yield_percent']:.2f}%</b></div>
    <div class="card">Failed devices<b>{overall['devices_failed']:,}</b></div>
    <div class="card">Quarantined rows<b>{summary['quarantined_rows']}</b></div></div>
    <section><h2>Investigation priority</h2><p>{finding}</p>
    <p>This recovers a deliberately simulated shift; it does not establish a physical root cause.</p></section>
    <section><h2>Yield by lot</h2>{bars}<p>Yield = passing valid devices / all valid devices × 100.</p></section>
    <section><h2>Lot detail</h2><table><tr><th>Lot</th><th>Tested</th><th>Passed</th><th>Yield %</th><th>Mean leakage µA</th></tr>{table}</table></section>
    <section><h2>Method and limitations</h2><p>Seed {summary['seed']}; {summary['raw_rows']:,} raw rows;
    {summary['unique_devices_raw']:,} original devices; {summary['devices_without_valid_result']} devices without a valid result.
    Invalid rows are excluded and disclosed, not silently counted as passing. Missing results can bias observed yield.</p>
    <p>Each device has one assigned test condition. Temperature groups contain different devices.
    Yield here is not proof of passing every operating condition. Limits: leakage ≤ 10 µA, current ≤ 60 mA, gain ≥ 18 dB.
    Gain and leakage are illustrative numerical models, not a validated RF/device simulator. No predictive ML is implemented.</p></section></html>'''
    return page, finding


def run(seed=42):
    output = ROOT / 'outputs'
    output.mkdir(exist_ok=True)
    raw = generate(seed)
    write_csv(ROOT/'data'/'raw_tests.csv', raw, FIELDS)
    # Read back the exported records so validation operates on actual CSV input.
    with (ROOT/'data'/'raw_tests.csv').open(newline='', encoding='utf-8') as f:
        valid, rejected = validate(list(csv.DictReader(f)))
    write_csv(output/'valid_tests.csv', valid, FIELDS + ['test_result', 'failure_modes', 'dc_power_mw'])
    write_csv(output/'quarantined_tests.csv', rejected, FIELDS + ['source_row', 'rejection_reason'])
    connection, results = analyze(valid)
    with sqlite3.connect(output/'tests.sqlite') as target:
        connection.backup(target)
    connection.close()
    for name, rows in results.items():
        if rows:
            write_csv(output/f'{name}.csv', rows, list(rows[0]))
    summary = dict(seed=seed, raw_rows=len(raw), valid_devices=len(valid), quarantined_rows=len(rejected),
        unique_devices_raw=len({r['device_id'] for r in raw}),
        devices_without_valid_result=len({r['device_id'] for r in raw} - {r['device_id'] for r in valid}),
        limits=LIMITS, **results['overall'][0])
    page, finding = report(summary, results)
    summary['finding'] = finding
    (output/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (output/'report.html').write_text(page, encoding='utf-8')
    print(json.dumps(summary, indent=2))
    print('\nOffline report: ' + str(output/'report.html'))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=42)
    run(parser.parse_args().seed)
