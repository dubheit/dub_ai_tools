from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    dub_ai_provider = fields.Selection(
        selection_add=[('ollama', 'Ollama')],
        ondelete={'ollama': 'set null'},
    )
    dub_ai_ollama_base_url = fields.Char(
        string="Ollama Base URL", default="http://localhost:11434",
    )
    dub_ai_ollama_api_key = fields.Char(string="Ollama API Key")
    dub_ai_ollama_model_id = fields.Many2one(
        'dub.ai.model', string="Ollama Model",
        domain="[('provider', '=', 'ollama'), ('active', '=', True)]",
    )
    dub_ai_ollama_temperature = fields.Float(
        string="Ollama Temperature", default=0.7,
    )
