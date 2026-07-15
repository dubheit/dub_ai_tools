{
    "name": "MCP Server",
    "summary": "Expose Odoo models via MCP protocol for AI assistants.",
    "description": """
        Enable AI assistants to interact with Odoo data through the
        Model Context Protocol (MCP) standard.

        Compatible with Claude Desktop, Claude Code, Cursor, Windsurf,
        Continue, Cline, and any MCP-enabled AI tool.

        Features:
        - Native SSE transport (no bridge required)
        - OAuth2 authentication with Device Authorization Flow
        - Granular CRUD permissions per model
        - Method execution with whitelist protection
        - Field denylist and domain restrictions
        - Rate limiting and request throttling
        - Full audit logging with configurable retention
        - Audit log UI for operation tracking
        - Optional get_logs tool for AI debugging
        - REST API endpoints for programmatic access
    """,
    "version": "19.0.1.4.0",
    "category": "Tools",
    "author": "Dubhe Srls",
    "website": "https://dubhe.it",
    "license": "LGPL-3",
    "depends": ["base", "fastapi", "dub_oauth2_provider"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/mcp_defaults.xml",
        "data/mcp_cron.xml",
        "data/fastapi_endpoint.xml",
        "views/mcp_config_views.xml",
        "views/mcp_elicitation_views.xml"
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "demo": ["demo/rules.xml"]
}
