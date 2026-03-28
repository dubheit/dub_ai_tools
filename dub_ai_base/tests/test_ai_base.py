from unittest.mock import patch, MagicMock
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestAiModel(TransactionCase):
    """Test dub.ai.model CRUD operations."""

    def test_create_ai_model(self):
        """Test creating an AI model."""
        model = self.env['dub.ai.model'].create({
            'name': 'test-model-123',
            'display_name': 'Test Model 123',
            'provider': 'openai',
        })

        self.assertTrue(model.id)
        self.assertEqual(model.name, 'test-model-123')
        self.assertEqual(model.provider, 'openai')
        self.assertTrue(model.active)

    def test_unique_constraint(self):
        """Test that model name must be unique per provider."""
        self.env['dub.ai.model'].create({
            'name': 'unique-test-model',
            'display_name': 'Unique Test',
            'provider': 'openai',
        })

        # Same name, same provider - should fail
        with self.assertRaises(Exception):
            self.env['dub.ai.model'].create({
                'name': 'unique-test-model',
                'display_name': 'Duplicate',
                'provider': 'openai',
            })

    def test_same_name_different_provider_allowed(self):
        """Test that same model name is allowed for different providers."""
        self.env['dub.ai.model'].create({
            'name': 'cross-provider-model',
            'display_name': 'OpenAI Version',
            'provider': 'openai',
        })

        # Same name, different provider - should succeed
        model2 = self.env['dub.ai.model'].create({
            'name': 'cross-provider-model',
            'display_name': 'Claude Version',
            'provider': 'claude',
        })

        self.assertTrue(model2.id)

    def test_model_ordering(self):
        """Test that models are ordered by provider, sequence, name."""
        self.env['dub.ai.model'].create({
            'name': 'z-model',
            'display_name': 'Z Model',
            'provider': 'openai',
            'sequence': 1,
        })
        self.env['dub.ai.model'].create({
            'name': 'a-model',
            'display_name': 'A Model',
            'provider': 'openai',
            'sequence': 1,
        })

        models = self.env['dub.ai.model'].search([
            ('name', 'in', ['z-model', 'a-model'])
        ])

        # Should be ordered by name within same provider/sequence
        self.assertEqual(models[0].name, 'a-model')


@tagged('post_install', '-at_install')
class TestCompanyAiConfig(TransactionCase):
    """Test AI configuration on res.company."""

    def test_default_provider(self):
        """Test that default provider is OpenAI."""
        company = self.env.company
        self.assertEqual(company.dub_ai_provider, 'openai')

    def test_set_api_keys(self):
        """Test setting API keys on company."""
        company = self.env.company

        company.dub_ai_openai_api_key = 'sk-test-key'
        company.dub_ai_claude_api_key = 'sk-ant-test'
        company.dub_ai_gemini_api_key = 'AIza-test'

        self.assertEqual(company.dub_ai_openai_api_key, 'sk-test-key')
        self.assertEqual(company.dub_ai_claude_api_key, 'sk-ant-test')
        self.assertEqual(company.dub_ai_gemini_api_key, 'AIza-test')

    def test_set_provider(self):
        """Test changing AI provider."""
        company = self.env.company

        for provider in ['openai', 'claude', 'gemini']:
            company.dub_ai_provider = provider
            self.assertEqual(company.dub_ai_provider, provider)

    def test_temperature_defaults(self):
        """Test temperature field defaults."""
        company = self.env.company

        self.assertEqual(company.dub_ai_openai_temperature, 0.7)
        self.assertEqual(company.dub_ai_claude_temperature, 0.7)
        self.assertEqual(company.dub_ai_gemini_temperature, 0.7)

    def test_set_model_id(self):
        """Test setting AI model on company."""
        company = self.env.company

        # Create a test model
        model = self.env['dub.ai.model'].create({
            'name': 'company-test-model',
            'display_name': 'Company Test Model',
            'provider': 'openai',
        })

        company.dub_ai_openai_model_id = model.id
        self.assertEqual(company.dub_ai_openai_model_id, model)


