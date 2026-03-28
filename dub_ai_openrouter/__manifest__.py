{
    "name": "AI Provider - OpenRouter",
    "version": "19.0.1.0.0",
    "category": "Technical",
    "summary": "OpenRouter provider for AI Base (multi-provider gateway)",
    "author": "Dubhe",
    "website": "https://www.dubhe.it",
    "license": "LGPL-3",
    "depends": ["dub_ai_base"],
    "external_dependencies": {
        "python": ["openai"],
    },
    "data": [
        "views/ai_model_views.xml",
        "views/res_config_settings.xml",
    ],
    "installable": True,
    "application": False,
}
