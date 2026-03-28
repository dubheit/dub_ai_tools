from odoo import models, _
from odoo.exceptions import UserError


class DubAiMixin(models.AbstractModel):
    _inherit = "dub.ai.mixin"

    def _ai_get_config(self, provider, model=None, temperature=None,
                       max_tokens=None):
        """Override to handle Ollama's optional API key and base_url."""
        if provider != "ollama":
            return super()._ai_get_config(
                provider, model, temperature, max_tokens
            )

        company = self.env.company
        base_url = company.dub_ai_ollama_base_url
        if not base_url:
            raise UserError(_("Ollama Base URL is not configured."))

        api_key = company.dub_ai_ollama_api_key

        if model:
            model_rec = self.env["dub.ai.model"].search([
                ("name", "=", model),
                ("provider", "=", "ollama"),
            ], limit=1)
            model_name = model or model_rec.name if model_rec else model
        else:
            model_rec = company.dub_ai_ollama_model_id
            model_name = model_rec.name if model_rec else None

        if not model_name:
            raise UserError(_("No model configured for Ollama."))

        if temperature is None:
            temperature = company.dub_ai_ollama_temperature

        return {
            "api_key": api_key or "ollama",
            "model": model_name,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
            "base_url": "%s/v1" % base_url.rstrip("/"),
        }

    def _ai_call_ollama(self, prompt, system_prompt, config, images):
        """Call Ollama via OpenAI-compatible API."""
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
            "provider": "ollama",
            "usage": usage,
        }
