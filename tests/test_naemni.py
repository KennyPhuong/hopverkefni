"""Prófa sams konar inntök og heiðarlega meðhöndlun keyrslu án incumbent."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from naemni import keyra_naemni
from greining import fingrafar_gagna
from test_model_pipeline import litil_gogn


class SensitivityTests(unittest.TestCase):
    def test_same_data_and_no_solution_does_not_get_fake_quality(self):
        gogn=litil_gogn()
        gogn['forsendur']={}
        fingerprint=fingrafar_gagna(gogn)
        calls=[]
        def run(g,folder,w_aukahelgi):
            calls.append((id(g),w_aukahelgi))
            folder.mkdir()
            has_solution=w_aukahelgi!=100
            result={'data_fingerprint':fingerprint,'status':'TIME_LIMIT','solution_count':int(has_solution),
                    'runtime_seconds':60,'gap':.2 if has_solution else None,
                    'unfilled_slots':0 if has_solution else None}
            if has_solution:
                result.update(independent_checker_run=True,checker_pass=True,
                              quality={'extra_weekend_days':4,'overstaffing':2})
                (folder/'check.json').write_text(json.dumps({'violations':[]}))
            return result
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'experiment'
            with patch('naemni.lesa_novembergogn',return_value=gogn), \
                 patch('naemni.keyra_likan',side_effect=run),patch('naemni.teikna_naemni'):
                _,rows=keyra_naemni('ónotuð_slóð',folder)
            self.assertEqual(calls,[(id(gogn),25),(id(gogn),50),(id(gogn),100)])
            self.assertIsNone(rows[2]['total_workload_deviation'])
            self.assertIsNone(rows[2]['unfilled_slots'])
            self.assertFalse(rows[2]['checker_pass'])
            self.assertEqual(len({r['data_fingerprint'] for r in rows}),1)
            self.assertTrue((folder/'sensitivity.csv').exists())

    def test_mutated_data_aborts_comparison(self):
        gogn=litil_gogn();gogn['forsendur']={}
        fingerprint=fingrafar_gagna(gogn)
        def mutate(g,*args,**kwargs):
            g['mark']['h1']+=1
            return {'data_fingerprint':fingerprint}
        with tempfile.TemporaryDirectory() as tmp:
            with patch('naemni.lesa_novembergogn',return_value=gogn),patch('naemni.keyra_likan',side_effect=mutate):
                with self.assertRaisesRegex(ValueError,'Gögn breyttust'):
                    keyra_naemni('ónotuð_slóð',Path(tmp)/'experiment')
