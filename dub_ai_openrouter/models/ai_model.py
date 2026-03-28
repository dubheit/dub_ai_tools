import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AiModel(models.Model):
    _inherit = 'dub.ai.model'

    provider = fields.Selection(
        selection_add=[('openrouter', 'OpenRouter')],
        ondelete={'openrouter': 'cascade'},
    )

    def _get_sync_providers(self):
        providers = super()._get_sync_providers()
        providers.append(('openrouter', 'dub_ai_openrouter_api_key'))
        return providers

    @api.model
    def action_sync_openrouter_models(self):
        """Fetch available models from OpenRouter API."""
        api_key = self.env.company.dub_ai_openrouter_api_key
        if not api_key:
            raise UserError(_("OpenRouter API key is not configured."))

        headers = {"Authorization": "Bearer %s" % api_key}
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers=headers, timeout=30,
        )
        response.raise_for_status()

        created = 0
        for info in response.json().get('data', []):
            mid = info.get('id', '')
            dname = info.get('name', mid)
            if mid and not self.search([
                ('name', '=', mid), ('provider', '=', 'openrouter')
            ], limit=1):
                self.create({
                    'name': mid, 'display_name': dname,
                    'provider': 'openrouter', 'sequence': 100,
                })
                created += 1

        return self._sync_notification("OpenRouter", created)
