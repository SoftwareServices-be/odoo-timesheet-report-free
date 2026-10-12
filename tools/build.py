#!/usr/bin/env python3
"""Build the Odoo modules for every supported Odoo version from one source.

The sources in ``src/`` are written for Odoo 18. The Odoo 19 and 20 versions are derived from them mechanically
(see ``convert``), and the ``{{...}}`` placeholders are filled in from ``product.json``.

  tools/build.py dist [18 19 20]          write dist/<version>.0/<module>/ (for an Odoo addons path)
  tools/build.py zip [--out DIR] [...]    write <main module>-<version>.0.zip files (all modules inside; default: dist/)
  tools/build.py check [--no-branches]    validate the build; compare the version branches if they exist
  tools/build.py release [18 19 20]       commit the build to the branches 18.0, 19.0 and 20.0

``release`` never touches your working tree: it writes the branch commits with git plumbing.
Only the standard library is used, so any Python 3.8+ can run it.
"""
import argparse
import ast
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
with open(ROOT / 'product.json', encoding='utf-8') as _f:
    _P = json.load(_f)
MODULES = tuple(_P['MODULES'])                         # the first one is the app of the store listing
MODULE = MODULES[0]
LICENSE = _P['LICENSE']
MODEL_NAMES = _P.get('MODEL_NAMES', {})                # Odoo 20 ir.access.csv: model xml id -> model name
SOURCE_VERSION = '18'
VERSIONS = ('18', '19', '20')
SKIP_DIRS = {'__pycache__'}
SKIP_SUFFIXES = {'.pyc', '.pyo'}
RENDER_SUFFIXES = {'.py', '.xml', '.csv', '.html', '.rst', '.txt', '.md', '.po', '.pot'}
CONVERT_SUFFIXES = {'.py', '.xml', '.csv'}
ZIP_DATE = (2026, 10, 12, 0, 0, 0)       # fixed, so the same source always gives the same zip
TOKEN = re.compile(r'\{\{([A-Z_]+)\}\}')
APP_NAME_MAX = 25                         # Odoo Apps vendor guidelines: "no more than 25 characters"
REQUIRED_FILES = ('__manifest__.py', 'static/description/icon.png')


def source_dir(module=MODULE):
    return ROOT / 'src' / module


def product():
    """product.json without comments: the values for the {{...}} placeholders."""
    with open(ROOT / 'product.json', encoding='utf-8') as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith('_') and isinstance(v, (str, int, float, bool))}


def module_version():
    return product()['MODULE_VERSION']


def full_version(version):
    return f'{version}.0.{module_version()}'


def zip_name(version):
    return f'{MODULE}-{version}.0.zip'


def _check_version(version):
    version = str(version).split('.')[0]
    if version not in VERSIONS:
        raise ValueError(f'unknown Odoo version: {version} (supported: {", ".join(VERSIONS)})')
    return version


# --- placeholders ---------------------------------------------------------------------------------------------

def render(text, version, values=None):
    """Fill in {{KEY}} from product.json (plus VERSION). An unknown placeholder is an error, never left behind."""
    values = dict(values or product())
    values['VERSION'] = f'{version}.0.{values["MODULE_VERSION"]}'
    values['ODOO_VERSION'] = f'{version}.0'

    def repl(m):
        if m.group(1) not in values:
            raise KeyError(f'unknown placeholder {{{{{m.group(1)}}}}}')
        return str(values[m.group(1)])
    for _ in range(5):                    # a value may itself use placeholders
        text, n = TOKEN.subn(repl, text)
        if not n:
            break
    return text


# --- Odoo 18 -> 19 / 20 ---------------------------------------------------------------------------------------

def rename(rel, version):
    if int(version) >= 20 and rel == 'security/ir.model.access.csv':
        return 'security/ir.access.csv'
    return rel


def _access_csv_20(text):
    """ir.model.access.csv (18/19) -> ir.access.csv (20): one `operation` column instead of four flags, model by name."""
    rows = [line.split(',') for line in text.strip().splitlines()]
    out = ['id,name,model_id,group_id/id,operation,domain']
    for rid, name, model, group, rd, wr, cr, ul in rows[1:]:
        ops = ''.join(letter for letter, flag in (('c', cr), ('r', rd), ('u', wr), ('d', ul)) if flag == '1')
        out.append(f"{rid},{name},{MODEL_NAMES[model]},{group},{ops},")
    return '\n'.join(out) + '\n'


def convert(rel, text, version):
    """The known API differences with Odoo 18. Add a rule here when the source needs something new."""
    v, n = version, int(version)
    if v == SOURCE_VERSION:
        return text
    text = text.replace(f"startswith('{SOURCE_VERSION}.0.')", f"startswith('{v}.0.')")      # tests
    if n >= 19:
        text = text.replace('groups_id', 'group_ids')
    if n >= 20:
        text = text.replace('security/ir.model.access.csv', 'security/ir.access.csv')
        if rel == 'security/ir.model.access.csv':
            text = _access_csv_20(text)
        text = text.replace('.get_param(', '.get_str(')
    return text


