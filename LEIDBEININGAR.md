# Einfalt nóvemberverkefni

Keyrslan er nú eingöngu fyrir nóvember 2026. Engin mánaðarvalmynd eða
argparse-viðmót er í main.py. Gögn eru áfram lesin eingöngu úr CSV:
HR-gognin(Hjúkkur).csv og HR-gognin(Sheet2).csv við hlið kóðans.
Upprunalegu CSV-skrárnar eru óbreyttar.

## Fjórar aðalskrár

- data.py: lesa_novembergogn(gagnamappa) setur verkefnisforsendur og
  staðfestar leiðréttingar á einn stað. Prófuð hreinsunarföll eru varðveitt.
- model.py: byggja_model(gogn) býr til líkanið; leysir það ekki.
- check_solution.py: les assignments.csv og athugar hörðu reglurnar án
  þess að flytja inn model.py eða gurobipy.
- main.py: les gögn, byggir/leysir, vistar og keyrir checker.

main_data_test.py sýnir sömu gogn-orðabók án þess að leysa MIP.

## Keyrsla

```bash
python -m pip install -r requirements.txt
HR_GAGNAMAPPA="$PWD" python -m unittest discover -s tests -v
python main.py
```

Slóðir eru reiknaðar út frá staðsetningu skránna, óháð vinnumöppu.
main.py tekur ekki lengur --manudur, --ar eða --timamork. TimeLimit=60 og
MIPGap=0.05 eru fastar stillingar efst í main.py. Engin föst starfsmannanöfn
eru í skorðum líkansins. Dagsetningar/breytur eru áfram byggðar með lykkjum.
Breyting á mánuði er ekki skilaviðmót verkefnisins.

## Staðfestar gagnabreytingar

Kennarinn heimilar h74 aðeins KV, að hunsa 4 í h124 og staðfestir h147/a=1.
Nýjasta svarið segir h100 í orlofi til 30.11; hún er útilokuð í nóvember.
Kennarinn samþykkir að neikvætt reiknað virkt hlutfall tákni enga tiltækni.
BÖR og NM eru ekki notuð í útreikningi, ekki dregin frá og ekki túlkuð sem
hlutverk. Ónotuð prósentugildi eru ekki töluhreinsuð.
Leiðréttingar/útilokanir eru skráðar í gogn og run.json, ekki framkvæmdar
á upprunalegu skránum.

## Óstaðfestar forsendur

Frádráttur verkefni, námsleyfi, stjórnun, fæðing, leyfi og veikindi er
varðveittur sem bráðabirgðaforsenda. Staðfesta þarf hvort hlutfall undir
mánaðarheitinu sé þegar nettó vaktavinnuhlutfall. Ef svo er væri þessi
frádráttur tvítalning. Þetta er nú merkt vinnuhlutfall_stadfest=False.
Fullt vaktamark er 30/7*5, ónámundað. Jafnlangar vaktir og sama daglega
þörf eru einföldunarforsendur. Gagnaárið er valið 2026, ekki staðfest af
CSV-hausum. Vaktatímar, lög og dagsettar textatakmarkanir eru ekki fulltúlkuð.
Óþekkt fyrri saga telst frí og engin framhaldsáætlun er gefin.

## Hörðu reglurnar

- Lágmarksmönnun í hverju hlutverki á hverri vakt; engin undirmönnunarbreyta.
- Aðeins leyfðar vaktir og hæfni; mest ein vakt á dag.
- Banna NV->MV, NV->KV og KV->MV á samliggjandi upphafsdögum.
- Mest fjórar NV og sex vinnudagar í röð.
- Eftir næturblokk með >=2 NV: svefndagur og engin MV næsta dag.
- Ef laugardagur og sunnudagur eru frí: engin föstudags-KV/NV, þegar öll
  þriggja daga helgin er innan mánaðarins.

## Þrjú mjúk markmið

