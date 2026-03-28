{
    "name": "AI Provider - OpenAI",
    "version": "19.0.1.0.0",
    "category": "Technical",
    "summary": "OpenAI provider for AI Base (GPT-4o, o1, o3, o4)",
    "author": "Dubhe",
    "website": "https://www.dubhe.it",
    "license": "LGPL-3",
    "depends": ["dub_ai_base"],
    "external_dependencies": {
        "python": ["openai"],
    },
    "data": [
        "data/ai_model_data.xml",
        "views/ai_model_views.xml",
        "views/res_config_settings.xml",
    ],
    "installable": True,
    "application": False,
}
