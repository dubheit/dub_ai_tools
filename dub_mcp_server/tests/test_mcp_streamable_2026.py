# Copyright 2025 Dubhe Srls
# License LGPL-3

"""
HttpCase integration tests for the stateless MCP 2026-07-28 transport.

The pure helpers of services/mcp_protocol.py and services/elicitation.py
are covered by TransactionCase unit tests; these tests instead POST to the
real /mcp endpoint and assert on the wire responses: pre-auth discovery,
auth ordering, mirrored-header validation, the result envelope
(resultType, cache hints, serverInfo) and the MRTR input_required path.
"""
import json
import secrets
from datetime import timedelta

from odoo import fields
from odoo.tests.common import HttpCase, tagged

from odoo.addons.dub_mcp_server.services import mcp_protocol


@tagged("post_install", "-at_install")
class TestMCPStreamable2026(HttpCase):
    """End-to-end coverage of the stateless 2026-07-28 revision over HTTP."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Fresh user (no completed elicitations, so the demo_external tool
        # triggers its URL elicitation on first call).
        cls.test_user = cls.env["res.users"].create({
            "name": "MCP 2026 Test User",
            "login": "mcp_2026_test_user",
            "email": "mcp2026@example.com",
            "groups_id": [
                (4, cls.env.ref("base.group_user").id),
            ],
        })

        # OAuth2 client and access token. The token string must be set
        # explicitly: the field has no default.
        cls.oauth_client = cls.env["oauth2.client"].create({
            "name": "MCP 2026 Test Client",
            "redirect_uris": "https://localhost/callback",
        })
        cls.access_token_string = secrets.token_urlsafe(32)
        cls.access_token = cls.env["oauth2.access_token"].create({
            "token": cls.access_token_string,
            "client_id": cls.oauth_client.id,
            "user_id": cls.test_user.id,
            "expires_at": fields.Datetime.now() + timedelta(hours=1),
        })

        # MCP config bound to the token's user (get_by_access_token resolves
        # the user-linked config first), with a res.partner rule so the
        # model tools resolve.
        cls.mcp_config = cls.env["mcp.server.config"].create({
            "name": "Test MCP Config 2026",
            "active": True,
            "user_ids": [(4, cls.test_user.id)],
        })
        cls.mcp_config.write({
            "rate_limit_window_s": 60,
            "rate_limit_max_requests": 1000,
            "default_page_size": 50,
            "max_page_size": 200,
        })
        partner_model = cls.env["ir.model"].search(
            [("model", "=", "res.partner")], limit=1
        )
        cls.partner_rule = cls.env["mcp.server.model.rule"].create({
            "config_id": cls.mcp_config.id,
            "model_id": partner_model.id,
            "allow_read": True,
        })

    # -- helpers ------------------------------------------------------------

    def _headers(self, method=None, name=None, authenticated=True):
        """Build the headers a stateless 2026-07-28 client sends on POST:
        the protocol version plus the mirrored Mcp-Method/Mcp-Name."""
        headers = {
            "Content-Type": "application/json",
            mcp_protocol.MCP_PROTOCOL_VERSION_HEADER:
                mcp_protocol.MCP_VERSION_2026_07_28,
        }
        if authenticated:
            headers["Authorization"] = "Bearer %s" % self.access_token_string
        if method is not None:
            headers[mcp_protocol.MCP_METHOD_HEADER] = method
        if name is not None:
            headers[mcp_protocol.MCP_NAME_HEADER] = name
        return headers

    def _stateless_meta(self, with_capabilities=True):
        """The _meta block every stateless request carries."""
        meta = {
            mcp_protocol.META_PROTOCOL_VERSION:
                mcp_protocol.MCP_VERSION_2026_07_28,
        }
        if with_capabilities:
            meta[mcp_protocol.META_CLIENT_CAPABILITIES] = {}
        return meta

    def _post(self, payload, headers):
        return self.url_open("/mcp", data=json.dumps(payload), headers=headers)

    # -- cases ---------------------------------------------------------------

    def test_server_discover_pre_auth(self):
        """server/discover needs no bearer token: it answers 200, echoes the
        protocol version header and advertises every served revision, the
        tasks extension and the server identity."""
        payload = {"jsonrpc": "2.0", "id": 1, "method": "server/discover"}
        response = self._post(
            payload,
            self._headers(method="server/discover", authenticated=False),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get(mcp_protocol.MCP_PROTOCOL_VERSION_HEADER),
            mcp_protocol.MCP_VERSION_2026_07_28,
        )
        body = response.json()
        self.assertEqual(body["id"], 1)
        result = body["result"]
        self.assertEqual(
            set(result["supportedVersions"]),
            set(mcp_protocol.SUPPORTED_VERSIONS),
        )
        self.assertIn(
            mcp_protocol.TASKS_EXTENSION_ID,
            result["capabilities"]["extensions"],
        )
        self.assertTrue(result["serverInfo"])

    def test_tools_list_result_envelope(self):
        """tools/list on the stateless revision carries resultType
        'complete', the private cache hints and the serverInfo in _meta."""
        payload = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/list",
            "params": {"_meta": self._stateless_meta()},
        }
        response = self._post(payload, self._headers(method="tools/list"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], 2)
        result = body["result"]
        self.assertEqual(result["resultType"], "complete")
        self.assertIn("ttlMs", result)
        self.assertEqual(result["cacheScope"], "private")
        self.assertTrue(result["_meta"][mcp_protocol.META_SERVER_INFO])
        self.assertIsInstance(result["tools"], list)

    def test_missing_client_capabilities_rejected(self):
        """A stateless request whose params._meta omits the client
        capabilities block is rejected with -32021."""
        payload = {
            "jsonrpc": "2.0", "id": 3, "method": "tools/list",
            "params": {"_meta": self._stateless_meta(with_capabilities=False)},
        }
        response = self._post(payload, self._headers(method="tools/list"))
        # Transport accepted the request; the fault is at JSON-RPC level.
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], 3)
        self.assertEqual(
            body["error"]["code"], mcp_protocol.MCP_MISSING_CAPABILITY
        )

    def test_initialize_removed_on_stateless(self):
        """The initialize handshake does not exist on 2026-07-28: the server
        answers -32601 instead of negotiating."""
        payload = {
            "jsonrpc": "2.0", "id": 4, "method": "initialize",
            "params": {"_meta": self._stateless_meta()},
        }
        response = self._post(payload, self._headers(method="initialize"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], 4)
        self.assertEqual(body["error"]["code"], -32601)

    def test_mirrored_method_header_mismatch(self):
        """An Mcp-Method header disagreeing with the body method is rejected
        with -32020 and HTTP 400."""
        payload = {
            "jsonrpc": "2.0", "id": 5, "method": "tools/list",
            "params": {"_meta": self._stateless_meta()},
        }
        # The mirrored header names a different method on purpose.
        response = self._post(payload, self._headers(method="resources/list"))
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["id"], 5)
        self.assertEqual(
            body["error"]["code"], mcp_protocol.MCP_HEADER_MISMATCH
        )

    def test_get_sse_removed_on_stateless(self):
        """GET /mcp (the SSE stream) is removed on 2026-07-28: the server
        answers 405 and points at POST."""
        response = self.url_open(
            "/mcp", headers=self._headers(authenticated=False)
        )
        self.assertEqual(response.status_code, 405)
        self.assertIn("POST", response.headers.get("Allow", ""))

    def test_tools_call_elicitation_input_required(self):
        """A tools/call needing out-of-band input returns an MRTR
        input_required result with inputRequests and a requestState,
        instead of the legacy -32042 error."""
        payload = {
            "jsonrpc": "2.0", "id": 7, "method": "tools/call",
            "params": {
                "name": "demo_external",
                "arguments": {},
                "_meta": self._stateless_meta(),
            },
        }
        response = self._post(
            payload,
            self._headers(method="tools/call", name="demo_external"),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], 7)
        result = body["result"]
        self.assertEqual(result["resultType"], "input_required")
        self.assertIsInstance(result["requestState"], str)
        self.assertTrue(result["requestState"])
        input_requests = result["inputRequests"]
        self.assertEqual(len(input_requests), 1)
        self.assertEqual(input_requests[0]["method"], "elicitation/create")
        params = input_requests[0]["params"]
        self.assertEqual(params["mode"], "url")
        self.assertTrue(params["url"])
        self.assertTrue(params["message"])