@tagged('post_install', '-at_install')
class TestModelSync(TransactionCase):
    """Test AI model synchronization from APIs."""

    def test_sync_openai_without_api_key_raises_error(self):
        """Test that syncing OpenAI models without API key raises error."""
        company = self.env.company
        company.dub_ai_openai_api_key = False

        with self.assertRaises(UserError):
            self.env['dub.ai.model'].action_sync_openai_models()

    def test_sync_claude_without_api_key_raises_error(self):
        """Test that syncing Claude models without API key raises error."""
        company = self.env.company
        company.dub_ai_claude_api_key = False

        with self.assertRaises(UserError):
            self.env['dub.ai.model'].action_sync_claude_models()

    def test_sync_gemini_without_api_key_raises_error(self):
        """Test that syncing Gemini models without API key raises error."""
        company = self.env.company
        company.dub_ai_gemini_api_key = False

        with self.assertRaises(UserError):
            self.env['dub.ai.model'].action_sync_gemini_models()

    def test_sync_all_without_any_keys_raises_error(self):
        """Test that syncing all models without any API keys raises error."""
        company = self.env.company
        company.dub_ai_openai_api_key = False
        company.dub_ai_claude_api_key = False
        company.dub_ai_gemini_api_key = False

        with self.assertRaises(UserError):
            self.env['dub.ai.model'].action_sync_all_models()

    @patch('odoo.addons.dub_ai_base.models.ai_model.requests.get')
    def test_sync_openai_creates_models(self, mock_get):
        """Test that OpenAI sync creates new models."""
        company = self.env.company
        company.dub_ai_openai_api_key = 'sk-test-key'

        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'data': [
                {'id': 'gpt-4-test'},
                {'id': 'gpt-3.5-test'},
                {'id': 'dall-e-3'},  # Should be filtered out
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Run sync
        result = self.env['dub.ai.model'].action_sync_openai_models()

        # Should have created gpt models but not dall-e
        gpt4 = self.env['dub.ai.model'].search([
            ('name', '=', 'gpt-4-test'),
            ('provider', '=', 'openai')
        ])
        self.assertTrue(gpt4, "GPT-4 model should be created")

        dalle = self.env['dub.ai.model'].search([
            ('name', '=', 'dall-e-3'),
            ('provider', '=', 'openai')
        ])
        self.assertFalse(dalle, "DALL-E model should not be created")

    @patch('odoo.addons.dub_ai_base.models.ai_model.requests.get')
    def test_sync_claude_creates_models(self, mock_get):
        """Test that Claude sync creates new models."""
        company = self.env.company
        company.dub_ai_claude_api_key = 'sk-ant-test'

        mock_response = MagicMock()
        mock_response.json.return_value = {
            'data': [
                {'id': 'claude-3-opus-test', 'display_name': 'Claude 3 Opus Test'},
                {'id': 'claude-3-sonnet-test', 'display_name': 'Claude 3 Sonnet Test'},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        self.env['dub.ai.model'].action_sync_claude_models()

        opus = self.env['dub.ai.model'].search([
            ('name', '=', 'claude-3-opus-test'),
            ('provider', '=', 'claude')
        ])
        self.assertTrue(opus, "Claude Opus model should be created")

    @patch('odoo.addons.dub_ai_base.models.ai_model.requests.get')
    def test_sync_gemini_creates_models(self, mock_get):
        """Test that Gemini sync creates new models."""
        company = self.env.company
        company.dub_ai_gemini_api_key = 'AIza-test'

        mock_response = MagicMock()
        mock_response.json.return_value = {
            'models': [
                {
                    'name': 'models/gemini-2.0-test',
                    'displayName': 'Gemini 2.0 Test',
                    'supportedGenerationMethods': ['generateContent']
                },
                {
                    'name': 'models/embedding-test',
                    'displayName': 'Embedding Test',
                    'supportedGenerationMethods': ['embedContent']
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        self.env['dub.ai.model'].action_sync_gemini_models()

        gemini = self.env['dub.ai.model'].search([
            ('name', '=', 'gemini-2.0-test'),
            ('provider', '=', 'gemini')
        ])
        self.assertTrue(gemini, "Gemini model should be created")

        embedding = self.env['dub.ai.model'].search([
            ('name', '=', 'embedding-test'),
            ('provider', '=', 'gemini')
        ])
        self.assertFalse(embedding, "Embedding model should not be created")

    @patch('odoo.addons.dub_ai_base.models.ai_model.requests.get')
    def test_sync_does_not_duplicate_existing(self, mock_get):
        """Test that sync does not create duplicate models."""
        company = self.env.company
        company.dub_ai_openai_api_key = 'sk-test-key'

        # Pre-create a model
        self.env['dub.ai.model'].create({
            'name': 'gpt-4-existing',
            'display_name': 'GPT-4 Existing',
            'provider': 'openai',
        })

        mock_response = MagicMock()
        mock_response.json.return_value = {
            'data': [{'id': 'gpt-4-existing'}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        self.env['dub.ai.model'].action_sync_openai_models()

        # Should still only have one
        count = self.env['dub.ai.model'].search_count([
            ('name', '=', 'gpt-4-existing'),
            ('provider', '=', 'openai')
        ])
        self.assertEqual(count, 1, "Should not create duplicate model")
