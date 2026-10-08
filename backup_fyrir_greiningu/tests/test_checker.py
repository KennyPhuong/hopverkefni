"""Villudæmi fyrir óháðan checker; enginn Gurobi-innflutningur."""
import csv
from datetime import date
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_solution import sannreyna_lausn
from data import bua_til_dagsetningar


class CheckerTests(unittest.TestCase):
    def athuga(self, rows, extra_demand=None, saga=None):
        gogn = {"dagar": bua_til_dagsetningar(2026, 11), "starfsmenn": ["h1"], "vaktir": ("MV", "KV", "NV"),
                "leyfdar": {"h1": ["MV", "KV", "NV"]}, "haefni": {"h1": ["D"]},
                "mark": {"h1": 3.5},
                "monnunar_thorf": {(date.fromisoformat(d), s, "D"): 1 for i, d, s, r in rows},
                "fyrri_vaktir": saga or {}}
        gogn["monnunar_thorf"].update(extra_demand or {})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "assignments.csv"
            with path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["nurse_id", "date", "shift", "role"])
                writer.writerows(rows)
            return sannreyna_lausn(gogn, path)

    def reglur(self, result):
        return {v["regla"] for v in result["violations"]}

    def test_valid_night_recovery(self):
        r = self.athuga([("h1", "2026-11-09", "NV", "D"),
                         ("h1", "2026-11-10", "NV", "D"),
                         ("h1", "2026-11-12", "KV", "D")])
        self.assertTrue(r["pass"])
        self.assertFalse(r["boundaries_verified"])

    def test_missing_coverage(self):
        r = self.athuga([], {(date(2026, 11, 2), "MV", "D"): 1})
        self.assertIn("monnun", self.reglur(r))

    def test_duplicates_and_unqualified_role(self):
        for rows, rule in (([("h1", "2026-11-02", "MV", "D")] * 2, "ein_vakt_a_dag"),
                           ([("h1", "2026-11-02", "MV", "V")], "hæfni_eða_vakt")):
            self.assertIn(rule, self.reglur(self.athuga(rows)))

    def test_rest_and_recovery(self):
        for rows, rule in (
            ([("h1", "2026-11-09", "NV", "D"), ("h1", "2026-11-10", "KV", "D")], "hvild"),
            ([("h1", "2026-11-09", "NV", "D"), ("h1", "2026-11-10", "NV", "D"),
              ("h1", "2026-11-12", "MV", "D")], "endurkoma_eftir_nv")):
            self.assertIn(rule, self.reglur(self.athuga(rows)))

    def test_run_limits(self):
        for n, shift, rule in ((5, "NV", "max_nv_rod"), (7, "MV", "max_dagar_rod")):
            rows = [("h1", f"2026-11-{d:02d}", shift, "D") for d in range(2, 2 + n)]
            self.assertIn(rule, self.reglur(self.athuga(rows)))

    def test_free_weekend_friday(self):
        r = self.athuga([("h1", "2026-11-06", "KV", "D")])
        self.assertIn("frihelgi_fostudagur", self.reglur(r))

    def test_given_history_is_checked(self):
        r = self.athuga([("h1", "2026-11-01", "MV", "D")],
                        saga={("h1", date(2026, 10, 31)): "NV"})
        self.assertIn("hvild", self.reglur(r))

    def test_invalid_id_and_date(self):
        for row, rule in ((('h999', '2026-11-02', 'MV', 'D'), 'auðkenni_eða_dagur'),
                          (('h1', 'ekki dagur', 'MV', 'D'), 'dagsetning')):
            # Vantar eða ógild dagsetning er prófuð án þess að nota hana sem demand-lykil.
            g = {"dagar": bua_til_dagsetningar(2026, 11), "starfsmenn": ["h1"], "vaktir": ("MV", "KV", "NV"),
                 "leyfdar": {"h1": ["MV"]}, "haefni": {"h1": ["D"]},
                 "mark": {"h1": 1}, "monnunar_thorf": {}}
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / 'assignments.csv'
                with p.open('w', newline='') as f:
                    w = csv.writer(f)
                    w.writerow(['nurse_id', 'date', 'shift', 'role'])
                    w.writerow(row)
                self.assertIn(rule, self.reglur(sannreyna_lausn(g, p)))
