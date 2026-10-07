from datetime import timedelta

import gurobipy as gp
from gurobipy import GRB

DAGUR = timedelta(days=1)

# Reglur og vigtir á einum stað. main.py getur sent inn breytta útgáfu
# (t.d. fyrir næmnigreiningu): byggja_model(gogn, {**STILLINGAR, "max_nv_rod": 5})
STILLINGAR = {
    # Harðar reglur
    "max_nv_rod": 4,             # hámark næturvakta í röð
    "max_dagar_rod": 6,          # hámark vinnudaga í röð
    "banna_kv_mv": True,         # engin MV daginn eftir KV (11 klst. hvíld)
    "fjoldi_helgarhopa": 3,      # vinna þriðju hverja helgi
    # Viðmið fyrir mjúkar reglur
    "vikmork_vaktir": 2,         # leyfilegt frávik frá jafnri skiptingu MV/KV/NV
    "hamark_hlutverks": 0.5,     # mest helmingur vakta sem vaktstjóri / í forgangsflokkun
    "stjornunarhlutverk": ("V", "T"),
    # Vigtir í markfalli
    "w_undirmonnun": 1000,
    "w_vinnuskylda": 10,
    "w_oskir": 20,
    "w_vaktajafnvaegi": 5,
    "w_hlutverk": 3,
    "w_helgarmynstur": 2,
    "w_umframmonnun": 1,
}


