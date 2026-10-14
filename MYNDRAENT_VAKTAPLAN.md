# Myndræn framsetning vaktaplans

`main.py` býr nú til heildarplan í Excel og mynd fyrir skýrsluna þegar fundin lausn hefur staðist óháðan checker. Þessi viðbót breytir ekki model.py eða markfallinu. Setjið upp viðbótina með `python -m pip install -r requirements.txt` (openpyxl 3.1.5).

Til að teikna vistaða lausn án nýrrar Gurobi-keyrslu:

```sh
python greining.py results/<valin-keyrsla>
```

Eða vistið myndirnar sérstaklega:

```sh
python greining.py results/<valin-keyrsla> --ut myndir
```

Gögn verða að hafa sama fingrafar og í run.json og lausnin verður að standast checkerinn. Ekki breyta assignments.csv til að snyrta myndina.

## Úttak

- `vaktaplan.xlsx`: allir virkir starfsmenn og allir dagar, vakt og hlutverk í reit. MV er blá, KV appelsínugul og NV fjólublá. Fríreitir eru hvítir og auðir. NV tilheyrir upphafsdegi. Helgar eru auðkenndar í dagsetningarhaus. Haus og starfsmannadálkur eru festir fyrir skrun.
- `vaktaplan_synishorn.png`: 300 dpi mynd með allt að 15 starfsmönnum og öllum 30 dögunum. Hún sýnir vaktategundir; hlutverk eru í Excel.
- `vaktaplan_mynd.json`: uppruni, SHA-256 af assignments.csv, sýnd auðkenni og valregla.
- `vaktaplan_myndatexti.txt`: myndatexti fyrir skýrsluna.

Valregla: fyrstu fimm eftir tölulegu auðkenni úr MV/KV/NV, MV/KV og MV-eingöngu. Ef hópur hefur færri en fimm eru laus sæti fyllt eftir auðkenni úr öðrum hópum. Birting er flokkuð eftir vaktamynstri. Val ræðst ekki af gæðum úthlutana.

## Fyrirliggjandi mynd og lausn

Viðbótin var prófuð á varðveittri lausn úr keyrslunni `einfalt_november_20261012_141028_ce7775`: markfall 2093,43, gap 3,25%, 2102 úthlutanir og 137 starfsmenn. Sú mappa var ekki lengur í repo-inu; yfirfarið afrit var til í Codex-vinnumöppunni. Fullt gagnasamræmi og checker voru staðfest áður en myndir voru búnar til. Myndirnar eru í Codex-úttaksmöppunni `outputs/vaktaplan_20261014` og fylgja þessari afhendingu.

Útsniðið sýnir átta MV/KV/NV, fimm MV/KV og tvo MV-eingöngu starfsmenn, því aðeins tveir virkir starfsmenn eru í síðasta hópnum. Það er útsnið, ekki mynd af öllum 137.

Ekki nota tölur úr þessari lausn með mynd úr nýrri keyrslu. Keyrslan frá 13. október hefur annað markfall og gap þótt heildarúthlutanir séu líka 2102.

## Setja í Overleaf

Flytjið PNG-myndina inn í sama Overleaf-verkefni og skýrsluna og notið t.d.:

```latex
% Í formála:
\usepackage{graphicx}

% Í niðurstöðukafla:
\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{vaktaplan_synishorn.png}
\caption{Útsnið úr bestu fundnu lausn valinnar keyrslu fyrir nóvember 2026.
Sýndir eru 15 af 137 starfsmönnum, valdir eftir leyfðum vaktategundum
og auðkenni. Litir tákna MV, KV og NV; hvítir reitir tákna frí.
Heildarvaktaplan með hlutverkum fylgir í Excel-skjali.}
\label{fig:vaktaplan}
\end{figure}
```

Athugið læsileika við raunverulega prentstærð og heildarlengd skýrslunnar. Excel-planið er viðbót við myndina, ekki staðgengill hennar í skýrslunni.

## Prófanir

Sjö ný próf í tests/test_vaktaplan.py athuga auðkennisröð, fólk án úthlutana, tvíteknar og óþekktar úthlutanir, val útsniðs, Excel-dagsetningar/liti/hlutverk og höfnun við röng gögn eða fallinn checker.

Allar 70 prófanir stóðust með raunverulegum gagnaprófum:

```sh
HR_GAGNAMAPPA="$PWD" python -m unittest discover -s tests -t . -v
```

`-t .` forðast núverandi nafnárekstur við tvíteknu test_model_pipeline.py í rót. Sú eldri prófaskipulagsbreyting var ekki hluti þessarar vaktamyndarviðbótar.
