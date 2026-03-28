import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AiModel(models.Model):
    _inherit = 'dub.ai.model'

    provider = fields.Selection(
        selection_add=[('mistral', 'Mistral AI')],
        ondelete={'mistral': 'cascade'},
    )

    def _get_sync_providers(self):
        providers = super()._get_sync_providers()
        providers.append(('mistral', 'dub_ai_mistral_api_key'))
        return providers

    @api.model
    def action_sync_mistral_models(self):
        """Fetch available models from Mistral AI API."""
        api_key = self.env.company.dub_ai_mistral_api_key
        if not api_key:
            raise UserError(_("Mistral API key is not configured."))

        headers = {"Authorization": "Bearer %s" % api_key}
        response = requests.get(
            "https://api.mistral.ai/v1/models",
            headers=headers, timeout=30,
        )
        response.raise_for_status()

        created = 0
        for info in response.json().get('data', []):
            mid = info.get('id', '')
            if not self.search([
                ('name', '=', mid), ('provider', '=', 'mistral')
            ], limit=1):
                self.create({
                    'name': mid, 'display_name': mid,
                    'provider': 'mistral', 'sequence': 100,
                })
                created += 1

        return self._sync_notification("Mistral", created)
