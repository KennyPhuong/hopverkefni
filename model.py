import re
from datetime import timedelta

import gurobipy as gp
from gurobipy import GRB

DAGUR = timedelta(days=1)
VAKTIR = ("MV", "KV", "NV")

# Reglur og vigtir á einum stað. main.py getur sent inn breytta útgáfu
# (t.d. fyrir næmnigreiningu): byggja_model(gogn, {"max_nv_rod": 5})
STILLINGAR = {
    # Harðar reglur
    "hord_monnun": True,         # lágmarksmönnun er hörð skorða
    "max_nv_rod": 4,             # hámark næturvakta í röð
    "max_dagar_rod": 6,          # hámark vinnudaga í röð
    "leyfa_mv_nv_sama_dag": False,  # AUKA: MV og NV sama sólarhring (leyft en óvinsælt)
    # Vaktatímar í klst. frá miðnætti upphafsdags; NV tilheyrir upphafsdegi.
    # Prófunarforsenda, ekki staðfestir vaktatímar deildarinnar.
    "vaktatimar": {"MV": (8, 16), "KV": (16, 24), "NV": (24, 32)},
    "lagmarkshvild": 11,         # klst. milli loka vaktar og upphafs næstu
    # Helgar (mjúk regla)
    "fjoldi_helgarhopa": 3,      # viðmið: vinna þriðju hverja helgi
    "max_aukahelgardagar": 3,    # mest svo margir helgardagar utan eigin hóps (None = ekkert hámark)
    # Viðmið fyrir aðrar mjúkar reglur
    "vikmork_vaktir": 2,         # leyfilegt frávik frá jafnri skiptingu MV/KV/NV
    "vikmork_vika": 1,           # leyfilegt frávik frá vikulegu vaktamarki (90% -> 4 eða 5)
    "nv_hlutfall_ur_texta": True,   # lesa t.d. "100% (50%NV)" úr gogn["texti"]
    "hamark_hlutverks": 0.5,     # mest helmingur vakta sem vaktstjóri / í forgangsflokkun
    "stjornunarhlutverk": ("V", "T"),
    # Vigtir í markfalli
    "w_undirmonnun": 1000,       # aðeins notað ef hord_monnun=False
    "w_aukahelgi": 50,
    "w_oskir": 20,
    "w_vinnuskylda": 10,
    "w_vaktajafnvaegi": 5,
    "w_vikujafnvaegi": 4,
    "w_mv_nv_sama_dag": 30,
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


def bonnud_vaktapor(vaktatimar, lagmarkshvild):
    """Vaktapör (s1 dag d, s2 dag d+1) með styttri hvíld en lagmarkshvild.

    Með sjálfgefnum vaktatímum: NV->MV (0 klst), NV->KV (8 klst), KV->MV (8 klst).
    """
    por = []
    for s1, (_, lok1) in vaktatimar.items():
        for s2, (byrjun2, _) in vaktatimar.items():
            hvild = byrjun2 + 24 - lok1
            if hvild < lagmarkshvild:
                por.append((s1, s2))
    return por


def nv_hlutfall_ur_texta(texti):
    """{starfsmaður: NV-hlutfall} úr samningstexta, t.d. "100% (50%NV)" -> 0.5.

    texti er gogn["texti"]: {starfsmaður: {"Vinnufyrirkomulag": ..., ...}}.
    """
    nidurstada = {}
    for i, dalkar in (texti or {}).items():
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*%\s*NV", dalkar.get("Vinnufyrirkomulag", ""),
                      flags=re.IGNORECASE)
        if m:
            nidurstada[i] = float(m.group(1).replace(",", ".")) / 100
    return nidurstada


