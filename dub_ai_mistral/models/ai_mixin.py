from odoo import models, _
from odoo.exceptions import UserError


class DubAiMixin(models.AbstractModel):
    _inherit = "dub.ai.mixin"

    def _ai_call_mistral(self, prompt, system_prompt, config, images):
        """Call Mistral AI API."""
        try:
            from mistralai.client import Mistral
        except ImportError:
            raise UserError(_("mistralai package not installed."))

        client = Mistral(api_key=config["api_key"])

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if images:
            content = [{"type": "text", "text": prompt}]
            for img in images:
                if isinstance(img, dict):
                    data = img["data"]
                    media_type = img.get("media_type", "image/png")
                else:
                    data = img
                    media_type = "image/png"
                content.append({
                    "type": "image_url",
                    "image_url": "data:%s;base64,%s" % (media_type, data),
                })
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})

        response = client.chat.complete(
            model=config["model"],
            messages=messages,
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
        )

        return {
            "text": response.choices[0].message.content,
            "model": response.model,
            "provider": "mistral",
            "usage": {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
        }
