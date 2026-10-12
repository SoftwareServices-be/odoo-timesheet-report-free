# TimeViking Time Report (Odoo 18, 19, 20)

Gratis Odoo-module (LGPL-3, Odoo Apps Store) van Software Services BV, onder de TimeViking-vlag: een urenrapport per
medewerker voor een periode, als PDF (QWeb, `web.external_layout`, de huisstijl van het bedrijf) en als Excel
(`xlsxwriter`, dat Odoo zelf meelevert). Alleen `hr_timesheet` nodig, werkt op Community.

Vergelijkbaar met de betaalde "HR Employee Timesheet Excel and PDF Report" van Browseinfo (`bi_employee_timesheet_report`,
OPL-1); geen code overgenomen. Wat deze module beter doet: tijd als h:mm, totaal over alle medewerkers, Excel met echte
datums en duurtijden die optellen, vertaald (nl, fr, de, es, it), rechten (eigen uren voor gewone gebruikers),
multi-company. De uitgebreide, betaalde versie is **Timesheet PDF Report Pro** (aparte privé-repo
`SoftwareServices-be/odoo-timesheet-pdf-report`; geen code gedeeld, geen afhankelijkheid).

## Functies

- Wizard onder Urenstaten › Rapportage › "TimeViking Time Report" (en Afdrukken op een werknemer): startdatum,
  einddatum (standaard vorige maand), medewerkers (leeg = alle), bedrijf.
- **Print PDF**: per medewerker datum, project, taak, omschrijving, tijd; totaal per medewerker en over alle.
- **Export Excel**: één blad, per medewerker een blok, datums als datum en tijd als `[h]:mm`.
- "Powered by TimeViking"-regeltje onder PDF en Excel; uit te zetten in Instellingen › Urenstaten.
- Gewone gebruiker: alleen eigen uren; goedkeurder/beheerder: alle.

## Bouwen en testen

```bash
python3 tools/build.py check --no-branches
python3 -m pytest -q
tools/odoo_test.sh 18          # (19, 20) installeren in databank odoo_tvrep_<v>0 en de Odoo-tests draaien
```

`tools/odoo_test.sh` gebruikt de test-Odoo's van het hoofdproject (`../softwareservices-odoo-timesheets/var/odoo`,
`<v>.0/tvreport.conf`), onder `flock var/odoo/.lock`. `tools/build.py` maakt van de bron (Odoo 18) de versies 19 en 20
(`groups_id` → `group_ids`, `ir.access.csv`, `get_param` → `get_str`).

## Testresultaten (12-10-2026)

Echte Odoo Community 18.0, 19.0 en 20.0, databank `odoo_tvrep_<v>0`: 7 tests groen per versie (gegevens en totalen,
eigen uren voor gewone gebruikers, HTML-render, instelling "Powered by" uit, Excel-inhoud, controles, menu, download via
de route met HttpCase en 404 voor andermans wizard).

Screenshots: `tools/seed_demo.py` (demodata) en `tools/screenshots.mjs` (zie de paid repo voor dezelfde werkwijze);
`tools/xlsx_preview.py` toont het echte Excel-bestand als rooster voor de store-afbeelding.

## Uitbrengen en publiceren

1. `MODULE_VERSION` in `product.json` ophogen, committen op `main`.
2. `tools/build.py release` (git-identiteit in de omgeving), dan `git push origin main 18.0 19.0 20.0`.
3. Deze repo is **publiek**: op https://apps.odoo.com/apps/upload per versie de URL registreren, bv.
   `https://github.com/SoftwareServices-be/odoo-timesheet-report-free.git#18.0` (en `#19.0`, `#20.0`). Geen
   leesrechten nodig. De store scant de branch en publiceert de module gratis (geen `price` in het manifest).
