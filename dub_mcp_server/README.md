# MCP Server for Odoo

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-18.0-875A7B.svg)](https://www.odoo.com/)
[![CI](https://github.com/dubheit/dub_ai_tools/actions/workflows/test.yml/badge.svg?branch=18.0)](https://github.com/dubheit/dub_ai_tools/actions)
[![MCP](https://img.shields.io/badge/MCP-compatible-3ECFB4.svg)](https://modelcontextprotocol.io/)

Expose Odoo to **any MCP-compatible AI assistant** — Claude Desktop, Claude
Code, Cursor, Windsurf, Continue, Cline, and more — with OAuth2
authentication, per-model permissions, PII masking, rate limiting and full
audit logs.

Safe by default: every new connection is denied unless explicitly authorised.

---

## Table of Contents

- [What is MCP?](#what-is-mcp)
- [Features](#features)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Supported MCP tools](#supported-mcp-tools)
- [Tasks (async execution)](#tasks-async-execution)
- [Elicitation (URL mode)](#elicitation-url-mode)
- [REST API](#rest-api)
- [Connecting AI assistants](#connecting-ai-assistants)
- [Permission model](#permission-model)
- [PII masking](#pii-masking)
- [Rate limiting](#rate-limiting)
- [Audit log](#audit-log)
- [Security notes](#security-notes)
- [Dependencies](#dependencies)
- [Development & tests](#development--tests)
- [Roadmap](#roadmap)
- [Support](#support)
- [License](#license)

---

## What is MCP?

The **Model Context Protocol** (MCP) is an open standard developed by
Anthropic that lets AI assistants plug into external data sources and tools
in a uniform, secure way. Think of it as "USB-C for AI" — one protocol, many
servers, many clients.

This module turns your Odoo instance into an MCP *server*: AI assistants can
discover available models, search and read records, and (if allowed) create,
update or delete them. Everything runs through OAuth2 and is subject to the
same access rules you configure in Odoo.

## Features

- 🚀 **Native SSE transport** — no bridge, no proxy, no polling
- 🔐 **OAuth2 authentication** — Authorization Code + PKCE, or Client Credentials
- 🎯 **Deny-by-default** — every user must be explicitly allowed
- 🔒 **Per-model CRUD permissions** — `read`, `create`, `write`, `unlink`
- 🎭 **PII masking** — hide or obfuscate sensitive fields in AI responses
- 🚫 **Field denylist** — block fields like `password`, `api_key`, `token` (always)
- 🔍 **Domain restrictions** — scope what records an AI assistant can see
- ⚙️ **Method execution** — call whitelisted model methods safely
- ⏱️ **Rate limiting** — protect your instance from runaway agents
- 📊 **Full audit log** — every call is recorded with status and excerpt
- 🪵 **Optional `get_logs` tool** — let trusted AI clients fetch server logs
- 🌐 **REST API** — drop-in alternative for non-MCP clients
- 🧩 **Tasks** — durable async execution for long-running tool calls (MCP 2025-11-25)
- 🪪 **URL-mode elicitation** — collect sensitive values via a secure Odoo web page
- 🖼️ **Tool & resource icons** — richer client UI metadata

This module targets **MCP protocol revision 2025-11-25** (it echoes the client's
version on `initialize` and falls back to the latest it supports). The canonical
endpoint is **`/mcp`** (the legacy `/mcp/sse` still works as an alias).

## Architecture

```text
                           ┌──────────────────────────────────────┐
                           │          Odoo + this module          │
                           │                                      │
 ┌───────────────┐ OAuth2  │  ┌──────────────────┐                │
 │  AI assistant │ Bearer  │  │ dub_oauth2_      │                │
 │ (Claude, etc.)├─────────┼─>│ provider         │                │
 └──────┬────────┘  token  │  └─────────┬────────┘                │
        │                  │            │ validate                │
        │ MCP / SSE        │            v                         │
        └──────────────────┼─>┌──────────────────┐  ┌───────────┐ │
                           │  │ MCP router + SSE ├─>│ authz     │ │
                           │  └─────────┬────────┘  └─────┬─────┘ │
                           │            │                 │       │
                           │            v                 v       │
                           │  ┌──────────────────┐  ┌───────────┐ │
                           │  │ adapter / tools  │  │ ratelimit │ │
                           │  └─────────┬────────┘  └───────────┘ │
                           │            │                         │
                           │            v                         │
                           │       Odoo ORM, views, records       │
                           └──────────────────────────────────────┘
```

The MCP endpoint is `/mcp` (with `/mcp/sse` kept as a backward-compatible
alias for older clients). It speaks the MCP JSON-RPC protocol. Every request
is authenticated via OAuth2, authorised against the MCP configuration bound
to the user or to the client, rate-limited, then delegated to a tool handler
that uses the Odoo ORM with the user's own permissions.

The same endpoint also accepts the **Streamable HTTP** transport: a `POST`
returns a single `application/json` response (pure stateless, no
`Mcp-Session-Id`, no server-initiated streaming). This is sufficient for the
CRUD-style tools exposed here; the persistent SSE `GET` stream is used for
server-pushed messages. On `initialize` the server echoes the client's
`protocolVersion` when supported, otherwise advertises a recent revision.

## Quick start

### 1. Install dependencies

```bash
pip install fastapi pydantic extendable a2wsgi parse-accept-language \
            python-multipart ujson httpx
```

You also need the OCA modules [`fastapi`](https://github.com/OCA/rest-framework)
and [`dub_oauth2_provider`](https://github.com/dubheit/dub_api_tools) on your
addons path.

### 2. Install the module

```bash
odoo -c odoo.conf -d your_db -i dub_mcp_server --stop-after-init --http-port=0
```

### 3. Configure OAuth2

Follow the [dub_oauth2_provider README](https://github.com/dubheit/dub_api_tools)
to create an OAuth2 client for your AI tool. The module fully supports
OAuth2 Dynamic Client Registration (RFC 7591), so many AI clients can
register themselves.

### 4. Create an MCP configuration

Go to **Settings → Technical → MCP Server → Configurations** and create a
new configuration:

1. Link it to either a **user** (per-user config) or an **OAuth2 client**
   (per-integration config). If both are set, user takes precedence.
2. Add **Model Rules** — one per Odoo model you want to expose — and pick
   which operations are allowed.
3. Optionally mark specific fields as **PII** (they will be masked in
   responses) or add them to the **field denylist** (they will be hidden).
4. Configure the rate-limit window, request timeout and retention for the
   audit log.

The module ships with sensible defaults in demo mode (`mcp_server_dev_config`)
but production installations require an explicit configuration — **nothing is
exposed by default**.

### 5. Connect your AI assistant

Point your AI client at:

```
https://your-odoo.example.com/mcp
```

(`/mcp/sse` still works as a legacy alias.)

and provide the OAuth2 client credentials. See
[Connecting AI assistants](#connecting-ai-assistants) for per-tool snippets.

## Supported MCP tools

| Tool | Purpose |
|------|---------|
| `list_models` | List all models the caller is allowed to use and the operations permitted on each |
| `list_fields` | Describe the fields of a model (type, label, required/readonly), denied fields hidden |
| `search` | Search records using an Odoo domain; pagination, sort and field selection supported |
| `read` | Read records by IDs with field filtering |
| `create` | Create a record (subject to `allow_create`) |
| `update` | Update records by IDs (subject to `allow_write`) |
| `delete` | Delete records by IDs (subject to `allow_unlink`) |
| `name_search` | Resolve records by display name (typeahead-style lookup) |
| `get_selection_values` | List the values/labels of a selection field |
| `domain_validate` | Validate an Odoo domain against a model without executing it |
| `get_record_actions` | List the actions available on a record |
| `list_methods` | Discover whitelisted methods of a model |
| `call_method` | Call a whitelisted method with positional or keyword arguments |
| `get_logs` *(optional)* | Tail recent Odoo logs for debugging (requires `allow_logs_tool`) |

Denied fields (per-rule `field_denylist` plus the always-denied
`password, api_key, token, secret`) are stripped from every tool response,
on both the MCP and REST transports.

Tools also expose `icons` metadata, and tools that may run long advertise
`execution.taskSupport` (see Tasks below).

## Tasks (async execution)

For long-running tool calls the server supports **MCP tasks** (revision
2025-11-25). A client augments a `tools/call` with a `task` field; the server
stores a durable **`mcp.server.task`** (bound to the authenticated user, with a
secure id and a TTL), returns a `CreateTaskResult` immediately, and the client
polls `tasks/get` / `tasks/result` (also `tasks/list`, `tasks/cancel`).

- Eligible tools declare `execution.taskSupport` (`optional`/`required`); the
  rest default to `forbidden`. Currently `search` and `call_method` are
  `optional`.
- Execution is **asynchronous via `ir.cron`** (`_cron_run_pending`) with an
  atomic claim, so a task runs exactly once. Expired tasks are purged by a cron.
- Install the optional **`dub_mcp_async_task`** module (depends on OCA
  `queue_job`) to run tasks immediately via queue_job instead of the cron.

> Note: tasks are experimental in the MCP spec; not all clients use them yet.

## Elicitation (URL mode)

A tool can ask the user for an out-of-band value (e.g. a third-party secret)
without exposing it to the AI client. The tool raises an elicitation; the server
returns a JSON-RPC `-32042` error with a URL pointing to a secure Odoo web page
(`/mcp/elicitation/<id>`). The user opens it (logged into Odoo — the page
enforces that the logged-in user is the elicitation's owner, anti-phishing),
submits the value (stored bound to their identity), then the client retries the
original call.

The `demo_external` tool demonstrates the full flow end to end.

> Form-mode elicitation (server-initiated input *during* a call) is **not yet
> implemented** — see [Roadmap](#roadmap).

## REST API

For tools that do not yet speak MCP, the module also exposes a small REST
API under `/mcp`:

| Path | Method | Purpose |
|------|--------|---------|
| `/mcp/health` | GET | Liveness probe (no auth) |
| `/mcp/search_read` | POST | Search + read in one call |
| `/mcp/read` | POST | Read by IDs |
| `/mcp/create` | POST | Create a record |
| `/mcp/write` | POST | Update by IDs |
| `/mcp/unlink` | POST | Delete by IDs |
| `/mcp/methods` | POST | List allowed methods |
| `/mcp/execute` | POST | Call a whitelisted method |

All endpoints except `/mcp/health` require an `Authorization: Bearer
<token>` header.

Example:

```bash
curl -X POST https://your-odoo.example.com/mcp/search_read \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "res.partner",
    "domain": [["is_company", "=", true]],
    "fields": ["id", "name", "email"],
    "limit": 25
  }'
```

## Connecting AI assistants

### Claude Desktop / Claude Code

Add to `claude_desktop_config.json` (Desktop) or your Claude Code settings:

```json
{
  "mcpServers": {
    "odoo": {
      "url": "https://your-odoo.example.com/mcp",
      "transport": "http"
    }
  }
}
```

`transport: "http"` selects Streamable HTTP (recommended; SSE is deprecated
upstream). The legacy SSE setup (`"transport": "sse"` against `/mcp/sse`)
still works for older clients.

Claude supports Dynamic Client Registration. On first use it will open your
browser for the consent page, then reuse the granted token.

### Cursor / Windsurf / Continue / Cline

All follow the same pattern — point them at the `/mcp` URL. Refer to
your tool's MCP documentation for the exact config key.

### Custom Python client

```python
import requests

TOKEN = "your_access_token"
URL = "https://your-odoo.example.com/mcp/search_read"

r = requests.post(
    URL,
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={
        "model": "sale.order",
        "domain": [["state", "=", "sale"]],
        "fields": ["name", "partner_id", "amount_total"],
        "limit": 10,
    },
)
for order in r.json()["result"]:
    print(order)
```

## Permission model

The module resolves the active configuration following this priority:

1. **User-specific** — a configuration where `user_ids` contains the current user
2. **OAuth2 client-specific** — a configuration linked to the OAuth2 client of the token
3. **None** — request is denied

Within a matching configuration, operations are governed by the **Model
Rules** (one record per model) with four boolean flags: `allow_read`,
`allow_create`, `allow_write`, `allow_unlink`.

All Odoo-level ACLs and record rules still apply on top of this: the MCP
config can only *narrow* what the underlying user could do, never expand it.

## PII masking

For every model rule you can flag fields as PII. Their values will be masked
in responses — for example `d****e@domain.com` instead of the full address.
Useful when giving AI assistants access to contacts or partner records.

The following fields are **always** denied, regardless of configuration:

```text
password, api_key, token, secret
```

## Rate limiting

Configurable per MCP configuration:

- **Window** (seconds) — sliding window size
- **Max requests** — requests allowed per window per `user_id`/`ip`

The limit is enforced on **every transport** — native SSE, Streamable HTTP
(`POST /mcp`) and the REST API — using the configuration resolved from
the caller's token.

The limiter is in-memory **per worker process** and resets on server
restart. With multiple Odoo workers the effective ceiling is up to
`workers × max_requests`; for strict enforcement put a limiter on the
reverse proxy or move the counters to a shared store. Likewise, native SSE
streams keep their session in worker memory, so multi-worker deployments
**must** enable sticky sessions (by `sessionId`/source IP) on the proxy. The
Streamable HTTP transport is stateless and needs no stickiness.

## Audit log

Every request is logged to `mcp.server.audit` with:

- timestamp, user, IP, transport
- operation (`discover`, `search`, `read`, `create`, ...)
- model and record IDs
- `status` (`success` or `fail`)
- truncated request excerpt and error excerpt

Available at **Settings → Technical → MCP Server → Audit Log**. A cron job
applies the configured retention.

## Security notes

- **Deny by default** — installing the module does not expose anything.
- **OAuth2 Bearer tokens only** — no basic auth, no shared secrets in query
  strings.
- **Method whitelist** — AI clients cannot call arbitrary methods; every
  callable is explicitly granted per model rule.
- **User context isolation** — MCP tools run with the token owner's ORM
  context and respect record rules.
- **Domain restrictions** — per-model domain clause AND-ed with any client
  query.
- **Full audit log** with retention — traceability for compliance.
- **PII masking and field denylist** — extra safety net on top of ACLs.

## Dependencies

- [`base`](https://github.com/odoo/odoo) — Odoo core
- [`fastapi`](https://github.com/OCA/rest-framework) — OCA FastAPI integration
- [`dub_oauth2_provider`](https://github.com/dubheit/dub_api_tools) — OAuth2 authentication

Python runtime:

- `fastapi >= 0.110.0`
- `pydantic >= 2.0.0`
- `extendable >= 0.0.4`
- `a2wsgi >= 1.10.6`
- `parse-accept-language`
- `python-multipart`
- `ujson`
- `httpx`

## Development & tests

```bash
# Run the full module test suite
odoo -c odoo.conf -d test_db --test-tags /dub_mcp_server \
     --stop-after-init --http-port=0
```

CI runs on every push via GitHub Actions against PostgreSQL 16 and Python
3.12, installing OCA `rest-framework` and `web-api` plus `dub_api_tools` as
dependencies.

## Roadmap

Implemented from MCP 2025-11-25: canonical `/mcp` endpoint, Origin validation,
tool/resource icons, tasks (cron + optional queue_job bridge), URL-mode
elicitation.

Not yet implemented:

- **Form-mode elicitation** — server-initiated input *during* a tool call.
  Requires a bidirectional channel (the Streamable HTTP POST is single-response):
  the planned approach is via tasks `input_required` + an SSE stream on
  `tasks/result`. Higher complexity/risk; deferred.
- **OIDC discovery** and **OAuth Client ID Metadata Documents** — these live in
  `dub_oauth2_provider`, not in this module.
- **Sampling** — intentionally skipped (no real use case for a CRUD server).
- **Multi-worker shared state** — SSE sessions and rate-limit counters are
  per-process; use sticky sessions / a proxy-side limiter, or move to a shared
  store (documented in [Rate limiting](#rate-limiting)).

## Support

- **Website:** [dubhe.it](https://dubhe.it)
- **Email:** [support@dubhe.it](mailto:support@dubhe.it)
- **Issues:** [github.com/dubheit/dub_ai_tools/issues](https://github.com/dubheit/dub_ai_tools/issues)

## License

LGPL-3. See [`LICENSE`](./LICENSE) for the full text.

Copyright © 2025 Dubhe Srls.
