import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Drop the temperature column left behind by the removed field.

    Claude models from Opus 4.7 on reject sampling parameters, so the module
    no longer sends a temperature and the stored value is dead weight.
    """
    cr.execute("""
        ALTER TABLE res_company
        DROP COLUMN IF EXISTS dub_ai_claude_temperature
    """)
    _logger.info("Dropped res_company.dub_ai_claude_temperature")
