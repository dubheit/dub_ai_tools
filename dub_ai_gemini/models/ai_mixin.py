import base64

from odoo import models, _
from odoo.exceptions import UserError


class DubAiMixin(models.AbstractModel):
    _inherit = "dub.ai.mixin"

    def _ai_call_gemini(self, prompt, system_prompt, config, images):
        """Call Google Gemini API."""
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise UserError(_("google-genai package not installed."))

        client = genai.Client(api_key=config["api_key"])

        contents = []
        for img in (images or []):
            if isinstance(img, dict):
                data = img["data"]
                media_type = img.get("media_type", "image/png")
            else:
                data = img
                media_type = "image/png"
            contents.append(
                types.Part.from_bytes(
                    data=base64.b64decode(data),
                    mime_type=media_type,
                )
            )
        contents.append(prompt)

        gen_config = types.GenerateContentConfig(
            temperature=config["temperature"],
            max_output_tokens=config["max_tokens"],
        )
        if system_prompt:
            gen_config.system_instruction = system_prompt

        response = client.models.generate_content(
            model=config["model"],
            contents=contents,
            config=gen_config,
        )

        usage = {}
        if response.usage_metadata:
            usage = {
                "input_tokens": response.usage_metadata.prompt_token_count,
                "output_tokens": response.usage_metadata.candidates_token_count,
            }

        return {
            "text": response.text,
            "model": config["model"],
            "provider": "gemini",
            "usage": usage,
        }
