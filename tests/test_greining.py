"""Afmörkuð próf á mælingum og fastum gögnum í næmnikeyrslum."""
import copy
import csv
from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data import bua_til_dagsetningar
from greining import fingrafar_gagna, meta_lausn, vista_gaedamat


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.rows = [('h1','2026-11-09','NV','D'), ('h1','2026-11-10','NV','D'),
                     ('h1','2026-11-12','KV','V'), ('h2','2026-11-06','MV','D'),
                     ('h4','2026-11-06','MV','D')]
        self.g = {'ar':2026,'manudur':11,'dagar':bua_til_dagsetningar(2026,11),
            'starfsmenn':['h1','h2','h3','h4'], 'vaktir':('MV','KV','NV'),
            'leyfdar':{'h1':['MV','KV','NV'],'h2':['MV','KV','NV'],'h3':['NV'],'h4':['MV']},
            'haefni':{'h1':['D','V','T'],'h2':['D'],'h3':['D'],'h4':['D']},
            'mark':{'h1':2,'h2':2,'h3':2,'h4':0},
            'monnunar_thorf':{(date.fromisoformat(d),s,r):1 for i,d,s,r in self.rows}}
        self.groups = {i:0 for i in self.g['starfsmenn']}
        self.write(self.rows)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rows):
        with (self.folder/'assignments.csv').open('w',newline='') as f:
            w=csv.writer(f); w.writerow(['nurse_id','date','shift','role']); w.writerows(rows)

    def test_deviations_zero_denominators_and_role_shares(self):
        q, nurses, shifts, groups = meta_lausn(self.g,self.folder/'assignments.csv',self.groups)
        n = {r['nurse_id']:r for r in nurses}
        self.assertEqual(q['below_target'],3)
        self.assertEqual(q['above_target'],2)
        self.assertEqual(q['total_workload_deviation'],5)
        self.assertEqual(q['overstaffing'],1)
        self.assertEqual(q['unfilled_slots'],0)
        self.assertEqual(n['h1']['relative_deviation'],.5)
        self.assertAlmostEqual(n['h1']['V_share'],1/3)
        self.assertIsNone(n['h3']['night_share'])
        self.assertIsNone(n['h4']['relative_deviation'])
        self.assertEqual(sum(r['assigned'] for r in shifts),5)

    def test_night_groups_exclude_noneligible_and_separate_patterns(self):
        _, _, _, groups = meta_lausn(self.g,self.folder/'assignments.csv',self.groups)
        mixed = next(r for r in groups if r['shift_pattern']=='MV-KV-NV')
        self.assertEqual(mixed['nurses'],2)
        self.assertEqual((mixed['min_NV'],mixed['max_NV']),(0,2))
        only = next(r for r in groups if r['shift_pattern']=='NV')
        self.assertEqual(only['nurse_ids'],'h3')
        self.assertFalse(any('h4' in r['nurse_ids'] for r in groups))

    def test_friday_morning_does_not_count_as_weekend_burden(self):
        q, *_ = meta_lausn(self.g,self.folder/'assignments.csv',self.groups)
        self.assertEqual(q['extra_weekend_days'],0)

    def test_weekend_days_and_blocks_from_exported_assignments(self):
        rows=[('h1',f'2026-11-{d:02d}','KV','D') for d in (6,7,8)]
        self.g['monnunar_thorf']={(date.fromisoformat(d),s,r):1 for i,d,s,r in rows}
        fos=date(2026,11,6)
        self.groups['h1']=((fos.toordinal()//7)%3+1)%3
        self.write(rows)
        q,nurses,*_=meta_lausn(self.g,self.folder/'assignments.csv',self.groups)
        n=next(r for r in nurses if r['nurse_id']=='h1')
        self.assertEqual(q['extra_weekend_days'],3)
        self.assertEqual(n['weekends_worked'],1)
        self.assertEqual(n['weekend_days'],3)

    def test_invalid_roster_is_not_scored(self):
        self.write(self.rows+[self.rows[0]])
        with self.assertRaises(ValueError):
            meta_lausn(self.g,self.folder/'assignments.csv',self.groups)

    def test_exports_include_all_staff_and_separate_units(self):
        vista_gaedamat(self.g,self.folder,self.groups)
        with (self.folder/'quality_by_nurse.csv').open() as f:
            nurses=list(csv.DictReader(f))
        self.assertEqual(len(nurses),4)
        self.assertEqual((self.folder/'quality.json').exists(),True)
        self.assertEqual((self.folder/'quality_by_shift.csv').exists(),True)
        self.assertEqual((self.folder/'night_groups.csv').exists(),True)

    def test_fingerprint_stable_and_sensitive_to_target_changes(self):
        original=fingrafar_gagna(self.g)
        self.assertEqual(original,fingrafar_gagna(copy.deepcopy(self.g)))
        self.g['mark']['h1']+=.1
        self.assertNotEqual(original,fingrafar_gagna(self.g))
