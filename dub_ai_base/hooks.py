"""Installation hooks for module migration."""
import logging

_logger = logging.getLogger(__name__)

OLD_MODULE = 'db_ai_base'
NEW_MODULE = 'dub_ai_base'


def pre_init_hook(env):
    """Migrate from old module if it exists."""
    cr = env.cr

    # Check if old module exists and is installed
    cr.execute(
        "SELECT id, state FROM ir_module_module WHERE name = %s",
        (OLD_MODULE,)
    )
    old_module = cr.fetchone()

    if not old_module or old_module[1] != 'installed':
        _logger.info(f"No installed {OLD_MODULE} found, skipping migration")
        return

    _logger.info(f"Migrating {OLD_MODULE} -> {NEW_MODULE}")

    # 1. Rename the model table
    cr.execute("ALTER TABLE IF EXISTS db_ai_model RENAME TO dub_ai_model")
    _logger.info("Renamed table db_ai_model -> dub_ai_model")

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
    _logger.info(f"Renamed {len(columns)} columns in res_company")

    # 3. Update ir_model for model rename
    cr.execute(
        "UPDATE ir_model SET model = 'dub.ai.model' WHERE model = 'db.ai.model'"
    )
    cr.execute(
        "UPDATE ir_model_fields SET model = 'dub.ai.model' WHERE model = 'db.ai.model'"
    )
    cr.execute(
        "UPDATE ir_model_fields SET relation = 'dub.ai.model' WHERE relation = 'db.ai.model'"
    )
    _logger.info("Updated ir_model references")

    # 4. Update module references in ir_model_data
    cr.execute(
        "UPDATE ir_model_data SET module = %s WHERE module = %s",
        (NEW_MODULE, OLD_MODULE)
    )
    _logger.info(f"Updated ir_model_data module: {cr.rowcount} rows")

    # 5. Update model name in ir_model_data
    cr.execute(
        "UPDATE ir_model_data SET model = 'dub.ai.model' WHERE model = 'db.ai.model'"
    )
    _logger.info(f"Updated ir_model_data model: {cr.rowcount} rows")

    # 6. Delete old module entry
    cr.execute(
        "DELETE FROM ir_module_module WHERE name = %s",
        (OLD_MODULE,)
    )
    _logger.info("Deleted old module entry")

    _logger.info(f"Migration {OLD_MODULE} -> {NEW_MODULE} completed")
