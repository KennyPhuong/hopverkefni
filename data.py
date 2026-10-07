"""Excel-gögn fyrir mánaðarlegt vaktaplan; engin Gurobi-háð virkni.

Frádráttarflokkar, fullt vaktamark og forgangur mánaðarprósenta gagnvart
texta eru skýr inntök. Óútkljáð gögn valda ValueError. Hrá gögn eru óbreytt.
"""
import calendar
import re
import unicodedata
from collections import Counter
from datetime import date
from math import isfinite
from numbers import Integral, Real
from pathlib import Path
import pandas as pd

VAKTIR = ("MV", "KV", "NV")
MANADARHEITI = ("Janúar", "Febrúar", "Mars", "Apríl", "Maí", "Júní",
               "Júlí", "Ágúst", "September", "Október", "Nóvember", "Desember")
HAEFNIDALKAR = {"v": "V", "t": "T", "h": "H", "a1": "A1", "a": "A",
               "b1": "B1", "b": "B", "c": "C", "d1": "D1", "dg": "Dg", "d": "D"}
MANADARMERKINGAR = ("hlutfall", "verkefni", "bor", "nm", "namsleyfi",
                    "stjornun", "faeding", "leyfi", "veikindi")
MANADARFYRIRSAGNIR = ("Verkefni", "BÖR", "NM", "Námsleyfi", "Stjórnun",
                      "Fæðing", "Leyfi", "Veikindi")
SKRA = "HR-gognin (1).xlsx"


def _texti(x):
    return unicodedata.normalize("NFC", str(x)).strip()


def _autt(x):
    return x is None or bool(pd.isna(x)) or (isinstance(x, str) and not x.strip())


def _tala(x, samhengi):
    """Ströng tölutúlkun. Bool, tóm gildi og óendanleg gildi eru villur."""
    if _autt(x) or isinstance(x, bool):
        raise ValueError(f"{samhengi}: ógilt gildi {x!r}.")
    if isinstance(x, Real):
        tala = float(x)
    elif isinstance(x, str):
        t = _texti(x).replace(",", ".")
        prosent = t.endswith("%")
        try:
            tala = float(t[:-1].strip() if prosent else t)
        except ValueError as e:
            raise ValueError(f"{samhengi}: ólæsilegt gildi {x!r}.") from e
        if prosent:
            tala /= 100
    else:
        raise ValueError(f"{samhengi}: óþekkt tölusnið {x!r}.")
    if not isfinite(tala):
        raise ValueError(f"{samhengi}: ekki endanleg tala {x!r}.")
    return tala


def _skraslod(gagnamappa):
    """Leyfa möppu eða beina Excel-slóð; samræma Unicode við nafnaleit."""
    p = Path(gagnamappa).expanduser().resolve()
    if p.is_file():
        if p.suffix.lower() != ".xlsx":
            raise ValueError("Aðalheimild þarf að vera .xlsx-skjal.")
        return p
    if not p.is_dir():
        raise FileNotFoundError(f"Gagnamappa er ekki til: {p}")
    fs = [f for f in p.iterdir() if _texti(f.name) == SKRA]
    if len(fs) != 1:
        raise FileNotFoundError(f"Vantar ótvíræða heimild {SKRA!r} í {p}.")
    return fs[0]


def bua_til_dagsetningar(ar, manudur):
    """Allar dagsetningar mánaðar; bool telst ekki gilt ár/mánuður."""
    if isinstance(ar, bool) or not isinstance(ar, Integral) or not 1 <= ar <= 9999:
        raise ValueError("Ár þarf að vera heiltala á bilinu 1–9999.")
    if isinstance(manudur, bool) or not isinstance(manudur, Integral) or not 1 <= manudur <= 12:
        raise ValueError("Mánuður þarf að vera heiltala á bilinu 1–12.")
    return [date(int(ar), int(manudur), d)
            for d in range(1, calendar.monthrange(ar, manudur)[1] + 1)]


