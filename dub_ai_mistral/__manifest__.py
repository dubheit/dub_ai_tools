{
    "name": "AI Provider - Mistral AI",
    "version": "19.0.1.0.0",
    "category": "Technical",
    "summary": "Mistral AI provider for AI Base (Large, Small, Pixtral, Codestral)",
    "author": "Dubhe",
    "website": "https://www.dubhe.it",
    "license": "LGPL-3",
    "depends": ["dub_ai_base"],
    "external_dependencies": {
        "python": ["mistralai"],
    },
    "data": [
        "data/ai_model_data.xml",
        "views/ai_model_views.xml",
        "views/res_config_settings.xml",
    ],
    "installable": True,
    "application": False,
}
