# Copyright 2025 Dubhe Srls
# License OPL-1

import logging

from fastapi import APIRouter

from odoo import fields, models

from ..routers import mcp_router

_logger = logging.getLogger(__name__)


class FastapiEndpoint(models.Model):
    _inherit = "fastapi.endpoint"

    app = fields.Selection(
        selection_add=[("mcp_server", "MCP Server API")],
        ondelete={"mcp_server": "cascade"}
    )

    def _get_fastapi_routers(self) -> list[APIRouter]:
        if self.app == "mcp_server":
            # SSE endpoints moved to native Odoo controller
            return [mcp_router.router]
        return super()._get_fastapi_routers()

    def _get_app(self):
        app = super()._get_app()
        if self.app == "mcp_server":
            _logger.info(
                "MCP Server API configured at %s",
                self.root_path
            )
        return app
