{
    "name": "AI Base",
    "version": "19.0.3.0.0",
    "category": "Technical",
    "summary": "AI providers integration base with unified calling interface",
    "description": """
AI Base
========

Base module for AI providers integration with unified calling interface.

Install individual provider modules to enable specific AI services:
- dub_ai_openai: OpenAI (GPT-4o, o1, o3, o4)
- dub_ai_claude: Anthropic Claude (Opus 4.6, Sonnet 4.6, Haiku 4.5)
- dub_ai_gemini: Google Gemini (2.5 Pro, 2.5 Flash, 2.0 Flash)
- dub_ai_mistral: Mistral AI (Large, Small, Pixtral, Codestral)
- dub_ai_ollama: Ollama (local/remote, OpenAI-compatible API)
- dub_ai_openrouter: OpenRouter (multi-provider gateway)

Features:
- Multi-provider support with per-company configuration
- Unified _ai_call() mixin for all providers
- Multimodal support (text + images)
- Dynamic model list with API sync
- Manual model management
    """,
    "author": "Dubhe Srls",
    "website": "https://dubhe.it",
    "license": "LGPL-3",
    "depends": ["base_setup"],
    "data": [
        "security/ir.model.access.csv",
        "data/ai_model_data.xml",
        "views/ai_model_views.xml",
        "views/res_config_settings.xml",
    ],
    "installable": True,
    "application": False,
}
