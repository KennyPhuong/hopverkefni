# Tenging data.py, model.py og main.py

Flæðið er: CSV → undirbua_gogn → gogn → byggja_model → model.optimize → CSV/JSON.
Líkanið í model.py er afrit af kóðanum sem var sendur 7. október. Skorðum og
markfalli var ekki breytt við tenginguna. main.py inniheldur ekki annað MIP.

## Setja upp og keyra

Taktu afrit af eldri main.py áður en samþættingarpakkinn er afþjappaður í
verkefnismöppuna. Upprunalegu CSV-skrárnar þurfa að vera við hlið main.py.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python main.py --ar 2026 --manudur 11 --timamork 60 --gap 0.05
```

Til að virkja einnig raunverulegu gagnaprófin:

```bash
HR_GAGNAMAPPA="$PWD" python -m unittest discover -s tests -v
```

Prófa frá annarri vinnumöppu með algildri slóð á main.py. Sjálfgefnar
slóðir miðast við staðsetningu skrárinnar, ekki núverandi vinnumöppu.
`--gagnamappa` og `--nidurstodumappa` geta breytt slóðunum.
`--vaktir-100` gefur fullt mánaðarvaktamark. Ef það vantar notar forritið
sýnilega prófunarforsendu dagar/7*5; hún er ekki staðfest vinnuskylduregla.

## Forsendur í þessari prófun

Frádráttur án NM, jafnlangar vaktir, sama mönnunarþörf alla daga,
mánaðarprósentur ráða hlutfalli og neikvætt virkt hlutfall verður 0.
Óútkljáðu starfsmennirnir h74, h124 og h147 eru útilokaðir; í nóvember
líka h100. Þetta er skráð í niðurstöðum. Nýjar villur hjá öðru starfsfólki
eru ekki hunsaðar. Engin fyrri vaktasaga eða óskagögn eru send í líkanið.
Samnings-/athugasemdatexti er ekki sjálfkrafa gerður að skorðum.
Markvaktir eru ónámundaðar; prentun má námunda án breytingar á líkaninu.

## Niðurstöður

Hver keyrsla fær eigin möppu undir results svo eldri niðurstöður haldist.

| Skrá | Innihald |
|---|---|
| assignments.csv | nurse_id,date,shift,role; ISO-dagsetning; NV tilheyrir upphafsdegi |
| coverage.csv | date,shift,role,required,assigned,missing; skortur talinn úr úthlutunum |
| workload.csv | nurse_id,target,assigned,deviation; frávik = assigned - target |
| progress.csv | elapsed_seconds,incumbent,best_bound,gap; eyður áður en gildi eru tiltæk |
| run.json | Solver-staða, lausnafjöldi, gap, forsendur, útilokanir, stillingar og SHA256 |
| solver.log | Gurobi-keyrsluskrá |

Engin assignments.csv er skrifuð þegar enginn incumbent finnst.
Exit-kóðar: 0 = lausn með fullri mönnun, 1 = inntaks-/keyrsluvilla,
2 = enginn incumbent, 3 = lausn með mönnunarskorti.
Exit 0 staðfestir ekki allar reglur; óháður lausnarchecker er enn nauðsynlegur.
Ekki er skrifað check.json sem gefur í skyn að slíkur checker hafi verið keyrður.

## Keyrt 7. október 2026

37 próf stóðust: 29 tilbúin gagnapróf, 5 raunveruleg CSV-próf og 3
samþættingarpróf fyrir smátt MIP og lausnarútflutning. Þau prófa meðal annars
að mönnunarskortur sé sýndur og að engin gervilausn sé vistuð við infeasibility.

Raunveruleg nóvemberkeyrsla: Gurobi 13.0.3, akademískt leyfi,
TimeLimit=30, MIPGap=0.05, Threads=2, Seed=0. Líkanið hafði 82354 breytur
og 31888 skorður. 134 virkir starfsmenn, 30 dagar og 1500 mönnunarsæti.
Lausnin hafði 2019 úthlutaðar vaktir og 32 ómönnuð sæti, öll á MV 14.–15.
nóvember. Tími 22.41 sekúndur og gap 1.9833%.

Status OPTIMAL hér þýðir að gefnu 5% gap-viðmiði var náð; það staðfestir
hvorki nákvæmt optimum né að mönnun sé fullnægjandi. Þetta er raunveruleg
samþættingarkeyrsla, ekki staðfest lokavaktaplan.

## Áður en þetta verður skilaverkefni

1. Gerið mönnun harða og þriðju-hverrar-helgar viðmiðið mjúkt. Með 134
   starfsmönnum í þremur hörðum helgarhópum getur minnsti hópur haft mest
   44 starfsmenn, en dagleg þörf er 50. Nóvember inniheldur allar þrjár
   helgarfasana. Núverandi uppsetning getur því ekki fullmannað allar helgar.
2. Fáið staðfestar vaktalengdir/hvíld og vinnuskylduforsendur; núverandi
   banna_kv_mv-flagg staðfestir ekki eitt og sér 11 klst. hvíld.
3. Bætið við óháðum lausnarchecker sem les assignments.csv og gögnin.
   Prófin hér eru samþættingarpróf, ekki sá checker.
4. Setjið inn raunverulegar óskir og takmarkanir sem eru nú aðeins í texta.
   Líkanið notar enga óskarefsingu þegar oskir vantar.
5. Yfirfarið mánaðarmörk. Óþekktar fyrri vaktir teljast frí í líkaninu og
   endi mánaðar hefur enga framhaldsáætlun. Hvíld yfir mörkin er því óstaðfest.
6. Búið til myndrit og skýrslu úr yfirförnum niðurstöðum. progress.csv er
   hrátt efni fyrir framvindurit, ekki tilbúið myndrit.
