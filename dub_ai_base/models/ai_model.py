import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AiModel(models.Model):
    _name = 'dub.ai.model'
    _description = 'AI Model'
    _order = 'provider, sequence, name'

    name = fields.Char(
        string="Model ID", required=True,
        help="The model identifier used in API calls",
    )
    display_name = fields.Char(string="Display Name", required=True)
    provider = fields.Selection(
        selection=[], string="Provider", required=True,
    )
    supports_vision = fields.Boolean(
        string="Vision", default=False,
        help="Model supports image/PDF inputs",
    )
    supports_tools = fields.Boolean(
        string="Tools", default=False,
        help="Model supports tool/function calling",
    )
    max_output_tokens = fields.Integer(
        string="Max Output Tokens", default=4096,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)

    _sql_constraints = [
        ('name_provider_uniq', 'unique(name, provider)',
         'Model ID must be unique per provider!')
    ]

    @api.depends('name', 'display_name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.display_name or record.name

    def _get_sync_providers(self):
        """Return list of (provider_name, api_key_field) tuples.

        Override in provider modules to register sync capability.
        """
        return []

    @api.model
    def action_sync_all_models(self):
        """Sync models from all configured providers."""
        company = self.env.company
        synced = []

        for name, key_field in self._get_sync_providers():
            key_value = getattr(company, key_field, None)
            if key_value:
                try:
                    getattr(self, 'action_sync_%s_models' % name)()
                    synced.append(name.capitalize())
                except Exception as e:
                    _logger.warning("Failed to sync %s models: %s", name, e)

        if not synced:
            raise UserError(_(
                "No API keys configured. "
                "Please configure at least one provider."
            ))

        return self._sync_notification(", ".join(synced), -1)

    def _sync_notification(self, provider, count):
        if count == -1:
            msg = _("Synced from: %s") % provider
        else:
            msg = _("%d new models added.") % count
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("%s Models Synced") % provider,
                'message': msg,
                'type': 'success',
                'sticky': False,
            },
        }
