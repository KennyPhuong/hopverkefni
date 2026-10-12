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
from model import byggja_model, STILLINGAR


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

    def test_weekend_weight_only_changes_its_objective_coefficients(self):
        other, _ = byggja_model(self.gogn, w_aukahelgi=25)
        try:
            self.model.update()
            other.update()
            self.assertEqual((self.model.NumVars, self.model.NumConstrs), (other.NumVars, other.NumConstrs))
            for a, b in zip(self.model.getVars(), other.getVars()):
                self.assertEqual(a.VarName, b.VarName)
                self.assertEqual((a.LB, a.UB, a.VType), (b.LB, b.UB, b.VType))
                if a.VarName.startswith("aukahelgi["):
                    self.assertEqual((a.Obj, b.Obj), (50, 25))
                else:
                    self.assertEqual(a.Obj, b.Obj)
            self.assertEqual(STILLINGAR["w_aukahelgi"], 50)
            for a, b in zip(self.model.getConstrs(), other.getConstrs()):
                self.assertEqual((a.ConstrName, a.Sense, a.RHS), (b.ConstrName, b.Sense, b.RHS))
        finally:
            other.dispose()

    def test_invalid_weekend_weights_are_rejected(self):
        for weight in (0, -1, True, "50", float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                byggja_model(self.gogn, w_aukahelgi=weight)

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


class FjolbreytniTests(unittest.TestCase):
    """Mjúku reglurnar um fjölbreytni vakta og hvíld frá vaktstjórn."""

    def _leysa(self, gogn):
        m, x = byggja_model(gogn)
        m.Params.OutputFlag = 0
        m.Params.TimeLimit = 20
        m.Params.Threads = 1
        m.optimize()
        self.assertGreater(m.SolCount, 0)
        return m, x

    def test_shift_types_are_balanced(self):
        dagar = [date(2026, 2, 2) + timedelta(days=k) for k in range(14)]
        folk = [f"h{k}" for k in range(1, 7)]
        g = {"ar": 2026, "manudur": 2, "dagar": dagar, "vaktir": ("MV", "KV", "NV"),
             "starfsmenn": folk, "leyfdar": {i: ["MV", "KV", "NV"] for i in folk},
             "haefni": {i: ["D"] for i in folk}, "mark": {i: 7 for i in folk},
             "hlutverk": ["D"],
             "monnunar_thorf": {(d, s, "D"): 1 for d in dagar for s in ("MV", "KV", "NV")}}
        m, x = self._leysa(g)
        try:
            vm = STILLINGAR["vikmork_vaktategund"]
            for i in folk:
                alls = x.sum(i, "*", "*", "*").getValue()
                for s in ("MV", "KV", "NV"):
                    self.assertLessEqual(abs(x.sum(i, "*", s, "*").getValue() - alls / 3), vm + 1e-6)
            self.assertAlmostEqual(sum(v.X for v in m._aux["ojafnvaegi_vakta"].values()), 0)
        finally:
            m.dispose()

    def test_charge_nurses_rotate_out_of_v_role(self):
        dagar = [date(2026, 2, 2) + timedelta(days=k) for k in range(14)]
        folk = [f"h{k}" for k in range(1, 5)]
        g = {"ar": 2026, "manudur": 2, "dagar": dagar, "vaktir": ("MV", "KV", "NV"),
             "starfsmenn": folk, "leyfdar": {i: ["MV"] for i in folk},
             # mark 8: hver má vera V mest 4 sinnum, 4 x 4 = 16 >= 14 V-vaktir.
             "haefni": {i: ["V", "D"] for i in folk}, "mark": {i: 8 for i in folk},
             "hlutverk": ["D", "V"],
             "monnunar_thorf": {(d, "MV", r): 1 for d in dagar for r in ("V", "D")}}
        m, x = self._leysa(g)
        try:
            for i in folk:
                alls = x.sum(i, "*", "*", "*").getValue()
                self.assertLessEqual(x.sum(i, "*", "*", "V").getValue(),
                                     STILLINGAR["hamark_vaktstjora"] * alls + 1e-6)
            self.assertAlmostEqual(sum(v.X for v in m._aux["ofmikid_vaktstjori"].values()), 0)
        finally:
            m.dispose()


if __name__ == "__main__":
    unittest.main()
