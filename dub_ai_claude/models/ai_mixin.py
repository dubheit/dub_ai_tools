from odoo import models, _
from odoo.exceptions import UserError


class DubAiMixin(models.AbstractModel):
    _inherit = "dub.ai.mixin"

    def _ai_call_claude(self, prompt, system_prompt, config, images):
        """Call Anthropic Claude API."""
        try:
            import anthropic
        except ImportError:
            raise UserError(_("anthropic package not installed."))

        client = anthropic.Anthropic(api_key=config["api_key"])

        content = []
        for img in (images or []):
            if isinstance(img, dict):
                data = img["data"]
                media_type = img.get("media_type", "image/png")
            else:
                data = img
                media_type = "image/png"
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": data,
                },
            })
        content.append({"type": "text", "text": prompt})

        kwargs = {
            "model": config["model"],
            "max_tokens": config["max_tokens"],
            "messages": [{"role": "user", "content": content}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if config["temperature"] is not None:
            kwargs["temperature"] = config["temperature"]

        response = client.messages.create(**kwargs)

        return {
            "text": response.content[0].text,
            "model": response.model,
            "provider": "claude",
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }
