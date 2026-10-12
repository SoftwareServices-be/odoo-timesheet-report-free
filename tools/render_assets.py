#!/usr/bin/env python3
"""Render the store images from the HTML sources in assets/.

  tools/render_assets.py      icon.png (256x256) and banner.png (560x280) into src/<module>/static/description/

It needs a headless Chromium: set SHOT (a script called as `shot.sh <url> <png> <width,height>`) or CHROME (a Chromium
binary). Without either, the sibling main project's var/browser/shot.sh is used when it exists.
The screenshots (screenshot_*.png) come from tools/screenshots.mjs against a test Odoo; see README.md.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {'icon.html': ('icon.png', 256, 256), 'banner.html': ('banner.png', 560, 280)}
DEFAULT_SHOT = ROOT.parent / 'softwareservices-odoo-timesheets' / 'var' / 'browser' / 'shot.sh'
MODULES = ('timeviking_timesheet_report',)


def screenshot(url, png, width, height):
    shot, chrome = os.environ.get('SHOT'), os.environ.get('CHROME')
    if not shot and not chrome and DEFAULT_SHOT.exists():
        shot = str(DEFAULT_SHOT)
    if shot:
        cmd = [shot, url, str(png), f'{width},{height}']
    elif chrome:
        cmd = [chrome, '--headless', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
               f'--screenshot={png}', f'--window-size={width},{height}', url]
    else:
        raise SystemExit('No headless Chromium: set SHOT or CHROME (see the docstring).')
    subprocess.run(cmd, check=False)
    if not Path(png).exists():
        raise SystemExit(f'screenshot failed: {png}')


def main():
    for name, (png, w, h) in TARGETS.items():
        page = ROOT / 'assets' / name
        for module in MODULES:
            if module != MODULES[0] and png != 'icon.png':
                continue
            out = ROOT / 'src' / module / 'static' / 'description'
            out.mkdir(parents=True, exist_ok=True)
            target = out / png
            if target.exists():
                target.unlink()
            screenshot(page.as_uri(), target, w, h)
            print(target)
    return 0


if __name__ == '__main__':
    sys.exit(main())