| Liður | Vigt |
|---|---:|
| Vinnuskyldufrávik, undir og yfir marki | 10 |
| Umframmönnun | 1 |
| Vinna utan viðmiðunarhelgarhóps | 50 |

Líkanið velur einn viðmiðunarhóp af þremur fyrir hvern starfsmann.
Laugardags-/sunnudagsvinna og föstudags-KV/NV utan hóps kosta 50 á dag.
Föstudags-MV kostar ekki aukahelgardag. Það er ekkert hart hámark á slíkum
frávikum. Vigtin 50 er varðveitt úr síðustu repo-útgáfu, ekki krafa kennara.

Fjarlægt: mjúk mönnun, val um tvöfaldar vaktir, vikulegar fráviksbreytur,
sjálfvirk NV-prósentutúlkun, óskakostnaður, jöfn vaktategundaskipting,
50% hlutverkaviðmið, stakur-helgardagur refsing og 3-daga aukahelgarhámark.
Vaktategundadreifing er mæld í check.json en ekki bestað eftir henni.
Hlutverkaskipting og vaktategundadreifing þarf að meta áður en lokalausn
verður valin; einföldunin er grunnlíkan, ekki staðfesting að þær séu góðar.

## Niðurstöðuskrár

Hver keyrsla fær eigin möppu undir results/einfalt_november_<tími>_<id>/.

| Skrá | Innihald |
|---|---|
| assignments.csv | nurse_id,date,shift,role; ISO-dagsetningar |
| coverage.csv | date,shift,role,required,assigned,missing |
| workload.csv | nurse_id,target,assigned,deviation |
| progress.csv | elapsed_seconds,incumbent,best_bound,gap |
| check.json | Pass/fail innan mánaðar, villur, mönnun og vinnuframlag |
| run.json | Solver-staða, gap, forsendur, leiðréttingar og markfallssundurliðun |
| solver.log | Gurobi-framvinda |
| infeasible.ilp | IIS ef líkanið er staðfest óleysanlegt |

Engin lausn er vistuð ef enginn incumbent fannst. Exit 0 þýðir lausn sem
stenst útfærðar reglur innan mánaðar; 1 keyrsluvilla, 2 enginn incumbent,
3 lausn sem fellur á checker. Exit 0 þýðir ekki staðfesta heildarfylgni við
lög, texta eða mánaðarmörk. boundaries_verified er áfram False.

## Prófun 8. október 2026

49 próf: 30 tilbúin gagnapróf, 6 raunveruleg CSV-próf, 5 smá líkanapróf
og 8 checker-próf. Án HR_GAGNAMAPPA er raunprófunum sex sleppt.

Raunkeyrsla á akademísku Gurobi 13.0.3: 137 virkir starfsmenn, 99.28
reiknuð stöðugildi, 2127.428571 markvaktir og 1500 mönnunarsæti.
78126 breytur og 32333 skorður. Við 60.02 sekúndur fannst lausn með
2096 úthlutunum og 0 ómönnuðum sætum. Checker stóðst fyrir sitt umfang.
Status TIME_LIMIT, gap 27.53%; besta mögulega markfallsgildið er óstaðfest.
Umframmönnun 596 og heildarvinnuskyldufrávik 47.142857 vaktareiningar.
Kostnaður: vinnuskylda um 471.43, umframmönnun 596, aukahelgar 2100;
heild um 3167.43. Þetta er ekki sambærilegt við gamla markfallið með
undirmönnunarrefsingu, því gögn og markfall hafa bæði breyst.

C ætti að yfirfara checkerinn og sýnishorn raunlausnarinnar sjálfstætt.
Myndrit, næmnigreining og lokaskýrsla eru ekki búin til í þessari vinnu.

Gamla skordur_model.tex og eldri ZIP-pakkar lýsa eldri líkönum og eru ekki
hluti nýja pakkans. Ekki nota gamla jöfnuskjalið sem lýsingu á þessari útgáfu.
