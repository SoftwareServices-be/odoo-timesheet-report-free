# Copyright 2026 Software Services BV
# License LGPL-3 (https://www.gnu.org/licenses/lgpl-3.0.html).
import io
import zipfile
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tests.common import new_test_user

REPORT = 'timeviking_timesheet_report.report_timesheet'


class Common:

    @classmethod
    def tv_setup(cls):
        env = cls.env
        cls.manager = new_test_user(env, login='tv_manager', name='Tom Manager', password='tv_manager_pw',
                                    groups='base.group_user,hr_timesheet.group_hr_timesheet_approver')
        cls.user = new_test_user(env, login='tv_user', name='Uma User',
                                 groups='base.group_user,hr_timesheet.group_hr_timesheet_user')
        cls.uma = env['hr.employee'].create({'name': 'Uma User', 'user_id': cls.user.id})
        cls.vic = env['hr.employee'].create({'name': 'Vic Viking'})
        cls.project = env['project.project'].create({'name': 'Longship', 'allow_timesheets': True,
                                                     'privacy_visibility': 'employees'})
        task = env['project.task'].create({'name': 'Rowing', 'project_id': cls.project.id})
        Line = env['account.analytic.line']
        cls.lines = Line.create([
            {'employee_id': cls.uma.id, 'project_id': cls.project.id, 'task_id': task.id, 'date': date(2026, 9, 1),
             'unit_amount': 1.5, 'name': 'Oars'},
            {'employee_id': cls.uma.id, 'project_id': cls.project.id, 'date': date(2026, 9, 2), 'unit_amount': 2.25,
             'name': 'Sails'},
            {'employee_id': cls.vic.id, 'project_id': cls.project.id, 'date': date(2026, 9, 3), 'unit_amount': 4.0,
             'name': 'Shields'},
            {'employee_id': cls.vic.id, 'project_id': cls.project.id, 'date': date(2026, 10, 3), 'unit_amount': 8.0,
             'name': 'October'},
        ])

    @classmethod
    def wizard(cls, user, **vals):
        employees = (cls.uma | cls.vic).ids                  # the test databank may hold other timesheets
        return cls.env['tv.timesheet.report.wizard'].with_user(user).create({
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30), 'employee_ids': [(6, 0, employees)], **vals})


@tagged('post_install', '-at_install')
class TestTimesheetReport(Common, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tv_setup()

    def test_data(self):
        data = self.wizard(self.manager)._tv_data()
        self.assertEqual([b['employee'] for b in data['employees']], ['Uma User', 'Vic Viking'])
        self.assertEqual(data['employees'][0]['hours_str'], '3:45')
        self.assertEqual(data['hours_str'], '7:45')
        self.assertTrue(data['powered_by'])

    def test_plain_user_only_own(self):
        wizard = self.env['tv.timesheet.report.wizard'].with_user(self.user).create({
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})
        self.assertEqual(wizard.employee_ids.ids, self.uma.ids)
        self.assertEqual([b['employee'] for b in wizard._tv_data()['employees']], ['Uma User'])

    def test_html_and_powered_by_setting(self):
        wizard = self.wizard(self.manager)
        html = self.env['ir.actions.report']._render_qweb_html(REPORT, wizard.ids)[0].decode()
        for text in ('Vic Viking', 'Shields', 'Longship', 'Rowing', '7:45', 'Powered by TimeViking'):
            self.assertIn(text, html)
        self.assertNotIn('October', html)
        settings = self.env['res.config.settings'].create({'tv_hide_powered_by': True})
        settings.execute()
        html = self.env['ir.actions.report']._render_qweb_html(REPORT, wizard.ids)[0].decode()
        self.assertNotIn('Powered by TimeViking', html)

    def test_xlsx(self):
        content = self.wizard(self.manager)._tv_xlsx()
        book = zipfile.ZipFile(io.BytesIO(content))
        strings = book.read('xl/sharedStrings.xml').decode()
        for text in ('Timesheet Report', 'Uma User', 'Vic Viking', 'Shields', 'Powered by TimeViking'):
            self.assertIn(text, strings)
        sheet = book.read('xl/worksheets/sheet1.xml').decode()
        self.assertIn('<v>0.0625</v>', sheet)                   # 1:30 as a fraction of a day

    def test_checks(self):
        with self.assertRaises(UserError):
            self.wizard(self.manager, date_from=date(2026, 9, 30), date_to=date(2026, 9, 1)).action_pdf()
        with self.assertRaises(UserError):
            self.wizard(self.manager, date_from=date(2025, 1, 1), date_to=date(2025, 1, 31)).action_excel()
        self.assertEqual(self.wizard(self.manager).action_pdf()['report_name'], REPORT)
        self.assertIn('/timeviking_timesheet_report/xlsx/', self.wizard(self.manager).action_excel()['url'])

    def test_menu(self):
        menu = self.env.ref('timeviking_timesheet_report.menu_tv_timesheet_report')
        self.assertEqual(menu.parent_id, self.env.ref('hr_timesheet.menu_timesheets_reports'))


@tagged('post_install', '-at_install')
class TestTimesheetReportHttp(Common, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tv_setup()

    def test_xlsx_download(self):
        wizard = self.wizard(self.manager)
        self.authenticate('tv_manager', 'tv_manager_pw')
        res = self.url_open('/timeviking_timesheet_report/xlsx/%d' % wizard.id)
        self.assertEqual(res.status_code, 200)
        self.assertIn('spreadsheetml', res.headers['Content-Type'])
        self.assertTrue(res.content.startswith(b'PK'))
        # someone else's wizard: not found
        other = self.wizard(self.env.ref('base.user_admin'))
        self.assertEqual(self.url_open('/timeviking_timesheet_report/xlsx/%d' % other.id).status_code, 404)
