import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AiModel(models.Model):
    _inherit = 'dub.ai.model'

    provider = fields.Selection(
        selection_add=[('gemini', 'Google Gemini')],
        ondelete={'gemini': 'cascade'},
    )

    def _get_sync_providers(self):
        providers = super()._get_sync_providers()
        providers.append(('gemini', 'dub_ai_gemini_api_key'))
        return providers

    @api.model
    def action_sync_gemini_models(self):
        """Fetch available models from Google Gemini API."""
        api_key = self.env.company.dub_ai_gemini_api_key
        if not api_key:
            raise UserError(_("Gemini API key is not configured."))

        response = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models"
            "?key=%s" % api_key,
            timeout=30,
        )
        response.raise_for_status()

        created = 0
        for info in response.json().get('models', []):
            mid = info.get('name', '').replace('models/', '')
            dname = info.get('displayName', mid)
            methods = info.get('supportedGenerationMethods', [])
            if 'generateContent' in methods and 'gemini' in mid.lower():
                if not self.search([
                    ('name', '=', mid), ('provider', '=', 'gemini')
                ], limit=1):
                    self.create({
                        'name': mid, 'display_name': dname,
                        'provider': 'gemini', 'sequence': 100,
                    })
                    created += 1

        return self._sync_notification("Gemini", created)
