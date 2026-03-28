import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AiModel(models.Model):
    _inherit = 'dub.ai.model'

    provider = fields.Selection(
        selection_add=[('ollama', 'Ollama')],
        ondelete={'ollama': 'cascade'},
    )

    def _get_sync_providers(self):
        providers = super()._get_sync_providers()
        providers.append(('ollama', 'dub_ai_ollama_base_url'))
        return providers

    @api.model
    def action_sync_ollama_models(self):
        """Fetch available models from Ollama API."""
        company = self.env.company
        base_url = company.dub_ai_ollama_base_url
        if not base_url:
            raise UserError(_("Ollama Base URL is not configured."))

        headers = {}
        api_key = company.dub_ai_ollama_api_key
        if api_key:
            headers["Authorization"] = "Bearer %s" % api_key

        response = requests.get(
            "%s/api/tags" % base_url.rstrip("/"),
            headers=headers, timeout=30,
        )
        response.raise_for_status()

        created = 0
        for info in response.json().get('models', []):
            mid = info.get('name', '')
            if mid and not self.search([
                ('name', '=', mid), ('provider', '=', 'ollama')
            ], limit=1):
                self.create({
                    'name': mid, 'display_name': mid,
                    'provider': 'ollama', 'sequence': 100,
                })
                created += 1

        return self._sync_notification("Ollama", created)
