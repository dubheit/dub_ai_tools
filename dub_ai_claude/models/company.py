from odoo import models, fields

# AWS regions served by the Bedrock EU endpoints.
AWS_EU_REGIONS = [
    ('eu-central-1', 'Europe (Frankfurt) - eu-central-1'),
    ('eu-central-2', 'Europe (Zurich) - eu-central-2'),
    ('eu-north-1', 'Europe (Stockholm) - eu-north-1'),
    ('eu-south-1', 'Europe (Milan) - eu-south-1'),
    ('eu-south-2', 'Europe (Spain) - eu-south-2'),
    ('eu-west-1', 'Europe (Ireland) - eu-west-1'),
    ('eu-west-2', 'Europe (London) - eu-west-2'),
    ('eu-west-3', 'Europe (Paris) - eu-west-3'),
]

# Google Cloud locations. Only the multi-region endpoints serve the current
# models: single regions stop at Claude Sonnet 4.6.
GCP_REGIONS = [
    ('eu', 'European Union (multi-region)'),
    ('europe-west1', 'Belgium - europe-west1'),
    ('global', 'Global (no data residency)'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    dub_ai_provider = fields.Selection(
        selection_add=[('claude', 'Anthropic Claude')],
        ondelete={'claude': 'set null'},
    )
    dub_ai_claude_route = fields.Selection(
        selection=[
            ('direct', 'Anthropic API'),
            ('bedrock', 'Amazon Bedrock (EU)'),
            ('bedrock_invoke', 'Amazon Bedrock InvokeModel (EU)'),
            ('vertex', 'Google Cloud (EU)'),
        ],
        string="Claude Route", default='direct', required=True,
        help="Anthropic API: inference runs in the US or globally, the API "
             "offers no EU inference geo.\n"
             "Amazon Bedrock and Google Cloud: requests go to the regional "
             "endpoint selected below, so data stays in that geography.\n"
             "Bedrock comes in two flavours: the Messages API endpoint, and "
             "the older InvokeModel one addressed through EU cross-region "
             "inference profiles. Which models each serves depends on the "
             "AWS account, so check both.",
    )
    dub_ai_claude_api_key = fields.Char(string="Claude API Key")
    dub_ai_claude_model_id = fields.Many2one(
        'dub.ai.model', string="Claude Model",
        domain="[('provider', '=', 'claude'), ('active', '=', True)]",
    )
    dub_ai_claude_aws_region = fields.Selection(
        selection=AWS_EU_REGIONS, string="AWS Region",
        default='eu-central-1',
        help="The region is part of the endpoint URL, so it is what keeps "
             "inference inside the chosen geography.",
    )
    dub_ai_claude_aws_access_key_id = fields.Char(
        string="AWS Access Key ID",
        help="Leave empty to use the AWS default credential chain "
             "(environment variables, instance or task role).",
    )
    dub_ai_claude_aws_secret_access_key = fields.Char(
        string="AWS Secret Access Key",
    )
    dub_ai_claude_bedrock_api_key = fields.Char(
        string="Bedrock API Key",
        help="Amazon Bedrock bearer token, used instead of the AWS keys "
             "when set.",
    )
    dub_ai_claude_gcp_project_id = fields.Char(string="Google Project ID")
    dub_ai_claude_gcp_region = fields.Selection(
        selection=GCP_REGIONS, string="Google Location", default='eu',
    )
    dub_ai_claude_gcp_credentials = fields.Text(
        string="Google Service Account Key",
        help="Service account key in JSON format. Leave empty to use the "
             "Application Default Credentials of the host.",
    )
