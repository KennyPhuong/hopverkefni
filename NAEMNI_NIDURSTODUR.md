# Næmnigreining á helgarvigt — nóvember 2026

Keyrt 8. október 2026 á raunverulegum CSV-gögnum. Sama gagnainnlestrinum
var haldið í minni fyrir allar keyrslurnar; fingrafar gagnanna var borið saman.
137 virkir starfsmenn, 30 dagar og 1500 nauðsynleg mönnunarsæti.
TimeLimit=60, MIPGap=0.05, Threads=2, Seed=0; engin warm start.
Eingöngu helgarvigtin breyttist. Mönnun og aðrar harðar reglur voru óbreyttar.

| Helgarvigt | Undir marki | Yfir marki | Heildarfrávik | Umframúthlutanir | Aukahelgardagar | Gap |
|---:|---:|---:|---:|---:|---:|---:|
| 25 | 37.29 | 7.86 | 45.14 | 598 | 42 | 21.62% |
| 50 | 39.29 | 7.86 | 47.14 | 596 | 42 | 27.53% |
| 100 | 43.00 | 8.57 | 51.57 | 593 | 38 | 26.75% |

Allar þrjár keyrslur fundu incumbent og stöðvuðust á tímamörkum.
Allar höfðu 0 ómönnuð sæti og stóðust óháða yfirferð útfærðra reglna innan
mánaðarins. Það staðfestir ekki óþekkta mánaðarsögu, textatakmarkanir,
vaktalengdir eða vinnuhlutfallsforsendur.

Í fundnu lausnunum fékk vigt 100 færri aukahelgardaga en 50 (38 í stað 42),
en meira vinnuskyldufrávik (51.57 í stað 47.14). Vigt 25 fékk sama fjölda
aukahelgardaga og 50, minna vinnuskyldufrávik og meiri umframmönnun.
Þetta eru mældar niðurstöður bestu fundnu lausna, ekki sönnun á því hvaða
vigt er best eða að munurinn stafi eingöngu af vigtinni. Ólokin lausnarleit
getur haft áhrif á samanburðinn. Grunnvigt 50 er áfram óbreytt.

Vaktir undir og yfir marki eru mældar í vaktareiningum, ekki staðfestri
launalegri yfirvinnu eða vanvinnu. Heildarfrávik er summa algildra frávika.
Aukahelgardagur er raunvinna utan valins viðmiðunarhóps: lau/sun eða KV/NV
á föstudegi. Föstudags-MV telst ekki. Mælingin er endurreiknuð úr CSV,
ekki tekin beint úr hjálparbreytum solver.

Næturhópar í night_groups.csv bera saman sömu leyfðu vaktategundir og sama
mark (hópalykill námundaður að sex aukastöfum). Einstaklingshópur með
range_NV=0 er ekki sönnun á sanngirni. Hæfnimunur, óstaðfestar NV-prósentur
og aðrar aðstæður geta einnig skipt máli. Mælingar á V/T eru hlutfall allra
úthlutaðra vakta viðkomandi; engin hlutverkarotation-skorða bættist við.

Aðgreining vinnuframlags, næturvakta og verkefnadreifingar er innblásin af
Hildi Jóhannsdóttur (2026), Bestun vaktauppbyggingar fyrir tiltekinn
íbúðakjarna, köflum 4.4, 4.6 og 5. Nýtt líkan eða tölugildi úr ritgerðinni
voru ekki afrituð. Hér er áfram eitt mánaðarlegt líkan með vigtuðu markfalli.
