# Copyright 2025 Dubhe Srls
# License LGPL-3

"""
Native Odoo HTTP controller for MCP SSE endpoint.
Bypasses FastAPI to enable proper streaming responses.
"""
import json
import logging
import secrets
import time
from queue import Queue, Empty
from urllib.parse import urlparse

from werkzeug.wrappers import Response

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Active SSE sessions: session_id -> session_data
#
# NOTE (multi-worker): this dict lives in the worker process memory. With
# multiple Odoo HTTP workers, an SSE stream (GET /mcp) and the matching
# POST /mcp/message may land on different workers, so the session would not
# be found. Deployments MUST enable sticky sessions (by sessionId / source
# IP) on the reverse proxy. The Streamable HTTP transport (POST /mcp) is
# stateless and not affected.
_active_sessions = {}

# Maximum SSE session duration in seconds (must be < limit_time_real in odoo.conf)
MAX_SSE_DURATION = 900  # 15 minutes


def get_config_and_user(env, auth_header):
    """Get MCP config and user from OAuth2 token."""
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, None

    token_string = auth_header[7:]
    try:
        AccessToken = env["oauth2.access_token"].sudo()
        token = AccessToken.search([
            ("token", "=", token_string),
            ("revoked", "=", False)
        ], limit=1)

        if token and token.is_valid():
            config = env["mcp.server.config"].sudo().get_by_access_token(token_string)
            return config, token.user_id.id
    except Exception as e:
        _logger.exception("Error validating OAuth2 token: %s", e)

    return None, None


