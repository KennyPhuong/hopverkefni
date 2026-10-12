# Uppfærsla mönnunar 12. október 2026

Heimild: skýringar BMT sem kennari miðlaði og notandi birti í verkefnisspjallinu. Nákvæmur dagur kennarasvarsins fylgdi ekki textanum.

| Hlutverk | MV | KV | NV |
|---|---:|---:|---:|
| V | 1 | 1 | 1 |
| T | 2 | 2 | 1 |
| H | 1 | 1 | 0 |
| A1 | 3 | 3 | 3 |
| A | 2 | 2 | 1 |
| B1 | 1 | 1 | 0 |
| B | 3 | 3 | 3 |
| C | 2 | 2 | 2 |
| D1 | 1 | 1 | 0 |
| D | 2 | 3 | 0 |
| DB | 0 | 0 | 1 |
| Samtals | 18 | 19 | 12 |

B var 4/4/3, D var 1/1/1 og Dg var 1/1/0. Dg er nú DB. T=2/2/1 og C=2/2/2 eru áfram bráðabirgðaforsendur úr eldri töflunni því nýja svarið fulltilgreindi ekki þessa fjölda. BÖR og NM eru áfram utan líkansins.

Ný CSV geymir hvert sæti sem endurtekið hlutverkaheiti. Tómir reitir tákna engin sæti. Ný heildarþörf er 49 á dag og 1470 í nóvember.

Í data.py er hrái hæfnidálkurinn dg varpaður á DB samkvæmt leiðréttingu heitisins. Sömu 0/1-gildi eru notuð; B eða D hæfni ein og sér veitir ekki DB hæfni. Starfsmanna-CSV er óbreytt. Eldra Dg-heiti er líka samþykkt sem inntaksheiti í mönnunartöflu og skilar DB. Sú samhæfni uppfærir ekki sjálfkrafa gamlar mönnunartölur: setja verður nýju CSV-skrána inn líka.

## Setja uppfærsluna í GitHub-möppuna

Pakkinn inniheldur HR-gognin(Sheet2).csv, data.py, tests/test_data.py og þessa skýringu. Hann inniheldur ekki nýja útgáfu af model.py; breyturnar og mönnunarskorðurnar byggjast þegar á gogn-dict.

Taktu afrit af þeim þremur skrám áður en þú afþjappar pakkanum í verkefnismöppuna. Skiptu út mönnunar-CSV á staðnum sem main.py les, sjálfgefið í sömu möppu og main.py. Ef þú notar aðra gagnamöppu þarf líka að uppfæra þá CSV-skrá.

Keyrðu síðan úr verkefnismöppunni:

```sh
HR_GAGNAMAPPA="$PWD" python -m unittest discover -s tests -v
python main.py
```

Öll 63 prófin stóðust með raunverulegu starfsmanna-CSV og nýju mönnunar-CSV. Starfsmenn fyrir síun voru 170; virkir í einfaldaða nóvemberlíkaninu voru 137. Prófin staðfesta nákvæma B/D/DB-talningu, T/C-forsendur, hæfnivörpun og 1470 sæti.

Eldri vaktaplön og næmnigreining notuðu 1500 sæti og gilda ekki sem niðurstöður fyrir nýju mönnunina. Keyrið python naemni.py aftur áður en þær niðurstöður eru notaðar í skýrslunni. Óstaðfestar vinnuskylduforsendur og óþekkt mánaðarmörk eru áfram óútkljáð.

## Full nóvemberkeyrsla eftir uppfærslu

Líkanið var keyrt með nýju gögnunum og 60 sekúndna tímamörkum. Það fann 2103 úthlutanir, engin ómönnuð sæti og stóðst óháða yfirferð innan mánaðar. Staða var TIME_LIMIT og gap 28,83%; þetta er gild lausn samkvæmt innleiddum reglum en ekki sönnuð besta lausn. Mánaðarmörk án sögulegra gagna eru ekki staðfest. Niðurstöður eru í outputs/results/monnun_uppfaerd_20261012 í vinnumöppu Codex.