def lesa_starfsfolk(gagnamappa):
    """Lesa Hjúkkur, varðveita prósentur og velja einstök h-auðkenni.

    Hráar fyrirsagnir fylgja í attrs. Endurtekin heiti fá eigin viðskeyti,
    svo mánaðarval sé óháð viðskeytum pandas.
    """
    slod = _skraslod(gagnamappa)
    hra = pd.read_excel(slod, sheet_name="Hjúkkur", header=None, dtype=object, engine="openpyxl")
    if hra.empty:
        raise ValueError("Hjúkkur-blaðið er tómt.")
    headers = ["" if _autt(x) else _texti(x) for x in hra.iloc[0]]
    # Hæfnidálkar eru fyrir framan Vaktir; mánaðar-BÖR er annar dálkur.
    skil = headers.index("Vaktir") if "Vaktir" in headers else 0
    headers = [h.lower() if j < skil and h.lower() in {*HAEFNIDALKAR, "bör"}
               else h for j, h in enumerate(headers)]
    counts, columns = Counter(), []
    for j, h in enumerate(headers):
        h = h or f"_autt_{j}"
        counts[h] += 1
        columns.append(h if counts[h] == 1 else f"{h}__{counts[h]}")
    if len(set(columns)) != len(columns):
        raise ValueError("Dálkaheiti eru ekki ótvíræð.")
    tafla = hra.iloc[1:].copy()
    tafla.columns = columns
    vantar = {"Nafn", "Vaktir", *HAEFNIDALKAR} - set(columns)
    if vantar:
        raise ValueError(f"Vantar skyldudálka í Hjúkkur: {sorted(vantar)}")
    nofn = tafla["Nafn"].map(lambda x: "" if _autt(x) else _texti(x))
    ogild = nofn[nofn.ne("") & ~nofn.str.fullmatch(r"h[1-9]\d*")]
    if not ogild.empty:
        raise ValueError(f"Ógild starfsmannaauðkenni: {ogild.to_dict()}")
    tafla = tafla.loc[nofn.str.fullmatch(r"h[1-9]\d*")].copy()
    tafla["Nafn"] = nofn.loc[tafla.index]
    if tafla.empty or tafla["Nafn"].duplicated().any():
        raise ValueError("Engir starfsmenn eða tvítekin auðkenni í Hjúkkur.")
    tafla.attrs.update(fyrirsagnir=headers, heimild=str(slod))
    return tafla


def velja_manadarblokk(tafla, manudur, *, bn_sem_nm=False):
    """Staðfesta níu dálka mánaðar. BN þarf skýra samþykkt vörpun."""
    bua_til_dagsetningar(2000, manudur)
    if not isinstance(bn_sem_nm, bool):
        raise ValueError("bn_sem_nm þarf að vera True eða False.")
    heiti = MANADARHEITI[manudur - 1]
    headers = tafla.attrs.get("fyrirsagnir")
    if headers is None:
        headers = [re.sub(r"(?:__\d+|\.\d+)$", "", _texti(c)) for c in tafla.columns]
    if len(headers) != len(tafla.columns) or headers.count(heiti) != 1:
        raise ValueError(f"Mánaðarblokk {heiti} er ekki ótvíræð.")
    j = headers.index(heiti)
    blokk = list(headers[j:j + 9])
    if len(blokk) == 9 and blokk[3] == "BN":
        if not bn_sem_nm:
            raise ValueError(f"{heiti}: BN í stað NM; þarf bn_sem_nm=True eftir staðfestingu.")
        blokk[3] = "NM"
    vaent = [heiti, *MANADARFYRIRSAGNIR]
    if blokk != vaent:
        raise ValueError(f"{heiti}: röng dálkaröð {blokk!r}; vænti {vaent!r}.")
    return dict(zip(MANADARMERKINGAR, tafla.columns[j:j + 9]))


def breyta_prosentum(tafla, dalkar):
    """Skila afriti með hlutföllum 0–1; ekki fylla villur með núlli."""
    nytt = tafla.copy()
    for c in dalkar:
        if c not in nytt:
            raise ValueError(f"Vantar prósentudálk {c!r}.")
        values = []
        for _, rod in nytt.iterrows():
            samhengi = f"Starfsmaður {rod['Nafn']}, dálkur {c}"
            v = _tala(rod[c], samhengi)
            if not 0 <= v <= 1:
                raise ValueError(f"{samhengi}: hlutfall utan 0–1, {rod[c]!r}.")
            values.append(v)
        nytt[c] = values
    return nytt


