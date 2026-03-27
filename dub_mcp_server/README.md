# Dubhe MCP Server (Odoo 19.0)

Expose selected Odoo models to MCP-compatible AI assistants (Claude, Cursor, Continue, Cline, etc.) with OAuth2 authentication, granular permissions, rate limiting, and audit logging.

## Features

- OAuth2 authentication via `dub_oauth2_provider`
- Granular CRUD permissions per model
- Field denylist and domain restrictions
- Rate limiting and request throttling
- Full audit logging of all operations
- SSE transport for MCP protocol
- Bridge script for stdio transport

## Endpoints

### MCP Protocol
- `GET /mcp/sse` - MCP protocol endpoint (SSE transport)

### REST API
- `GET /mcp/health` - Health check
- `POST /mcp/search_read` - Search and read records
- `POST /mcp/read` - Read records by IDs
- `POST /mcp/create` - Create new records
- `POST /mcp/write` - Update existing records
- `POST /mcp/unlink` - Delete records
- `POST /mcp/methods` - List available methods for a model
- `POST /mcp/execute` - Execute whitelisted methods

All endpoints require OAuth2 Bearer token authentication.

## Authentication

This module uses OAuth2 authentication via `dub_oauth2_provider`.

1. Create an OAuth2 Client in **Settings > Technical > OAuth2 Provider > Clients**
2. Create an MCP Configuration linked to the OAuth2 client
3. Obtain an access token via OAuth2 flow
4. Send requests with header: `Authorization: Bearer <access_token>`

## Quick Setup

1. Install `dub_oauth2_provider` module
2. Create an OAuth2 Client for your AI application
3. Create an MCP Configuration linked to the OAuth2 client
4. Add Model Rules to define which models can be accessed
5. Configure your AI tool with the MCP endpoint: `/mcp/sse`

## MCP Tools

The following MCP tools are exposed to AI assistants:

- `list_models` - List available models and permissions
- `search` - Search records with domains and filters
- `read` - Read specific records by ID
- `create` - Create new records
- `update` - Update existing records
- `delete` - Delete records by ID

## Configuration

Go to **Settings > Technical > MCP Server** to:
- Enable/disable the server
- Add Model Rules for accessible models
- Configure field denylists
- Set domain restrictions
- Configure rate limits

## Security

- OAuth2 Bearer token authentication
- Method whitelist protection
- User context isolation
- Field denylist per model
- Domain restrictions
- Rate limiting

## Dependencies

- `base` - Odoo base module
- `fastapi` - OCA FastAPI module
- `dub_oauth2_provider` - OAuth2 authentication

## License

OPL-1
