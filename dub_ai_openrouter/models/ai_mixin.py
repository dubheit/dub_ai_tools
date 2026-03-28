from odoo import models, _
from odoo.exceptions import UserError


class DubAiMixin(models.AbstractModel):
    _inherit = "dub.ai.mixin"

    def _ai_get_config(self, provider, model=None, temperature=None,
                       max_tokens=None):
        """Override to add OpenRouter base_url."""
        config = super()._ai_get_config(
            provider, model, temperature, max_tokens
        )
        if provider == "openrouter":
            config["base_url"] = "https://openrouter.ai/api/v1"
        return config

    def _ai_call_openrouter(self, prompt, system_prompt, config, images):
        """Call OpenRouter via OpenAI-compatible API."""
        try:
            from openai import OpenAI
        except ImportError:
            raise UserError(_("openai package not installed."))

        client = OpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
        )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if images:
            content = [{"type": "text", "text": prompt}]
            content.extend(self._ai_format_images_openai(images))
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=config["model"],
            messages=messages,
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
        )

        usage = {}
        if response.usage:
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }

        return {
            "text": response.choices[0].message.content,
            "model": response.model,
            "provider": "openrouter",
            "usage": usage,
        }