def reikna_virkt_hlutfall(tafla, dalkakort, fra_drattur):
    """Mánaðarhlutfall mínus eingöngu skýrt valdir frádráttarflokkar."""
    if fra_drattur is None or isinstance(fra_drattur, str):
        raise ValueError("Velja þarf fra_drattur sem lista; engin sjálfgefin NM-túlkun.")
    flokkar = tuple(fra_drattur)
    if len(set(flokkar)) != len(flokkar) or "hlutfall" in flokkar or set(flokkar) - set(dalkakort):
        raise ValueError(f"Ógildir eða tvíteknir frádráttarflokkar: {flokkar}")
    nidur, villur = {}, []
    for _, rod in tafla.iterrows():
        base = _tala(rod[dalkakort["hlutfall"]], f"{rod['Nafn']}: mánaðarhlutfall")
        lidur = {k: _tala(rod[dalkakort[k]], f"{rod['Nafn']}: {k}") for k in flokkar}
        if not 0 <= base <= 1 or any(not 0 <= v <= 1 for v in lidur.values()):
            raise ValueError(f"{rod['Nafn']}: liðir utan 0–1.")
        v = base - sum(lidur.values())
        if abs(v) < 1e-12:  # Eingöngu reikningsskekkja, ekki efnisleg klipping.
            v = 0.0
        if v < 0:
            villur.append(f"{rod['Nafn']}: {base} - {lidur} = {v:.6g}")
        nidur[rod["Nafn"]] = v
    if villur:
        raise ValueError("Neikvætt virkt hlutfall; leiðrétta áður en síað er:\n" + "\n".join(villur))
    return nidur


def hreinsa_vaktir(tafla):
    """Staðfesta allan vaktakóðann, ekki aðeins þekkta hluta hans."""
    nidur, villur = {}, []
    for _, rod in tafla.iterrows():
        hra = rod["Vaktir"]
        texti = "" if _autt(hra) else _texti(hra).upper()
        hlutar = [x.strip() for x in texti.split("-")]
        if not texti or any(x not in VAKTIR for x in hlutar):
            villur.append(f"{rod['Nafn']}, Vaktir: {hra!r}")
        else:
            nidur[rod["Nafn"]] = list(dict.fromkeys(hlutar))
    if villur:
        raise ValueError("Óþekktir vaktakóðar; þarf staðfesta leiðréttingu:\n" + "\n".join(villur))
    return nidur


def hreinsa_haefni(tafla):
    """Aðeins fáni 1 veitir hæfni; bör er ekki mönnunarhlutverk."""
    if set(HAEFNIDALKAR) - set(tafla.columns):
        raise ValueError("Vantar hæfnidálka.")
    nidur, villur = {}, []
    for _, rod in tafla.iterrows():
        hlutverk = []
        for c, r in HAEFNIDALKAR.items():
            samhengi = f"{rod['Nafn']}, hæfnidálkur {c}"
            try:
                if isinstance(rod[c], str) and "%" in rod[c]:
                    raise ValueError(f"{samhengi}: hæfni er fáni, ekki prósenta.")
                flag = _tala(rod[c], samhengi)
                if flag not in (0, 1):
                    raise ValueError(f"{samhengi}: vænti 0/1, fékk {rod[c]!r}.")
                if flag == 1:
                    hlutverk.append(r)
            except ValueError as e:
                villur.append(str(e))
        nidur[rod["Nafn"]] = hlutverk
        if not hlutverk:
            villur.append(f"{rod['Nafn']}: engin klínísk hæfni.")
    if villur:
        raise ValueError("Ógild hæfni:\n" + "\n".join(villur))
    return nidur


def reikna_markvaktir(virkt, ar, manudur, vaktir_100):
    """Ónámundað mark; kallandi gefur fullt viðmið fyrir valinn mánuð."""
    bua_til_dagsetningar(ar, manudur)
    if isinstance(vaktir_100, bool) or not isinstance(vaktir_100, Real):
        raise ValueError("vaktir_100 þarf að vera tala, ekki texti eða prósentustrengur.")
    fullt = _tala(vaktir_100, "vaktir_100")
    if fullt <= 0:
        raise ValueError("vaktir_100 þarf að vera jákvætt.")
    nidur = {}
    for n, hlutfall in virkt.items():
        h = _tala(hlutfall, f"{n}: virkt hlutfall")
        if not 0 <= h <= 1:
            raise ValueError(f"{n}: virkt hlutfall utan 0–1.")
        nidur[n] = h * fullt
    return nidur


