import json

from odoo import models, _
from odoo.exceptions import UserError

# Niente brotli: su Odoo.sh convivono httpx 0.28 e un pacchetto brotli
# il cui Decompressor espone ``process()`` e non ``decompress()``.
# L'httpx prende allora il ramo scritto per brotlipy e lo chiama con
# argomenti che quella firma non accetta, quindi ogni risposta
# compressa in brotli muore in decodifica - e l'SDK la ripresenta come
# APIConnectionError, che manda a cercare un problema di rete che non
# c'e'. Su risposte JSON gzip vale quanto brotli.
CLAUDE_DEFAULT_HEADERS = {"accept-encoding": "gzip, deflate"}

GCP_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

# Le due rotte Bedrock condividono le credenziali ma non gli endpoint:
# a identificatori diversi corrispondono client diversi.
BEDROCK_ROUTES = {
    "bedrock": ("bedrock_model_id", "AnthropicBedrockMantle"),
    "bedrock_invoke": ("bedrock_invoke_model_id", "AnthropicBedrock"),
}


class DubAiMixin(models.AbstractModel):
    _inherit = "dub.ai.mixin"

    def _ai_get_config(self, provider, model=None, temperature=None,
                       max_tokens=None):
        """Override to resolve the Claude route.

        The Amazon Bedrock and Google Cloud routes authenticate with cloud
        credentials instead of an Anthropic API key, and address the models
        with their own identifiers.
        """
        if provider != "claude":
            return super()._ai_get_config(
                provider, model, temperature, max_tokens
            )

        company = self.env.company
        route = company.dub_ai_claude_route or "direct"

        if model:
            model_rec = self.env["dub.ai.model"].search([
                ("name", "=", model),
                ("provider", "=", "claude"),
            ], limit=1)
            model_name = model
        else:
            model_rec = company.dub_ai_claude_model_id
            model_name = model_rec.name if model_rec else None

        if not model_name:
            raise UserError(_("No model configured for Claude."))

        config = {
            "route": route,
            "model": model_name,
            "max_tokens": max_tokens or 4096,
        }

        if route in BEDROCK_ROUTES:
            # Su Bedrock gli id non sono mai quelli dell'API Anthropic, e i
            # due endpoint non li condividono fra loro: senza la mappatura
            # della rotta in uso la chiamata fallirebbe con un 400.
            id_field = BEDROCK_ROUTES[route][0]
            bedrock_model = model_rec[id_field] if model_rec else None
            if not bedrock_model:
                raise UserError(_(
                    "Model %(model)s has no id for the %(route)s route and "
                    "cannot be used there."
                ) % {
                    "model": model_name,
                    "route": dict(
                        company._fields["dub_ai_claude_route"].selection
                    )[route],
                })
            if not company.dub_ai_claude_aws_region:
                raise UserError(_(
                    "No AWS region configured for the Claude Bedrock route."
                ))
            config.update({
                "model": bedrock_model,
                "aws_region": company.dub_ai_claude_aws_region,
                "aws_access_key": company.dub_ai_claude_aws_access_key_id,
                "aws_secret_key": company.dub_ai_claude_aws_secret_access_key,
                "bedrock_api_key": company.dub_ai_claude_bedrock_api_key,
            })
        elif route == "vertex":
            if not company.dub_ai_claude_gcp_project_id:
                raise UserError(_(
                    "No Google project configured for the Claude Google "
                    "Cloud route."
                ))
            if not company.dub_ai_claude_gcp_region:
                raise UserError(_(
                    "No Google location configured for the Claude Google "
                    "Cloud route."
                ))
            # Su Google Cloud gli id coincidono con quelli dell'API
            # tranne per gli snapshot datati, in forma nome@data.
            if model_rec and model_rec.vertex_model_id:
                config["model"] = model_rec.vertex_model_id
            config.update({
                "gcp_project_id": company.dub_ai_claude_gcp_project_id,
                "gcp_region": company.dub_ai_claude_gcp_region,
                "gcp_credentials": company.dub_ai_claude_gcp_credentials,
            })
        else:
            if not company.dub_ai_claude_api_key:
                raise UserError(_("Claude API key is not configured."))
            config["api_key"] = company.dub_ai_claude_api_key

        return config

    def _ai_claude_client(self, config):
        """Return the Anthropic client matching the configured route."""
        try:
            import anthropic
        except ImportError:
            raise UserError(_("anthropic package not installed."))

        route = config.get("route") or "direct"
        if route in BEDROCK_ROUTES:
            return self._ai_claude_client_bedrock(anthropic, config)
        if route == "vertex":
            return self._ai_claude_client_vertex(anthropic, config)

        return anthropic.Anthropic(
            api_key=config["api_key"],
            default_headers=CLAUDE_DEFAULT_HEADERS,
        )

    def _ai_claude_client_bedrock(self, anthropic, config):
        """Return a client for the Amazon Bedrock endpoint of a region."""
        cls_name = BEDROCK_ROUTES[config["route"]][1]
        client_cls = getattr(anthropic, cls_name, None)
        if client_cls is None:
            raise UserError(_(
                "The installed anthropic package has no Amazon Bedrock "
                "support. Install it with: pip install -U 'anthropic[bedrock]'"
            ))

        kwargs = {
            "aws_region": config["aws_region"],
            "default_headers": CLAUDE_DEFAULT_HEADERS,
        }
        if config.get("bedrock_api_key"):
            kwargs["api_key"] = config["bedrock_api_key"]
        elif config.get("aws_access_key") and config.get("aws_secret_key"):
            kwargs["aws_access_key"] = config["aws_access_key"]
            kwargs["aws_secret_key"] = config["aws_secret_key"]
        elif not self._ai_claude_has_module("boto3"):
            # Senza credenziali esplicite l'SDK firma con la catena AWS di
            # default, che passa da boto3.
            raise UserError(_(
                "No Bedrock credentials configured and boto3 is not "
                "installed, so the AWS default credential chain cannot be "
                "used. Set the AWS keys or the Bedrock API key."
            ))

        return client_cls(**kwargs)

    def _ai_claude_client_vertex(self, anthropic, config):
        """Return a client for a Google Cloud location."""
        client_cls = getattr(anthropic, "AnthropicVertex", None)
        if client_cls is None:
            raise UserError(_(
                "The installed anthropic package has no Google Cloud "
                "support. Install it with: pip install -U 'anthropic[vertex]'"
            ))
        if not self._ai_claude_has_module("google.auth"):
            raise UserError(_(
                "google-auth is not installed, so Google Cloud cannot be "
                "reached. Install it with: pip install -U "
                "'anthropic[vertex]'"
            ))

        kwargs = {
            "project_id": config["gcp_project_id"],
            "region": config["gcp_region"],
            "default_headers": CLAUDE_DEFAULT_HEADERS,
        }
        raw_key = (config.get("gcp_credentials") or "").strip()
        if raw_key:
            from google.oauth2 import service_account
            try:
                key_info = json.loads(raw_key)
            except ValueError:
                raise UserError(_(
                    "The Google service account key is not valid JSON."
                ))
            kwargs["credentials"] = (
                service_account.Credentials.from_service_account_info(
                    key_info, scopes=GCP_SCOPES,
                )
            )

        return client_cls(**kwargs)

    def _ai_claude_has_module(self, name):
        import importlib.util
        try:
            return importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            return False

    def _ai_call_claude(self, prompt, system_prompt, config, images):
        """Call Claude on the Anthropic API, Amazon Bedrock or Google Cloud.

        Temperature is never sent: models from Claude Opus 4.7 on reject
        sampling parameters, and since anthropic 1.x the SDK rejects the
        argument locally anyway.
        """
        client = self._ai_claude_client(config)

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

        response = client.messages.create(**kwargs)

        # I modelli con reasoning restituiscono anche blocchi 'thinking':
        # concatena solo i blocchi di testo, non il primo blocco a caso.
        text_blocks = [
            b.text for b in response.content
            if getattr(b, "type", None) == "text"
        ]
        return {
            "text": "".join(text_blocks),
            "model": response.model,
            "provider": "claude",
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }
