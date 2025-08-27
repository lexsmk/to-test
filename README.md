# Testovací sada Barrel & Measurement API

Automatizovaná sada testů rozdělená do tří vrstev markerů: `behavior`, `contract`, `robustness`.

## Závislosti

Požadováno: Python >= 3.11

Instalace:
```bash
pip install -r requirements.txt
```

Použité knihovny: `pytest`, `requests`, `python-dotenv`, `jsonschema`, `hypothesis`.

## Proměnné prostředí

| Proměnná | Význam |
|----------|--------|
| BASE_URL | Základní URL API (např. https://api.example.com) |
| STRICT | 1 = tvrdé pády na drift (aktuálně není soft režim) |
| SHOW_HTTP | 1 = logování odpovědí (pokud je implementováno v klientovi) |
| RETRY | (rezervováno / momentálně neaktivní) |
| RETRY_BACKOFF | Základní backoff sekundy (rezervováno) |

## Struktura vrstev

- behavior: Základní pozitivní scénáře (flow vytvoření + čtení) 
- contract: Validace schémat, povinných/extra polí, tvaru seznamů dle OpenAPI
- robustness: Negativní / edge vstupy (neexistující ID, prázdné hodnoty)

## Hlavní soubory

| Soubor | Popis |
|--------|-------|
| `src/client.py` | Lehký HTTP klient + pomocné funkce |
| `tests/conftest.py` | Fixturny, snapshot hash OpenAPI, healthcheck |
| `tests/test_smoke.py` | Ručně psané behavior/contract/robustness testy |
| `tests/test_contract_auto.py` | Autogenerované list kontrakty z OpenAPI |
| `openapi.json` | OpenAPI specifikace |
| `openapi.snapshot` | Uložený hash specifikace pro detekci driftu |

## OpenAPI snapshot

První běh uloží hash do `tests/openapi.snapshot`. Změna specifikace → nový hash → při STRICT=1 test fail (zachytí neohlášený drift). 

## Autogenerované kontraktní testy

`test_contract_auto.py` prochází všechny GET list endpointy (bez `{id}`) a validuje první položku seznamu vůči definovanému schématu komponenty. Pokud je seznam prázdný, test se jednou pokusí seednout ukázková data a zkusí znovu.

## Property-based fuzz

Hypothesis generuje prázdné a whitespace varianty `qr` pro ověření odmítnutí nevalidních hodnot bez duplikace parametrizovaných případů.

## Spuštění

Rychlý běh všeho:
```bash
pytest -q
```
Filtrování podle markeru:
```bash
pytest -m behavior -q
pytest -m contract -q
pytest -m robustness -q
```

## Známé problémy backendu (aktuálně odhalené)

1. GET /barrels/{uuid} vrací 500 místo 404/400 pro neexistující ID.
2. DELETE /barrels/{id} někdy končí 500 (i během cleanup ve fixture).
3. Vytváření barrel akceptuje extra / chybějící pole (nedostatečná validace additionalProperties / required).
4. Prázdné nebo whitespace `qr` je přijato (mělo by být 4xx).
5. Možný drift u /measurements (tvar odpovědi neodpovídá očekávanému `Measurement`).

