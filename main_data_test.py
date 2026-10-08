"""Sýna gögn sama nóvemberverkefnis og main.py; ekkert MIP leyst."""
from pathlib import Path
from pprint import pprint
from data import lesa_novembergogn


def main():
    gogn = lesa_novembergogn(Path(__file__).resolve().parent)
    print("Starfsmenn:", len(gogn["starfsmenn"]))
    print("Dagar:", len(gogn["dagar"]))
    print("Markvaktir:", round(sum(gogn["mark"].values()), 2))
    print("Mönnunarþörf:", sum(gogn["monnunar_thorf"].values()))
    pprint(gogn, sort_dicts=False)


if __name__ == "__main__":
    main()