def _beita_leidrettingum(tafla, leidrettingar, manudur, dalkakort):
    """Listi: starfsmadur/dalkur/gamalt/nytt/astaeda, með varðveittu loggi.

    Mánaðarleiðrétting notar merkingu, t.d. faeding, og krefst manudur.
    Aðrir dálkar nota hrátt heiti, t.d. Vaktir eða a.
    """
    nytt, log = tafla.copy(), []
    for l in leidrettingar or ():
        skyldu = {"starfsmadur", "dalkur", "gamalt", "nytt", "astaeda"}
        if not skyldu <= set(l) or not isinstance(l["astaeda"], str) or not l["astaeda"].strip():
            raise ValueError("Leiðrétting þarf starfsmadur, dalkur, gamalt, nytt og astaeda.")
        if "manudur" in l:
            bua_til_dagsetningar(2000, l["manudur"])
            if l["manudur"] != manudur:
                continue
        c = l["dalkur"]
        if c in dalkakort:
            if "manudur" not in l:
                raise ValueError("Leiðrétting mánaðargildis þarf manudur.")
            c = dalkakort[c]
        elif c not in {"Vaktir", "Vinnufyrirkomulag", "Athugasemdir", "bör", *HAEFNIDALKAR}:
            raise ValueError("Nota þarf merkingu og manudur fyrir mánaðarleiðréttingu.")
        if c == "Nafn" or c not in nytt:
            raise ValueError(f"Óleyfilegur leiðréttingardálkur {c!r}.")
        index = nytt.index[nytt["Nafn"] == l["starfsmadur"]]
        if len(index) != 1:
            raise ValueError(f"Óþekktur starfsmaður í leiðréttingu: {l['starfsmadur']}")
        gamalt = nytt.at[index[0], c]
        if _autt(gamalt) or gamalt != l["gamalt"]:
            raise ValueError(f"Úrelt leiðrétting fyrir {l['starfsmadur']}/{c}: "
                             f"heimild {gamalt!r}, vænti {l['gamalt']!r}.")
        nytt.at[index[0], c] = l["nytt"]
        log.append({**l, "heimildardalkur": c, "gamalt": gamalt})
    return nytt, log


def lesa_og_hreinsa_starfsfolk(gagnamappa, ar, manudur, *, fra_drattur=None,
                              vaktir_100=None, bn_sem_nm=False,
                              leidrettingar=None, textastefna=None):
    """Samþætta innlestur, mánaðarval og hreinsun.

    textastefna='manadarprosentur' er skýr einföldun: mánaðarprósentur
    ráða reiknuðu hlutfalli. Texti er varðveittur, ekki sjálfkrafa túlkaður
    sem dagsett ófáanleiki, ósk eða staðfestur samningur.
    """
    bua_til_dagsetningar(ar, manudur)
    if fra_drattur is None or vaktir_100 is None:
        raise ValueError("Gefðu fra_drattur og vaktir_100; engin sjálfgefin túlkun.")
    if isinstance(fra_drattur, str):
        raise ValueError("fra_drattur þarf að vera listi, ekki texti.")
    fra_drattur = tuple(fra_drattur)
    reikna_markvaktir({}, ar, manudur, vaktir_100)
    if textastefna not in (None, "manadarprosentur"):
        raise ValueError("Óþekkt textastefna; leyfilegt er 'manadarprosentur'.")
    tafla = lesa_starfsfolk(gagnamappa)
    kort = velja_manadarblokk(tafla, manudur, bn_sem_nm=bn_sem_nm)
    tafla, log = _beita_leidrettingum(tafla, leidrettingar, manudur, kort)
    if manudur == 8 and bn_sem_nm and tafla.attrs["fyrirsagnir"][
            list(tafla.columns).index(kort["nm"])] == "BN":
        log.append({"dalkur": kort["nm"], "gamalt": "BN", "nytt": "NM",
                    "manudur": 8, "astaeda": "Kallandi valdi bn_sem_nm=True sérstaklega."})
    tafla = breyta_prosentum(tafla, list(kort.values()))
    virkt = reikna_virkt_hlutfall(tafla, kort, fra_drattur)
    virk = tafla.loc[tafla["Nafn"].map(virkt) > 0].copy()
    textar = {}
    for _, rod in tafla.iterrows():
        t = {c: _texti(rod[c]) for c in ("Vinnufyrirkomulag", "Athugasemdir")
             if c in tafla and isinstance(rod[c], str) and not _autt(rod[c])}
        if t:
            textar[rod["Nafn"]] = t
    if textar and textastefna is None:
        raise ValueError("Frjáls samnings-/athugasemdatexti er til staðar. "
                         "Veldu textastefna='manadarprosentur' aðeins sem skráða "
                         "einföldun; texti verður þá ekki sjálfkrafa að skorðum.")
    leyfdar, haefni = hreinsa_vaktir(virk), hreinsa_haefni(virk)
    nofn = virk["Nafn"].tolist()
    virkt = {n: virkt[n] for n in nofn}
    return {"starfsmenn": nofn, "leyfdar": leyfdar, "haefni": haefni,
            "mark": reikna_markvaktir(virkt, ar, manudur, vaktir_100),
            "virkt": virkt, "leidrettingar": log, "texti": textar}