def sidustu_vaktir(x, gogn, fjoldi_daga=7):
    """Vaktir síðustu daga mánaðarins á sniði gogn["fyrri_vaktir"].

    Notað til að tengja mánuði: lausn nóvember -> fyrri_vaktir desember,
    svo hvíldar- og raðareglur gildi yfir mánaðarmörkin.
    """
    sidustu = set(gogn["dagar"][-fjoldi_daga:])
    return {(i, d): s for (i, d, s, r), v in x.items() if d in sidustu and v.X > 0.5}


def byggja_model(gogn, stillingar=None):
    """
    Byggir líkan fyrir dagsetningarnar og gögnin sem eru gefin.

    Skilar:
        model: Gurobi-líkaninu
        x: Binary úthlutunarbreytunum

    Hjálparbreytur (undirmönnun, aukahelgar, frávik o.fl.) eru geymdar í
    model._aux svo main.py geti lesið þær eftir lausn.

    Valkvæð gögn í gogn:
        "fyrri_vaktir": {(starfsmaður, dagsetning): vakt} síðustu daga
                        fyrri mánaðar, t.d. úr sidustu_vaktir().
        "oskir":        {(starfsmaður, dagsetning): "FRI" | "MV" | "KV" | "NV"}
        "nv_hlutfall":  {starfsmaður: hlutfall NV af vöktum}, t.d. 0.5.
                        Ef það vantar er það lesið úr gogn["texti"].

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
    if "nv_hlutfall" in gogn:
        nv_hlutfall = dict(gogn["nv_hlutfall"])
    elif st["nv_hlutfall_ur_texta"]:
        nv_hlutfall = nv_hlutfall_ur_texta(gogn.get("texti"))
    else:
        nv_hlutfall = {}
    nv_hlutfall = {i: h for i, h in nv_hlutfall.items()
                   if i in leyfdar and "NV" in leyfdar[i] and len(leyfdar[i]) >= 2}

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
        """Fjöldi vakta dagsins (getur verið 2 ef MV+NV sama dag er leyft)."""
        return gp.quicksum(vinnur(i, d, s) for s in VAKTIR)

    tvofold = {}          # tvofold[i, d] = 1 ef i tekur bæði MV og NV dag d

    def vinnudagur(i, d):
        """1 ef i vinnur dag d (óháð fjölda vakta þann dag)."""
        if (i, d) in tvofold:
            return vinnur_dag(i, d) - tvofold[i, d]
        return vinnur_dag(i, d)

    def skorda(segd, haegri, nafn):
        """Bætir við segd <= haegri, nema segðin innihaldi engar breytur."""
        if segd.size() > 0:
            model.addConstr(segd <= haegri, name=nafn)

    # ---------- 5. Ein vakt á dag ----------
    # Ef leyfa_mv_nv_sama_dag: eina leyfða tvennan er MV + NV (ekki MV+KV eða KV+NV),
    # og hún kostar w_mv_nv_sama_dag.
    for i in starfsmenn:
        tvennan_moguleg = (st["leyfa_mv_nv_sama_dag"]
                           and "MV" in leyfdar[i] and "NV" in leyfdar[i])
        for d in dagar:
            if not tvennan_moguleg:
                model.addConstr(
                    x.sum(i, d, "*", "*") <= 1,
                    name=f"ein_vakt_{i}_{d.isoformat()}",
                )
                continue
            mv, kv, nv = vinnur(i, d, "MV"), vinnur(i, d, "KV"), vinnur(i, d, "NV")
            skorda(mv + kv, 1, f"ekki_mv_kv_{i}_{d.isoformat()}")
            skorda(kv + nv, 1, f"ekki_kv_nv_{i}_{d.isoformat()}")
            t2 = model.addVar(lb=0, ub=1, name=f"mv_nv_{i}_{d.isoformat()}")
            model.addConstr(t2 >= mv + nv - 1)
            model.addConstr(t2 <= mv)
            model.addConstr(t2 <= nv)
            tvofold[i, d] = t2

    # ---------- 6. Lágmarksmönnun ----------
    # Hörð sjálfgefið. Með hord_monnun=False er skortur leyfður gegn refsingu,
    # sem nýtist til að greina hvar mönnun bregst ef hart líkan er óleysanlegt.
    if st["hord_monnun"]:
        undirmonnun = None
        for (d, s, r), lagmark in monnunar_thorf.items():
            model.addConstr(
                x.sum("*", d, s, r) >= lagmark,
                name=f"monnun_{d.isoformat()}_{s}_{r}",
            )
    else:
        undirmonnun = model.addVars(monnunar_thorf.keys(), lb=0, name="undirmonnun")
        for (d, s, r), lagmark in monnunar_thorf.items():
            model.addConstr(
                x.sum("*", d, s, r) + undirmonnun[d, s, r] >= lagmark,
                name=f"monnun_{d.isoformat()}_{s}_{r}",
            )

    # Umframmönnun: fjöldi á vakt umfram heildarþörf vaktarinnar
    heildarthorf = {}
    for (d, s, r), f in monnunar_thorf.items():
        heildarthorf[d, s] = heildarthorf.get((d, s), 0) + f
    umframmonnun = model.addVars(heildarthorf.keys(), lb=0, name="umframmonnun")
    for (d, s), thorf in heildarthorf.items():
        model.addConstr(
            umframmonnun[d, s] >= x.sum("*", d, s, "*") - thorf,
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

    # Vikuleg dreifing: vaktir hverrar viku nálægt hlutfallslegu marki
    # (100% -> ~5 á viku, 90% -> 4 eða 5). Hlutavikur í upphafi/lok mánaðar fá hlutfall.
    vikur = {}
    for d in dagar:
        vikur.setdefault(tuple(d.isocalendar()[:2]), []).append(d)
    vika_frav = model.addVars([(i, w) for i in starfsmenn for w in vikur], lb=0,
                              name="vika_frav")
    for i in starfsmenn:
        for w, vdagar in vikur.items():
            markmid = mark[i] * len(vdagar) / len(dagar)
            fjoldi = gp.quicksum(x.sum(i, d, "*", "*") for d in vdagar)
            model.addConstr(fjoldi <= markmid + st["vikmork_vika"] + vika_frav[i, w],
                            name=f"vika_upp_{i}_{w[0]}_{w[1]}")
            model.addConstr(fjoldi >= markmid - st["vikmork_vika"] - vika_frav[i, w],
                            name=f"vika_nidur_{i}_{w[0]}_{w[1]}")

    # ---------- 8. Hvíld milli vakta ----------
    # Bönnuð pör eru reiknuð úr vaktatímum og lágmarkshvíld.
    # d1 má vera síðasti dagur fyrri mánaðar (fyrri_vaktir).
    bonnud_por = bonnud_vaktapor(st["vaktatimar"], st["lagmarkshvild"])
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
                skorda(gp.quicksum(vinnudagur(i, g) for g in gluggi), dg_k,
                       f"max_dagar_rod_{i}_{d.isoformat()}")

    # ---------- 10. Helgar (mjúk regla) ----------
    # Hver starfsmaður er í einum helgarhópi. Vinna utan eigin helgar
    # (lau/sun, eða KV/NV á föstudegi) er leyfð gegn refsingu, að hámarki
    # max_aukahelgardagar á mann. MV á föstudegi er alltaf leyfð.
    G = list(range(st["fjoldi_helgarhopa"]))
    z = model.addVars(starfsmenn, G, vtype=GRB.BINARY, name="helgarhopur")
    for i in starfsmenn:
        model.addConstr(z.sum(i, "*") == 1, name=f"einn_helgarhopur_{i}")

    aukahelgi = {}
    for i in starfsmenn:
        for d in dagar:
            g = helgar_hopur(d, len(G))
            if g is None:
                continue
            if d.weekday() in (5, 6):
                segd = vinnudagur(i, d)
            else:
                segd = vinnur(i, d, "KV") + vinnur(i, d, "NV")
            if segd.size() == 0:
                continue
            aukahelgi[i, d] = model.addVar(lb=0, name=f"aukahelgi_{i}_{d.isoformat()}")
            model.addConstr(aukahelgi[i, d] >= segd - z[i, g],
                            name=f"aukahelgi_{i}_{d.isoformat()}")
    aukahelgi = gp.tupledict(aukahelgi)

    if st["max_aukahelgardagar"] is not None:
        for i in starfsmenn:
            skorda(aukahelgi.sum(i, "*"), st["max_aukahelgardagar"], f"max_aukahelgi_{i}")

    # Helgarmynstur: vinna bæði lau og sun frekar en stakan helgardag
    helgar = [(d, d + DAGUR) for d in dagar if d.weekday() == 5 and d + DAGUR in dagar]
    stakur_helgardagur = model.addVars(
        [(i, lau) for i in starfsmenn for (lau, sun) in helgar], lb=0, name="stakur_helgardagur")
    for i in starfsmenn:
        for lau, sun in helgar:
            mismunur = vinnudagur(i, lau) - vinnudagur(i, sun)
            model.addConstr(stakur_helgardagur[i, lau] >= mismunur)
            model.addConstr(stakur_helgardagur[i, lau] >= -mismunur)

    # ---------- 11. Markfall ----------
    # (a) Ójafnvægi í vaktategundum: hver tegund nálægt mark / fjölda leyfðra tegunda.
    #     Ef samningur tilgreinir NV-hlutfall fær NV það hlutfall og hinar skipta afganginum.
    def markmid_vaktar(i, s):
        if i in nv_hlutfall:
            h = nv_hlutfall[i]
            if s == "NV":
                return mark[i] * h
            return mark[i] * (1 - h) / (len(leyfdar[i]) - 1)
        return mark[i] / len(leyfdar[i])

    vakta_lyklar = [(i, s) for i in starfsmenn if len(leyfdar[i]) >= 2 for s in leyfdar[i]]
    ojafn_vaktir = model.addVars(vakta_lyklar, lb=0, name="ojafn_vaktir")
    for (i, s) in vakta_lyklar:
        markmid = markmid_vaktar(i, s)
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
            oskir_kostnadur += vinnudagur(i, d)
        elif osk in leyfdar[i]:
            oskir_kostnadur += 1 - vinnur(i, d, osk)

    markfall = (
        st["w_aukahelgi"] * aukahelgi.sum()
        + st["w_vinnuskylda"] * (undir.sum() + yfir.sum())
        + st["w_oskir"] * oskir_kostnadur
        + st["w_vaktajafnvaegi"] * ojafn_vaktir.sum()
        + st["w_hlutverk"] * ofmikid_hlutverk.sum()
        + st["w_helgarmynstur"] * stakur_helgardagur.sum()
        + st["w_umframmonnun"] * umframmonnun.sum()
        + st["w_vikujafnvaegi"] * vika_frav.sum()
        + st["w_mv_nv_sama_dag"] * gp.quicksum(tvofold.values())
    )
    if undirmonnun is not None:
        markfall += st["w_undirmonnun"] * undirmonnun.sum()
    model.setObjective(markfall, GRB.MINIMIZE)

    model._aux = {
        "undirmonnun": undirmonnun,
        "umframmonnun": umframmonnun,
        "undir_vinnuskyldu": undir,
        "yfir_vinnuskyldu": yfir,
        "helgarhopur": z,
        "aukahelgi": aukahelgi,
        "stakur_helgardagur": stakur_helgardagur,
        "ojafn_vaktir": ojafn_vaktir,
        "ofmikid_hlutverk": ofmikid_hlutverk,
        "oskir_kostnadur": oskir_kostnadur,
        "bonnud_vaktapor": bonnud_por,
        "vika_frav": vika_frav,
        "mv_nv_sama_dag": tvofold,
        "nv_hlutfall": nv_hlutfall,
        "stillingar": st,
    }

    return model, x