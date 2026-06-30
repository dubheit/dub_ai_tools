{
    "name": "MCP Server — Async Tasks (queue_job)",
    "summary": "Run MCP tasks via OCA queue_job instead of the built-in cron.",
    "description": """
        Optional bridge for dub_mcp_server.

        When installed, MCP tasks (mcp.server.task) are executed immediately
        through OCA queue_job instead of being picked up by the built-in
        ir.cron. This removes the ~1 minute cron latency and adds retries and
        monitoring, without changing the MCP protocol surface.

        The base module remains fully functional on its own (cron-based); this
        module only overrides how a task is dispatched.
    """,
    "version": "18.0.1.0.0",
    "category": "Tools",
    "author": "Dubhe Srls",
    "website": "https://dubhe.it",
    "license": "LGPL-3",
    "depends": ["dub_mcp_server", "queue_job"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
