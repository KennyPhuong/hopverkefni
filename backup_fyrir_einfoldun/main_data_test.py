"""Prófa gagnaundirbúning á raunverulegum CSV-skrám; ekkert MIP keyrt.

Sjálfgefið eru skrárnar í sömu möppu og þetta forrit. Frádráttarregla
og fimm vaktir/viku eru sýnilegar prófunarforsendur, ekki staðfest lög/reglur.
"""
import argparse
from pathlib import Path
from pprint import pprint
import sys

from data import (
    VAKTIR, bua_til_dagsetningar, lesa_starfsfolk,
    lesa_og_hreinsa_monnun, undirbua_gogn,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ar", type=int, default=2026)
    parser.add_argument("--manudur", type=int, default=11)
    parser.add_argument("--gagnamappa", type=Path,
                        default=Path(__file__).resolve().parent)
    parser.add_argument("--vaktir-100", type=float, default=None,
                        help="Fullt mánaðarvaktamark; annars sýnileg prófunarregla dagar/7*5.")
    args = parser.parse_args()

    try:
        dagar = bua_til_dagsetningar(args.ar, args.manudur)
        tafla = lesa_starfsfolk(args.gagnamappa)
        thorf = lesa_og_hreinsa_monnun(args.gagnamappa)
        print("Heimild:", tafla.attrs["heimild"], flush=True)
        print("Starfsmenn í heimild fyrir síun:", len(tafla), flush=True)
        print("Dagleg mönnun:", {
            s: sum(q for (ss, r), q in thorf.items() if ss == s)
            for s in VAKTIR
        }, flush=True)
        vaktir_100 = args.vaktir_100
        if vaktir_100 is None:
            vaktir_100 = len(dagar) / 7 * 5
            print("PRÓFUNARFORSENDA: fullt vaktamark = dagar/7*5 =",
                  round(vaktir_100, 4), flush=True)
        print("PRÓFUNARFORSENDUR: frádráttur án NM, "
              "jafnlangar vaktir, sama þörf alla daga, mánaðarprósentur "
              "ráða hlutfalli og neikvæð niðurstaða verður 0.", flush=True)

        # Notandi hefur valið að sleppa núverandi óútkljáðum frávikum.
        # Þetta eru útilokanir úr prófun, ekki staðfestar gagnaleiðréttingar.
        sleppa = {
            "h74": "Óútkljáður vaktakóði 12-20-KV.",
            "h124": "Óútkljáður vaktakóði MV-KV-4.",
            "h147": "Ógildur hæfnifáni a=11.",
        }
        if args.manudur == 11:
            sleppa["h100"] = "Neikvætt reiknað hlutfall í nóvember."
        print("Sleppt í þessari prófun:", sleppa, flush=True)

        gogn = undirbua_gogn(
            ar=args.ar,
            manudur=args.manudur,
            gagnamappa=args.gagnamappa,
            fra_drattur=["verkefni", "bor", "namsleyfi", "stjornun",
                         "faeding", "leyfi", "veikindi"],
            vaktir_100=vaktir_100,
            jafnlangar_vaktir=True,
            sama_thorf_alla_daga=True,
            textastefna="manadarprosentur",
            neikvaett_i_null=True,
            sleppa_starfsmonnum=sleppa,
        )
    except (ValueError, FileNotFoundError) as villa:
        print("\nGagnaprófun stöðvað:", villa, flush=True)
        print("Engin full staðfest gogn-orðabók hefur verið búin til.", flush=True)
        return 1

    print("\nÚtilokaðir vegna frávika:", len(gogn["utskildir"]))
    print("Starfsmenn eftir síun:", len(gogn["starfsmenn"]))
    print("Dagar:", len(gogn["dagar"]))
    print("Markvaktir:", sum(gogn["mark"].values()))
    print("Mönnunarþörf:", sum(gogn["monnunar_thorf"].values()))
    print("\nAðalorðabók fyrir model.py:")
    pprint(gogn, sort_dicts=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
