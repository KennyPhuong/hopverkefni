"""Einfalt vaktaplanslíkan: hörð mönnun og hvíld, fimm mjúk markmið.

Fallið byggir líkanið; main.py leysir það. Reglurnar hér staðfesta ekki
heildarfylgni við vinnulöggjöf. Vaktatímar og mánaðarmörk þurfa yfirferð.
"""
from datetime import timedelta
from math import isfinite
import gurobipy as gp
from gurobipy import GRB

DAGUR = timedelta(days=1)
STILLINGAR = {
    "max_nv_rod": 4,
    "max_dagar_rod": 6,
    "fjoldi_helgarhopa": 3,
    "w_vinnuskylda": 10,
    "w_umframmonnun": 1,
    "w_aukahelgi": 50,
    # Fjölbreytni: hver vaktategund nálægt jöfnum hlut af vöktum viðkomandi.
    "vikmork_vaktategund": 2,
    "w_vaktajafnvaegi": 5,
    # Vaktstjórar fá hvíld frá hlutverkinu: mest helmingur vakta sem V.
    "vaktstjorahlutverk": "V",
    "hamark_vaktstjora": 0.5,
    "w_vaktstjori": 3,
}
# Staðfest vaktatímaskrá vantar; þetta eru skýrar reglur um vaktapör.
BONNUD_POR = (("NV", "MV"), ("NV", "KV"), ("KV", "MV"))