# --- build ----------------------------------------------------------------------------------------------------

def source_files(src):
    src = Path(src)
    for path in sorted(src.rglob('*')):
        rel = path.relative_to(src)
        if path.is_file() and not (SKIP_DIRS & set(rel.parts)) and path.suffix not in SKIP_SUFFIXES:
            yield rel.as_posix(), path


def build_tree(version, module=MODULE, values=None):
    """{path inside the module: bytes} for one module and one Odoo version."""
    version = _check_version(version)
    values = values or product()
    files = {}
    for rel, path in source_files(source_dir(module)):
        data = path.read_bytes()
        if path.suffix in RENDER_SUFFIXES:
            text = render(data.decode('utf-8'), version, values)
            if path.suffix in CONVERT_SUFFIXES:
                text = convert(rel, text, version)
            data = text.encode('utf-8')
        files[rename(rel, version)] = data
    return files


def build_all(version):
    """{module: tree} for every module."""
    return {m: build_tree(version, m) for m in MODULES}


def manifest(tree):
    return ast.literal_eval(tree['__manifest__.py'].decode('utf-8'))


def validate(version, trees=None):
    """Problems that would break an install or the Odoo Apps listing (empty list = fine)."""
    version = _check_version(version)
    trees = trees if trees is not None else build_all(version)
    problems = []
    for module, tree in trees.items():
        problems += [f'{module}: missing {rel}' for rel in REQUIRED_FILES if rel not in tree]
        if '__manifest__.py' not in tree:
            continue
        man = manifest(tree)
        if man.get('version') != full_version(version):
            problems.append(f"{module}: manifest version {man.get('version')!r} != {full_version(version)!r}")
        name = man.get('name', '')
        if not name or len(name) > APP_NAME_MAX:
            problems.append(f'{module}: app name {name!r} must have 1-{APP_NAME_MAX} characters (vendor guidelines)')
        if 'odoo' in name.lower():
            problems.append(f'{module}: app name {name!r} must not contain the Odoo trademark')
        if man.get('license') != LICENSE:
            problems.append(f'{module}: license must be {LICENSE}')
        for key in ('summary', 'author', 'website', 'support', 'category'):
            if not man.get(key):
                problems.append(f'{module}: manifest has no {key}')
        for img in man.get('images', []):
            if img not in tree:
                problems.append(f'{module}: manifest image {img} is missing')
        for rel in man.get('data', []):
            if rel not in tree:
                problems.append(f'{module}: manifest data file {rel} is missing')
        for rel, data in tree.items():
            if Path(rel).suffix in RENDER_SUFFIXES and TOKEN.search(data.decode('utf-8')):
                problems.append(f'{module}: placeholder left in {rel}')
    main, values = manifest(trees[MODULE]), product()
    if values.get('PRICE') and (main.get('price') != float(values['PRICE']) or main.get('currency') != values['CURRENCY']):
        problems.append(f'{MODULE}: price/currency do not match product.json')
    if not values.get('PRICE') and main.get('price'):
        problems.append(f'{MODULE}: a free module must not have a price')
    if 'static/description/index.html' not in trees[MODULE]:
        problems.append(f'{MODULE}: missing static/description/index.html')
    return problems


