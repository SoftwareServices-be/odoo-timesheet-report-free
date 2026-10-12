# Copyright 2026 Software Services BV
# License LGPL-3 (https://www.gnu.org/licenses/lgpl-3.0.html).
{
    'name': '{{APP_NAME}}',
    'summary': '{{SUMMARY}}',
    'description': """
Timesheet report per employee in PDF and Excel
==============================================
Timesheets > Reporting > TimeViking Time Report: choose a period and employees, then print a PDF in your
company document layout or download an Excel file. Free, by the makers of TimeViking (https://timeviking.com).
""",
    'version': '{{VERSION}}',
    'category': '{{CATEGORY}}',
    'author': '{{AUTHOR}}',
    'website': '{{WEBSITE}}',
    'support': '{{SUPPORT_EMAIL}}',
    'license': 'LGPL-3',
    'depends': ['hr_timesheet'],
    'external_dependencies': {'python': ['xlsxwriter']},
    'data': [
        'security/ir.model.access.csv',
        'report/report.xml',
        'wizard/timesheet_report_wizard_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