def helgar_hopur(d):
    """Sameiginlegur hópur fyrir föstudag/laugardag/sunnudag; annars None."""
    if d.weekday() < 4:
        return None
    fostudagur = d - (d.weekday() - 4) * DAGUR
    return (fostudagur.toordinal() // 7) % STILLINGAR["fjoldi_helgarhopa"]


def byggja_model(gogn, w_aukahelgi=50):
    """Skila Gurobi-líkani og x[nurse,date,shift,role]."""
    if isinstance(w_aukahelgi, bool) or not isinstance(w_aukahelgi, (int, float)):
        raise ValueError("Helgarvigt þarf að vera jákvæð tala.")
    if not isfinite(w_aukahelgi) or w_aukahelgi <= 0:
        raise ValueError("Helgarvigt þarf að vera jákvæð og endanleg.")
    st = {**STILLINGAR, "w_aukahelgi": w_aukahelgi}
    starfsmenn, dagar = gogn["starfsmenn"], gogn["dagar"]
    thorf, mark = gogn["monnunar_thorf"], gogn["mark"]
    saga = gogn.get("fyrri_vaktir", {})
    model = gp.Model("vaktaplan_november")
    # Sleppa óleyfilegum samsetningum og hlutverkum án þarfar á vaktinni.
    lyklar = [(i, d, s, r) for i in starfsmenn for (d, s, r), q in thorf.items()
              if q > 0 and s in gogn["leyfdar"][i] and r in gogn["haefni"][i]]
    x = model.addVars(lyklar, vtype=GRB.BINARY, name="x")
    vakt = {}
    for i, d, s, r in lyklar:
        vakt.setdefault((i, d, s), gp.LinExpr()).add(x[i, d, s, r])

    def vinnur(i, d, s):
        if d < dagar[0]:
            return gp.LinExpr(int(saga.get((i, d)) == s))
        return vakt.get((i, d, s), gp.LinExpr())

    def vinnur_dag(i, d):
        return gp.quicksum(vinnur(i, d, s) for s in gogn["vaktir"])

    # 1. Hörð mönnun, rétt hæfni og mest ein vakt á dag.
    for (d, s, r), q in thorf.items():
        model.addConstr(x.sum("*", d, s, r) >= q, name=f"monnun_{d}_{s}_{r}")
    for i in starfsmenn:
        for d in dagar:
            model.addConstr(x.sum(i, d, "*", "*") <= 1, name=f"ein_vakt_{i}_{d}")

    # 2. Hvíld, næturblokkir og hámark samfelldrar vinnu.
    for i in starfsmenn:
        for d in dagar:
            for s1, s2 in BONNUD_POR:
                model.addConstr(vinnur(i, d - DAGUR, s1) + vinnur(i, d, s2) <= 1,
                                name=f"hvild_{i}_{d}_{s1}_{s2}")
            nv = STILLINGAR["max_nv_rod"]
            dg = STILLINGAR["max_dagar_rod"]
            model.addConstr(gp.quicksum(vinnur(i, d - k * DAGUR, "NV") for k in range(nv + 1)) <= nv,
                            name=f"max_nv_{i}_{d}")
            model.addConstr(gp.quicksum(vinnur_dag(i, d - k * DAGUR) for k in range(dg + 1)) <= dg,
                            name=f"max_dagar_{i}_{d}")
            model.addConstr(vinnur(i, d - 3 * DAGUR, "NV") + vinnur(i, d - 2 * DAGUR, "NV")
                            - vinnur(i, d - DAGUR, "NV") + vinnur(i, d, "MV") <= 2,
                            name=f"svefndagur_{i}_{d}")

    # 3. Mjúkt vinnuskyldumark; ekki námunda eða búa til hörð mörk.
    undir = model.addVars(starfsmenn, lb=0, name="undir_marki")
    yfir = model.addVars(starfsmenn, lb=0, name="yfir_marki")
    for i in starfsmenn:
        model.addConstr(x.sum(i, "*", "*", "*") + undir[i] - yfir[i] == mark[i],
                        name=f"vinnuskylda_{i}")

    # 4. Umframmönnun. Hörð hlutverkamönnun tryggir að skortur sé ekki falinn.
    heildarthorf = {}
    for (d, s, r), q in thorf.items():
        heildarthorf[d, s] = heildarthorf.get((d, s), 0) + q
    umfram = model.addVars(heildarthorf, lb=0, name="umframmonnun")
    for (d, s), q in heildarthorf.items():
        model.addConstr(umfram[d, s] >= x.sum("*", d, s, "*") - q,
                        name=f"umfram_{d}_{s}")

    # 5. Þriðju-hverrar-helgar hópur er aðeins viðmið; utan hans má vinna.
    hopar = range(STILLINGAR["fjoldi_helgarhopa"])
    z = model.addVars(starfsmenn, hopar, vtype=GRB.BINARY, name="helgarhopur")
    helgardagar = [d for d in dagar if d.weekday() >= 4]
    auka = model.addVars(starfsmenn, helgardagar, lb=0, name="aukahelgi")
    for i in starfsmenn:
        model.addConstr(z.sum(i, "*") == 1, name=f"einn_hopur_{i}")
        for d in helgardagar:
            vinna = (vinnur_dag(i, d) if d.weekday() >= 5
                     else vinnur(i, d, "KV") + vinnur(i, d, "NV"))
            model.addConstr(auka[i, d] >= vinna - z[i, helgar_hopur(d)],
                            name=f"aukahelgi_{i}_{d}")

        # Raunveruleg fríhelgi: ef lau/sun eru frí má ekki vinna föstudags-KV/NV.
        # Þetta er hörð regla óháð því hvaða viðmiðunarhóp viðkomandi tilheyrir.
        for lau in dagar:
            fos, sun = lau - DAGUR, lau + DAGUR
            if lau.weekday() == 5 and fos in dagar and sun in dagar:
                model.addConstr(vinnur(i, fos, "KV") + vinnur(i, fos, "NV")
                                <= vinnur_dag(i, lau) + vinnur_dag(i, sun),
                                name=f"frihelgi_fos_{i}_{fos}")

    # 6. Fjölbreytni vakta: hjá þeim sem taka fleiri en eina vaktategund á hver
    #    tegund að vera nálægt jöfnum hlut af þeirra eigin vöktum (±vikmörk).
    #    Frávik umfram vikmörk kostar, svo fólk lendi ekki alltaf á sömu vöktum.
    vaktalyklar = [(i, s) for i in starfsmenn if len(gogn["leyfdar"][i]) >= 2
                   for s in gogn["leyfdar"][i]]
    ojafn = model.addVars(vaktalyklar, lb=0, name="ojafnvaegi_vakta")
    for i, s in vaktalyklar:
        jafnt = x.sum(i, "*", "*", "*") * (1 / len(gogn["leyfdar"][i]))
        fjoldi = x.sum(i, "*", s, "*")
        vm = STILLINGAR["vikmork_vaktategund"]
        model.addConstr(fjoldi <= jafnt + vm + ojafn[i, s], name=f"vaktir_upp_{i}_{s}")
        model.addConstr(fjoldi >= jafnt - vm - ojafn[i, s], name=f"vaktir_nidur_{i}_{s}")

    # 7. Vaktstjórar ekki alltaf vaktstjórar: mest hamark_vaktstjora af vöktum
    #    viðkomandi í V-hlutverki. Á aðeins við þá sem hafa líka önnur hlutverk.
    V = STILLINGAR["vaktstjorahlutverk"]
    v_hopur = [i for i in starfsmenn if V in gogn["haefni"][i] and len(gogn["haefni"][i]) >= 2]
    ofmikid_v = model.addVars(v_hopur, lb=0, name="ofmikid_vaktstjori")
    for i in v_hopur:
        model.addConstr(x.sum(i, "*", "*", V)
                        <= STILLINGAR["hamark_vaktstjora"] * x.sum(i, "*", "*", "*") + ofmikid_v[i],
                        name=f"vaktstjori_{i}")

    model.setObjective(STILLINGAR["w_vinnuskylda"] * (undir.sum() + yfir.sum())
                       + STILLINGAR["w_umframmonnun"] * umfram.sum()
                       + st["w_aukahelgi"] * auka.sum()
                       + STILLINGAR["w_vaktajafnvaegi"] * ojafn.sum()
                       + STILLINGAR["w_vaktstjori"] * ofmikid_v.sum(), GRB.MINIMIZE)
    model._aux = {"undir_vinnuskyldu": undir, "yfir_vinnuskyldu": yfir,
                  "umframmonnun": umfram, "aukahelgi": auka,
                  "ojafnvaegi_vakta": ojafn, "ofmikid_vaktstjori": ofmikid_v,
                  "helgarhopur": z, "stillingar": st}
    return model, x