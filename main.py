from pathlib import Path

import pandas as pd
import gurobipy as gp
from gurobipy import GRB
import matplotlib.pyplot as plt

MAPPA = Path(__file__).parent

hjukkur = pd.read_csv(MAPPA / "HR-gognin(Hjúkkur).csv", encoding="latin1")
monnun = pd.read_csv(MAPPA / "HR-gognin(Sheet2).csv", encoding="latin1")

print(hjukkur.head())
print(monnun)

print("sup")