def build_zip(version):
    """The zip as bytes: one folder per module at the top, no bytecode, reproducible."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for module, tree in build_all(version).items():
            for rel, data in tree.items():
                info = zipfile.ZipInfo(f'{module}/{rel}', ZIP_DATE)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                zf.writestr(info, data)
    return buf.getvalue()


def write_dist(version, out=None):
    """dist/<version>.0/<module>/ for every module, rebuilt from scratch (stale files removed)."""
    version = _check_version(version)
    root = Path(out or ROOT / 'dist') / f'{version}.0'
    for module, tree in build_all(version).items():
        base = root / module
        if base.exists():
            for p in sorted(base.rglob('*'), reverse=True):
                rel = p.relative_to(base).as_posix()
                if p.is_file() and rel not in tree:
                    p.unlink()
                elif p.is_dir() and not any(p.iterdir()):
                    p.rmdir()
        for rel, data in tree.items():
            target = base / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or target.read_bytes() != data:
                target.write_bytes(data)
    return root


# --- version branches -----------------------------------------------------------------------------------------

def branch_name(version):
    return f'{_check_version(version)}.0'


def branch_readme(version):
    values = product()
    return (f"# {values['APP_NAME']} for Odoo {version}.0\n\n"
            f"This branch is generated by `tools/build.py release` from the `main` branch. Do not edit it by hand.\n\n"
            f"Copy the module folder(s) {', '.join(f'`{m}`' for m in MODULES)} into your Odoo addons path, update the "
            f"apps list and install \"{values['APP_NAME']}\".\n\n"
            f"Support: {values['SUPPORT_EMAIL']}. License: {LICENSE} (see LICENSE).\n"
            ).encode('utf-8')


def branch_tree(version):
    """{path in the branch: bytes}: the module folders at the root (as the Odoo Apps store reads them), README, LICENSE."""
    files = {}
    for module, tree in build_all(version).items():
        files.update({f'{module}/{rel}': data for rel, data in tree.items()})
    files['README.md'] = branch_readme(version)
    files['LICENSE'] = (ROOT / 'LICENSE').read_bytes()
    return files


def _git(repo, *args, env=None, data=None):
    res = subprocess.run(['git', '-C', str(repo), *args], input=data, capture_output=True,
                         env={**os.environ, **(env or {})}, check=True)
    return res.stdout.decode().strip()


def _write_git_tree(repo, files):
    with tempfile.TemporaryDirectory() as tmp:
        env = {'GIT_INDEX_FILE': os.path.join(tmp, 'index')}
        _git(repo, 'read-tree', '--empty', env=env)
        lines = []
        for rel, data in sorted(files.items()):
            blob = _git(repo, 'hash-object', '-w', '--stdin', data=data)
            lines.append(f'100644 {blob}\t{rel}')
        _git(repo, 'update-index', '--add', '--index-info', env=env, data=('\n'.join(lines) + '\n').encode())
        return _git(repo, 'write-tree', env=env)


def _branch_head(repo, branch):
    try:
        return _git(repo, 'rev-parse', '--verify', '--quiet', f'refs/heads/{branch}')
    except subprocess.CalledProcessError:
        return None


def branch_differs(version, repo=None):
    """None if the branch does not exist, else True/False: does the branch hold something other than the build?"""
    repo = repo or ROOT
    head = _branch_head(repo, branch_name(version))
    if head is None:
        return None
    return _git(repo, 'rev-parse', f'{head}^{{tree}}') != _write_git_tree(repo, branch_tree(version))


def release(version, repo=None, message=None):
    """Commit the build to branch <version>.0 (created when missing). Returns the new commit, or None if unchanged."""
    repo = repo or ROOT
    version = _check_version(version)
    branch = branch_name(version)
    problems = validate(version)
    if problems:
        raise SystemExit(f'{branch}: not released, ' + '; '.join(problems))
    tree = _write_git_tree(repo, branch_tree(version))
    head = _branch_head(repo, branch)
    if head and _git(repo, 'rev-parse', f'{head}^{{tree}}') == tree:
        return None
    try:
        source = _git(repo, 'rev-parse', '--short', 'HEAD')
    except subprocess.CalledProcessError:
        source = 'uncommitted'
    msg = message or f'{full_version(version)}: build from main {source}'
    args = ['commit-tree', tree, '-m', msg] + (['-p', head] if head else [])
    try:
        commit = _git(repo, *args)
    except subprocess.CalledProcessError as e:
        raise SystemExit(f'{branch}: git commit-tree failed ({e.stderr.decode().strip()}). Is a git identity set? Export '
                         'GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL, GIT_COMMITTER_NAME and GIT_COMMITTER_EMAIL first.')
    _git(repo, 'update-ref', f'refs/heads/{branch}', commit, *([head] if head else []))
    return commit


# --- command line ---------------------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=('dist', 'zip', 'check', 'release'))
    ap.add_argument('versions', nargs='*', default=list(VERSIONS))
    ap.add_argument('--out', help='output directory (dist and zip)')
    ap.add_argument('-m', '--message', help='commit message for release')
    ap.add_argument('--no-branches', action='store_true', help='check: do not compare the version branches')
    args = ap.parse_args(argv)
    versions = [_check_version(v) for v in args.versions]
    status = 0
    for v in versions:
        if args.command == 'dist':
            print(write_dist(v, args.out))
        elif args.command == 'zip':
            out = Path(args.out or ROOT / 'dist')
            out.mkdir(parents=True, exist_ok=True)
            (out / zip_name(v)).write_bytes(build_zip(v))
            print(out / zip_name(v))
        elif args.command == 'check':
            problems = validate(v)
            differs = None if args.no_branches else branch_differs(v)
            if differs:
                problems.append(f'branch {branch_name(v)} is behind main (run tools/build.py release)')
            state = 'no branch yet' if differs is None else 'branch up to date' if not differs else 'branch differs'
            print(f'{v}.0: ' + ('ok, ' + state if not problems else '; '.join(problems)))
            status |= bool(problems)
        elif args.command == 'release':
            commit = release(v, message=args.message)
            print(f'{branch_name(v)}: ' + (f'committed {commit[:10]}' if commit else 'unchanged'))
    return status


if __name__ == '__main__':
    sys.exit(main())
