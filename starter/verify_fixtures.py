#!/usr/bin/env python3
"""Inspect starter data and planted examples. This is NOT the implemented rule engine."""
import csv, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def read(name,previous=False):
    p=ROOT/'data'/'raw'/('previous' if previous else 'current')/(name+'.csv')
    with p.open(newline='',encoding='utf-8') as fh: return list(csv.DictReader(fh))

def verify(verbose=True):
    expected=json.loads((ROOT/'data'/'expected'/'seeded_scenarios.json').read_text())
    datasets={k:read(k,previous=(k=='payer_claims_previous')) for k in expected['expected_raw_rows']}
    for k,count in expected['expected_raw_rows'].items():
        assert len(datasets[k])==count, f'{k}: expected {count}, got {len(datasets[k])}'
    payer=datasets['payer_claims']; ids=[r['payer_claim_id'] for r in payer]
    assert ids.count('P003')==2
    lookup={r['payer_claim_id']:r for r in payer}
    assert lookup['P006']['member_id']==''
    assert lookup['P007']['provider_id']=='PR999'
    assert lookup['P008']['member_id']=='M013' and lookup['P008']['service_date']>'2026-06-30'
    assert int(lookup['P009']['paid_cents'])>int(lookup['P009']['allowed_cents'])
    assert lookup['P010']['status']=='DENIED' and int(lookup['P010']['paid_cents'])!=0
    remits=datasets['provider_remittances']; remit={r['payer_claim_id']:r for r in remits}
    assert int(remit['P012']['paid_cents'])-int(lookup['P012']['paid_cents'])==275
    assert 'P_NO_SUCH_CLAIM' in remit
    rx={r['rx_claim_id']:r for r in datasets['pharmacy_claims']}
    assert rx['RX003']['days_supply']=='0'
    assert rx['RX004']['original_rx_claim_id']=='RX_UNKNOWN'
    assert rx['RX010']['original_rx_claim_id']=='RX002' and int(rx['RX010']['paid_cents'])==-int(rx['RX002']['paid_cents'])
    controls={r['source_name']:r for r in datasets['source_controls']}
    assert int(controls['payer_claims']['expected_rows'])==len(payer)+1
    assert int(controls['pharmacy_claims']['expected_paid_cents'])==sum(int(r['paid_cents']) for r in rx.values())+1234
    assert 'P099' in {r['payer_claim_id'] for r in datasets['payer_claims_previous']} and 'P099' not in ids
    assert len(expected['expected_findings'])==13
    if verbose: print('PASS: starter fixtures, 13 planted scenarios and valid matched reversal RX010 verified')
    return True

if __name__=='__main__':
    try: verify()
    except Exception as e:
        print(f'FAIL: {e}',file=sys.stderr);sys.exit(1)
