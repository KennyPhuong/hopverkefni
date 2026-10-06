from pathlib import Path

import pandas as pd
import gurobipy as gp
from gurobipy import GRB
import matplotlib.pyplot as plt

MAPPA = Path(__file__).parent

hjukkur = pd.read_csv(MAPPA / "HR-gognin(Hjúkkur).csv", encoding="latin1")
monnun = pd.read_csv(MAPPA / "HR-gognin(Sheet2).csv", encoding="latin1", skiprows=1)

print(hjukkur.head())
print(monnun)

hjukkur = hjukkur[hjukkur["Nafn"].notna()]
print(len(hjukkur))   # á að vera 170

MANUDUR = "Nóvember"
i = list(hjukkur.columns).index(MANUDUR)
man_dalkar = list(hjukkur.columns[i : i + 9])
print(man_dalkar)

def prosenta_i_tolu(dalkur):
    return pd.to_numeric(dalkur.astype(str).str.rstrip("%"), errors="coerce").fillna(0) / 100

for d in man_dalkar:
    hjukkur[d] = prosenta_i_tolu(hjukkur[d])

print(hjukkur[["Nafn"] + man_dalkar].head(12))

hjukkur["virkt"] = hjukkur[man_dalkar[0]] - hjukkur[man_dalkar[1:]].sum(axis=1)
hjukkur = hjukkur[hjukkur["virkt"] > 0].copy()

print(len(hjukkur), "hjúkrunarfræðingar í nóvember")
print("Heildar stöðugildi:", round(hjukkur["virkt"].sum(), 1))