from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMcpModels(TransactionCase):
    """Basic MCP model tests"""

    def test_mcp_config_model_available(self):
        """Test that MCP config model is available and can be created"""
        config = self.env["mcp.server.config"].create({
            "name": "Test Config",
            "active": True,
        })
        self.assertTrue(config)
        self.assertTrue(config.active)
