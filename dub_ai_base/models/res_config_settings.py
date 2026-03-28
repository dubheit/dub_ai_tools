import logging
import markupsafe

from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dub_ai_provider = fields.Selection(
        related='company_id.dub_ai_provider',
        readonly=False,
    )

    module_dub_ai_openai = fields.Boolean(string="OpenAI")
    module_dub_ai_claude = fields.Boolean(string="Anthropic Claude")
    module_dub_ai_gemini = fields.Boolean(string="Google Gemini")
    module_dub_ai_mistral = fields.Boolean(string="Mistral AI")
    module_dub_ai_ollama = fields.Boolean(string="Ollama")
    module_dub_ai_openrouter = fields.Boolean(string="OpenRouter")

    dub_ai_test_prompt = fields.Char(
        string="Test Prompt",
        default="Say hello in one word",
    )

    def _action_test_provider(self, provider):
        """Run a health check call for the given provider."""
        self.ensure_one()
        prompt = self.dub_ai_test_prompt or "Say hello in one word"
        mixin = self.env['dub.ai.mixin']

        try:
            result = mixin._ai_call(prompt=prompt, provider=provider)
            text = str(markupsafe.escape(result.get('text', '')))
            notif_msg = _(
                "Model: %s\n"
                "Input: %s tokens | Output: %s tokens\n"
                "Response: %s"
            ) % (
                result.get('model', ''),
                result.get('usage', {}).get('input_tokens', '?'),
                result.get('usage', {}).get('output_tokens', '?'),
                text[:200],
            )
            notif_type = 'success'
            notif_title = _("%s — OK") % provider.upper()
        except (UserError, Exception) as e:
            notif_type = 'danger'
            notif_title = _("%s — Error") % provider.upper()
            notif_msg = str(e)[:300]

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': notif_title,
                'message': notif_msg,
                'type': notif_type,
                'sticky': True,
            },
        }
