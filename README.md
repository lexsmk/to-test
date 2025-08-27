# Testovaci sada Barrel a Measurement API

## Requirements

Python verze 3.11 nebo novejsi

### Instalace zavislosti
```
pip install -r requirements.txt
```
Pouzite knihovny: `pytest requests python dotenv jsonschema hypothesis`

## Promenne prostredi

- BASE_URL adresa API vychozi je https://to-barrel-monitor.azurewebsites.net
- OPENAPI_URL url vzdalenou specifikaci pouzivaji testy a snapshot
- STRICT hodnota 1 true yes on zapne tvrde selhani pri driftu a extra polich jinak se nektere odchylky oznaci jako xfail
- SHOW_HTTP hodnota 1 zapne vypis http volani
- RETRY ignorovano aktualne neni implementace
- RETRY_BACKOFF ignorovano neni v kodu

## Markery testu

- **behavior:** pozitivni tok vytvoreni precteni smazani
- **contract:** kontrola tvaru seznamu podle OpenAPI a klice detailu Measurement plus detekce driftu specifikace
- **robustness:** negativni scenare chybna data neexistujici identifikatory prazdne retezce

## OpenAPI snapshot

Prvni beh vypocte hash a ulozi do tests/openapi.snapshot dalsi behy porovnaji hash se vzdalenym JSON pri zmene a STRICT aktivni test selze jinak xfail drift

## Generovane testy

Test seznamu najde GET endpointy bez parametru kdyz vrati prazdny seznam jednou osadi minimalni data a zkusi znovu validuje prvni polozku proti schematu
Negativni testy vytvori validni barrely a mereni pak generuji mutace odebrani povinneho pole nebo nastaveni prazdneho a whitespace retezce
Hypothesis generuje prazdne a whitespace hodnoty pro qr

## Omezeni a todo

- Detail Barrel neni kontrolovan proti schematu jen id
- Detail Measurement validace klicu je rucni a zavisla na konstantach
- Measurements se nemaze data mohou rust
- Specifikace se stahuje pri importu dvou test souboru coz prodluzuje start
- Retry promenne nejsou implementovane

## Spusteni
```
pytest -q
```
### Filtrovani markeru priklad jen contract
```
pytest -m contract -q
```

## Zname problemy backendu pozorovano

- GET /barrels/{id} muze vratit 500 pro neexistujici id ocekavane je 404 nebo 400
- DELETE /barrels/{id} muze vratit 500 klient oznaci jako xfail kdyz STRICT vypnut
- Server prijima extra pole nebo prazdne retezce u Barrel a nekdy u Measurement
- Prazdne nebo whitespace qr muze byt prijato
- Obcas 500 pri detail odpovedi measurement nebo barrel pri STRICT vypnut prevede se na xfail