class MCPController(http.Controller):
    """MCP transport controller (SSE + Streamable HTTP), native Odoo HTTP,
    bypassing the FastAPI dispatcher buffering."""

    def _origin_allowed(self, env):
        """Validate the Origin header (anti DNS-rebinding) per MCP spec.

        Browser-less MCP clients (Claude Code/Desktop, API) send no Origin
        and are allowed. A present Origin is allowed only if same-origin,
        localhost, or listed in the ``mcp.allowed_origins`` system parameter
        (comma-separated origins or hostnames). Otherwise the caller must
        get HTTP 403.
        """
        origin = request.httprequest.headers.get("Origin")
        if not origin:
            return True
        host = (request.httprequest.host or "").split(":")[0]
        parsed = urlparse(origin)
        if parsed.hostname in (host, "localhost", "127.0.0.1"):
            return True
        allowed = env["ir.config_parameter"].sudo().get_param(
            "mcp.allowed_origins", ""
        )
        allow = {a.strip() for a in allowed.split(",") if a.strip()}
        return origin in allow or (parsed.hostname and parsed.hostname in allow)

    @http.route(
        ["/mcp", "/mcp/sse"],
        type="http",
        auth="none",
        methods=["GET", "POST"],
        csrf=False,
    )
    def mcp_endpoint(self, **kwargs):
        """
        MCP endpoint supporting both SSE and Streamable HTTP transports.
        - POST: Streamable HTTP transport (stateless request/response) [canonical]
        - GET: SSE transport (persistent connection with event stream) [legacy]

        Canonical path is ``/mcp``; ``/mcp/sse`` is kept as a backward-compatible
        alias for clients configured before the rename.
        """
        env = request.env
        if not self._origin_allowed(env):
            return request.make_json_response(
                {"error": "Origin not allowed"}, status=403,
            )
        auth_header = request.httprequest.headers.get("Authorization", "")

        # Handle POST requests (Streamable HTTP transport)
        if request.httprequest.method == "POST":
            return self._handle_streamable_http(env, auth_header)

        # GET request handling (SSE transport)
        accept = request.httprequest.headers.get("Accept", "")

        # If no auth and not asking for SSE, return server info
        if not auth_header and "text/event-stream" not in accept:
            return request.make_json_response({
                "name": "Dubhe MCP Server",
                "version": "1.0.0",
                "protocol": "MCP over SSE and Streamable HTTP",
                "endpoint": "/mcp",
                "endpoint_legacy": "/mcp/sse",
                "message_endpoint": "/mcp/message",
            })

        # Validate token
        config, user_id = get_config_and_user(env, auth_header)

        if not user_id:
            return request.make_json_response(
                {"error": "Authentication required. Provide a valid OAuth2 Bearer token."},
                status=401,
                headers=[("WWW-Authenticate", "Bearer")],
            )

        # Create session
        session_id = secrets.token_urlsafe(16)
        message_queue = Queue()

        _active_sessions[session_id] = {
            "queue": message_queue,
            "config_id": config.id if config else None,
            "user_id": user_id,
            "db": env.cr.dbname,
        }
        _logger.info("Created SSE session %s for user %s", session_id, user_id)

        # Build message endpoint URL
        scheme = request.httprequest.headers.get("X-Forwarded-Proto", "http")
        host = request.httprequest.headers.get("X-Forwarded-Host", request.httprequest.host)
        message_endpoint = f"{scheme}://{host}/mcp/message?sessionId={session_id}"
        _logger.info("MCP message endpoint URL: %s", message_endpoint)

        # SSE lifetime: configurable per-config, fallback to module default.
        max_duration = MAX_SSE_DURATION
        if config and config.sse_max_duration_s:
            max_duration = config.sse_max_duration_s

        def generate():
            """Generator for SSE events - yields bytes."""
            heartbeat_count = 0
            start_time = time.time()
            try:
                # Send padding to flush buffers
                yield (": " + ("x" * 2048) + "\n\n").encode("utf-8")

                # Send endpoint event
                endpoint_event = f"event: endpoint\ndata: {message_endpoint}\n\n"
                yield endpoint_event.encode("utf-8")
                _logger.info("Sent endpoint event for native session %s", session_id)

                # Keep alive loop
                while True:
                    # Check session timeout to avoid Odoo's limit_time_real
                    elapsed = time.time() - start_time
                    if elapsed >= max_duration:
                        _logger.info(
                            "SSE session %s reached max duration (%ds), asking client to reconnect",
                            session_id, max_duration
                        )
                        yield b"event: reconnect\ndata: timeout\n\n"
                        break

                    try:
                        # Check for messages (non-blocking)
                        message = message_queue.get(timeout=30.0)
                        # Sanitize message to prevent oversized SSE responses
                        from ..services.response_sanitizer import sanitize_response
                        message = sanitize_response(message)
                        msg_event = f"event: message\ndata: {json.dumps(message)}\n\n"
                        yield msg_event.encode("utf-8")
                        _logger.info("Sent message for native session %s", session_id)
                    except Empty:
                        # Send heartbeat
                        heartbeat_count += 1
                        yield b": heartbeat\n\n"
                        _logger.debug(
                            "Sent heartbeat #%d for native session %s",
                            heartbeat_count, session_id
                        )
            except GeneratorExit:
                _logger.info("Native SSE generator exit for session %s", session_id)
            except Exception as e:
                _logger.exception("Native SSE error for session %s: %s", session_id, e)
            finally:
                _active_sessions.pop(session_id, None)
                from ..services.context_tracker import get_tracker
                get_tracker().clear_session(session_id)
                _logger.info("Cleaned up SSE session %s", session_id)

        # Create streaming response directly with werkzeug
        response = Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        response.direct_passthrough = True
        return response

    @http.route(
        "/mcp/message",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def mcp_message(self, sessionId=None, **kwargs):
        """
        Receive MCP messages for SSE sessions.
        """
        if not self._origin_allowed(request.env):
            return request.make_json_response(
                {"error": "Origin not allowed"}, status=403,
            )
        if not sessionId:
            return request.make_json_response(
                {"error": "sessionId parameter required"},
                status=400,
            )

        session = _active_sessions.get(sessionId)
        if not session:
            return request.make_json_response(
                {"error": "Invalid or expired session"},
                status=400,
            )

        try:
            body = request.httprequest.get_data(as_text=True)
            request_data = json.loads(body)
        except json.JSONDecodeError:
            error_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            }
            session["queue"].put(error_resp)
            return request.make_json_response({"status": "accepted"}, status=202)

        _logger.info(
            "Processing MCP message for session %s: method=%s",
            sessionId, request_data.get("method")
        )

        # Process MCP request with fresh environment
        env = request.env
        config = None
        if session.get("config_id"):
            config = env["mcp.server.config"].sudo().browse(session["config_id"])

        response = self._handle_mcp_request(
            env,
            request_data,
            config=config,
            user_id=session["user_id"],
            session_id=sessionId,
            transport="sse",
        )

        # Put response in queue for SSE stream
        session["queue"].put(response)

        return request.make_json_response({"status": "accepted"}, status=202)

    def _client_ip(self):
        """Best-effort real client IP for rate limiting / audit."""
        headers = request.httprequest.headers
        fwd = headers.get("X-Forwarded-For")
        if fwd:
            return fwd.split(",")[0].strip()
        return headers.get("X-Real-IP") or request.httprequest.remote_addr or ""

    def _handle_mcp_request(self, env, request_data, config=None, user_id=None,
                            session_id=None, transport="streamable_http"):
        """Handle MCP JSON-RPC request."""
        method = request_data.get("method", "")
        params = request_data.get("params", {})
        req_id = request_data.get("id")

        try:
            if method == "initialize":
                db_name = env.cr.dbname
                company = env["res.company"].sudo().browse(1)
                company_name = company.name if company.exists() else "Unknown"
                base_url = env["ir.config_parameter"].sudo().get_param("web.base.url", "")
                user_name = env.user.name if user_id else "Unknown"
                # Echo the client's protocol version when we support it,
                # otherwise advertise a recent revision (MCP spec behaviour).
                supported_protocols = {
                    "2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25",
                }
                client_proto = params.get("protocolVersion")
                protocol_version = (
                    client_proto if client_proto in supported_protocols
                    else "2025-11-25"
                )
                server_name = "Odoo MCP - %s (%s)" % (company_name, db_name)
                instructions = (
                    "You are connected to the Odoo instance '%s' "
                    "(database: %s, URL: %s). "
                    "The authenticated user is '%s'. "
                    "All operations via these tools will affect this specific "
                    "Odoo database. Be aware of this context when performing "
                    "operations."
                ) % (company_name, db_name, base_url, user_name)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": protocol_version,
                        "capabilities": {
                            "tools": {"listChanged": False},
                            "resources": {"listChanged": False},
                        },
                        "serverInfo": {
                            "name": server_name,
                            "version": "1.0.0"
                        },
                        "instructions": instructions
                    }
                }

            elif method == "initialized":
                return {"jsonrpc": "2.0", "id": req_id, "result": {}}

            elif method == "tools/list":
                from ..services.mcp_tools import get_tools_list
                tools = get_tools_list(env, config=config)
                return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

            elif method == "tools/call":
                from ..services.mcp_tools import execute_tool
                from ..services.context_tracker import get_tracker
                from ..services import authz, ratelimit
                from ..services.errors import RateLimited

                # Rate limit the live transport (per user+ip), using the
                # already-resolved config from the token.
                if config:
                    rl_ctx = authz.AuthContext(
                        user_id=user_id, login="", ip=self._client_ip()
                    )
                    try:
                        ratelimit.ensure_within_limit(
                            rl_ctx, env, config=config
                        )
                    except RateLimited as e:
                        return {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32000, "message": str(e)},
                        }

                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})
                result, tracking_info = execute_tool(
                    env, tool_name, arguments,
                    config=config, user_id=user_id,
                    return_tracking_info=True,
                    transport=transport, client_ip=self._client_ip()
                )

                # Update context tracking if session is active
                if session_id and tracking_info:
                    tracker = get_tracker()
                    for info in tracking_info:
                        tracker.track_operation(session_id, **info)

                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": result}]}
                }

                # Add _context if session has tracked records
                if session_id:
                    ctx = get_tracker().get_context(session_id)
                    if ctx:
                        response["result"]["_context"] = ctx

                return response

            elif method == "resources/list":
                from ..services.mcp_resources import get_resources_list
                resources = get_resources_list(env, config=config)
                return {
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {"resources": resources},
                }

            elif method == "resources/templates/list":
                from ..services.mcp_resources import get_resource_templates_list
                templates = get_resource_templates_list(env, config=config)
                return {
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {"resourceTemplates": templates},
                }

            elif method == "resources/read":
                from ..services.mcp_resources import read_resource
                uri = params.get("uri", "")
                content, mime_type = read_resource(
                    env, uri, config=config, user_id=user_id,
                )
                return {
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {
                        "contents": [{
                            "uri": uri,
                            "mimeType": mime_type,
                            "text": content,
                        }],
                    },
                }

            elif method == "ping":
                return {"jsonrpc": "2.0", "id": req_id, "result": {}}

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }

        except Exception as e:
            _logger.exception("Error handling MCP request: %s", e)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": "Internal server error"}
            }

    def _handle_streamable_http(self, env, auth_header):
        """
        Handle Streamable HTTP transport (POST requests).
        Stateless request/response - no session management needed.
        """
        # Validate token
        config, user_id = get_config_and_user(env, auth_header)

        if not user_id:
            return request.make_json_response(
                {"error": "Authentication required. Provide a valid OAuth2 Bearer token."},
                status=401,
                headers=[("WWW-Authenticate", "Bearer")],
            )

        # Parse request body
        try:
            body = request.httprequest.get_data(as_text=True)
            request_data = json.loads(body)
        except json.JSONDecodeError:
            return request.make_json_response({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            }, status=400)

        _logger.info(
            "Streamable HTTP request: method=%s, user=%s",
            request_data.get("method"), user_id
        )

        # Process request and return response directly
        response = self._handle_mcp_request(
            env,
            request_data,
            config=config,
            user_id=user_id,
        )

        # Sanitize tool responses to prevent oversized SSE messages
        # Skip sanitization for resources (client explicitly requested the data)
        method = request_data.get("method", "")
        if not method.startswith("resources/"):
            from ..services.response_sanitizer import sanitize_response
            response = sanitize_response(response)

        return request.make_json_response(response)
