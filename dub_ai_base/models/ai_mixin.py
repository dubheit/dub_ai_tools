import logging

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DubAiMixin(models.AbstractModel):
    _name = "dub.ai.mixin"
    _description = "AI Provider Mixin"

    def _ai_call(
        self,
        prompt,
        system_prompt=None,
        provider=None,
        model=None,
        images=None,
        temperature=None,
        max_tokens=None,
    ):
        """Unified AI call across all providers.

        Args:
            prompt: User message text
            system_prompt: System instructions (optional)
            provider: Provider name override (openai/claude/gemini/...)
            model: Model ID override (e.g. 'gpt-4o', 'claude-sonnet-4-6')
            images: List of base64-encoded images or dicts with
                    {'data': base64, 'media_type': 'image/png'}
            temperature: Temperature override (0-2)
            max_tokens: Max output tokens override

        Returns:
            dict with keys: text, model, provider, usage
        """
        company = self.env.company

        if not provider:
            provider = company.dub_ai_provider
        if not provider:
            raise UserError(_(
                "No AI provider configured. "
                "Go to Settings > AI Providers."
            ))

        config = self._ai_get_config(provider, model, temperature, max_tokens)

        method_name = "_ai_call_%s" % provider
        handler = getattr(self, method_name, None)
        if not handler:
            raise UserError(_("Unsupported AI provider: %s") % provider)

        return handler(prompt, system_prompt, config, images)

    def _ai_get_config(self, provider, model=None, temperature=None,
                       max_tokens=None):
        """Resolve configuration for the given provider."""
        company = self.env.company

        api_key = getattr(company, "dub_ai_%s_api_key" % provider, None)
        if not api_key:
            raise UserError(
                _("API key for %s is not configured.") % provider
            )

        if model:
            model_rec = self.env["dub.ai.model"].search([
                ("name", "=", model),
                ("provider", "=", provider),
            ], limit=1)
            model_name = model or model_rec.name if model_rec else model
        else:
            model_rec = getattr(
                company, "dub_ai_%s_model_id" % provider, None
            )
            model_name = model_rec.name if model_rec else None

        if not model_name:
            raise UserError(
                _("No model configured for %s.") % provider
            )

        if temperature is None:
            temperature = getattr(
                company, "dub_ai_%s_temperature" % provider, 0.7
            )

        return {
            "api_key": api_key,
            "model": model_name,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
        }

    def _ai_format_images_openai(self, images):
        """Format images for OpenAI-compatible APIs.

        Used by openai, ollama, and openrouter providers.
        """
        content = []
        for img in (images or []):
            if isinstance(img, dict):
                data = img["data"]
                media_type = img.get("media_type", "image/png")
            else:
                data = img
                media_type = "image/png"
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": "data:%s;base64,%s" % (media_type, data),
                },
            })
        return content
