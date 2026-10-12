"""Tests for tools/build.py: one source, three Odoo versions, Apps store metadata."""
import ast
import importlib.util
import io
import re
import struct
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('build', ROOT / 'tools' / 'build.py')
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

MODULE = build.MODULE
LANGS = ('nl', 'fr', 'de', 'es', 'it')


def read(version, rel):
    return build.build_tree(version)[rel].decode()


@pytest.mark.parametrize('version', build.VERSIONS)
def test_build_is_valid_for_the_store(version):
    assert build.validate(version) == []


@pytest.mark.parametrize('version', build.VERSIONS)
def test_zip(version):
    entries = zipfile.ZipFile(io.BytesIO(build.build_zip(version))).namelist()
    assert {n.split('/')[0] for n in entries} == {MODULE}
    assert not [n for n in entries if '__pycache__' in n or n.endswith(('.pyc', '.pyo'))]


def test_manifest_free_lgpl():
    for v in build.VERSIONS:
        man = build.manifest(build.build_tree(v))
        assert man['license'] == 'LGPL-3' and 'price' not in man
        assert man['version'] == f'{v}.0.{build.module_version()}'
        assert man['depends'] == ['hr_timesheet']
        assert 'TimeViking' in man['name'] and len(man['name']) <= 25


def test_known_differences_per_version():
    assert 'groups_id' in read('18', 'wizard/timesheet_report_wizard_views.xml')
    assert 'group_ids' in read('19', 'wizard/timesheet_report_wizard_views.xml')
    assert '.get_param(' in read('19', 'wizard/timesheet_report_wizard.py')
    assert '.get_str(' in read('20', 'wizard/timesheet_report_wizard.py')
    assert 'security/ir.access.csv' in build.build_tree('20')
    assert ',tv.timesheet.report.wizard,hr_timesheet.group_hr_timesheet_user,crud,' in read('20', 'security/ir.access.csv')


def test_python_compiles():
    for v in build.VERSIONS:
        for rel, data in build.build_tree(v).items():
            if rel.endswith('.py'):
                ast.parse(data.decode(), filename=f'{v}/{rel}')


def po_entries(text):
    """{msgid: msgstr} of a .po/.pot, with multi-line strings joined."""
    entries, key, cur = {}, None, None
    for line in text.splitlines() + ['']:
        m = re.match(r'^(msgid|msgstr) "(.*)"$', line)
        if m:
            if m.group(1) == 'msgid':
                key, cur = 'id', [m.group(2)]
                mid = cur
            else:
                key, cur = 'str', [m.group(2)]
                mstr = cur
        elif line.startswith('"') and cur is not None:
            cur.append(line[1:-1])
        elif key == 'str':
            entries[''.join(mid)] = ''.join(mstr)
            key, cur = None, None
    return entries


def test_translations_complete():
    i18n = build.source_dir() / 'i18n'
    ids = {i for i in po_entries((i18n / f'{MODULE}.pot').read_text(encoding='utf-8')) if i and not i.startswith("'")}
    assert ids
    for lang in LANGS:
        done = {i for i, s in po_entries((i18n / f'{lang}.po').read_text(encoding='utf-8')).items() if s}
        assert not ids - done, (lang, sorted(ids - done)[:5])


def test_store_page():
    html = read('18', 'static/description/index.html')
    assert 'https://timeviking.com' in html
    for img in re.findall(r'src="([^"]+\.(?:png|jpg))"', html):
        assert f'static/description/{img}' in build.build_tree('18'), img
    data = build.build_tree('18')['static/description/icon.png']
    assert struct.unpack('>II', data[16:24]) == (256, 256)
