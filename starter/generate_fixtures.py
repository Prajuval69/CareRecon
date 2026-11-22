#!/usr/bin/env python3
"""Deterministic synthetic fixture generator; NOT the CareRecon application."""
import argparse, csv, json, random
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / 'data' / 'raw' / 'current'
PREVIOUS = ROOT / 'data' / 'raw' / 'previous'

def write_csv(path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=headers, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)

def main(seed):
    rng = random.Random(seed)
    members = [{'member_id':f'M{i:03}', 'effective_date':'2026-01-01',
                'end_date':'2026-06-30' if i == 13 else '2026-12-31',
                'plan_id':f'PL{(i%3)+1:02}'} for i in range(1,14)]
    providers = [{'provider_id':f'PR{i:03}', 'specialty':specialty,
                  'active_from':'2025-01-01','active_to':'2027-12-31'}
                 for i,specialty in enumerate(['Primary Care','Cardiology','Radiology','Orthopedics','Dermatology','General'],1)]
    pharmacies = [{'pharmacy_id':f'PH{i:03}','name':f'Synthetic Pharmacy {i}',
                   'active_from':'2025-01-01','active_to':'2027-12-31'} for i in range(1,5)]
    payer=[]
    for i in range(1,19):
        allowed=6000+i*250+rng.randrange(0,5)*100
        paid=allowed-500
        payer.append({'payer_claim_id':f'P{i:03}','member_id':f'M{((i-1)%12)+1:03}',
         'provider_id':f'PR{((i-1)%6)+1:03}','service_date':'2026-04-15',
         'status':'PAID','billed_cents':str(allowed+3000),
         'allowed_cents':str(allowed),'paid_cents':str(paid)})
    byid={r['payer_claim_id']:r for r in payer}
    byid['P006']['member_id']=''
    byid['P007']['provider_id']='PR999'
    byid['P008']['member_id']='M013'; byid['P008']['service_date']='2026-11-15'
    byid['P009']['paid_cents']=str(int(byid['P009']['allowed_cents'])+550)
    byid['P010']['status']='DENIED'; byid['P010']['paid_cents']='300'
    payer.append(dict(byid['P003']))  # duplicate business key
    remits=[]
    for ix,claim in enumerate(['P001','P002','P003','P004','P005','P012'],1):
        amt=int(byid[claim]['paid_cents'])+(275 if claim=='P012' else 0)
        remits.append({'remit_id':f'RM{ix:03}','payer_claim_id':claim,
         'provider_id':byid[claim]['provider_id'],'remit_date':'2026-05-01',
         'paid_cents':str(amt),'remit_status':'POSTED'})
    remits.append({'remit_id':'RM_ORPHAN','payer_claim_id':'P_NO_SUCH_CLAIM',
         'provider_id':'PR001','remit_date':'2026-05-02','paid_cents':'2300',
         'remit_status':'POSTED'})
    rx=[]
    for i in range(1,11):
        paid=1000+i*200
        rx.append({'rx_claim_id':f'RX{i:03}','member_id':f'M{((i-1)%12)+1:03}',
          'pharmacy_id':f'PH{((i-1)%4)+1:03}', 'ndc':f'000000000{i:02}',
          'fill_date':'2026-05-15','days_supply':'30','quantity':'30',
          'paid_cents':str(paid),'transaction_type':'DISPENSE','original_rx_claim_id':''})
    rx[2]['days_supply']='0'  # RX003
    rx[3]['transaction_type']='REVERSAL'; rx[3]['original_rx_claim_id']='RX_UNKNOWN'; rx[3]['paid_cents']='-1800' # RX004 orphan
    rx[9]['transaction_type']='REVERSAL'; rx[9]['original_rx_claim_id']='RX002'; rx[9]['paid_cents']=str(-int(rx[1]['paid_cents'])) # RX010 clean reversal
    previous=[]
    previous_seen=set()
    for r in payer:
        if r['payer_claim_id'] in {f'P{i:03}' for i in range(1,13)} and r['payer_claim_id'] not in previous_seen:
            previous.append(dict(r))
            previous_seen.add(r['payer_claim_id'])
    previous.append({'payer_claim_id':'P099','member_id':'M001','provider_id':'PR001',
      'service_date':'2026-03-01','status':'PAID','billed_cents':'6000',
      'allowed_cents':'5500','paid_cents':'4500'})
    names={'member_eligibility':members,'provider_directory':providers,'pharmacy_directory':pharmacies,
           'payer_claims':payer,'provider_remittances':remits,'pharmacy_claims':rx}
    for name,rows in names.items():
        write_csv(CURRENT/f'{name}.csv', list(rows[0].keys()), rows)
    write_csv(PREVIOUS/'payer_claims_previous.csv',list(previous[0].keys()),previous)
    # 2 intentionally incorrect external controls; other controls correct
    controls=[]
    for name,rows in names.items():
        money=sum(int(r['paid_cents']) for r in rows) if 'paid_cents' in rows[0] else 0
        controls.append({'source_name':name,
          'expected_rows':str(len(rows)+(1 if name=='payer_claims' else 0)),
          'expected_paid_cents':str(money+(1234 if name=='pharmacy_claims' else 0)),
          'snapshot_date':'2026-05-31'})
    write_csv(CURRENT/'source_controls.csv',list(controls[0].keys()),controls)
    print(f'Generated {len(names)+2} synthetic CSV fixtures with seed={seed}')
    for name,rows in names.items(): print(f'  {name}: {len(rows)} rows')
    print(f'  payer_claims_previous: {len(previous)} rows; source_controls: {len(controls)} rows')

if __name__=='__main__':
    p=argparse.ArgumentParser(description='Generate deterministic synthetic healthcare fixtures')
    p.add_argument('--seed',type=int,default=2026)
    a=p.parse_args()
    main(a.seed)
