"""Mæla gæði úr assignments.csv; engar nýjar skorður eða Gurobi-háð föll.

Frávik eru vaktareiningar, ekki staðfest launaleg yfirvinna/vanvinna.
Sanngirnismælingar lýsa úthlutunum; staðfesta ekki að lausnin sé sanngjörn.
"""
from collections import Counter, defaultdict
import csv
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
from statistics import mean, pstdev

DAGUR = timedelta(days=1)


def skrifa_toflu(slod, radir, haus):
    with Path(slod).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=haus)
        w.writeheader()
        w.writerows(radir)


def fingrafar_gagna(gogn):
    """Stöðugt fingrafar þeirra gagna og forsendna sem líkanið notar."""
    data = {
        "ar": gogn["ar"], "manudur": gogn["manudur"],
        "dagar": [d.isoformat() for d in gogn["dagar"]],
        "starfsmenn": [{"id": i, "mark": gogn["mark"][i],
            "leyfdar": sorted(gogn["leyfdar"][i]), "haefni": sorted(gogn["haefni"][i])}
            for i in sorted(gogn["starfsmenn"])],
        "thorf": [[d.isoformat(), s, r, q] for (d, s, r), q in sorted(gogn["monnunar_thorf"].items())],
        "saga": [[i, d.isoformat(), s] for (i, d), s in sorted(gogn.get("fyrri_vaktir", {}).items())],
        "forsendur": gogn.get("forsendur", {})}
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def meta_lausn(gogn, assignments, helgarhopar):
    """Skila samantekt, starfsmannatöflu, vaktatöflu og sambærilegum NV-hópum.

    Kallandi keyrir óháðan checker fyrst. Hér eru eingöngu mældar gildar
    úthlutanir með einn viðmiðunarhelgarhóp (0/1/2) fyrir hvern starfsmann.
    """
    if set(helgarhopar) != set(gogn["starfsmenn"]) or any(g not in (0, 1, 2) for g in helgarhopar.values()):
        raise ValueError("Vantar gildan viðmiðunarhelgarhóp fyrir alla starfsmenn.")
    shifts, roles, seats = Counter(), Counter(), Counter()
    helgardagar, auka, helgar = Counter(), Counter(), defaultdict(set)
    seen = set()
    with Path(assignments).open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            i, d, s, r = row["nurse_id"], date.fromisoformat(row["date"]), row["shift"], row["role"]
            if (i not in gogn["starfsmenn"] or d not in gogn["dagar"]
                    or s not in gogn["leyfdar"][i] or r not in gogn["haefni"][i]
                    or gogn["monnunar_thorf"].get((d, s, r), 0) <= 0 or (i, d) in seen):
                raise ValueError("Gæðamat þarf gildar úthlutanir; keyrið checker fyrst.")
            seen.add((i, d))
            shifts[i, s] += 1
            roles[i, r] += 1
            seats[d, s, r] += 1
            if d.weekday() >= 5 or (d.weekday() == 4 and s in ("KV", "NV")):
                fos = d - (d.weekday() - 4) * DAGUR
                group = (fos.toordinal() // 7) % 3
                helgardagar[i] += 1
                helgar[i].add(fos)
                auka[i] += int(group != helgarhopar[i])

    nurses = []
    for i in gogn["starfsmenn"]:
        fjoldi = sum(shifts[i, s] for s in gogn["vaktir"])
        mark = gogn["mark"][i]
        fravik = fjoldi - mark
        row = {"nurse_id": i, "target": mark, "assigned": fjoldi,
            "below_target": max(0, -fravik), "above_target": max(0, fravik),
            "deviation": fravik, "relative_deviation": fravik / mark if mark > 0 else None,
            "MV": shifts[i, "MV"], "KV": shifts[i, "KV"], "NV": shifts[i, "NV"],
            "night_share": shifts[i, "NV"] / fjoldi if fjoldi else None,
            "shift_pattern": "-".join(s for s in gogn["vaktir"] if s in gogn["leyfdar"][i]),
            "weekend_days": helgardagar[i], "weekends_worked": len(helgar[i]),
            "reference_group": helgarhopar[i], "extra_weekend_days": auka[i],
            "V_eligible": "V" in gogn["haefni"][i], "V_count": roles[i, "V"],
            "V_share": roles[i, "V"] / fjoldi if fjoldi else None,
            "T_eligible": "T" in gogn["haefni"][i], "T_count": roles[i, "T"],
            "T_share": roles[i, "T"] / fjoldi if fjoldi else None}
        nurses.append(row)

    coverage = []
    for s in gogn["vaktir"]:
        need = sum(q for (d, ss, r), q in gogn["monnunar_thorf"].items() if ss == s)
        assigned = sum(n[s] for n in nurses)
        missing = sum(max(0, q - seats[d, ss, r]) for (d, ss, r), q in gogn["monnunar_thorf"].items() if ss == s)
        surplus = sum(max(0, seats[d, ss, r] - q) for (d, ss, r), q in gogn["monnunar_thorf"].items() if ss == s)
        coverage.append({"shift": s, "required": need, "assigned": assigned,
                         "missing": missing, "overstaffing": surplus})

    # Aðeins fólk með NV-heimild; jafn vaktamark og sama vaktamynstur í hverjum hópi.
    # Þetta tekur ekki tillit til óstaðfestra NV-óska í frjálsum texta.
    groups = defaultdict(list)
    for n in nurses:
        if "NV" in gogn["leyfdar"][n["nurse_id"]]:
            groups[n["shift_pattern"], round(n["target"], 6)].append(n)
    night_groups = []
    for (pattern, target), group in sorted(groups.items()):
        nights = [n["NV"] for n in group]
        night_groups.append({"shift_pattern": pattern, "target": target, "nurses": len(group),
            "min_NV": min(nights), "max_NV": max(nights), "mean_NV": mean(nights),
            "range_NV": max(nights) - min(nights),
            "nurse_ids": ";".join(n["nurse_id"] for n in group)})
    deviations = [n["deviation"] for n in nurses]
    relative = [n["relative_deviation"] for n in nurses if n["relative_deviation"] is not None]
    worst = max(nurses, key=lambda n: abs(n["deviation"]), default=None)
    worst_relative = max((n for n in nurses if n["relative_deviation"] is not None),
                         key=lambda n: abs(n["relative_deviation"]), default=None)
    summary = {"below_target": sum(n["below_target"] for n in nurses),
        "above_target": sum(n["above_target"] for n in nurses),
        "total_workload_deviation": sum(abs(v) for v in deviations),
        "mean_deviation": mean(deviations) if deviations else None,
        "std_deviation": pstdev(deviations) if deviations else None,
        "std_relative_deviation": pstdev(relative) if relative else None,
        "max_absolute_deviation": abs(worst["deviation"]) if worst else None,
        "worst_absolute_nurse": worst["nurse_id"] if worst else None,
        "max_absolute_relative_deviation": abs(worst_relative["relative_deviation"]) if worst_relative else None,
        "worst_relative_nurse": worst_relative["nurse_id"] if worst_relative else None,
        "extra_weekend_days": sum(auka.values()),
        "max_extra_weekend_days": max(auka.values(), default=0),
        "overstaffing": sum(c["overstaffing"] for c in coverage),
        "unfilled_slots": sum(c["missing"] for c in coverage),
        "assignment_count": len(seen), "night_count": sum(n["NV"] for n in nurses)}
    return summary, nurses, coverage, night_groups


def vista_gaedamat(gogn, mappa, helgarhopar):
    summary, nurses, coverage, night_groups = meta_lausn(gogn, mappa / "assignments.csv", helgarhopar)
    skrifa_toflu(mappa / "quality_by_nurse.csv", nurses, list(nurses[0]) if nurses else ["nurse_id"])
    skrifa_toflu(mappa / "quality_by_shift.csv", coverage, list(coverage[0]))
    skrifa_toflu(mappa / "night_groups.csv", night_groups,
        ["shift_pattern", "target", "nurses", "min_NV", "max_NV", "mean_NV", "range_NV", "nurse_ids"])
    (mappa / "quality.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return summary


def teikna_keyrslu(mappa):
    """Vista framvindu og stærstu vinnuskyldufrávik sem sjálfstæð PNG-myndrit."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with (mappa / "progress.csv").open(encoding="utf-8") as f:
        progress = list(csv.DictReader(f))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    for name, label in (("incumbent", "Besta fundna lausn"), ("best_bound", "Neðri mörk")):
        data = [(float(r["elapsed_seconds"]), float(r[name])) for r in progress if r[name]]
        if data:
            axes[0].plot(*zip(*data), label=label)
    axes[0].set(xlabel="Tími (sek.)", ylabel="Markfallseiningar", title="Incumbent og BestBd")
    axes[0].legend()
    gaps = [(float(r["elapsed_seconds"]), float(r["gap"]) * 100) for r in progress if r["gap"]]
    if gaps:
        axes[1].plot(*zip(*gaps))
    axes[1].set(xlabel="Tími (sek.)", ylabel="Gap (%)", title="Óvissa í lausnarleit")
    fig.savefig(mappa / "solver_progress.png", dpi=180)
    plt.close(fig)
    with (mappa / "quality_by_nurse.csv").open(encoding="utf-8") as f:
        nurses = list(csv.DictReader(f))
    worst = sorted(nurses, key=lambda n: abs(float(n["deviation"])), reverse=True)[:20]
    fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
    ax.bar([n["nurse_id"] for n in worst], [float(n["deviation"]) for n in worst])
    ax.axhline(0, color="black", linewidth=.8)
    ax.set(xlabel="Starfsmaður", ylabel="Vaktir yfir (+) / undir (−) marki",
           title="20 stærstu einstaklingsfrávikin frá vinnuskyldumarki")
    ax.tick_params(axis="x", rotation=45)
    fig.savefig(mappa / "workload_deviation.png", dpi=180)
    plt.close(fig)


def teikna_naemni(mappa, radir):
    """Bera saman hráa mælikvarða, ekki mismunandi vigtuð markfallsgildi."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    valid = [r for r in radir if r.get("checker_pass")]
    if not valid:
        return
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), layout="constrained")
    for ax, key, title in zip(axes, ("total_workload_deviation", "overstaffing", "extra_weekend_days"),
                             ("Heildarvinnuskyldufrávik", "Umframúthlutanir", "Aukahelgardagar")):
        ax.bar([str(r["weekend_weight"]) for r in valid], [r[key] for r in valid])
        ax.set(xlabel="Helgarvigt", ylabel="Vaktir / dagar", title=title)
    fig.suptitle("Sami mánuður og sömu tímamörk; besta lausn hverrar keyrslu, ekki staðfest optimum")
    fig.savefig(mappa / "sensitivity.png", dpi=180)
    plt.close(fig)
