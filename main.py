"""Tengja CSV-gögn og núverandi MIP; vista lausn og sýna mönnunarskort.

Þetta er samþættingarprófun með skráðum einföldunarforsendum.
Óháður lausnarchecker, myndrit og skýrsla eru ekki hluti þessarar skrár.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys
from uuid import uuid4

import gurobipy as gp
from gurobipy import GRB

from data import bua_til_dagsetningar, undirbua_gogn
from model import byggja_model

MAPPA = Path(__file__).resolve().parent
FRA_DRATTUR = ["verkefni", "bor", "namsleyfi", "stjornun", "faeding", "leyfi", "veikindi"]


def skrifa_csv(slod, haus, radir):
    """Vista fast dálkasnið, einnig haus þegar engar raðir eru til."""
    with slod.open("w", encoding="utf-8", newline="") as skra:
        writer = csv.writer(skra)
        writer.writerow(haus)
        writer.writerows(radir)


def framvinda(model, where):
    """Skrá incumbent/bound á MIP-stigi; None þar til lausn hefur fundist."""
    if where != GRB.Callback.MIP:
        return
    timi = model.cbGet(GRB.Callback.RUNTIME)
    if model._progress and timi - model._progress[-1][0] < 1:
        return
    fjoldi = model.cbGet(GRB.Callback.MIP_SOLCNT)
    incumbent = model.cbGet(GRB.Callback.MIP_OBJBST) if fjoldi else None
    bound = model.cbGet(GRB.Callback.MIP_OBJBND)
    bound = bound if abs(bound) < 1e90 else None
    gap = reikna_gap(incumbent, bound)
    model._progress.append((timi, incumbent, bound, gap))


def reikna_gap(incumbent, bound):
    """Óskilgreint gap er None, aldrei tilbúið núll."""
    if incumbent is None or bound is None:
        return None
    if incumbent == 0:
        return 0.0 if bound == 0 else None
    return abs(incumbent - bound) / abs(incumbent)


def vista_nidurstodu(model, x, gogn, mappa):
    """Lesa X aðeins ef incumbent er til; telja raunmönnun úr úthlutunum."""
    status_heiti = {GRB.OPTIMAL: "OPTIMAL", GRB.TIME_LIMIT: "TIME_LIMIT",
        GRB.INFEASIBLE: "INFEASIBLE", GRB.INF_OR_UNBD: "INF_OR_UNBD",
        GRB.UNBOUNDED: "UNBOUNDED", GRB.INTERRUPTED: "INTERRUPTED"}
    hefur_lausn = model.SolCount > 0
    yfirlit = {"schema_version": 1, "ar": gogn["ar"], "manudur": gogn["manudur"],
        "status": status_heiti.get(model.Status, str(model.Status)),
        "status_code": model.Status, "solution_count": model.SolCount,
        "runtime_seconds": model.Runtime, "variables": model.NumVars,
        "constraints": model.NumConstrs, "objective": model.ObjVal if hefur_lausn else None,
        "bound": model.ObjBound if model.IsMIP and abs(model.ObjBound) < 1e90 else None,
        "gap": model.MIPGap if hefur_lausn and math.isfinite(model.MIPGap) else None,
        "staff_count": len(gogn["starfsmenn"]), "forsendur": gogn.get("forsendur", {}),
        "utskildir": gogn.get("utskildir", []), "leidrettingar": gogn.get("leidrettingar", []),
        "stillingar": model._aux["stillingar"],
        "fyrri_vaktir_gefnar": bool(gogn.get("fyrri_vaktir")),
        "oskir_gefnar": bool(gogn.get("oskir")),
        "independent_checker_run": False,
        "coverage_met": None, "unfilled_slots": None}
    # Engin assignments.csv er skrifuð ef lausn vantar.
    if hefur_lausn:
        radir = sorted((i, d.isoformat(), s, r) for (i, d, s, r), v in x.items() if v.X > .5)
        skrifa_csv(mappa / "assignments.csv", ["nurse_id", "date", "shift", "role"], radir)
        talning = Counter((d, s, r) for i, d, s, r in radir)
        monnun, skortur = [], 0
        for (d, s, r), thorf in sorted(gogn["monnunar_thorf"].items()):
            fjoldi = talning[d.isoformat(), s, r]
            vantar = max(0, thorf - fjoldi)
            skortur += vantar
            monnun.append((d.isoformat(), s, r, thorf, fjoldi, vantar))
        skrifa_csv(mappa / "coverage.csv", ["date", "shift", "role", "required", "assigned", "missing"], monnun)
        vaktatalning = Counter(i for i, d, s, r in radir)
        skrifa_csv(mappa / "workload.csv", ["nurse_id", "target", "assigned", "deviation"],
            ((i, gogn["mark"][i], vaktatalning[i], vaktatalning[i] - gogn["mark"][i]) for i in gogn["starfsmenn"]))
        yfirlit.update(coverage_met=skortur == 0, unfilled_slots=skortur,
                       assignment_count=len(radir))
    return yfirlit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ar", type=int, default=2026)
    parser.add_argument("--manudur", type=int, default=11)
    parser.add_argument("--gagnamappa", type=Path, default=MAPPA)
    parser.add_argument("--nidurstodumappa", type=Path, default=MAPPA / "results")
    parser.add_argument("--vaktir-100", type=float,
        help="Fullt vaktamark; annars sýnileg prófunarforsenda dagar/7*5.")
    parser.add_argument("--timamork", type=float, default=60)
    parser.add_argument("--gap", type=float, default=.05)
    args = parser.parse_args(argv)
    if not math.isfinite(args.timamork) or args.timamork <= 0:
        parser.error("timamork þurfa að vera jákvæð og endanleg.")
    if not math.isfinite(args.gap) or not 0 <= args.gap <= 1:
        parser.error("gap þarf að vera á bilinu 0–1.")

    model = None
    try:
        dagar = bua_til_dagsetningar(args.ar, args.manudur)
        fullt = args.vaktir_100 if args.vaktir_100 is not None else len(dagar) / 7 * 5
        sleppa = {"h74": "Óútkljáður vaktakóði 12-20-KV.",
                  "h124": "Óútkljáður vaktakóði MV-KV-4.",
                  "h147": "Ógildur hæfnifáni a=11."}
        if args.manudur == 11:
            sleppa["h100"] = "Neikvætt reiknað hlutfall í nóvember."
        print("PRÓFUNARFORSENDUR: frádráttur án NM; jafnlangar vaktir; sama þörf alla daga; "
              "mánaðarprósentur ráða; neikvætt virkt hlutfall verður 0.", flush=True)
        print("Fullt vaktamark:", round(fullt, 4),
              "(prófunarregla dagar/7*5)" if args.vaktir_100 is None else "(gefið inntak)", flush=True)
        print("Útilokanir:", sleppa, flush=True)
        gogn = undirbua_gogn(args.ar, args.manudur, args.gagnamappa,
            fra_drattur=FRA_DRATTUR, vaktir_100=fullt, jafnlangar_vaktir=True,
            sama_thorf_alla_daga=True, textastefna="manadarprosentur",
            neikvaett_i_null=True, sleppa_starfsmonnum=sleppa)
        print(f"Gögn tilbúin: {len(gogn['starfsmenn'])} starfsmenn, {len(dagar)} dagar.", flush=True)
        print("Líkanið hefur mjúka mönnun og harða helgarhópa. Fyrri vaktir og óskir "
              "eru ekki gefnar; hvíld yfir mánaðarmörk er því ekki staðfest.", flush=True)
        mappa = args.nidurstodumappa.resolve() / (
            f"{args.ar}-{args.manudur:02d}_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}")
        mappa.mkdir(parents=True)
        model, x = byggja_model(gogn)
        model.Params.TimeLimit = args.timamork
        model.Params.MIPGap = args.gap
        model.Params.Seed = 0
        model.Params.Threads = 2
        model.Params.LogFile = str(mappa / "solver.log")
        model._progress = []
        model.optimize(framvinda)
        yfirlit = vista_nidurstodu(model, x, gogn, mappa)
        yfirlit.update(gurobi_version=list(gp.gurobi.version()),
            solver_parameters={"TimeLimit": args.timamork, "MIPGap": args.gap, "Seed": 0, "Threads": 2},
            vaktamark_heimild="inntak" if args.vaktir_100 is not None else "profun: dagar/7*5")
        # Vista fingraför CSV-heimilda og kóðans svo keyrslan sé rekjanleg.
        heimild = args.gagnamappa.resolve()
        if heimild.is_file():
            heimild = heimild.parent
        skrar = [*sorted(heimild.glob("HR-gognin*.csv")),
                 MAPPA / "data.py", MAPPA / "model.py", MAPPA / "main.py"]
        yfirlit["sha256"] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in skrar}
        yfirlit["boundaries"] = "Engin saga; óþekktar fyrri vaktir teljast frí. Engin framhaldsáætlun."
        (mappa / "run.json").write_text(json.dumps(yfirlit, ensure_ascii=False, indent=2,
                                                  allow_nan=False), encoding="utf-8")
        final_gap = reikna_gap(yfirlit["objective"], yfirlit["bound"])
        model._progress.append((model.Runtime, yfirlit["objective"], yfirlit["bound"], final_gap))
        skrifa_csv(mappa / "progress.csv", ["elapsed_seconds", "incumbent", "best_bound", "gap"], model._progress)
        print("\nStaða:", yfirlit["status"], "| Lausnir:", model.SolCount)
        print("Niðurstöður:", mappa)
        if model.SolCount == 0:
            print("Engin úthlutun vistuð: engin lausn fannst í þessari keyrslu.")
            return 2
        print("Úthlutaðar vaktir:", yfirlit["assignment_count"])
        print("Ómönnuð sæti:", yfirlit["unfilled_slots"])
        if not yfirlit["coverage_met"]:
            print("Mönnunarþörf er ekki uppfyllt. Þetta vaktaplan er ekki tilbúið til skila.")
            return 3
        print("Mönnunarþörf uppfyllt. Óháður checker hefur ekki verið keyrður.")
        return 0
    except (ValueError, FileNotFoundError, gp.GurobiError) as villa:
        print("Keyrsla stöðvað:", villa, file=sys.stderr)
        return 1
    finally:
        if model is not None:
            model.dispose()


if __name__ == "__main__":
    sys.exit(main())
