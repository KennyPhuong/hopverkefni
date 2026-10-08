"""Óháð yfirferð assignments.csv; enginn innflutningur úr model.py.

Athugar útfærðu hörðu reglurnar innan nóvember. Hún staðfestir ekki
vinnulöggjöf, textatakmarkanir eða óþekkta vaktasögu yfir mánaðarmörk.
"""
from collections import Counter
import csv
from datetime import date, timedelta
import json
from pathlib import Path
import sys

DAGUR = timedelta(days=1)


def sannreyna_lausn(gogn, assignments):
    """Skila JSON-hæfu pass/violations/metrics yfirliti úr vistuðum úthlutunum."""
    villur = []

    def villa(regla, **atriði):
        villur.append({"regla": regla, **atriði})

    dagar = gogn["dagar"]
    nofn = set(gogn["starfsmenn"])
    thorf = gogn["monnunar_thorf"]
    unnir, monnun, fjoldi, tegundir = {}, Counter(), Counter(), Counter()
    with Path(assignments).open(encoding="utf-8", newline="") as skra:
        reader = csv.DictReader(skra)
        if reader.fieldnames != ["nurse_id", "date", "shift", "role"]:
            return {"pass": False, "violations": [{"regla": "skrasnid"}], "metrics": {}}
        for rad, row in enumerate(reader, 2):
            i, s, r = row["nurse_id"], row["shift"], row["role"]
            try:
                d = date.fromisoformat(row["date"])
                if row["date"] != d.isoformat():
                    raise ValueError("Dagsetning þarf ISO-snið")
            except (ValueError, TypeError):
                villa("dagsetning", rad=rad, gildi=row["date"])
                continue
            if i not in nofn or d not in dagar:
                villa("auðkenni_eða_dagur", rad=rad, starfsmaður=i, dagur=d.isoformat())
                continue
            if s not in gogn["leyfdar"][i] or r not in gogn["haefni"][i]:
                villa("hæfni_eða_vakt", rad=rad, starfsmaður=i, vakt=s, hlutverk=r)
            if (d, s, r) not in thorf or thorf.get((d, s, r), 0) <= 0:
                villa("óskilgreint_sæti", rad=rad, dagur=d.isoformat(), vakt=s, hlutverk=r)
            if (i, d) in unnir:
                villa("ein_vakt_a_dag", starfsmaður=i, dagur=d.isoformat())
            else:
                unnir[i, d] = s
            monnun[d, s, r] += 1
            fjoldi[i] += 1
            tegundir[i, s] += 1
    vantar = 0
    for (d, s, r), q in thorf.items():
        missir = max(0, q - monnun[d, s, r])
        vantar += missir
        if missir:
            villa("monnun", dagur=d.isoformat(), vakt=s, hlutverk=r, vantar=missir)

    saga = gogn.get("fyrri_vaktir", {})
    for i in nofn:
        vaktir = {d: s for (n, d), s in saga.items() if n == i and d < dagar[0]}
        vaktir.update({d: s for (n, d), s in unnir.items() if n == i})
        nv_rod = vinnu_rod = 0
        # Streak-talning, ekki endurnotkun á gluggaskorðum model.py.
        d = dagar[0] - 7 * DAGUR
        while d <= dagar[-1]:
            s, fyrri = vaktir.get(d), vaktir.get(d - DAGUR)
            if d in dagar:
                if (fyrri == "NV" and s in ("MV", "KV")) or (fyrri == "KV" and s == "MV"):
                    villa("hvild", starfsmaður=i, dagur=d.isoformat(), fyrri=fyrri, vakt=s)
                if fyrri == "NV" and s != "NV" and nv_rod >= 2:
                    if s is not None:
                        villa("svefndagur", starfsmaður=i, dagur=d.isoformat())
                    eftir = d + DAGUR
                    if eftir in dagar and vaktir.get(eftir) == "MV":
                        villa("endurkoma_eftir_nv", starfsmaður=i, dagur=eftir.isoformat())
            nv_rod = nv_rod + 1 if s == "NV" else 0
            vinnu_rod = vinnu_rod + 1 if s is not None else 0
            if d in dagar and nv_rod > 4:
                villa("max_nv_rod", starfsmaður=i, dagur=d.isoformat(), fjöldi=nv_rod)
            if d in dagar and vinnu_rod > 6:
                villa("max_dagar_rod", starfsmaður=i, dagur=d.isoformat(), fjöldi=vinnu_rod)
            d += DAGUR
        for lau in dagar:
            fos, sun = lau - DAGUR, lau + DAGUR
            if lau.weekday() == 5 and fos in dagar and sun in dagar:
                if (i, lau) not in unnir and (i, sun) not in unnir and unnir.get((i, fos)) in ("KV", "NV"):
                    villa("frihelgi_fostudagur", starfsmaður=i, dagur=fos.isoformat())

    auka = sum(max(0, monnun[k] - q) for k, q in thorf.items())
    return {"pass": not villur, "scope": "útfærðar harðar reglur innan mánaðar",
        "boundaries_verified": False,
        "notes": ["Óþekkt saga telst frí; framhald eftir lok mánaðar er óþekkt.",
                  "Vinnuskylda og helgarmynstur eru mjúk viðmið, ekki pass/fail reglur.",
                  "Samnings-/athugasemdatexti og raunverulegar hvíldarklukkustundir eru ekki yfirfarin."],
        "violations": villur, "metrics": {"unfilled_slots": vantar,
            "assignment_count": sum(fjoldi.values()), "overstaffing": auka,
            "total_workload_deviation": sum(abs(fjoldi[i] - gogn["mark"][i]) for i in nofn),
            "shifts_by_nurse": dict(sorted(fjoldi.items())),
            "shift_mix": {i: {s: tegundir[i, s] for s in gogn["vaktir"]} for i in sorted(nofn)}}}


if __name__ == "__main__":
    from data import lesa_novembergogn
    if len(sys.argv) != 2:
        raise SystemExit("Notkun: python check_solution.py results/<keyrsla>/assignments.csv")
    result = sannreyna_lausn(lesa_novembergogn(Path(__file__).resolve().parent), sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 1)
