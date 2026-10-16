import logging

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
