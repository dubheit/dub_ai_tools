{
    "name": "AI Provider - Anthropic Claude",
    "version": "19.0.1.2.0",
    "category": "Technical",
    "summary": "Anthropic Claude provider for AI Base, on the Anthropic API or on Amazon Bedrock / Google Cloud for EU data residency",
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
