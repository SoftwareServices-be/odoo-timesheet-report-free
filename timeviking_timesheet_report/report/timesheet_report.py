# Copyright 2026 Software Services BV
# License LGPL-3 (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import api, models


class ReportTimesheet(models.AbstractModel):
    _name = 'report.timeviking_timesheet_report.report_timesheet'
    _description = 'TimeViking timesheet report (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['tv.timesheet.report.wizard'].browse(docids)
        return {'doc_ids': docids, 'doc_model': 'tv.timesheet.report.wizard', 'docs': docs,
                'reports': {doc.id: doc._tv_data() for doc in docs}}