def lesa_og_hreinsa_monnun(gagnamappa):
    """Telja hlutverkasæti undir MV/KV/NV á Sheet2."""
    tafla = pd.read_excel(_skraslod(gagnamappa), sheet_name="Sheet2",
                          header=None, dtype=object, engine="openpyxl")
    headers = []
    for j, rod in tafla.iterrows():
        gild = ["" if _autt(x) else _texti(x).upper() for x in rod]
        if all(gild.count(s) == 1 for s in VAKTIR):
            if any(x and x not in VAKTIR for x in gild):
                raise ValueError(f"Sheet2, röð {j + 1}: óþekkt vaktarfyrirsögn.")
            headers.append((j, {s: gild.index(s) for s in VAKTIR}))
    if len(headers) != 1:
        raise ValueError("Sheet2: vantar ótvíræða MV/KV/NV-fyrirsögn.")
    j, dalkar = headers[0]
    roles = {r.upper(): r for r in HAEFNIDALKAR.values()}
    thorf = Counter()
    for s, c in dalkar.items():
        for idx, x in tafla.loc[j + 1:, c].items():
            if _autt(x):
                continue
            r = roles.get(_texti(x).upper())
            if r is None:
                raise ValueError(f"Sheet2, röð {idx + 1}, {s}: óþekkt hlutverk {x!r}.")
            thorf[s, r] += 1
        if not any(v == s for v, r in thorf):
            raise ValueError(f"Sheet2: engin mönnunarsæti á {s}.")
    return dict(thorf)


def undirbua_gogn(ar, manudur, gagnamappa=None, *, fra_drattur=None,
                 vaktir_100=None, bn_sem_nm=False, leidrettingar=None,
                 textastefna=None, jafnlangar_vaktir=None, sama_thorf_alla_daga=None):
    """Aðalviðmót. Kallandi samþykkir einföldunarforsendur sérstaklega.

    mark er soft viðmið, ekki hörð mörk; þau bíða staðfestrar reglu.
    Mánaðarheiti staðfesta ekki ár gagna: notandi þarf að yfirfara það.
    """
    dagar = bua_til_dagsetningar(ar, manudur)
    if jafnlangar_vaktir is not True:
        raise ValueError("Vaktatalning þarf jafnlangar_vaktir=True sem skýra forsendu; "
                         "mislangar vaktir krefjast stundaviðmóts í model.py.")
    if sama_thorf_alla_daga is not True:
        raise ValueError("Dagleg endurtekning þarf sama_thorf_alla_daga=True sem skýra forsendu.")
    if gagnamappa is None:
        gagnamappa = Path(__file__).resolve().parent / "data" / "raw"
    sf = lesa_og_hreinsa_starfsfolk(
        gagnamappa, ar, manudur, fra_drattur=fra_drattur, vaktir_100=vaktir_100,
        bn_sem_nm=bn_sem_nm, leidrettingar=leidrettingar, textastefna=textastefna)
    thorf = lesa_og_hreinsa_monnun(gagnamappa)
    gogn = {"ar": ar, "manudur": manudur, "dagar": dagar, "vaktir": VAKTIR,
            **{k: sf[k] for k in ("starfsmenn", "leyfdar", "haefni", "mark")},
            "hlutverk": sorted({r for s, r in thorf}),
            "monnunar_thorf": {(d, s, r): q for d in dagar for (s, r), q in thorf.items()},
            "virkt": sf["virkt"], "leidrettingar": sf["leidrettingar"], "texti": sf["texti"],
            "forsendur": {"fra_drattur": list(fra_drattur), "vaktir_100": vaktir_100,
                          "bn_sem_nm": bn_sem_nm, "textastefna": textastefna,
                          "jafnlangar_vaktir": True, "sama_thorf_alla_daga": True}}
    sannreyna_gogn(gogn)
    return gogn


