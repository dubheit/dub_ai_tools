from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMcpModels(TransactionCase):
    """Basic MCP model tests"""

    def test_mcp_config_exists(self):
        """Test that MCP config model is available"""
        config = self.env["mcp.server.config"].get_singleton()
        self.assertTrue(config)
