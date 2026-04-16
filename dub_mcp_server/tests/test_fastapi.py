# Copyright 2025 Dubhe Srls
# License OPL-1

"""Test MCP Server configuration and models."""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMCPConfig(TransactionCase):
    """Test MCP Server configuration."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test user
        cls.test_user = cls.env['res.users'].create({
            'name': 'Test MCP User',
            'login': 'test_mcp',
            'email': 'test@mcp.com',
        })

        # Create MCP config (deny by default, no singleton fallback)
        cls.mcp_config = cls.env['mcp.server.config'].create({
            'name': 'Test MCP Config',
            'active': True,
        })
        cls.mcp_config.write({
            'active': True,
            'rate_limit_window_s': 60,
            'rate_limit_max_requests': 100,
            'default_page_size': 50,
            'max_page_size': 200,
        })

        # Create test model rule
        partner_model = cls.env['ir.model'].search(
            [('model', '=', 'res.partner')], limit=1
        )
        existing_rule = cls.mcp_config.rule_ids.filtered(
            lambda r: r.model_name == 'res.partner'
        )
        if not existing_rule:
            cls.partner_rule = cls.env['mcp.server.model.rule'].create({
                'config_id': cls.mcp_config.id,
                'model_id': partner_model.id,
                'allow_read': True,
                'allow_create': True,
                'allow_write': True,
                'allow_unlink': False,
            })
        else:
            # Get first rule if multiple exist
            cls.partner_rule = existing_rule[0] if len(existing_rule) > 1 else existing_rule

        # Create test partners
        cls.test_partner = cls.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'partner@test.com',
            'phone': '+1234567890',
        })

    def test_config_deny_by_default(self):
        """Test that get_singleton returns empty recordset (deny by default)."""
        config = self.env['mcp.server.config'].get_singleton()
        self.assertFalse(config)

    def test_config_values(self):
        """Test config has expected values."""
        self.assertTrue(self.mcp_config.active)
        self.assertEqual(self.mcp_config.rate_limit_window_s, 60)
        self.assertEqual(self.mcp_config.rate_limit_max_requests, 100)

    def test_model_rule_permissions(self):
        """Test model rule permissions."""
        self.assertTrue(self.partner_rule.allow_read)
        self.assertTrue(self.partner_rule.allow_create)
        self.assertTrue(self.partner_rule.allow_write)
        self.assertFalse(self.partner_rule.allow_unlink)

    def test_model_rule_model_name(self):
        """Test model rule has correct model name."""
        self.assertEqual(self.partner_rule.model_name, 'res.partner')

    def test_field_denylist(self):
        """Test field denylist functionality."""
        from ..services.authz import apply_field_denylist

        # Update partner rule with denylist
        self.partner_rule.field_denylist = 'phone,email'

        fields = ['name', 'email', 'phone', 'password']
        filtered = apply_field_denylist(fields, self.partner_rule)

        self.assertIn('name', filtered)
        self.assertNotIn('email', filtered)
        self.assertNotIn('phone', filtered)
        self.assertNotIn('password', filtered)  # Always denied

    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        from ..services import ratelimit
        from ..services.authz import AuthContext
        from ..services.errors import RateLimited

        # Create auth context
        ctx = AuthContext(
            user_id=self.test_user.id,
            login=self.test_user.login,
            ip='127.0.0.1'
        )

        # Update config to very restrictive rate limit
        self.mcp_config.write({
            'rate_limit_window_s': 1,
            'rate_limit_max_requests': 2,
        })

        # First two requests should pass
        ratelimit.ensure_within_limit(ctx, self.env)
        ratelimit.ensure_within_limit(ctx, self.env)

        # Third request should fail
        with self.assertRaises(RateLimited):
            ratelimit.ensure_within_limit(ctx, self.env)
