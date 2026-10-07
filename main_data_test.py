from pathlib import Path
from data import undirbua_gogn


def profa_gogn(ar, manudur, fra_drattur, vaktir_100):
    gagnamappa = Path(__file__).resolve().parent / "data" / "raw"

    gogn = undirbua_gogn(
        ar=ar,
        manudur=manudur,
        gagnamappa=gagnamappa,
        fra_drattur=fra_drattur,
        vaktir_100=vaktir_100,
        jafnlangar_vaktir=True,
        sama_thorf_alla_daga=True,
        textastefna="manadarprosentur",
    )

    print("Starfsmenn:", len(gogn["starfsmenn"]))
    print("Dagar:", len(gogn["dagar"]))
    print("Markvaktir:", sum(gogn["mark"].values()))
    print("Mönnunarþörf:", sum(gogn["monnunar_thorf"].values()))

    return gogn