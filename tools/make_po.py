#!/usr/bin/env python3
"""Write src/<module>/i18n/<lang>.po from the .pot (exported by Odoo) and the table i18n_src/translations.tsv.

  tools/make_po.py            all modules of product.json, languages nl fr de es it

translations.tsv: one line per English source text, tab-separated: en, nl, fr, de, es, it. Needs polib (Odoo's venv
has it: <venv>/bin/python tools/make_po.py). A source text missing from the table is reported and left untranslated.
"""
import csv
import json
import sys
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parents[1]
LANGS = ('nl', 'fr', 'de', 'es', 'it')


def table():
    rows = {}
    with open(ROOT / 'i18n_src' / 'translations.tsv', encoding='utf-8') as f:
        for row in csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
            if row and not row[0].startswith('#'):
                rows[row[0].replace('\\n', '\n')] = dict(zip(LANGS, [c.replace('\\n', '\n') for c in row[1:]]))
    return rows


def main():
    modules = json.loads((ROOT / 'product.json').read_text(encoding='utf-8'))['MODULES']
    rows, missing = table(), set()
    for module in modules:
        i18n = ROOT / 'src' / module / 'i18n'
        pot = polib.pofile(str(i18n / f'{module}.pot'))
        for lang in LANGS:
            po = polib.POFile()
            po.metadata = dict(pot.metadata, **{'Language': lang, 'Content-Type': 'text/plain; charset=UTF-8',
                                                'Content-Transfer-Encoding': '8bit', 'Plural-Forms': ''})
            for entry in pot:
                msgstr = rows.get(entry.msgid, {}).get(lang, '')
                if not msgstr and not entry.msgid.startswith("'"):
                    missing.add(entry.msgid)
                po.append(polib.POEntry(msgid=entry.msgid, msgstr=msgstr, occurrences=entry.occurrences,
                                        comment=entry.comment, tcomment=entry.tcomment, flags=entry.flags))
            po.save(str(i18n / f'{lang}.po'))
    for m in sorted(missing):
        print('missing:', repr(m))
    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main())
