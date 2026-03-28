"""Pre-migration script for module rename."""
import logging

_logger = logging.getLogger(__name__)

OLD_MODULE = 'db_ai_base'
NEW_MODULE = 'dub_ai_base'


def migrate(cr, version):
    """Pre-migration: rename old module to new module in database."""
    if not version:
        return

    _logger.info(f"Pre-migrating {OLD_MODULE} -> {NEW_MODULE}")

    # 1. Rename the model table
    cr.execute("ALTER TABLE IF EXISTS db_ai_model RENAME TO dub_ai_model")

    # 2. Rename columns in res_company
    columns = [
        ('db_ai_provider', 'dub_ai_provider'),
        ('db_ai_openai_api_key', 'dub_ai_openai_api_key'),
        ('db_ai_openai_model_id', 'dub_ai_openai_model_id'),
        ('db_ai_openai_temperature', 'dub_ai_openai_temperature'),
        ('db_ai_claude_api_key', 'dub_ai_claude_api_key'),
        ('db_ai_claude_model_id', 'dub_ai_claude_model_id'),
        ('db_ai_claude_temperature', 'dub_ai_claude_temperature'),
        ('db_ai_gemini_api_key', 'dub_ai_gemini_api_key'),
        ('db_ai_gemini_model_id', 'dub_ai_gemini_model_id'),
        ('db_ai_gemini_temperature', 'dub_ai_gemini_temperature'),
    ]

    for old_col, new_col in columns:
        cr.execute(f"""
            DO $$ BEGIN
                ALTER TABLE res_company RENAME COLUMN {old_col} TO {new_col};
            EXCEPTION WHEN undefined_column THEN NULL;
            END $$;
        """)
        _logger.info(f"Renamed column {old_col} -> {new_col}")

    # 3. Update ir_model for model rename
    cr.execute("UPDATE ir_model SET model = 'dub.ai.model' WHERE model = 'db.ai.model'")
    cr.execute("UPDATE ir_model_fields SET model = 'dub.ai.model' WHERE model = 'db.ai.model'")
    cr.execute("UPDATE ir_model_fields SET relation = 'dub.ai.model' WHERE relation = 'db.ai.model'")

    # 4. Update module references in ir_model_data
    cr.execute(f"UPDATE ir_model_data SET module = '{NEW_MODULE}' WHERE module = '{OLD_MODULE}'")

    # 5. Update module name in ir_module_module
    cr.execute(f"UPDATE ir_module_module SET name = '{NEW_MODULE}' WHERE name = '{OLD_MODULE}'")

    _logger.info(f"Pre-migration {OLD_MODULE} -> {NEW_MODULE} completed")
