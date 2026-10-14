"""Keyra eitt verkefni: nóvember 2026. Engin mánaðarvalmynd eða CLI-stillingar.

Les CSV, byggir/leysir líkan, vistar lausn og keyrir óháða yfirferð.
Óstaðfestar gagnatúlkanir eru sýndar og varðveittar í run.json.
"""
from collections import Counter
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
from uuid import uuid4

import gurobipy as gp
from gurobipy import GRB

from data import lesa_novembergogn
from model import byggja_model
from check_solution import sannreyna_lausn
from greining import fingrafar_gagna, vista_gaedamat, teikna_keyrslu, vista_vaktaplan

MAPPA = Path(__file__).resolve().parent
TIMAMORK = 600
GAP = 0


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


def keyra_likan(gogn, mappa, w_aukahelgi=50):
    """Sameiginleg keyrsla með sömu solver-stillingum; engin warm start.

    Hver keyrsla fær nýja möppu. Eingöngu helgarvigt er breytileg.
    """
    mappa = Path(mappa)
    mappa.mkdir(parents=True, exist_ok=False)
    model = None
    try:
        model, x = byggja_model(gogn, w_aukahelgi=w_aukahelgi)
        model.Params.TimeLimit = TIMAMORK
        model.Params.MIPGap = GAP
        model.Params.Seed = 0
        model.Params.Threads = 2
        # Gurobi á Windows ræður ekki við stafi eins og ó/ð í slóð.
        # Þá er loggurinn skrifaður í Temp og færður í niðurstöðumöppuna á eftir.
        loka_log = mappa / "solver.log"
        if str(loka_log).isascii():
            gurobi_log = loka_log
        else:
            gurobi_log = Path(tempfile.gettempdir()) / f"gurobi_{uuid4().hex}.log"
        model.Params.LogFile = str(gurobi_log)
        model._progress = []
        model.optimize(framvinda)
        if gurobi_log != loka_log:
            model.Params.LogFile = ""          # loka loggskránni áður en hún er færð
            shutil.move(str(gurobi_log), str(loka_log))
        yfirlit = vista_nidurstodu(model, x, gogn, mappa)
        yfirlit["gurobi_version"] = list(gp.gurobi.version())
        yfirlit["data_fingerprint"] = fingrafar_gagna(gogn)
        yfirlit["solver_parameters"] = {"TimeLimit": TIMAMORK, "MIPGap": GAP, "Seed": 0, "Threads": 2}
        if model.SolCount:
            check = sannreyna_lausn(gogn, mappa / "assignments.csv")
            (mappa / "check.json").write_text(json.dumps(check, ensure_ascii=False, indent=2), encoding="utf-8")
            yfirlit.update(independent_checker_run=True, checker_pass=check["pass"],
                           boundaries_verified=check["boundaries_verified"])
            yfirlit["objective_components"] = {
                "vinnuskylda": model._aux["stillingar"]["w_vinnuskylda"] *
                    sum(v.X for key in ("undir_vinnuskyldu", "yfir_vinnuskyldu") for v in model._aux[key].values()),
                "umframmonnun": model._aux["stillingar"]["w_umframmonnun"] *
                    sum(v.X for v in model._aux["umframmonnun"].values()),
                "aukahelgi": model._aux["stillingar"]["w_aukahelgi"] *
                    sum(v.X for v in model._aux["aukahelgi"].values()),
                "vaktajafnvaegi": model._aux["stillingar"]["w_vaktajafnvaegi"] *
                    sum(v.X for v in model._aux["ojafnvaegi_vakta"].values()),
                "vaktstjori": model._aux["stillingar"]["w_vaktstjori"] *
                    sum(v.X for v in model._aux["ofmikid_vaktstjori"].values())}
            helgarhopar = {i: g for (i, g), v in model._aux["helgarhopur"].items() if v.X > .5}
            skrifa_csv(mappa / "weekend_groups.csv", ["nurse_id", "reference_group"], sorted(helgarhopar.items()))
            if check["pass"]:
                yfirlit["quality"] = vista_gaedamat(gogn, mappa, helgarhopar)
        elif model.Status == GRB.INFEASIBLE:
            model.computeIIS()
            model.write(str(mappa / "infeasible.ilp"))
        (mappa / "run.json").write_text(json.dumps(yfirlit, ensure_ascii=False, indent=2,
                                                  allow_nan=False), encoding="utf-8")
        model._progress.append((model.Runtime, yfirlit["objective"], yfirlit["bound"],
                                reikna_gap(yfirlit["objective"], yfirlit["bound"])))
        skrifa_csv(mappa / "progress.csv", ["elapsed_seconds", "incumbent", "best_bound", "gap"], model._progress)
        if yfirlit.get("checker_pass"):
            teikna_keyrslu(mappa)
            vista_vaktaplan(gogn, mappa)
        print("\nStaða:", yfirlit["status"], "| Niðurstöður:", mappa)
        if model.SolCount == 0:
            print("Engin lausn fannst; ekkert vaktaplan var vistað.")
            return yfirlit
        print("Úthlutaðar vaktir:", yfirlit["assignment_count"], "| Ómönnuð sæti:", yfirlit["unfilled_slots"])
        print("Óháð yfirferð innan mánaðar:", "STÓÐST" if yfirlit["checker_pass"] else "FÉLL")
        print("Þetta staðfestir ekki óþekkt mánaðarmörk, textatakmarkanir eða vinnuskylduforsendurnar.")
        return yfirlit
    finally:
        if model is not None:
            model.dispose()


def main(gagnamappa=MAPPA):
    """Baseline fyrir nóvember 2026; engin mánaðarvalmynd."""
    try:
        gogn = lesa_novembergogn(gagnamappa)
        print("Nóvember 2026:", len(gogn["starfsmenn"]), "virkir starfsmenn.", flush=True)
        print("ÓSTAÐFEST: vinnuhlutfallsfrádráttur, fullt vaktamark 30/7*5, "
              "textatakmarkanir og mánaðarmörk.", flush=True)
        mappa = MAPPA / "results" / f"einfalt_november_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}"
        yfirlit = keyra_likan(gogn, mappa)
        if not yfirlit["solution_count"]:
            return 2
        return 0 if yfirlit.get("checker_pass") else 3
    except (ValueError, FileNotFoundError, gp.GurobiError) as villa:
        print("Keyrsla stöðvað:", villa, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
