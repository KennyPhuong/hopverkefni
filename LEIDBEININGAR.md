# Gagnaundirbúningur tilbúinn til samþættingar

`data.py` hefur engin óútfærð föll eða `NotImplementedError`. Öll tólf föllin
úr beinagrindinni eru útfærð. Gurobi er ekki nauðsynlegt fyrir þennan hluta.
Uppsetning og prófanir, úr möppunni með `data.py`:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

`requirements.txt` festir útgáfurnar sem voru prófaðar: pandas 2.2.3;
openpyxl er ekki lengur nauðsynlegt. Engar breytingar voru gerðar á upprunalegu gagnaskránum.

## Kall úr main.py

Innlestrarheimildir eru eingöngu `HR-gognin(Hjúkkur).csv` og
`HR-gognin(Sheet2).csv`. Kóðinn notar ekki .xlsx-skjalið. CSV-gildin eru
notuð eins og þau eru, þar með talið námundun þeirra. Hann styður
Latin-1 og UTF-8 með eða án BOM.

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
    neikvaett_i_null=True,
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
fyrir þetta ár; mánaðarheiti CSV-skjalanna staðfesta ekki sjálf gagnaárið.

`gagnamappa` má einnig vera bein slóð á starfsmanna-CSV; mönnunar-CSV
þarf að vera í sömu möppu. Sjálfgefin mappa er
`data/raw` við hlið data.py, óháð því hvaðan forritið er keyrt.

## Frádráttarflokkar og vinnuskylda

Leyfilegar merkingar til frádráttar eru `verkefni`, `bor`, `nm`, `namsleyfi`,
`stjornun`, `faeding`, `leyfi`, `veikindi`.

Til samanburðar dregur samantekt upprunalega vinnubókarinnar frá öllum þessum flokkum **nema nm**.
Kóðinn gerir það ekki sjálfgefna reglu. Þið gefið `fra_drattur` sérstaklega.
`bn_sem_nm=True` leyfir vörpun BN í ágúst yfir í NM og skráir vörpunina;
sjálfgefið er False og villuboð ef BN kemur fyrir.

`mark[n] = virkt[n] * vaktir_100` er varðveitt án námundunar. Það er soft
viðmið, ekki harður hámarks-/lágmarksfjöldi. Hörð vinnuskyldumörk eru ekki
búin til þar sem samþykkt námundunarregla vantar. Þetta er skjalfest
ákvörðunarháð atriði, ekki óútfært fall.

## Leiðréttingar með rekjanleika

### Neikvæð reiknuð hlutföll í núll

Með `neikvaett_i_null=True` er `virkt = max(0, reiknað_hlutfall)`.
Starfsmaður með neikvæða niðurstöðu fær því ekkert vinnuframboð og er
síaður út. Viðvörun sýnir starfsmann, mánuð, neikvæða gildið og frádrátt.
Upprunalega niðurstaðan og núllgildið fara í `gogn["leidrettingar"]` með
ástæðu. Stillingin er líka í `gogn["forsendur"]`.

Þetta er valin einföldun, ekki staðfest leiðrétting á CSV-gögnum.
Sjálfgefið er `False`: neikvætt hlutfall veldur þá áfram villu.
Stillingin meðhöndlar aðeins reiknaða niðurstöðu; ógild hrá prósentugildi,
vaktakóðar og hæfnifánar eru enn villur.

Í h100/nóvember-dæminu verður -0.1 að 0. Gögnin komast þá fram hjá
hlutfallsvillunni, en næstu óútkljáðu vaktakóðar stöðva áfram keyrsluna.

### Handvirkar staðfestar leiðréttingar

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
| `utskildir` | Auðkenni, ástæða, ár og mánuður fyrir sérstaklega útilokaðar raðir |
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

34 próf voru keyrð og stóðust: 29 með tilbúnum gögnum og 5 með raunverulegu
CSV-skjalinu. Prófin voru keyrð úr annarri vinnumöppu en skráarmöppunni.

Raunverulegu prófin eru valfrjáls hjá liðinu: skilgreinið `HR_GAGNAMAPPA`
sem möppu upprunalegu gagnanna áður en unittest er keyrt. Án hennar eru
þau fimm próf merkt sleppt, ekki staðist.

Staðfest á raunverulegu heimildinni:

- 170 einstakar starfsmannaraðir fyrir síun.
- Mönnun úr endurteknum sætum: MV=19, KV=19, NV=12.
- Október: 139 jákvæð hlutföll og 98.58 FTE samkvæmt frádráttarreglu CSV.
- Óþekktir vaktakóðar h74/h124 og ógildur hæfnifáni h147 greinast.
- Nóvember: neikvætt virkt hlutfall hjá h100 veldur villu áður en síað er.
- Með núllstillingu: h100 fær 0 og viðvörun, en óþekktir vaktakóðar eru
  enn greindir. Sjálfgefna stranga leiðin er einnig prófuð.

Full samþætt gagnakeyrsla tókst á tilbúnu CSV-dæmi, þar með talið skráðar
leiðréttingar og varðveisla hrárrar skráar. **Óleiðrétta raunheimildin skilar
ekki enn samþykktum model-gögnum**: hún stöðvast rétt við óútkljáð gildi.

Nánari gagnavillur og ákvarðanir eru í GAGNAVILLUR.md.

## Sýna önnur gögn án núverandi frávika

`main_data_test.py` sleppir h74, h124 og h147 sérstaklega; í nóvember einnig
h100. Þetta eru útilokanir heilla raða, ekki ágiskaðar leiðréttingar.
`data.py` útilokar enga starfsmenn sjálfgefið. Viðmótið er
`sleppa_starfsmonnum={"h74": "Óútkljáður vaktakóði"}`: hver útilokun þarf
þekkt auðkenni og ástæðu. Útilokanir eru skráðar í `gogn["utskildir"]`.
Nýjar villur hjá öðrum starfsmönnum eru enn greindar.

Raunkeyrsla fyrir nóvember með þessum fjórum útilokunum skilaði 134 virkum
starfsmönnum, 30 dögum, 2067.428571 markvöktum og 1500 mönnunarsætum.
Núllhlutföll eru líka síuð út samkvæmt venjulegri reglu. Allur gogn-dict
er í gogn-november-2026.txt, þar með talin hæfni, leyfdar vaktir,
mönnunarþörf, texti og prófunarforsendur. Þetta er gagnainnlestrarpróf,
ekki leyst eða staðfest vaktaplan.

```bash
python main_data_test.py
# Eða vista allt úttakið:
python main_data_test.py > gogn-ut.txt
```
