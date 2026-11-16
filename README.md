# Lawai · Del 2

En lokal Python-prototype som returnerer kildeutdrag i den rekkefølgen en
språkmodell bør få dem. Casens sju fiktive dokumenter ligger i `case.json`.
Prototypen krever Python 3.9 eller nyere og bruker standardbiblioteket.

## Kjør demoen

```sh
python3 lawai.py 'Hva er minstelønnen for en fagarbeider på sykkelverksted?'
python3 lawai.py 'Hva var minstelønnen for en fagarbeider på sykkelverksted i februar 2026?'
python3 lawai.py 'Hvordan har minstelønnen for fagarbeidere på sykkelverksted endret seg siden 2024?'
python3 lawai.py --conflict-demo
python3 -B -m unittest -v
```

De tre første kommandoene gir henholdsvis D3, D2 og D1 → D2 → D3.
Konfliktdemoen viser to udaterte håndbøker med ulike opplysninger.
Bruk `--curated` for å kjøre med håndregistrerte virkningsdatoer og
erstatningslenker. Standardmodus leser disse fra teksten.

## Grunnleggende og videre

1. Del dokumentene i utdrag med en ID for hver regel. D1 har separate utdrag
   for fagarbeidere, arbeidstakere uten fagbrev og overtid. D2 og D3 endrer
   bare fagarbeidersatsen.
2. Finn den aktuelle regelen ved hjelp av norske søkeord for bransje og emne.
   Hvis flere regler passer, ber CLI-resultatet om en presisering.
3. Les virkningsdato og erstatningsreferanse fra protokollen eller håndboka.
   For protokoller kontrolleres den oppgitte gamle satsen mot forrige versjon.
   Håndboka peker på den tidligere utgaven ved måned og år. En tvetydig lenke
   gir en usikkerhetsstatus når den påvirker den forespurte perioden.
4. Velg utdragene som overlapper perioden i spørsmålet. Vis kilde, dato og
   begrunnelse. En historikk vises fra eldste til nyeste.

Demodatoen er 11. november 2026 og kan endres med
`--reference-date YYYY-MM-DD`. Tidstolkningen dekker spørsmål uten
tidsuttrykk, «i februar 2026», «siden 2024» og en dato som «den 1. mai 2026».
Prototypen støtter ordlyden i casen og har håndregistrerte regel-ID-er og
verdier. Når avtalen eller håndboka mangler en eksplisitt virkningsdato, bruker
vi dokumentdatoen som antakelse og viser det i resultatet. Historiske svar
viser hva som gjaldt på datoen slik det fremgår av den tilgjengelige samlingen.
Derfor kan en protokoll fra juni dokumentere en sats med virkning fra mai.
Et «hva visste vi da?»-oppslag ville også krevd å filtrere på tilgjengelighetsdato.

## Bonus

Ved flere hundre tusen dokumenter ville vi indeksert utdrag for både
ordbasert søk og vektorsøk. Ordsøk fanger opp presise referanser som § 3 og
avtalenavn. Vektorsøk hjelper med omskrivinger. Begge søk begrenses til kilder
kunden kan lese, og treffene slås sammen på regel-ID. Et treff på D1 henter
dermed også endringskjeden med D2 og D3. Virkningsdatoene avgjør hvilke
utdrag modellen får. Oppdater de berørte tidslinjene ved innlesing av en ny
protokoll. Sammenlign treff på riktig regel, andel utdaterte kilder i
resultatet og svartid. Bruk vektorindeksen i eksisterende søkeinfrastruktur
hvis den er tilgjengelig, og vurder egen vektordatabase ut fra målingene.

D4 er en sekundærkilde og får ikke forrang over avtalen og protokollene.
Hvis to udaterte kilder med samme autoritet er uenige, vis begge og marker
konflikten. En verifisert erstatningslenke kan avklare hvilken kilde som er
etterfølger, men det kreves fortsatt en virkningsdato for å plassere den på
tidslinjen.

## Bruk av KI

Codex ble brukt til å utforme planen, skrive prototypen og testene og kjøre
verifiseringen. Selve prototypen bruker ingen språkmodell eller nettjeneste.
