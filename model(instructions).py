
import gurobipy as gp
from gurobipy import GRB


def byggja_model(gogn):
    """
    Byggir líkan fyrir dagsetningarnar og gögnin sem eru gefin.

    Skilar:
        model: Gurobi-líkaninu
        x: Binary úthlutunarbreytunum

    Fallið leysir ekki líkanið. Það er gert í main.py.
    """

    # ---------- 1. Gögn ----------
    starfsmenn = gogn["starfsmenn"]
    dagar = gogn["dagar"]
    leyfdar = gogn["leyfdar"]
    haefni = gogn["haefni"]
    hlutverk = gogn["hlutverk"]
    monnunar_thorf = gogn["monnunar_thorf"]

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

    # ---------- 5. Ein vakt á dag ----------
    for i in starfsmenn:
        for d in dagar:
            model.addConstr(
                x.sum(i, d, "*", "*") <= 1,
                name=f"ein_vakt_{i}_{d.isoformat()}",
            )

    # ---------- 6. Lágmarksmönnun ----------
    for (d, s, r), lagmark in monnunar_thorf.items():
        model.addConstr(
            x.sum("*", d, s, r) >= lagmark,
            name=f"monnun_{d.isoformat()}_{s}_{r}",
        )

    # ---------- 7. Vinnuskylda ----------
    # TODO:
    # Lesa staðfest vinnuskyldumörk úr gogn.
    # Takmarka heildarvaktir eða vinnustundir hvers starfsmanns.

    # ---------- 8. Hvíld milli vakta ----------
    # TODO:
    # Banna NV -> MV og NV -> KV daginn eftir.
    # Bæta við öðrum óleyfilegum vaktapörum miðað við vaktatíma.
    # Meðhöndla hvíld yfir mánaðarmörk sérstaklega.

    # ---------- 9. Samfelld vinna ----------
    # TODO:
    # Takmarka samfelldar næturvaktir.
    # Tryggja hvíld þegar næturvaktatörn lýkur.
    # Takmarka samfellda vinnudaga.

    # ---------- 10. Helgar ----------
    # TODO:
    # Skilgreina fríhelgar og reglur fyrir föstudagsvaktir.
    # Bæta við soft reglu fyrir helgarmynstur.

    # ---------- 11. Markfall ----------
    # Til bráðabirgða: finna einhverja leyfilega lausn.
    # Þetta markfall metur ekki gæði vaktaplansins.
    model.setObjective(0.0, GRB.MINIMIZE)

    # TODO:
    # Skipta út núllmarkfallinu fyrir kostnað vegna:
    # - Frávika frá vinnuskyldumarki.
    # - Óuppfylltra óska.
    # - Ójafnvægis í vaktategundum og hlutverkum.
    # - Óþarfa umframmönnunar.

    return model, x