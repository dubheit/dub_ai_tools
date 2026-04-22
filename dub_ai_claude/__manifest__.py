{
    "name": "AI Provider - Anthropic Claude",
    "version": "18.0.1.0.0",
    "category": "Technical",
    "summary": "Anthropic Claude provider for AI Base (Opus, Sonnet, Haiku)",
    "author": "Dubhe Srls",
    "website": "https://dubhe.it",
    "license": "LGPL-3",
    "depends": ["dub_ai_base"],
    "external_dependencies": {
        "python": ["anthropic"],
    },
    "data": [
        "data/ai_model_data.xml",
        "views/ai_model_views.xml",
        "views/res_config_settings.xml",
    ],
    "installable": True,
    "application": False,
}
