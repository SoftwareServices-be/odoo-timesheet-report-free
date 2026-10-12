# Copyright 2026 Software Services BV
# License LGPL-3 (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    tv_hide_powered_by = fields.Boolean(
        string='Hide "Powered by TimeViking"',
        config_parameter='timeviking_timesheet_report.hide_powered_by',
        help='Remove the small "Powered by TimeViking" line under the timesheet report.')
