from pathlib import Path

import pandas as pd
import gurobipy as gp
from gurobipy import GRB
import matplotlib.pyplot as plt

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

print(len(hjukkur), "hjúkrunarfræðingar í nóvember")
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