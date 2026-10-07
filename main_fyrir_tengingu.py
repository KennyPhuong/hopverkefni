from pathlib import Path

import pandas as pd
import gurobipy as gp
from gurobipy import GRB
import matplotlib.pyplot as plt
from datetime import date

MAPPA = Path(__file__).parent

# ---------- 1. Innlestur ----------
hjukkur = pd.read_csv(MAPPA / "HR-gognin(Hjúkkur).csv", encoding="latin1")
monnun = pd.read_csv(MAPPA / "HR-gognin(Sheet2).csv", encoding="latin1", skiprows=1)

# print(hjukkur.head())
# print(monnun)

hjukkur = hjukkur[hjukkur["Nafn"].notna()]
# print(len(hjukkur))   # á að vera 170

# ---------- 2. Dálkar mánaðarins ----------
MANUDUR = "Nóvember"
i = list(hjukkur.columns).index(MANUDUR)
man_dalkar = list(hjukkur.columns[i : i + 9])
# print(man_dalkar)

# ---------- 3. Prósentur -> tölur ----------
def prosenta_i_tolu(dalkur):
    return pd.to_numeric(dalkur.astype(str).str.rstrip("%"), errors="coerce").fillna(0) / 100

for d in man_dalkar:
    hjukkur[d] = prosenta_i_tolu(hjukkur[d])

# print(hjukkur[["Nafn"] + man_dalkar].head(12))

# ---------- 4. Virkt hlutfall og síun ----------
hjukkur["virkt"] = hjukkur[man_dalkar[0]] - hjukkur[man_dalkar[1:]].sum(axis=1)
hjukkur = hjukkur[hjukkur["virkt"] > 0].copy()

print(f"{len(hjukkur)} hjúkrunarfræðingar í {MANUDUR}")
print("Heildar stöðugildi:", round(hjukkur["virkt"].sum(), 1))

# ---------- 5. Markfjöldi vakta ----------
DAGAR = 30
VAKTIR_100 = DAGAR / 7 * 5          # ~21,4 vaktir fyrir 100%

hjukkur["mark"] = (hjukkur["virkt"] * VAKTIR_100).round().astype(int)
print(hjukkur[["Nafn", "virkt", "mark"]].head(12))
print("Samtals markvaktir:", hjukkur["mark"].sum(), " (þörf: 1500)")

# ---------- 6. Hreinsa Vaktir-dálkinn ----------
def hreinsa_vaktir(texti):
    hlutar = [h.strip() for h in str(texti).split("-")]
    return [h for h in hlutar if h in ("MV", "KV", "NV")]

hjukkur["leyfdar"] = hjukkur["Vaktir"].apply(hreinsa_vaktir)
print(hjukkur["leyfdar"].astype(str).value_counts())

tomir = hjukkur[hjukkur["leyfdar"].apply(len) == 0]
print("Með engar leyfðar vaktir:", tomir["Nafn"].tolist())

# ---------- 7. Hæfni ----------
HAEFNI = ["V", "T", "H", "A1", "A", "B1", "B", "C", "D1", "Dg", "D"]

def hafa_haefni(rod):
    return [p for p in HAEFNI if rod[p.lower()] == 1]

hjukkur["haefni"] = hjukkur.apply(hafa_haefni, axis=1)

engin = hjukkur[hjukkur["haefni"].apply(len) == 0]
print(f"Með enga hæfni: {engin['Nafn'].tolist()}")

# ---------- 8. Mönnunarþörf ----------
VAKTIR = ["MV", "KV", "NV"]
thorf = {s: monnun[s].dropna().value_counts().to_dict() for s in VAKTIR}

for s in VAKTIR:
    print(f"{s}: {thorf[s]}  samtals {sum(thorf[s].values())}")

# ---------- 9. Framboð á móti þörf eftir stöðu ----------
print(f"\n{'Vakt':5} {'Staða':6} {'Þörf':>6} {'Framboð':>8}")
for s in VAKTIR:
    for p, fjoldi in thorf[s].items():
        geta = hjukkur[hjukkur["leyfdar"].apply(lambda l: s in l) &
                       hjukkur["haefni"].apply(lambda h: p in h)]
        print(f"{s:5} {p:6} {fjoldi*DAGAR:>6} {geta['mark'].sum():>8}")

# ============================================================
# 10. LÍKAN – ÞREP A
# ============================================================

