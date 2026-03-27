from odoo.tests import TransactionCase


class TestMcpConfig(TransactionCase):

    def setUp(self):
        super().setUp()
        self.MCP = self.env['mcp.server.config']
        self.Rule = self.env['mcp.server.model.rule']
        self.Model = self.env['ir.model']

    def test_model_id_field(self):
        """Test model_id field with Many2one to ir.model"""
        # Create a config
        config = self.MCP.create({
            'name': 'Test Config',
            'active': False,
        })

        # Get the partner model
        domain = [('model', '=', 'res.partner')]
        partner_model = self.Model.search(domain, limit=1)
        self.assertTrue(partner_model, "Partner model should exist")

        # Create a rule with model_id
        rule = self.Rule.create({
            'config_id': config.id,
            'model_id': partner_model.id,
            'allow_read': True,
            'allow_create': True,
            'allow_write': False,
            'allow_unlink': False,
            'field_denylist': 'password,api_key',
            'description': 'Test rule for partners',
        })

        # Check that model_name is correctly populated from model_id
        self.assertEqual(rule.model_name, 'res.partner')
        self.assertEqual(rule.model_id.id, partner_model.id)

    def test_model_name_related_field(self):
        """Test that model_name is correctly computed from model_id"""
        config = self.MCP.create({
            'name': 'Test Config 2',
            'active': False,
        })

        # Get different models
        partner_dom = [('model', '=', 'res.partner')]
        partner_model = self.Model.search(partner_dom, limit=1)
        user_dom = [('model', '=', 'res.users')]
        user_model = self.Model.search(user_dom, limit=1)

        # Create rule with partner model
        rule = self.Rule.create({
            'config_id': config.id,
            'model_id': partner_model.id,
            'allow_read': True,
        })

        self.assertEqual(rule.model_name, 'res.partner')

        # Change to user model
        rule.model_id = user_model
        self.assertEqual(rule.model_name, 'res.users')

    def test_multiple_rules_different_models(self):
        """Test creating multiple rules with different models"""
        config = self.MCP.create({
            'name': 'Multi Model Config',
            'active': True,
        })

        # Get various models
        models_to_test = [
            'res.partner',
            'res.users',
            'res.company',
            'product.product',
        ]

        rules = []
        for model_name in models_to_test:
            model = self.Model.search([('model', '=', model_name)], limit=1)
            if model:
                rule = self.Rule.create({
                    'config_id': config.id,
                    'model_id': model.id,
                    'allow_read': True,
                    'allow_create': False,
                    'allow_write': False,
                    'allow_unlink': False,
                })
                rules.append(rule)

        # Verify all rules were created correctly
        expected = len([
            m for m in models_to_test
            if self.Model.search([('model', '=', m)], limit=1)
        ])
        self.assertEqual(len(rules), expected)

        # Verify each rule has the correct model_name
        for rule in rules:
            self.assertIn(rule.model_name, models_to_test)
            self.assertEqual(rule.model_name, rule.model_id.model)
