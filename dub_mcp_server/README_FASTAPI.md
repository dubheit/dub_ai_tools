# MCP Server FastAPI Integration

## Overview

The MCP Server module uses FastAPI endpoints (via OCA fastapi module) with OAuth2 authentication for secure access to Odoo data.

## Features

- FastAPI-based REST endpoints
- OAuth2 Bearer token authentication via `dub_oauth2_provider`
- SSE (Server-Sent Events) transport for MCP protocol
- Automatic OpenAPI documentation
- Type validation with Pydantic models
- Async support

## Endpoints

All endpoints are available under the `/mcp` root path:

### Public Endpoints (No Auth Required)
- `GET /mcp/health` - Health check

### MCP Protocol (OAuth2 Required)
- `GET /mcp/sse` - MCP protocol endpoint (SSE transport)

### REST API (OAuth2 Required)
- `POST /mcp/search_read` - Search and read records
- `POST /mcp/read` - Read records by IDs
- `POST /mcp/create` - Create new records
- `POST /mcp/write` - Update existing records
- `POST /mcp/unlink` - Delete records
- `POST /mcp/methods` - List available methods for a model
- `POST /mcp/execute` - Execute whitelisted methods

## Authentication

All authenticated endpoints require an OAuth2 Bearer token:

```bash
curl -X POST http://localhost:8069/mcp/search_read \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "res.partner",
    "domain": [["is_company", "=", true]],
    "fields": ["name", "email"],
    "limit": 10
  }'
```

## Setup Instructions

### 1. Install Required Modules

- `dub_oauth2_provider` - OAuth2 authentication
- `fastapi` - OCA FastAPI module

### 2. Create OAuth2 Client

Go to **Settings > Technical > OAuth2 Provider > Clients** and create a new client.

### 3. Create MCP Configuration

Go to **Settings > Technical > MCP Server** and:
- Create a new MCP Configuration
- Link it to the OAuth2 client
- Add Model Rules for accessible models

### 4. Obtain Access Token

Use OAuth2 flow to obtain an access token:
- Authorization Code flow for user authentication
- Client Credentials flow for machine-to-machine

## Example Usage

### Python Client

```python
import requests

ACCESS_TOKEN = "your_access_token_here"
BASE_URL = "http://localhost:8069/mcp"

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# Search for partners
response = requests.post(
    f"{BASE_URL}/search_read",
    headers=headers,
    json={
        "model": "res.partner",
        "domain": [["is_company", "=", True]],
        "fields": ["name", "email"],
        "limit": 10
    }
)

if response.status_code == 200:
    data = response.json()
    if data.get("ok"):
        for partner in data["result"]:
            print(f"{partner['name']}: {partner.get('email', 'N/A')}")
```

### cURL Examples

```bash
# Health check
curl http://localhost:8069/mcp/health

# Search partners
curl -X POST http://localhost:8069/mcp/search_read \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "res.partner",
    "domain": [["is_company", "=", false]],
    "fields": ["id", "name", "email"],
    "limit": 25
  }'

# Create record
curl -X POST http://localhost:8069/mcp/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "res.partner",
    "values": {"name": "New Partner", "email": "new@example.com"}
  }'
```

## Dependencies

- `fastapi` - OCA FastAPI module
- `dub_oauth2_provider` - OAuth2 authentication module
- `base` - Odoo base module

## License

OPL-1