# ---------- Gögn á þægilegu formi ----------
N = hjukkur["Nafn"].tolist()
D = list(range(1, DAGAR + 1))
leyfdar = dict(zip(hjukkur["Nafn"], hjukkur["leyfdar"]))
haefni  = dict(zip(hjukkur["Nafn"], hjukkur["haefni"]))
mark    = dict(zip(hjukkur["Nafn"], hjukkur["mark"]))

m = gp.Model("vaktaplan")

# ---------- Breytur ----------
# x[n,d,s] = 1 ef n vinnur vakt s á degi d
x_lyklar = [(n, d, s) for n in N for d in D for s in leyfdar[n]]
x = m.addVars(x_lyklar, vtype=GRB.BINARY, name="x")

# y[n,d,s,p] = 1 ef n er í stöðu p á vakt s á degi d
y_lyklar = [(n, d, s, p) for (n, d, s) in x_lyklar
            for p in haefni[n] if p in thorf[s]]
y = m.addVars(y_lyklar, vtype=GRB.BINARY, name="y")

# slaki = fjöldi sem vantar í stöðu (undirmönnun)
s_lyklar = [(d, s, p) for d in D for s in VAKTIR for p in thorf[s]]
slaki = m.addVars(s_lyklar, lb=0, name="slaki")

# frávik frá vinnuskyldu
undir = m.addVars(N, lb=0, name="undir")
yfir  = m.addVars(N, lb=0, name="yfir")

print(f"x: {len(x)}  y: {len(y)}  breytur")

# ---------- Skorður ----------
# (1) Mönnun: nógu margir í hverja stöðu (annars slaki)
m.addConstrs(
    (y.sum("*", d, s, p) + slaki[d, s, p] >= thorf[s][p] for (d, s, p) in s_lyklar),
    name="monnun")

# (2) Tenging: ef n vinnur vaktina er hann í nákvæmlega einni stöðu
m.addConstrs(
    (y.sum(n, d, s, "*") == x[n, d, s] for (n, d, s) in x_lyklar),
    name="tenging")

# (3) Mest ein vakt á dag
m.addConstrs(
    (x.sum(n, d, "*") <= 1 for n in N for d in D),
    name="ein_vakt")

# (4) Vinnuskylda: fjöldi vakta = mark (mjúk skorða)
m.addConstrs(
    (x.sum(n, "*", "*") + undir[n] - yfir[n] == mark[n] for n in N),
    name="vinnuskylda")

# ---------- Hjálparfall ----------
# Skilar x-breytunni ef hún er til, annars 0.
# (Ekki allir hafa allar vaktir, og dagur 31 er ekki til.)
def X(n, d, s):
    return x[n, d, s] if (n, d, s) in x else 0

# ===== ÞREP B =====
# (5) Engin MV eða KV daginn eftir næturvakt
m.addConstrs(
    (X(n, d, "NV") + X(n, d + 1, s) <= 1
     for n in N if "NV" in leyfdar[n]
     for s in ("MV", "KV") if s in leyfdar[n]
     for d in D[:-1]),
    name="eftir_NV")

# ===== ÞREP C =====
# (6) Hámark 4 næturvaktir í röð:
#     í hverjum 5 daga glugga mega vera mest 4 NV
MAX_NV_ROD = 4
m.addConstrs(
    (gp.quicksum(X(n, d + k, "NV") for k in range(MAX_NV_ROD + 1)) <= MAX_NV_ROD
     for n in N if "NV" in leyfdar[n]
     for d in D if d + MAX_NV_ROD <= DAGAR),
    name="max_NV_rod")

# (7) Svefndagur: eftir ≥2 NV í röð er í fyrsta lagi KV á degi tvö (ekki MV)
m.addConstrs(
    (X(n, d - 1, "NV") + X(n, d, "NV") - X(n, d + 1, "NV") + X(n, d + 2, "MV") <= 2
     for n in N if "NV" in leyfdar[n] and "MV" in leyfdar[n]
     for d in D if d >= 2 and d + 2 <= DAGAR),
    name="svefndagur")

# (8) Hámark 6 vinnudagar í röð:
#     í hverjum 7 daga glugga mega vera mest 6 vaktir
MAX_DAGAR_ROD = 6
m.addConstrs(
    (gp.quicksum(x.sum(n, d + k, "*") for k in range(MAX_DAGAR_ROD + 1)) <= MAX_DAGAR_ROD
     for n in N
     for d in D if d + MAX_DAGAR_ROD <= DAGAR),
    name="max_dagar_rod")

# (9) Engin MV daginn eftir KV (11 klst. hvíld)
m.addConstrs(
    (X(n, d, "KV") + X(n, d + 1, "MV") <= 1
     for n in N if "KV" in leyfdar[n] and "MV" in leyfdar[n]
     for d in D[:-1]),
    name="KV_MV")

