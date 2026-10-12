#!/usr/bin/env node
// Store screenshots from a running test Odoo with the demo data of tools/seed_demo.py.
//
//   NODE_PATH=../softwareservices-odoo-timesheets/node_modules ODOO_URL=http://127.0.0.1:8049 \
//   DEMO_WIZARD_EMPLOYEE=.. DEMO_WIZARD_PROJECT=.. DEMO_INVOICE=.. [DEMO_TV_WIZARD=..] node tools/screenshots.mjs
//
// The PDFs are fetched from Odoo (/report/pdf/..., rendered by wkhtmltopdf) and page 1 is turned into a PNG with
// PyMuPDF (python3 -m pip install pymupdf). Output: src/<module>/static/description/screenshot_*.png
import { chromium } from 'playwright-core';
import { execFileSync, execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const product = JSON.parse(fs.readFileSync(path.join(ROOT, 'product.json'), 'utf8'));
const MODULE = product.MODULES[0];
const OUT = path.join(ROOT, 'src', MODULE, 'static/description');
const ODOO = (process.env.ODOO_URL || 'http://127.0.0.1:8049').replace(/\/$/, '');
const B = process.env.BROWSER_DIR || path.join(ROOT, '..', 'softwareservices-odoo-timesheets', 'var/browser');
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'shots-'));
const env = process.env;

async function launch() {
    const exe = execSync(`find ${os.homedir()}/.cache/ms-playwright -path '*chrome-linux64/chrome' -type f | head -1`).toString().trim();
    const libs = execSync(`find ${B}/root -name "*.so*" -printf '%h\\n' | sort -u | tr '\\n' ':'`).toString();
    return chromium.launch({ executablePath: exe, args: ['--no-sandbox', '--font-render-hinting=none', '--lang=en-US'],
        env: { ...env, LD_LIBRARY_PATH: libs, FONTCONFIG_FILE: path.join(B, 'fonts.conf') } });
}

function pdfToPng(pdf, png, clipHeight) {
    execFileSync('python3', ['-c', `import sys, pymupdf
doc = pymupdf.open(sys.argv[1]); page = doc[0]; r = page.rect
clip = pymupdf.Rect(0, 0, r.width, min(r.height, r.width * float(sys.argv[3])))
page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=clip).save(sys.argv[2])`, pdf, png, String(clipHeight || 1.42)]);
    console.log(png);
}

async function settle(page) {
    await page.waitForSelector('.o_action_manager .o_view_controller, .modal .o_form_view', { timeout: 60000 });
    await page.waitForTimeout(1500);
}

async function pdf(page, report, id, name, clip) {
    const res = await page.request.get(`${ODOO}/report/pdf/${report}/${id}`);
    const file = path.join(TMP, `${name}.pdf`);
    fs.writeFileSync(file, await res.body());
    pdfToPng(file, path.join(OUT, `${name}.png`), clip);
}

const browser = await launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, locale: 'en-US' });
await page.goto(`${ODOO}/web/login`);
await page.fill('input[name=login]', 'admin');
await page.fill('input[name=password]', 'admin');
await Promise.all([page.waitForNavigation(), page.click('button[type=submit]')]);

if (MODULE === 'ss_timesheet_pdf_report') {
    await page.goto(`${ODOO}/odoo/action-hr_timesheet.act_hr_timesheet_line`); await settle(page);
    await page.goto(`${ODOO}/odoo/action-ss_timesheet_pdf_report.ss_timesheet_pdf_wizard_action`); await settle(page);
    await page.click('.modal .o_field_widget[name=show_signatures] input');
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(OUT, 'screenshot_wizard.png') }); console.log('wizard');
    await pdf(page, 'ss_timesheet_pdf_report.report_timesheet', env.DEMO_WIZARD_EMPLOYEE, 'screenshot_report_employee');
    await pdf(page, 'ss_timesheet_pdf_report.report_timesheet', env.DEMO_WIZARD_PROJECT, 'screenshot_report_project');
    if (env.DEMO_INVOICE) {
        await page.goto(`${ODOO}/odoo/action-account.action_move_out_invoice_type/${env.DEMO_INVOICE}`); await settle(page);
        await page.screenshot({ path: path.join(OUT, 'screenshot_invoice.png') }); console.log('invoice');
    }
} else {
    await page.goto(`${ODOO}/odoo/action-hr_timesheet.act_hr_timesheet_line`); await settle(page);
    await page.goto(`${ODOO}/odoo/action-timeviking_timesheet_report.tv_timesheet_report_wizard_action`); await settle(page);
    await page.screenshot({ path: path.join(OUT, 'screenshot_wizard.png') }); console.log('wizard');
    await pdf(page, 'timeviking_timesheet_report.report_timesheet', env.DEMO_TV_WIZARD, 'screenshot_pdf');
    // the Excel file as Odoo serves it, shown as a spreadsheet grid (tools/xlsx_preview.py)
    const res = await page.request.get(`${ODOO}/timeviking_timesheet_report/xlsx/${env.DEMO_TV_WIZARD}`);
    const xlsx = path.join(TMP, 'report.xlsx'); fs.writeFileSync(xlsx, await res.body());
    const html = path.join(TMP, 'xlsx.html');
    execFileSync(env.XLSX_PYTHON || 'python3', [path.join(ROOT, 'tools/xlsx_preview.py'), xlsx, html]);
    await page.setViewportSize({ width: 1100, height: 700 });
    await page.goto('file://' + html);
    await page.screenshot({ path: path.join(OUT, 'screenshot_excel.png') }); console.log('excel');
}
await browser.close();
