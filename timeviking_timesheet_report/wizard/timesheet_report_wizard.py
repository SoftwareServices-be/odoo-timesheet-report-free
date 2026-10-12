# Copyright 2026 Software Services BV
# License LGPL-3 (https://www.gnu.org/licenses/lgpl-3.0.html).
import io

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date

try:
    import xlsxwriter
except ImportError:                                            # an Odoo requirement; the manifest declares it as well
    xlsxwriter = None


def _first_of_last_month(wizard):
    return fields.Date.context_today(wizard).replace(day=1) - relativedelta(months=1)


def _last_of_last_month(wizard):
    return fields.Date.context_today(wizard).replace(day=1) - relativedelta(days=1)


class TimesheetReportWizard(models.TransientModel):
    _name = 'tv.timesheet.report.wizard'
    _description = 'TimeViking timesheet report'

    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    date_from = fields.Date(string='Start date', required=True, default=_first_of_last_month)
    date_to = fields.Date(string='End date', required=True, default=_last_of_last_month)
    employee_ids = fields.Many2many('hr.employee.public', 'tv_timesheet_report_wizard_employee_rel', 'wizard_id', 'employee_id',
                                    string='Employees', help='Leave empty for all employees you are allowed to see.')
    is_manager = fields.Boolean(compute='_compute_is_manager')

    @api.model
    def _tv_is_manager(self):
        return self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver')

    def _compute_is_manager(self):
        self.is_manager = self._tv_is_manager()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'hr.employee' and self.env.context.get('active_ids'):
            res['employee_ids'] = [fields.Command.set(self.env.context['active_ids'])]
        elif not self._tv_is_manager() and self.env.user.employee_id:
            res['employee_ids'] = [fields.Command.set(self.env.user.employee_id.ids)]
        return res

    # --- data ----------------------------------------------------------------------------------------------------

    def _tv_lines(self):
        self.ensure_one()
        domain = [('project_id', '!=', False), ('company_id', '=', self.company_id.id),
                  ('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        if not self._tv_is_manager():
            domain.append(('user_id', '=', self.env.uid))         # "own timesheets only", as Odoo's record rules
        return self.env['account.analytic.line'].search(domain, order='date, id')

    @api.model
    def _tv_hours(self, hours):
        minutes = round(abs(hours or 0.0) * 60)
        return '%s%d:%02d' % ('-' if (hours or 0) < 0 and minutes else '', minutes // 60, minutes % 60)

    def _tv_data(self):
        """[{'employee': name, 'lines': [...], 'hours': float, 'hours_str': str}] per employee, plus the total."""
        self.ensure_one()
        blocks = {}
        for line in self._tv_lines():
            employee = line.employee_id.sudo()
            block = blocks.setdefault(employee.id, {'employee': employee.name or '', 'lines': [], 'hours': 0.0})
            block['lines'].append({
                'date': line.date,
                'date_str': format_date(self.env, line.date),
                'project': line.project_id.display_name or '',
                'task': line.task_id.name or '',
                'description': line.name if line.name and line.name != '/' else '',
                'hours': line.unit_amount,
                'hours_str': self._tv_hours(line.unit_amount),
            })
            block['hours'] += line.unit_amount
        employees = sorted(blocks.values(), key=lambda b: b['employee'])
        for block in employees:
            block['hours_str'] = self._tv_hours(block['hours'])
        total = sum(b['hours'] for b in employees)
        return {
            'employees': employees,
            'hours': total,
            'hours_str': self._tv_hours(total),
            'period': '%s - %s' % (format_date(self.env, self.date_from), format_date(self.env, self.date_to)),
            'powered_by': not self.env['ir.config_parameter'].sudo().get_param('timeviking_timesheet_report.hide_powered_by'),
        }

    def _tv_check(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(self.env._('The start date must be before the end date.'))
        if not self._tv_lines():
            raise UserError(self.env._('There are no timesheets for this period and these employees.'))

    # --- outputs -------------------------------------------------------------------------------------------------

    def action_pdf(self):
        self._tv_check()
        return self.env.ref('timeviking_timesheet_report.action_report_timesheet').report_action(self)

    def action_excel(self):
        self._tv_check()
        return {'type': 'ir.actions.act_url', 'url': '/timeviking_timesheet_report/xlsx/%d' % self.id, 'target': 'self'}

    def _tv_xlsx_filename(self):
        return 'Timesheets %s - %s.xlsx' % (self.date_from, self.date_to)

    def _tv_xlsx(self):
        """The Excel file as bytes: one sheet, a block per employee, real dates and hours as numbers (h:mm format)."""
        self.ensure_one()
        if xlsxwriter is None:
            raise UserError(self.env._('The Python library xlsxwriter is not installed.'))
        _ = self.env._
        data = self._tv_data()
        out = io.BytesIO()
        book = xlsxwriter.Workbook(out, {'in_memory': True})
        sheet = book.add_worksheet(_('Timesheets')[:31])
        title = book.add_format({'bold': True, 'font_size': 16})
        muted = book.add_format({'font_color': '#555555'})
        head = book.add_format({'bold': True, 'bg_color': '#EEEEEE', 'bottom': 1})
        name = book.add_format({'bold': True, 'font_size': 12, 'top': 1})
        date = book.add_format({'num_format': 'yyyy-mm-dd'})
        wrap = book.add_format({'text_wrap': True, 'valign': 'top'})
        # hours are stored as days for Excel's time format, so totals add up and stay editable
        dur = book.add_format({'num_format': '[h]:mm'})
        dur_bold = book.add_format({'num_format': '[h]:mm', 'bold': True, 'top': 1})
        bold = book.add_format({'bold': True, 'top': 1})
        sheet.set_column(0, 0, 12)
        sheet.set_column(1, 2, 28)
        sheet.set_column(3, 3, 50)
        sheet.set_column(4, 4, 10)
        sheet.write(0, 0, _('Timesheet Report'), title)
        sheet.write(1, 0, '%s: %s' % (_('Period'), data['period']), muted)
        sheet.write(2, 0, self.company_id.name, muted)
        row = 4
        headers = [_('Date'), _('Project'), _('Task'), _('Description'), _('Hours')]
        for block in data['employees']:
            sheet.merge_range(row, 0, row, 4, block['employee'], name)
            row += 1
            sheet.write_row(row, 0, headers, head)
            row += 1
            for line in block['lines']:
                sheet.write_datetime(row, 0, fields.Datetime.to_datetime(line['date']), date)
                sheet.write(row, 1, line['project'], wrap)
                sheet.write(row, 2, line['task'], wrap)
                sheet.write(row, 3, line['description'], wrap)
                sheet.write_number(row, 4, line['hours'] / 24.0, dur)
                row += 1
            sheet.write(row, 3, _('Total %s', block['employee']), bold)
            sheet.write_number(row, 4, block['hours'] / 24.0, dur_bold)
            row += 2
        sheet.write(row, 3, _('Total'), bold)
        sheet.write_number(row, 4, data['hours'] / 24.0, dur_bold)
        if data['powered_by']:
            sheet.write(row + 2, 0, _('Powered by TimeViking - https://timeviking.com'), muted)
        sheet.freeze_panes(4, 0)
        book.close()
        return out.getvalue()