def sannreyna_gogn(gogn):
    """Prófa gagnasamning og augljósa ómönnunarhæfni, ekki MIP-leysanleika."""
    skyldu = {"ar", "manudur", "dagar", "vaktir", "starfsmenn", "leyfdar",
              "haefni", "mark", "hlutverk", "monnunar_thorf"}
    if skyldu - set(gogn):
        raise ValueError(f"Vantar lykla í gogn: {sorted(skyldu - set(gogn))}")
    if gogn["dagar"] != bua_til_dagsetningar(gogn["ar"], gogn["manudur"]):
        raise ValueError("dagar þurfa að innihalda allan mánuðinn einu sinni og í röð.")
    nofn = gogn["starfsmenn"]
    if len(set(nofn)) != len(nofn) or any(not isinstance(n, str) or not n for n in nofn):
        raise ValueError("Starfsmannaauðkenni eru ógild eða tvítekin.")
    if tuple(gogn["vaktir"]) != VAKTIR:
        raise ValueError("vaktir þurfa að vera MV, KV, NV.")
    roles = gogn["hlutverk"]
    if len(set(roles)) != len(roles) or not set(roles) <= set(HAEFNIDALKAR.values()):
        raise ValueError("hlutverk eru óþekkt eða tvítekin.")
    for k in ("leyfdar", "haefni", "mark"):
        if set(gogn[k]) != set(nofn):
            raise ValueError(f"Auðkenni í {k} passa ekki við starfsmenn.")
    for n in nofn:
        for k, leyfilegt in (("leyfdar", set(VAKTIR)), ("haefni", set(HAEFNIDALKAR.values()))):
            gild = gogn[k][n]
            if not gild or len(set(gild)) != len(gild) or not set(gild) <= leyfilegt:
                raise ValueError(f"{n}: ógild eða tvítekin gildi í {k}.")
        mark = gogn["mark"][n]
        if isinstance(mark, bool) or not isinstance(mark, Real):
            raise ValueError(f"{n}: mark þarf að vera tala.")
        if _tala(mark, f"{n}: mark") < 0:
            raise ValueError(f"{n}: neikvætt mark.")
    dagleg = {}
    fyrir = {(s, r) for n in nofn for s in gogn["leyfdar"][n] for r in gogn["haefni"][n]}
    for lykill, q in gogn["monnunar_thorf"].items():
        if not isinstance(lykill, tuple) or len(lykill) != 3:
            raise ValueError(f"Ógildur mönnunarlykill {lykill!r}.")
        d, s, r = lykill
        if d not in gogn["dagar"] or s not in VAKTIR or r not in roles:
            raise ValueError(f"Ógild dagsetning/vakt/hlutverk í {lykill!r}.")
        if isinstance(q, bool) or not isinstance(q, Integral) or q < 0:
            raise ValueError(f"{lykill}: mönnun þarf að vera heiltala >= 0.")
        if q > 0 and (s, r) not in fyrir:
            raise ValueError(f"{lykill}: enginn gjaldgengur starfsmaður.")
        dagleg.setdefault(d, {})[s, r] = q
    if set(dagleg) != set(gogn["dagar"]):
        raise ValueError("Mönnunarþörf vantar fyrir dagsetningu.")
    fyrst = dagleg[gogn["dagar"][0]]
    if any(v != fyrst for v in dagleg.values()):
        raise ValueError("Mönnunarþörf er ekki samræmd milli daga í föstu daglega viðmótinu.")
    if any(not any(s == v and q > 0 for (v, r), q in fyrst.items()) for s in VAKTIR):
        raise ValueError("Mönnunarþörf vantar fyrir vaktategund.")

