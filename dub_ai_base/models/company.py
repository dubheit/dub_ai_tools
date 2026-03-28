from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    dub_ai_provider = fields.Selection(
        selection=[],
        string="Default AI Provider",
    )
