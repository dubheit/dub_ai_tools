import logging
import os
from xml.etree import ElementTree

from odoo.modules.module import get_module_path

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Let the model catalogue be refreshed by this and later upgrades.

    The records were created under noupdate, and that flag lives in the
    database, so dropping it from the XML only affects new records. Without
    this, existing installs would keep a catalogue with no identifiers for
    the Amazon Bedrock and Google Cloud routes, and every call on those
    routes would fail with a misleading "model has no id" error.
    """
    cr.execute("""
        UPDATE ir_model_data
           SET noupdate = false
         WHERE module = 'dub_ai_claude'
           AND model = 'dub.ai.model'
    """)
    _logger.info("Unlocked %s catalogue records for update", cr.rowcount)
    _adopt_synced_models(cr)


def _adopt_synced_models(cr):
    """Give the catalogue identifiers to models the API sync already created.

    action_sync_claude_models creates records without an identifier, so a
    catalogue entry whose name is already in the database would be inserted
    a second time and break the unique (name, provider) constraint, failing
    the whole upgrade. Binding the identifier makes the upgrade update that
    record instead.
    """
    path = os.path.join(get_module_path("dub_ai_claude"), "data", "ai_model_data.xml")
    for record in ElementTree.parse(path).getroot().iter("record"):
        if record.get("model") != "dub.ai.model":
            continue
        name = next((f.text for f in record.iter("field") if f.get("name") == "name"), None)
        cr.execute("""
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            SELECT 'dub_ai_claude', %(xmlid)s, 'dub.ai.model', m.id, false
              FROM dub_ai_model m
             WHERE m.provider = 'claude' AND m.name = %(name)s
               AND NOT EXISTS (SELECT 1 FROM ir_model_data d
                                WHERE d.module = 'dub_ai_claude' AND d.name = %(xmlid)s)
               AND NOT EXISTS (SELECT 1 FROM ir_model_data d
                                WHERE d.model = 'dub.ai.model' AND d.res_id = m.id)
             ORDER BY m.id
             LIMIT 1
        """, {"xmlid": record.get("id"), "name": name})
        if cr.rowcount:
            _logger.info("Bound %s to the synced model %s", record.get("id"), name)
