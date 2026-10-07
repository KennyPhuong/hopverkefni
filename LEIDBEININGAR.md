# Gagnaundirbúningur tilbúinn til samþættingar

`data.py` hefur engin óútfærð föll eða `NotImplementedError`. Öll tólf föllin
úr beinagrindinni eru útfærð. Gurobi er ekki nauðsynlegt fyrir þennan hluta.
Uppsetning og prófanir, úr möppunni með `data.py`:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

`requirements.txt` festir útgáfurnar sem voru prófaðar: pandas 2.2.3 og
openpyxl 3.1.5. Engar breytingar voru gerðar á upprunalegu gagnaskránum.

## Kall úr main.py

Eftirfarandi er stutt kall. Breyturnar `stadfestir_fra_drattarflokkar` og
`stadfest_vaktamark_100` þarf að skilgreina með samþykktum gildum fyrir
valinn mánuð. Ekki setja 20 eða `dagar/7*5` sjálfkrafa í vaktamarkið.

```python
from pathlib import Path
from data import undirbua_gogn

gogn = undirbua_gogn(
    ar=2026,
    manudur=11,
    gagnamappa=Path(__file__).resolve().parent / "data" / "raw",
    fra_drattur=stadfestir_fra_drattarflokkar,
    vaktir_100=stadfest_vaktamark_100,
    jafnlangar_vaktir=True,
    sama_thorf_alla_daga=True,
    textastefna="manadarprosentur",
)
```

Þetta dæmi samþykkir þrjár einföldunarforsendur sérstaklega:

- **Jafnlangar vaktir:** talning vakta er viðeigandi. Fyrir mislangar vaktir
  þarf stundaviðmót bæði hér og í model.py; fallið hafnar þeim núna.
- **Sama þörf alla daga:** dagleg talning úr Sheet2 er endurtekin yfir mánuð.
- **Mánaðarprósentur ráða hlutfalli:** frjáls texti er varðveittur, en ekki
  sjálfkrafa breytt í dagsetta ófáanleika, samninga eða óskir. Árekstrar við
  texta eru því ekki sjálfkrafa leystir. Veljið þessa stefnu aðeins sem
  skráða einföldun. Annars þarf handvirka yfirferð fyrst.

Ár og mánuður ákvarða almanakið. Notandi þarf að staðfesta að heimildin sé
fyrir þetta ár; mánaðarheiti Excel-skjalanna staðfesta ekki sjálf gagnaárið.

`gagnamappa` má einnig vera bein slóð á .xlsx-skrána. Sjálfgefin mappa er
`data/raw` við hlið data.py, óháð því hvaðan forritið er keyrt.

## Frádráttarflokkar og vinnuskylda

Leyfilegar merkingar til frádráttar eru `verkefni`, `bor`, `nm`, `namsleyfi`,
`stjornun`, `faeding`, `leyfi`, `veikindi`.

Til samanburðar dregur samantekt Excel frá öllum þessum flokkum **nema nm**.
Kóðinn gerir það ekki sjálfgefna reglu. Þið gefið `fra_drattur` sérstaklega.
`bn_sem_nm=True` leyfir vörpun BN í ágúst yfir í NM og skráir vörpunina;
sjálfgefið er False og villuboð ef BN kemur fyrir.

`mark[n] = virkt[n] * vaktir_100` er varðveitt án námundunar. Það er soft
viðmið, ekki harður hámarks-/lágmarksfjöldi. Hörð vinnuskyldumörk eru ekki
búin til þar sem samþykkt námundunarregla vantar. Þetta er skjalfest
ákvörðunarháð atriði, ekki óútfært fall.

## Leiðréttingar með rekjanleika

`leidrettingar` er valfrjáls listi af orðabókum. Engar leiðréttingar fylgja
sjálfgefið. Hver orðabók þarf:

```python
{
    "starfsmadur": "hX",
    "dalkur": "a",
    "gamalt": gamla_gildid,
    "nytt": stadfesta_nyja_gildid,
    "astaeda": "Ástæða og heimild staðfestingar",
}
```

Þetta er sniðdæmi, ekki raunveruleg leiðrétting. Fyrir mánaðarprósentu er
`dalkur` merking eins og `faeding` og `manudur` er nauðsynlegur. Ekki nota
hrá mánaðardálkaheiti í leiðréttingum. Fyrir vaktakóða er `dalkur="Vaktir"`.
Leiðréttingin er aðeins framkvæmd ef gamla gildið passar við heimildina.
Óþekktir starfsmenn, vantar ástæðu eða úrelt gamalt gildi valda villu.

Kóðinn breytir aðeins afriti í minni; upprunalega skráin er aldrei vistuð yfir.

## Viðmót við model.py

Upprunalegir lyklar haldast:
`ar`, `manudur`, `dagar`, `vaktir`, `starfsmenn`, `leyfdar`, `haefni`, `mark`,
`hlutverk`, `monnunar_thorf`.

Viðbætur eru:

| Lykill | Innihald |
|---|---|
| `virkt` | Virkt hlutfall fyrir starfsmenn sem eru teknir með |
| `leidrettingar` | Gamalt/nytt gildi og ástæða hverrar framkvæmdrar leiðréttingar |
| `texti` | Varðveittur samnings-/athugasemdatexti, einnig um óvirkt starfsfólk |
| `forsendur` | Frádráttarflokkar, full vinnuskylda og valdar einföldunarforsendur |

`dagar` eru datetime.date; eldri model.py-kóði sem notar heiltöludaga þarf
að nota dagsetningareikning, til dæmis timedelta(days=1).

Hæfnifánar eru sannreyndir fyrir starfsfólk með jákvætt virkt hlutfall.
`bör` er varðveitt í hráu starfsmannatöflunni en ekki talið demand-hlutverk.
Óvirkar raðir eru ekki látnar mynda ómönnunarhæfni eða vaktakóðavillur.

## Prófanir og raunverulegur innlestur

25 próf voru keyrð og stóðust: 22 með tilbúnum gögnum og 3 með raunverulegu
Excel-skjalinu. Prófin voru keyrð úr annarri vinnumöppu en skráarmöppunni.

Raunverulegu prófin eru valfrjáls hjá liðinu: skilgreinið `HR_GAGNAMAPPA`
sem möppu upprunalegu gagnanna áður en unittest er keyrt. Án hennar eru
þau þrjú próf merkt sleppt, ekki staðist.

Staðfest á raunverulegu heimildinni:

- 170 einstakar starfsmannaraðir fyrir síun.
- Mönnun úr endurteknum sætum: MV=19, KV=19, NV=12.
- Október: 139 jákvæð hlutföll og 98.579 FTE samkvæmt frádráttarreglu Excel.
- Óþekktir vaktakóðar h74/h124 og ógildur hæfnifáni h147 greinast.
- Nóvember: neikvætt virkt hlutfall hjá h100 veldur villu áður en síað er.

Full samþætt gagnakeyrsla tókst á tilbúnu Excel-dæmi, þar með talið skráðar
leiðréttingar og varðveisla hrárrar skráar. **Óleiðrétta raunheimildin skilar
ekki enn samþykktum model-gögnum**: hún stöðvast rétt við óútkljáð gildi.

Nánari gagnavillur og ákvarðanir eru í GAGNAVILLUR.md.
