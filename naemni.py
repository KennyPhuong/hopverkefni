"""Þrjár næmnikeyrslur fyrir sama nóvember: helgarvigt 25, 50 og 100."""
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4
from data import lesa_novembergogn
from greining import fingrafar_gagna, skrifa_toflu, teikna_naemni
from main import MAPPA, TIMAMORK, GAP, keyra_likan

VIGTIR = (25, 50, 100)


def keyra_naemni(gagnamappa=MAPPA, nidurstodumappa=None):
    """Lesa gögn einu sinni og breyta aðeins helgarvigt; ekkert mánaðarviðmót."""
    gogn = lesa_novembergogn(gagnamappa)
    fingerprint = fingrafar_gagna(gogn)
    mappa = Path(nidurstodumappa) if nidurstodumappa else (
        MAPPA / "results" / f"naemni_november_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}")
    mappa.mkdir(parents=True, exist_ok=False)
    radir = []
    for vigt in VIGTIR:
        print(f"\nNÆMNIGREINING: helgarvigt {vigt}, tímamörk {TIMAMORK} sek.", flush=True)
        run = keyra_likan(gogn, mappa / f"helgarvigt_{vigt}", w_aukahelgi=vigt)
        if fingrafar_gagna(gogn) != fingerprint or run["data_fingerprint"] != fingerprint:
            raise ValueError("Gögn breyttust milli næmnikeyrslna.")
        row = {"weekend_weight": vigt, "status": run["status"],
            "solution_count": run["solution_count"], "runtime_seconds": run["runtime_seconds"],
            "gap": run["gap"], "checker_pass": run.get("checker_pass", False),
            "hard_violations": None, "unfilled_slots": run["unfilled_slots"],
            "data_fingerprint": fingerprint, "run_folder": f"helgarvigt_{vigt}"}
        if run.get("independent_checker_run"):
            check = json.loads((mappa / row["run_folder"] / "check.json").read_text())
            row["hard_violations"] = len(check["violations"])
        for key in ("below_target", "above_target", "total_workload_deviation", "overstaffing",
                    "extra_weekend_days", "max_extra_weekend_days", "max_absolute_deviation",
                    "max_absolute_relative_deviation", "assignment_count"):
            row[key] = run.get("quality", {}).get(key)
        radir.append(row)
        skrifa_toflu(mappa / "sensitivity.csv", radir, list(row))
    (mappa / "experiment.json").write_text(json.dumps({"data_fingerprint": fingerprint,
        "weekend_weights": VIGTIR, "time_limit": TIMAMORK, "mip_gap": GAP,
        "seed": 0, "threads": 2, "warm_start": False,
        "interpretation": "Samanburður bestu fundnu lausna; mismunandi gap getur haft áhrif á niðurstöður.",
        "forsendur": gogn["forsendur"], "results": radir}, ensure_ascii=False, indent=2), encoding="utf-8")
    teikna_naemni(mappa, radir)
    print("\nNæmniniðurstöður:", mappa)
    return mappa, radir


if __name__ == "__main__":
    _, rows = keyra_naemni()
    raise SystemExit(0 if all(r["checker_pass"] for r in rows) else 1)