def helgar_hopur(d, fjoldi_hopa=3):
    """Helgarhópur dagsetningar (fös/lau/sun), eða None fyrir mán–fim."""
    vd = d.weekday()                       # 0=mán ... 4=fös, 5=lau, 6=sun
    if vd < 4:
        return None
    fostudagur = d - (vd - 4) * DAGUR
    return (fostudagur.toordinal() // 7) % fjoldi_hopa


def byggja_model(gogn, stillingar=None):
    """
    Byggir líkan fyrir dagsetningarnar og gögnin sem eru gefin.

    Skilar:
        model: Gurobi-líkaninu
        x: Binary úthlutunarbreytunum

    Hjálparbreytur (undirmönnun, frávik o.fl.) eru geymdar í model._aux
    svo main.py geti lesið þær eftir lausn.

    Valkvæð gögn í gogn:
        "fyrri_vaktir": {(starfsmaður, dagsetning): vakt} síðustu daga
                        fyrri mánaðar, notað fyrir hvíld yfir mánaðarmörk.
        "oskir":        {(starfsmaður, dagsetning): "FRI" | "MV" | "KV" | "NV"}

    Fallið leysir ekki líkanið. Það er gert í main.py.
    """
    st = {**STILLINGAR, **(stillingar or {})}

    # ---------- 1. Gögn ----------
    starfsmenn = gogn["starfsmenn"]
    dagar = gogn["dagar"]
    leyfdar = gogn["leyfdar"]
    haefni = gogn["haefni"]
    hlutverk = gogn["hlutverk"]
    monnunar_thorf = gogn["monnunar_thorf"]
    mark = gogn["mark"]
    fyrri_vaktir = gogn.get("fyrri_vaktir", {})
    oskir = gogn.get("oskir", {})

    fyrsti_dagur = dagar[0]
    fjoldi_saga = max(st["max_nv_rod"], st["max_dagar_rod"]) + 1
    saga_dagar = [fyrsti_dagur - k * DAGUR for k in range(fjoldi_saga, 0, -1)]
    allir_dagar = saga_dagar + dagar        # fyrri mánuður + þessi mánuður

    # ---------- 2. Stofna líkan ----------
    model = gp.Model("vaktaplan")

    # ---------- 3. Leyfilegar samsetningar ----------
    # Aðeins búa til breytur fyrir vaktir og hlutverk
    # sem starfsmaðurinn má sinna.
    lyklar = [
        (i, d, s, r)
        for i in starfsmenn
        for d in dagar
        for s in leyfdar[i]
        for r in hlutverk
        if r in haefni[i]
    ]

    # ---------- 4. Binary ákvörðunarbreytur ----------
    # x[i, d, s, r] = 1 ef starfsmaður i vinnur
    # dag d, vakt s, í hlutverki r.
    x = model.addVars(
        lyklar,
        vtype=GRB.BINARY,
        name="x",
    )

    # Hjálparsegðir: vakt[i, d, s] = 1 ef i vinnur vakt s á degi d (óháð hlutverki)
    vakt = {}
    for (i, d, s, r) in lyklar:
        vakt.setdefault((i, d, s), gp.LinExpr()).add(x[i, d, s, r])

    def vinnur(i, d, s):
        """Segð fyrir dag í mánuðinum, fasti (0/1) fyrir dag í fyrri mánuði."""
        if d >= fyrsti_dagur:
            return vakt.get((i, d, s), gp.LinExpr())
        return gp.LinExpr(1 if fyrri_vaktir.get((i, d)) == s else 0)

    def vinnur_dag(i, d):
        return gp.quicksum(vinnur(i, d, s) for s in ("MV", "KV", "NV"))

    def skorda(segd, haegri, nafn):
        """Bætir við segd <= haegri, nema segðin innihaldi engar breytur."""
        if segd.size() > 0:
            model.addConstr(segd <= haegri, name=nafn)

    # ---------- 5. Ein vakt á dag ----------
    for i in starfsmenn:
        for d in dagar:
            model.addConstr(
                x.sum(i, d, "*", "*") <= 1,
                name=f"ein_vakt_{i}_{d.isoformat()}",
            )

    # ---------- 6. Lágmarksmönnun ----------
    # Mjúk með hárri refsingu: með helgarreglunni er ekki hægt að manna
    # allar stöður, og hörð skorða myndi gera líkanið óleysanlegt.
    undirmonnun = model.addVars(monnunar_thorf.keys(), lb=0, name="undirmonnun")
    for (d, s, r), lagmark in monnunar_thorf.items():
        model.addConstr(
            x.sum("*", d, s, r) + undirmonnun[d, s, r] >= lagmark,
            name=f"monnun_{d.isoformat()}_{s}_{r}",
        )

    # Umframmönnun: fjöldi á vakt umfram heildarþörf vaktarinnar
    vaktir_dags = sorted({(d, s) for (d, s, r) in monnunar_thorf})
    umframmonnun = model.addVars(vaktir_dags, lb=0, name="umframmonnun")
    for (d, s) in vaktir_dags:
        heildarthorf = sum(f for (dd, ss, r), f in monnunar_thorf.items() if dd == d and ss == s)
        model.addConstr(
            umframmonnun[d, s] >= x.sum("*", d, s, "*") - heildarthorf,
            name=f"umfram_{d.isoformat()}_{s}",
        )

    # ---------- 7. Vinnuskylda ----------
    # Fjöldi vakta á að vera sem næst marki (mjúk skorða).
    undir = model.addVars(starfsmenn, lb=0, name="undir_vinnuskyldu")
    yfir = model.addVars(starfsmenn, lb=0, name="yfir_vinnuskyldu")
    for i in starfsmenn:
        model.addConstr(
            x.sum(i, "*", "*", "*") + undir[i] - yfir[i] == mark[i],
            name=f"vinnuskylda_{i}",
        )

    # ---------- 8. Hvíld milli vakta ----------
    # Pör (d1, d2) þar sem d2 er í mánuðinum; d1 má vera síðasti dagur fyrri mánaðar.
    bonnud_por = [("NV", "MV"), ("NV", "KV")]
    if st["banna_kv_mv"]:
        bonnud_por.append(("KV", "MV"))

    for i in starfsmenn:
        for k in range(len(saga_dagar), len(allir_dagar)):
            d1, d2 = allir_dagar[k - 1], allir_dagar[k]
            for s1, s2 in bonnud_por:
                skorda(vinnur(i, d1, s1) + vinnur(i, d2, s2), 1,
                       f"hvild_{s1}_{s2}_{i}_{d2.isoformat()}")

    # ---------- 9. Samfelld vinna ----------
    nv_k = st["max_nv_rod"]
    dg_k = st["max_dagar_rod"]
    for i in starfsmenn:
        for k in range(len(saga_dagar), len(allir_dagar)):
            d = allir_dagar[k]

            # (a) Mest nv_k næturvaktir í röð: í hverjum nv_k+1 daga glugga mest nv_k
            if k - nv_k >= 0:
                gluggi = allir_dagar[k - nv_k: k + 1]
                skorda(gp.quicksum(vinnur(i, g, "NV") for g in gluggi), nv_k,
                       f"max_nv_rod_{i}_{d.isoformat()}")

            # (b) Eftir >=2 NV í röð: frídagur (leiðir af 8) og ekki MV á degi tvö.
            #     NV(d-3) + NV(d-2) - NV(d-1) + MV(d) <= 2
            if k - 3 >= 0:
                d3, d2_, d1_ = allir_dagar[k - 3], allir_dagar[k - 2], allir_dagar[k - 1]
                skorda(vinnur(i, d3, "NV") + vinnur(i, d2_, "NV")
                       - vinnur(i, d1_, "NV") + vinnur(i, d, "MV"), 2,
                       f"svefndagur_{i}_{d.isoformat()}")

            # (c) Mest dg_k vinnudagar í röð: í hverjum dg_k+1 daga glugga mest dg_k
            if k - dg_k >= 0:
                gluggi = allir_dagar[k - dg_k: k + 1]
                skorda(gp.quicksum(vinnur_dag(i, g) for g in gluggi), dg_k,
                       f"max_dagar_rod_{i}_{d.isoformat()}")

    # ---------- 10. Helgar ----------
    # Hver starfsmaður er í einum helgarhópi og vinnur bara "sína" helgi.
    # Á fríhelgi: engin vakt lau/sun og hvorki KV né NV á föstudegi (MV má).
    G = list(range(st["fjoldi_helgarhopa"]))
    z = model.addVars(starfsmenn, G, vtype=GRB.BINARY, name="helgarhopur")
    for i in starfsmenn:
        model.addConstr(z.sum(i, "*") == 1, name=f"einn_helgarhopur_{i}")

    for i in starfsmenn:
        for d in dagar:
            g = helgar_hopur(d, len(G))
            if g is None:
                continue
            if d.weekday() in (5, 6):
                skorda(vinnur_dag(i, d), z[i, g], f"frihelgi_{i}_{d.isoformat()}")
            else:
                skorda(vinnur(i, d, "KV") + vinnur(i, d, "NV"), z[i, g],
                       f"frihelgi_fos_{i}_{d.isoformat()}")

    # Mjúk regla fyrir helgarmynstur: vinna bæði lau og sun frekar en stakan helgardag
    helgar = [(d, d + DAGUR) for d in dagar if d.weekday() == 5 and d + DAGUR in dagar]
    stakur_helgardagur = model.addVars(
        [(i, lau) for i in starfsmenn for (lau, sun) in helgar], lb=0, name="stakur_helgardagur")
    for i in starfsmenn:
        for lau, sun in helgar:
            mismunur = vinnur_dag(i, lau) - vinnur_dag(i, sun)
            model.addConstr(stakur_helgardagur[i, lau] >= mismunur)
            model.addConstr(stakur_helgardagur[i, lau] >= -mismunur)

    # ---------- 11. Markfall ----------
    # (a) Ójafnvægi í vaktategundum: hver tegund nálægt mark / fjölda leyfðra tegunda
    vakta_lyklar = [(i, s) for i in starfsmenn if len(leyfdar[i]) >= 2 for s in leyfdar[i]]
    ojafn_vaktir = model.addVars(vakta_lyklar, lb=0, name="ojafn_vaktir")
    for (i, s) in vakta_lyklar:
        markmid = mark[i] / len(leyfdar[i])
        fjoldi = x.sum(i, "*", s, "*")
        model.addConstr(fjoldi <= markmid + st["vikmork_vaktir"] + ojafn_vaktir[i, s],
                        name=f"vaktajafnvaegi_upp_{i}_{s}")
        model.addConstr(fjoldi >= markmid - st["vikmork_vaktir"] - ojafn_vaktir[i, s],
                        name=f"vaktajafnvaegi_nidur_{i}_{s}")

    # (b) Ójafnvægi í hlutverkum: vaktstjórar o.fl. ekki alltaf í sama hlutverki
    hlutverka_lyklar = [(i, r) for i in starfsmenn for r in st["stjornunarhlutverk"]
                        if r in haefni[i] and len(haefni[i]) >= 2]
    ofmikid_hlutverk = model.addVars(hlutverka_lyklar, lb=0, name="ofmikid_hlutverk")
    for (i, r) in hlutverka_lyklar:
        model.addConstr(
            x.sum(i, "*", "*", r)
            <= st["hamark_hlutverks"] * x.sum(i, "*", "*", "*") + ofmikid_hlutverk[i, r],
            name=f"hlutverkajafnvaegi_{i}_{r}",
        )

    # (c) Óuppfylltar óskir
    oskir_kostnadur = gp.LinExpr()
    for (i, d), osk in oskir.items():
        if i not in leyfdar or d not in dagar:
            continue
        if osk == "FRI":
            oskir_kostnadur += vinnur_dag(i, d)
        elif osk in leyfdar[i]:
            oskir_kostnadur += 1 - vinnur(i, d, osk)

    model.setObjective(
        st["w_undirmonnun"] * undirmonnun.sum()
        + st["w_vinnuskylda"] * (undir.sum() + yfir.sum())
        + st["w_oskir"] * oskir_kostnadur
        + st["w_vaktajafnvaegi"] * ojafn_vaktir.sum()
        + st["w_hlutverk"] * ofmikid_hlutverk.sum()
        + st["w_helgarmynstur"] * stakur_helgardagur.sum()
        + st["w_umframmonnun"] * umframmonnun.sum(),
        GRB.MINIMIZE,
    )

    model._aux = {
        "undirmonnun": undirmonnun,
        "umframmonnun": umframmonnun,
        "undir_vinnuskyldu": undir,
        "yfir_vinnuskyldu": yfir,
        "helgarhopur": z,
        "stakur_helgardagur": stakur_helgardagur,
        "ojafn_vaktir": ojafn_vaktir,
        "ofmikid_hlutverk": ofmikid_hlutverk,
        "oskir_kostnadur": oskir_kostnadur,
        "stillingar": st,
    }

    return model, x