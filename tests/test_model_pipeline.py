"""Prófa tengingu gagnaviðmóts, líkanagerðar og lausnarútflutnings.

Þessi próf koma ekki í stað óháðs lausnarcheckers.
"""
import csv
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

from gurobipy import GRB
from main import reikna_gap, vista_nidurstodu
from model import byggja_model


def litil_gogn():
    dagar = [date(2026, 2, 1) + timedelta(days=k) for k in range(28)]
    starfsmenn = [f"h{k}" for k in range(1, 7)]
    return {"ar": 2026, "manudur": 2, "dagar": dagar,
            "vaktir": ("MV", "KV", "NV"), "starfsmenn": starfsmenn,
            "leyfdar": {i: ["MV"] for i in starfsmenn},
            "haefni": {i: ["D"] for i in starfsmenn},
            "mark": {i: 4.5 for i in starfsmenn}, "hlutverk": ["D"],
            "monnunar_thorf": {(d, "MV", "D"): 1 for d in dagar}}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mappa = Path(self.tmp.name)
        self.gogn = litil_gogn()
        self.model, self.x = byggja_model(self.gogn)
        self.model.Params.OutputFlag = 0
        self.model.Params.TimeLimit = 10
        self.model.Params.Threads = 1

    def tearDown(self):
        self.model.dispose()
        self.tmp.cleanup()

    def test_solution_export_and_unrounded_targets(self):
        self.model.optimize()
        self.assertGreater(self.model.SolCount, 0)
        r = vista_nidurstodu(self.model, self.x, self.gogn, self.mappa)
        self.assertTrue(r["coverage_met"])
        with (self.mappa / "assignments.csv").open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), r["assignment_count"])
        self.assertTrue(all(row["shift"] == "MV" and row["role"] == "D" for row in rows))
        self.assertTrue(all(date.fromisoformat(row["date"]) in self.gogn["dagar"] for row in rows))
        self.assertEqual(len({(row["nurse_id"], row["date"]) for row in rows}), len(rows))
        self.assertEqual(self.gogn["mark"]["h1"], 4.5)

    def test_soft_coverage_is_reported_as_shortage(self):
        self.model.addConstr(self.x.sum() == 0)
        self.model.optimize()
        r = vista_nidurstodu(self.model, self.x, self.gogn, self.mappa)
        self.assertFalse(r["coverage_met"])
        self.assertEqual(r["unfilled_slots"], 28)
        self.assertFalse(r["independent_checker_run"])

    def test_no_incumbent_no_fake_roster(self):
        self.model.addConstr(self.x.sum() <= -1)
        self.model.optimize()
        r = vista_nidurstodu(self.model, self.x, self.gogn, self.mappa)
        self.assertEqual(r["status"], "INFEASIBLE")
        self.assertIsNone(r["coverage_met"])
        self.assertIsNone(r["objective"])
        self.assertFalse((self.mappa / "assignments.csv").exists())
        self.assertIsNone(reikna_gap(None, 5))
        self.assertIsNone(reikna_gap(0, -1))
        self.assertEqual(reikna_gap(0, 0), 0)


if __name__ == "__main__":
    unittest.main()
