"""Starter-fixture tests only, not the CareRecon implementation tests."""
import csv, json, subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class StarterFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable,str(ROOT/'starter'/'generate_fixtures.py'),'--seed','2026'],check=True,capture_output=True)
    def load(self,name,prior=False):
        p=ROOT/'data'/'raw'/('previous' if prior else 'current')/(name+'.csv')
        with p.open(newline='',encoding='utf-8') as f: return list(csv.DictReader(f))
    def test_generator_outputs_eight_csv_sources(self):
        self.assertEqual(len(list((ROOT/'data'/'raw'/'current').glob('*.csv'))),7)
        self.assertEqual(len(list((ROOT/'data'/'raw'/'previous').glob('*.csv'))),1)
    def test_exact_expected_counts(self):
        expected=json.loads((ROOT/'data'/'expected'/'seeded_scenarios.json').read_text())['expected_raw_rows']
        for name,count in expected.items(): self.assertEqual(len(self.load(name,prior=(name=='payer_claims_previous'))),count)
    def test_duplicate_business_key(self):
        rows=self.load('payer_claims');self.assertEqual(sum(r['payer_claim_id']=='P003' for r in rows),2)
    def test_member_and_provider_exceptions(self):
        rows={r['payer_claim_id']:r for r in self.load('payer_claims')}
        self.assertEqual(rows['P006']['member_id'],'');self.assertEqual(rows['P007']['provider_id'],'PR999')
    def test_payment_and_denial_examples(self):
        rows={r['payer_claim_id']:r for r in self.load('payer_claims')}
        self.assertGreater(int(rows['P009']['paid_cents']),int(rows['P009']['allowed_cents']))
        self.assertEqual(rows['P010']['status'],'DENIED');self.assertNotEqual(int(rows['P010']['paid_cents']),0)
    def test_remit_examples(self):
        rows={r['payer_claim_id']:r for r in self.load('provider_remittances')}
        self.assertIn('P_NO_SUCH_CLAIM',rows);self.assertEqual(rows['P012']['remit_status'],'POSTED')
    def test_pharmacy_valid_reversal(self):
        rows={r['rx_claim_id']:r for r in self.load('pharmacy_claims')}
        self.assertEqual(rows['RX010']['original_rx_claim_id'],'RX002')
        self.assertEqual(int(rows['RX010']['paid_cents']),-int(rows['RX002']['paid_cents']))
    def test_controls_intentionally_wrong(self):
        controls={r['source_name']:r for r in self.load('source_controls')}
        self.assertEqual(int(controls['payer_claims']['expected_rows']),20)
        self.assertEqual(int(controls['pharmacy_claims']['expected_paid_cents']),sum(int(r['paid_cents']) for r in self.load('pharmacy_claims'))+1234)
    def test_snapshot_disappearance_example(self):
        prev={r['payer_claim_id'] for r in self.load('payer_claims_previous',prior=True)}
        curr={r['payer_claim_id'] for r in self.load('payer_claims')}
        self.assertIn('P099',prev-curr)
    def test_rule_manifest_coverage(self):
        rules=json.loads((ROOT/'config'/'rules.json').read_text())['rules']
        expected=json.loads((ROOT/'data'/'expected'/'seeded_scenarios.json').read_text())['expected_findings']
        self.assertEqual({r['rule_id'] for r in rules},{r['rule_id'] for r in expected})

if __name__=='__main__':unittest.main()
