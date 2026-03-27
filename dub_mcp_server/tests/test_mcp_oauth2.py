# Copyright 2025 Dubhe Srls
# License OPL-1

"""
Test MCP Server logic with OAuth2 authentication.
Unit tests that don't require HTTP/FastAPI runtime.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMCPLogic(TransactionCase):
    """
    Test MCP Server logic without HTTP.
    These tests verify the core MCP functionality.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test user - basic user is sufficient for most tests
        # Note: Create/Update tests use SUPERUSER_ID to bypass Odoo ACL issues in CI
        cls.test_user = cls.env["res.users"].create({
            "name": "MCP Test User",
            "login": "mcp_test_user",
            "email": "mcptest@example.com",
            "groups_id": [
                (4, cls.env.ref("base.group_user").id),
            ],
        })

        # Ensure MCP config exists and is active
        cls.mcp_config = cls.env["mcp.server.config"].get_singleton()
        cls.mcp_config.write({
            "active": True,
            "rate_limit_window_s": 60,
            "rate_limit_max_requests": 1000,
            "default_page_size": 50,
            "max_page_size": 200,
        })

        # Create model rule for res.partner
        partner_model = cls.env["ir.model"].search(
            [("model", "=", "res.partner")], limit=1
        )
        existing_rule = cls.mcp_config.rule_ids.filtered(
            lambda r: r.model_name == "res.partner"
        )
        if not existing_rule:
            cls.partner_rule = cls.env["mcp.server.model.rule"].create({
                "config_id": cls.mcp_config.id,
                "model_id": partner_model.id,
                "allow_read": True,
                "allow_create": True,
                "allow_write": True,
                "allow_unlink": False,
            })
        else:
            # Get first rule if multiple exist
            cls.partner_rule = existing_rule[0] if len(existing_rule) > 1 else existing_rule

        # Create test data
        cls.test_partner = cls.env["res.partner"].create({
            "name": "MCP Test Partner",
            "email": "mcppartner@test.com",
        })

    def test_mcp_config_singleton(self):
        """Test MCP config singleton pattern"""
        config1 = self.env["mcp.server.config"].get_singleton()
        config2 = self.env["mcp.server.config"].get_singleton()
        self.assertEqual(config1.id, config2.id)

    def test_mcp_config_active(self):
        """Test MCP config is active"""
        self.assertTrue(self.mcp_config.active)

    def test_model_rule_exists(self):
        """Test model rule for res.partner exists"""
        rules = self.mcp_config.rule_ids.filtered(
            lambda r: r.model_name == "res.partner"
        )
        self.assertTrue(rules)
        # Get first rule if multiple exist
        rule = rules[0] if len(rules) > 1 else rules
        self.assertTrue(rule.allow_read)
        self.assertTrue(rule.allow_create)
        self.assertTrue(rule.allow_write)
        self.assertFalse(rule.allow_unlink)

    def test_execute_tool_list_models(self):
        """Test execute_tool with list_models"""
        from ..services.mcp_tools import execute_tool

        result = execute_tool(
            self.env,
            "list_models",
            {},
            config=self.mcp_config,
            user_id=self.test_user.id,
        )

        self.assertIn("res.partner", result)
        self.assertIn("read", result)

    def test_execute_tool_search(self):
        """Test execute_tool with search"""
        from ..services.mcp_tools import execute_tool

        result = execute_tool(
            self.env,
            "search",
            {
                "model": "res.partner",
                "domain": [["id", "=", self.test_partner.id]],
                "fields": ["id", "name"],
                "limit": 10,
            },
            config=self.mcp_config,
            user_id=self.test_user.id,
        )

        self.assertIn("MCP Test Partner", result)

    def test_execute_tool_read(self):
        """Test execute_tool with read"""
        from ..services.mcp_tools import execute_tool

        result = execute_tool(
            self.env,
            "read",
            {
                "model": "res.partner",
                "ids": [self.test_partner.id],
                "fields": ["name", "email"],
            },
            config=self.mcp_config,
            user_id=self.test_user.id,
        )

        self.assertIn("MCP Test Partner", result)
        self.assertIn("mcppartner@test.com", result)

    def test_execute_tool_create(self):
        """Test execute_tool with create - uses superuser to bypass Odoo ACL"""
        from odoo import SUPERUSER_ID
        from ..services.mcp_tools import execute_tool

        result = execute_tool(
            self.env,
            "create",
            {
                "model": "res.partner",
                "values": {
                    "name": "Created via MCP Test",
                    "email": "mcp_test_create@test.com",
                },
            },
            config=self.mcp_config,
            user_id=SUPERUSER_ID,
        )

        self.assertIn("Created", result)

        # Verify partner was created
        partner = self.env["res.partner"].search([
            ("email", "=", "mcp_test_create@test.com")
        ], limit=1)
        self.assertTrue(partner)
        self.assertEqual(partner.name, "Created via MCP Test")

    def test_execute_tool_update(self):
        """Test execute_tool with update - uses superuser to bypass Odoo ACL"""
        from odoo import SUPERUSER_ID
        from ..services.mcp_tools import execute_tool

        # Create partner with sudo
        partner = self.env["res.partner"].sudo().create({
            "name": "To Update MCP",
            "email": "toupdate_mcp@test.com",
        })

        result = execute_tool(
            self.env,
            "update",
            {
                "model": "res.partner",
                "ids": [partner.id],
                "values": {"name": "Updated via MCP Test"},
            },
            config=self.mcp_config,
            user_id=SUPERUSER_ID,
        )

        self.assertIn("Updated", result)

        # Verify update
        partner.invalidate_recordset()
        self.assertEqual(partner.name, "Updated via MCP Test")

    def test_execute_tool_delete_denied(self):
        """Test execute_tool with delete is denied"""
        from ..services.mcp_tools import execute_tool

        # Create partner with sudo - ACL is tested in MCP code, not here
        partner = self.env["res.partner"].sudo().create({
            "name": "To Delete MCP",
            "email": "todelete_mcp@test.com",
        })

        result = execute_tool(
            self.env,
            "delete",
            {
                "model": "res.partner",
                "ids": [partner.id],
            },
            config=self.mcp_config,
            user_id=self.test_user.id,
        )

        # Should be denied
        self.assertIn("Access denied", result)

        # Partner should still exist
        self.assertTrue(partner.exists())

    def test_execute_tool_unconfigured_model(self):
        """Test access to unconfigured model is denied"""
        from ..services.mcp_tools import execute_tool

        result = execute_tool(
            self.env,
            "search",
            {
                "model": "ir.cron",  # Not configured
                "domain": [],
            },
            config=self.mcp_config,
            user_id=self.test_user.id,
        )

        self.assertIn("not configured", result.lower())

    def test_execute_tool_unknown(self):
        """Test unknown tool returns error"""
        from ..services.mcp_tools import execute_tool

        result = execute_tool(
            self.env,
            "unknown_tool",
            {},
            config=self.mcp_config,
            user_id=self.test_user.id,
        )

        self.assertIn("Unknown tool", result)

    def test_get_tools_list(self):
        """Test get_tools_list returns expected tools"""
        from ..services.mcp_tools import get_tools_list

        tools = get_tools_list(self.env, config=self.mcp_config)
        tool_names = [t["name"] for t in tools]

        self.assertIn("list_models", tool_names)
        self.assertIn("search", tool_names)
        self.assertIn("read", tool_names)
        self.assertIn("create", tool_names)
        self.assertIn("update", tool_names)
        self.assertIn("delete", tool_names)

    def test_tools_have_schema(self):
        """Test all tools have proper schema"""
        from ..services.mcp_tools import get_tools_list

        tools = get_tools_list(self.env, config=self.mcp_config)

        for tool in tools:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("inputSchema", tool)
            self.assertIn("type", tool["inputSchema"])

    def test_mcp_response_format(self):
        """Test create_mcp_response format"""
        from ..services.mcp_tools import create_mcp_response

        # Test success response
        response = create_mcp_response(1, result={"foo": "bar"})
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], 1)
        self.assertEqual(response["result"], {"foo": "bar"})
        self.assertNotIn("error", response)

        # Test error response
        response = create_mcp_response(
            2, error={"code": -32600, "message": "Invalid Request"}
        )
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], 2)
        self.assertIn("error", response)
        self.assertNotIn("result", response)

    def test_permission_check(self):
        """Test _check_permission function"""
        from ..services.mcp_tools import _check_permission

        # Allowed operations
        allowed, msg = _check_permission(self.mcp_config, "res.partner", "read")
        self.assertTrue(allowed)

        allowed, msg = _check_permission(self.mcp_config, "res.partner", "create")
        self.assertTrue(allowed)

        # Denied operation
        allowed, msg = _check_permission(self.mcp_config, "res.partner", "delete")
        self.assertFalse(allowed)

        # Unconfigured model
        allowed, msg = _check_permission(self.mcp_config, "ir.cron", "read")
        self.assertFalse(allowed)
        self.assertIn("not configured", msg.lower())

    def test_validate_model(self):
        """Test _validate_model function"""
        from ..services.mcp_tools import _validate_model

        # Valid model
        valid, msg = _validate_model(self.env, "res.partner")
        self.assertTrue(valid)

        # Invalid model
        valid, msg = _validate_model(self.env, "nonexistent.model")
        self.assertFalse(valid)

        # Invalid format
        valid, msg = _validate_model(self.env, "invalid!model")
        self.assertFalse(valid)

    def test_validate_ids(self):
        """Test _validate_ids function"""
        from ..services.mcp_tools import _validate_ids

        # Valid IDs
        valid, msg = _validate_ids([1, 2, 3])
        self.assertTrue(valid)

        # Empty list
        valid, msg = _validate_ids([])
        self.assertFalse(valid)

        # Invalid type
        valid, msg = _validate_ids("not a list")
        self.assertFalse(valid)

        # Invalid ID values
        valid, msg = _validate_ids([1, -1, 3])
        self.assertFalse(valid)

        valid, msg = _validate_ids([1, "two", 3])
        self.assertFalse(valid)