# ===== ÞREP D =====

# ---------- Helgar ----------
AR, MAN_NR = 2026, 11

def vikudagur(d):
    return date(AR, MAN_NR, d).weekday()      # 0=mán ... 4=fös, 5=lau, 6=sun

def helgar_hopur(d):
    """Hvaða helgi (0, 1 eða 2) dagur d tilheyrir, eða None ef ekki helgi."""
    vd = vikudagur(d)
    if vd < 4:
        return None
    fostudagur = d - (vd - 4)                  # föstudagur sömu helgar
    return (fostudagur // 7) % 3

# z[n,g] = 1 ef n vinnur helgar í hópi g
G = [0, 1, 2]
z = m.addVars(N, G, vtype=GRB.BINARY, name="z")

# (10) Hver og einn er í nákvæmlega einum helgarhópi
m.addConstrs((z.sum(n, "*") == 1 for n in N), name="einn_hopur")

# (11) Lau/sun: má bara vinna ef það er "þín" helgi
m.addConstrs(
    (x.sum(n, d, "*") <= z[n, helgar_hopur(d)]
     for n in N for d in D if vikudagur(d) in (5, 6)),
    name="helgi_lausun")

# (12) Föstudagur: KV/NV bara ef það er "þín" helgi (MV má alltaf)
m.addConstrs(
    (X(n, d, "KV") + X(n, d, "NV") <= z[n, helgar_hopur(d)]
     for n in N for d in D if vikudagur(d) == 4),
    name="helgi_fos")

# ---------- Jafnvægi vaktategunda ----------
# (13) Hver vaktategund nálægt mark / (fjöldi leyfðra vakta)
VIKMORK = 2
ojafn = m.addVars(x_lyklar_ns := [(n, s) for n in N for s in leyfdar[n]], lb=0, name="ojafn")

for n in N:
    k = len(leyfdar[n])
    if k < 2:
        continue                       # bara ein tegund -> ekkert að jafna
    markmid = mark[n] / k
    for s in leyfdar[n]:
        m.addConstr(x.sum(n, "*", s) <= markmid + VIKMORK + ojafn[n, s], name=f"jafn_upp[{n},{s}]")
        m.addConstr(x.sum(n, "*", s) >= markmid - VIKMORK - ojafn[n, s], name=f"jafn_nidur[{n},{s}]")

# ---------- Markfall ----------
W_SLAKI = 1000   # undirmönnun er það versta
W_FRAVIK = 10    # frávik frá vinnuskyldu

W_SLAKI  = 1000
W_FRAVIK = 10
W_OJAFN  = 5

m.setObjective(
    W_SLAKI  * slaki.sum()
  + W_FRAVIK * (undir.sum() + yfir.sum())
  + W_OJAFN  * ojafn.sum(),
    GRB.MINIMIZE)

# ---------- Leysa ----------
m.Params.TimeLimit = 120
m.optimize()

# ---------- Niðurstöður ----------
if m.SolCount > 0:
    print(f"\nMarkfallsgildi: {m.ObjVal:.0f}")
    print(f"Undirmönnun samtals: {slaki.sum().getValue():.0f}")
    print(f"Undir vinnuskyldu:   {undir.sum().getValue():.0f}")
    print(f"Yfir vinnuskyldu:    {yfir.sum().getValue():.0f}")

    # Sýna plan fyrir fyrstu 5 hjúkrunarfræðingana
    for n in N[:5]:
        rod = ""
        for d in D:
            vakt = next((s for s in leyfdar[n] if x[n, d, s].X > 0.5), "-")
            rod += f"{vakt:>3}"
        print(f"{n:5}{rod}")
    
    # Hvar vantar fólk?
    print("\nUndirmönnun eftir degi:")
    vd_nafn = ["mán", "þri", "mið", "fim", "fös", "lau", "sun"]
    for d in D:
        vantar = {(s, p): slaki[d, s, p].X for s in VAKTIR for p in thorf[s]
                  if slaki[d, s, p].X > 0.5}
        if vantar:
            lysing = ", ".join(f"{s}-{p}: {v:.0f}" for (s, p), v in vantar.items())
            print(f"  Dagur {d:2} ({vd_nafn[vikudagur(d)]}, hópur {helgar_hopur(d)}): {lysing}")

    # Stærð helgarhópa
    for g in G:
        fjoldi = sum(1 for n in N if z[n, g].X > 0.5)
        print(f"Helgarhópur {g}: {fjoldi} manns")