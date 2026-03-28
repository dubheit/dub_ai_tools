from odoo import models, _
from odoo.exceptions import UserError


class DubAiMixin(models.AbstractModel):
    _inherit = "dub.ai.mixin"

    def _ai_call_openai(self, prompt, system_prompt, config, images):
        """Call OpenAI API."""
        try:
            from openai import OpenAI
        except ImportError:
            raise UserError(_("openai package not installed."))

        client = OpenAI(api_key=config["api_key"])

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if images:
            content = [{"type": "text", "text": prompt}]
            content.extend(self._ai_format_images_openai(images))
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": config["model"],
            "messages": messages,
            "max_tokens": config["max_tokens"],
        }
        # o1/o3 models don't support temperature
        if not config["model"].startswith(("o1", "o3")):
            kwargs["temperature"] = config["temperature"]

        response = client.chat.completions.create(**kwargs)

        return {
            "text": response.choices[0].message.content,
            "model": response.model,
            "provider": "openai",
            "usage": {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
        }
