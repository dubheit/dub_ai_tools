{
    "name": "AI Provider - Ollama",
    "version": "19.0.1.0.0",
    "category": "Technical",
    "summary": "Ollama provider for AI Base (local/remote, OpenAI-compatible API)",
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
