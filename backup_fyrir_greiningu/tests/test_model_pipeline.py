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
from check_solution import sannreyna_lausn
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
        self.assertTrue(sannreyna_lausn(self.gogn, self.mappa / "assignments.csv")["pass"])

    def test_hard_coverage_rejects_empty_roster(self):
        self.model.addConstr(self.x.sum() == 0)
        self.model.optimize()
        r = vista_nidurstodu(self.model, self.x, self.gogn, self.mappa)
        self.assertEqual(r["status"], "INFEASIBLE")
        self.assertIsNone(r["coverage_met"])
        self.assertFalse((self.mappa / "assignments.csv").exists())

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

    def test_work_outside_weekend_group_is_allowed(self):
        self.model.dispose()
        self.gogn["monnunar_thorf"] = {(d, "MV", "D"): 6 if d.weekday() >= 5 else 0
                                      for d in self.gogn["dagar"]}
        self.model, self.x = byggja_model(self.gogn)
        self.model.Params.OutputFlag = 0
        self.model.optimize()
        self.assertGreater(self.model.SolCount, 0)
        # Allir þurfa að vinna allar helgar; það hefði brotið gamla 3 daga hámarkið.
        self.assertGreater(sum(v.X for (i, d), v in self.model._aux["aukahelgi"].items()
                               if i == "h1"), 3)

    def test_friday_late_shift_on_free_weekend_is_forbidden(self):
        self.model.dispose()
        fos, lau, sun = date(2026, 2, 6), date(2026, 2, 7), date(2026, 2, 8)
        for i in self.gogn["starfsmenn"]:
            self.gogn["leyfdar"][i] = ["MV", "KV"]
        self.gogn["monnunar_thorf"][fos, "KV", "D"] = 1
        self.model, self.x = byggja_model(self.gogn)
        self.model.Params.OutputFlag = 0
        self.model.addConstr(self.x["h1", fos, "KV", "D"] == 1)
        self.model.addConstr(self.x.sum("h1", lau, "*", "*") == 0)
        self.model.addConstr(self.x.sum("h1", sun, "*", "*") == 0)
        self.model.optimize()
        self.assertEqual(self.model.Status, GRB.INFEASIBLE)


if __name__ == "__main__":
    unittest.main()
