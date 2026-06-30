# Copyright 2025 Dubhe Srls
# License LGPL-3

import json
import logging
import secrets

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Terminal statuses per MCP spec
TERMINAL = ("completed", "failed", "cancelled")
DEFAULT_TTL_MS = 3600000      # 1h
DEFAULT_POLL_MS = 2000


class McpServerTask(models.Model):
    """Durable state machine for a task-augmented MCP request (MCP 2025-11-25).

    Execution is async: the base module runs pending tasks via ir.cron; the
    optional dub_mcp_async_task bridge overrides _dispatch() to use queue_job.
    Either way _run_task() is idempotent thanks to an atomic claim.
    """
    _name = "mcp.server.task"
    _description = "MCP Server Task"
    _order = "create_date desc"

    task_id = fields.Char(required=True, index=True, copy=False)
    user_id = fields.Many2one(
        "res.users", required=True, ondelete="cascade", index=True
    )
    config_id = fields.Many2one("mcp.server.config", ondelete="set null")

    status = fields.Selection(
        [
            ("working", "Working"),
            ("input_required", "Input Required"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        required=True, default="working", index=True
    )
    status_message = fields.Char()

    tool_name = fields.Char()
    arguments = fields.Text()
    transport = fields.Char(default="task")

    result = fields.Text(help="Serialized CallToolResult content text")
    is_error = fields.Boolean(default=False)

    ttl_ms = fields.Integer(default=DEFAULT_TTL_MS)
    poll_interval_ms = fields.Integer(default=DEFAULT_POLL_MS)
    picked = fields.Boolean(default=False, index=True)
    last_updated_at = fields.Datetime()

    _sql_constraints = [
        ("task_id_uniq", "unique(task_id)", "Task id must be unique"),
    ]

    # --- creation / dispatch -------------------------------------------------

    @api.model
    def create_task(self, user_id, tool_name, arguments, config=None,
                    transport="task", ttl_ms=None):
        """Create a working task bound to the user and schedule execution."""
        task = self.sudo().create({
            "task_id": secrets.token_urlsafe(24),
            "user_id": user_id,
            "config_id": config.id if config else False,
            "tool_name": tool_name,
            "arguments": json.dumps(arguments or {}),
            "transport": transport,
            "ttl_ms": ttl_ms or DEFAULT_TTL_MS,
            "status": "working",
            "last_updated_at": fields.Datetime.now(),
        })
        task._dispatch()
        return task

    def _dispatch(self):
        """Hook: schedule async execution.

        Base implementation is a no-op: the ir.cron picks the task up. The
        dub_mcp_async_task bridge overrides this to run via queue_job.
        """
        return

    # --- execution -----------------------------------------------------------

    def _claim(self):
        """Atomically claim the task. Returns True if this caller won."""
        self.ensure_one()
        self.env.cr.execute(
            "UPDATE mcp_server_task SET picked=true "
            "WHERE id=%s AND picked=false RETURNING id",
            (self.id,),
        )
        won = bool(self.env.cr.fetchone())
        if won:
            self.env.cr.commit()
            self.invalidate_recordset(["picked"])
        return won

    def _run_task(self):
        """Execute the wrapped tool. Idempotent via atomic claim."""
        self.ensure_one()
        if not self._claim():
            return
        self.invalidate_recordset(["status"])
        if self.status != "working":
            # cancelled between claim and run
            return
        from ..services.mcp_tools import execute_tool
        try:
            args = json.loads(self.arguments or "{}")
            result = execute_tool(
                self.env, self.tool_name, args,
                config=self.config_id or None,
                user_id=self.user_id.id,
                transport=self.transport or "task",
            )
            self.write({
                "status": "completed",
                "result": result,
                "is_error": False,
                "last_updated_at": fields.Datetime.now(),
            })
        except Exception as e:
            _logger.exception("MCP task %s failed", self.task_id)
            self.write({
                "status": "failed",
                "status_message": str(e)[:500],
                "last_updated_at": fields.Datetime.now(),
            })
        self.env.cr.commit()

    # --- serialization -------------------------------------------------------

    def _iso(self, dt):
        return (dt.isoformat() + "Z") if dt else None

    def to_task_dict(self):
        """Return the MCP Task object for tasks/* responses."""
        self.ensure_one()
        return {
            "taskId": self.task_id,
            "status": self.status,
            "statusMessage": self.status_message or "",
            "createdAt": self._iso(self.create_date),
            "lastUpdatedAt": self._iso(self.last_updated_at or self.write_date),
            "ttl": self.ttl_ms or None,
            "pollInterval": self.poll_interval_ms or DEFAULT_POLL_MS,
        }

    def to_call_tool_result(self):
        """Return the CallToolResult for tasks/result on a terminal task."""
        self.ensure_one()
        return {
            "content": [{"type": "text", "text": self.result or ""}],
            "isError": self.is_error,
            "_meta": {
                "io.modelcontextprotocol/related-task": {"taskId": self.task_id}
            },
        }

    # --- cron ----------------------------------------------------------------

    @api.model
    def _cron_run_pending(self):
        """Execute pending tasks not yet picked (base async engine)."""
        pending = self.search(
            [("status", "=", "working"), ("picked", "=", False)], limit=20
        )
        for task in pending:
            task._run_task()

    @api.model
    def _cron_cleanup_expired(self):
        """Delete tasks past their ttl since creation."""
        now = fields.Datetime.now()
        stale = self.search([])
        to_unlink = self.browse()
        for t in stale:
            ttl_s = (t.ttl_ms or DEFAULT_TTL_MS) / 1000.0
            if t.create_date and (now - t.create_date).total_seconds() > ttl_s:
                to_unlink |= t
        if to_unlink:
            to_unlink.unlink()
