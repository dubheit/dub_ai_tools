import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AiModel(models.Model):
    _inherit = 'dub.ai.model'

    provider = fields.Selection(
        selection_add=[('openai', 'OpenAI')],
        ondelete={'openai': 'cascade'},
    )

    def _get_sync_providers(self):
        providers = super()._get_sync_providers()
        providers.append(('openai', 'dub_ai_openai_api_key'))
        return providers

    @api.model
    def action_sync_openai_models(self):
        """Fetch available models from OpenAI API."""
        api_key = self.env.company.dub_ai_openai_api_key
        if not api_key:
            raise UserError(_("OpenAI API key is not configured."))

        headers = {"Authorization": "Bearer %s" % api_key}
        response = requests.get(
            "https://api.openai.com/v1/models",
            headers=headers, timeout=30,
        )
        response.raise_for_status()

        created = 0
        for info in response.json().get('data', []):
            mid = info.get('id', '')
            if any(x in mid.lower() for x in ['gpt', 'o1', 'o3', 'o4']):
                if not self.search([
                    ('name', '=', mid), ('provider', '=', 'openai')
                ], limit=1):
                    self.create({
                        'name': mid, 'display_name': mid,
                        'provider': 'openai', 'sequence': 100,
                    })
                    created += 1

        return self._sync_notification("OpenAI", created)
