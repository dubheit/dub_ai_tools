{
    "name": "AI Provider - Google Gemini",
    "version": "19.0.1.0.0",
    "category": "Technical",
    "summary": "Google Gemini provider for AI Base (Pro, Flash)",
    "author": "Dubhe",
    "website": "https://www.dubhe.it",
    "license": "LGPL-3",
    "depends": ["dub_ai_base"],
    "external_dependencies": {
        "python": ["google-genai"],
    },
    "data": [
        "data/ai_model_data.xml",
        "views/ai_model_views.xml",
        "views/res_config_settings.xml",
    ],
    "installable": True,
    "application": False,
}
