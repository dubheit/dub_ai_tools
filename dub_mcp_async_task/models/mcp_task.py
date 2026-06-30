# Copyright 2025 Dubhe Srls
# License LGPL-3

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class McpServerTask(models.Model):
    _inherit = "mcp.server.task"

    def _dispatch(self):
        """Run the task immediately via queue_job instead of waiting for cron.

        Overrides the base no-op hook. The base cron (_cron_run_pending) stays
        active as a harmless fallback: the atomic claim in _run_task() ensures a
        task is executed exactly once even if both queue_job and the cron try.
        """
        for task in self:
            task.with_delay(
                description="MCP task %s (%s)" % (task.task_id, task.tool_name),
            )._run_task()
