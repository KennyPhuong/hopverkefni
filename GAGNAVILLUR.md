# Yfirferð CSV-gagna

Núverandi innlestur: HR-gognin(Hjúkkur).csv og HR-gognin(Sheet2).csv,
yfirfarið 7. október 2026. Aðeins CSV-skrárnar eru lesnar af data.py.
CSV-prósentur eru námundaðar; þær eru notaðar án endurheimtar Excel-gilda.

## Staðfest ósamræmi eða óútkljáð snið

| Atriði | Staðsetning | Meðhöndlun |
|---|---|---|
| Hæfnifáni 11 í stað 0/1 | h147, a | ValueError; ekki sjálfkrafa breytt í 1 |
| Óþekktur vaktakóði 12-20-KV | h74 | ValueError þegar virkur; staðfesta hvort sérstök vakt sé nauðsynleg |
| Óþekktur vaktakóði MV-KV-4 | h124 | ValueError þegar virkur; staðfesta hvað 4 þýðir |
| BN í stað NM | Ágúst, fjórði dálkur mánaðarblokkar | Staðfest vörpun þarf bn_sem_nm=True; hún er skráð |
| Neikvætt virkt hlutfall | Tafla fyrir neðan | Sjálfgefið villa; neikvaett_i_null=True setur í núll með viðvörun og skráningu |
| Frjáls texti samhliða tölulegum prósentum | Vinnufyrirkomulag/Athugasemdir | Varðveittur; skýr textastefna þarf til að forgangsraða mánaðarprósentum |

Eftirfarandi neikvæð hlutföll koma fram með frádráttarreglu sem var áður notuð við samanburð við Excel:
frádráttur Verkefni, BÖR, Námsleyfi, Stjórnun, Fæðing, Leyfi og Veikindi,
en ekki NM. Þetta er samanburðarregla í yfirferð, ekki samþykkt sjálfgefið.

| Mánuður | Starfsmaður | Reiknað virkt hlutfall |
|---|---|---:|
| Febrúar | h78 | -1.0000 |
| Febrúar | h88 | -0.1000 |
| Mars | h87 | -0.8000 |
| Nóvember | h100 | -0.1000 |

Valin einföldun getur sett þessi reiknuðu gildi í núll með
`neikvaett_i_null=True`. Gamla gildið, mánuður, starfsmaður og ástæða eru
skráð. Það breytir ekki upprunalega CSV-skránum eða staðfestir túlkunina.
Starfsmennirnir verða þá ekki tiltækir fyrir vaktavinnu þann mánuð.

## Jákvætt hlutfall án klínískrar hæfni

Þessi tilvik komu fram í þeim mánuðum þar sem frádráttarútreikningurinn
hafði ekki þegar stöðvast á neikvæðum hlutföllum. Þau kunna að endurspegla
núverandi hæfnisfána í töflu með eldri starfshlutföllum; ekki álykta hæfni.

| Mánuður | Auðkenni án hlutverks |
|---|---|
| Janúar | h4, h5, h35, h40, h50, h66, h71, h87, h91, h139, h166 |
| Apríl | h5, h50, h66, h71, h91, h139, h166 |
| Maí | h5, h50, h58, h71, h91, h139 |
| Júní | h5, h50, h71, h139 |
| Júlí | h5, h50, h71 |
| Ágúst | h5, h50, h71 |
| September | h5, h71 |
| Október og desember | Enginn án allra hlutverka; h147 hefur þó ógildan a-fána |

Febrúar, mars og nóvember þarf að enduryfirfara eftir staðfestingu neikvæðu
hlutfallanna. Ströng keyrsla sýnir fyrst villu sem kemur í veg fyrir áframhald;
allur villulistinn er ekki endilega í einu villuboði.

## Ákvarðanir sem enn vantar

1. Hvort NM er vaktavinna eða frádráttarliður, og hvort BN merkir sama hlut.
2. Rétta merkingu h74/h124-vaktakóðanna og h147-hæfnifánans.
3. Fulla mánaðarvinnuskyldu og hvort allar vaktir eru jafnlangar.
4. Samþykkta námundunarreglu fyrir hörð vinnuskyldumörk.
5. Forgang mánaðarprósenta gagnvart frjálsum texta og dagsettum breytingum.
6. Árið sem mánaðarprósenturnar eiga við. Almanak styður hvaða gilt ár sem
   er; það breytir ekki gögnunum í ný gögn fyrir annað ár.
7. Hvort sama mönnunarþörf eigi við alla daga, einnig helgar og hátíðir.

Sérstaklega þarf að yfirfara:

- h46: texti um leyfi frá 16. október, en allur október settur í Fæðing.
- h135: leyfi frá 25. október, með mánaðarlegri verkefna-/leyfisúthlutun.
- h141: texti um fulla vinnu í tvo mánuði, en októberhlutfall 0.8.
- h149: óskýra dagsetningin 3010.26 og allur október í Fæðing.
- h7 og h82: athugasemdir um orlof sem þarf að yfirfara.
- h16, h78, h79, h99, h108, h113 og h155: texti um verkefni, viðburði,
  aðrar skyldur og vaktatakmarkanir. Hann er ekki enn dagsett ófáanleiki.
- h37, h62 og h83: texti um fastar helgar, mánudagsnætur eða helgamynstur.
- NV-prósentur í samningslýsingum: staðfesta hvort um hlutfall vakta,
  vinnustunda eða starfshlutfalls er að ræða áður en þær fara í líkanið.

## Atriði sem innlesturinn meðhöndlar

- Samantektarraðir 173, 175 og 177–182 og munaðarlaus texti í röð 192
  verða ekki starfsmenn.
- Endurtekin mánaðarheiti undirflokka fá ótvíræða dálka; hráir hausar
  fylgja með til staðfestingar á hverri mánaðarblokk.
- Bil í MV - KV eru samræmd; kóðinn verður MV-KV.
- CSV-gildi, þar með talið námundun þeirra, eru notuð sem innlestrarheimild.
- Skill-bör og mánaðar-BÖR eru aðgreind. Bör er ekki demand-hlutverk.

Þetta er gagnayfirferð. Hún sannar hvorki heildarleysanleika MIP-líkans
né að frjáls texti eða allar samningskröfur hafi verið útfærðar sem skorður.

## Núverandi prófun með útilokunum

Að beiðni notanda sleppir main_data_test.py h74, h124 og h147, og h100
í nóvember. Ástæður eru skráðar í gogn["utskildir"]. Með þessum útilokunum
var full gogn-orðabók búin til úr raunverulegu CSV-gögnunum fyrir nóvember:
134 virkir starfsmenn og 1500 mönnunarsæti. Villurnar hér fyrir ofan eru
enn óútkljáðar; útilokunin staðfestir ekki ný gildi þeirra.
