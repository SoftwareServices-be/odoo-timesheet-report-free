# Copyright 2026 Software Services BV
# License LGPL-3 (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import http
from odoo.http import request

try:
    from odoo.http.stream import content_disposition        # 20
except ImportError:
    from odoo.http import content_disposition               # 18, 19


class TimesheetReportController(http.Controller):

    @http.route('/timeviking_timesheet_report/xlsx/<int:wizard_id>', type='http', auth='user')
    def xlsx(self, wizard_id):
        # the wizard is read as the logged-in user: access rights and record rules apply
        wizard = request.env['tv.timesheet.report.wizard'].browse(wizard_id).exists()
        if not wizard or wizard.create_uid != request.env.user:
            return request.not_found()
        content = wizard._tv_xlsx()
        return request.make_response(content, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(wizard._tv_xlsx_filename())),
        ])
