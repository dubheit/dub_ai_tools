# Copyright 2025 Dubhe Srls
# License LGPL-3

"""
Test the MCP protocol revision registry and message builders.
Unit tests calling services.mcp_protocol and the MRTR elicitation helpers
directly, without HTTP.
"""
import base64

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.dub_mcp_server.services import elicitation, mcp_protocol


@tagged("post_install", "-at_install")
class TestMCPProtocol(TransactionCase):
    """Verify profile resolution, result envelopes, mirrored-header
    validation and the server/discover builder of mcp_protocol."""

    def setUp(self):
        super().setUp()
        self.stateless = mcp_protocol.get_profile(
            mcp_protocol.MCP_VERSION_2026_07_28
        )
        self.legacy = mcp_protocol.get_profile(mcp_protocol.MCP_DEFAULT_VERSION)

    # -- profile registry ------------------------------------------------

    def test_profiles_flags(self):
        """The 2026-07-28 profile is stateless; legacy ones are not."""
        self.assertTrue(self.stateless.stateless)
        self.assertEqual(self.stateless.result_type, "complete")
        self.assertFalse(self.stateless.supports_sessions)
        self.assertTrue(self.stateless.has_tasks_extension)
        self.assertTrue(self.stateless.uses_mrtr)
        for version in mcp_protocol.SESSION_VERSIONS:
            profile = mcp_protocol.get_profile(version)
            self.assertFalse(profile.stateless)
            self.assertIsNone(profile.result_type)
            self.assertTrue(profile.supports_sessions)
            self.assertFalse(profile.has_tasks_extension)
            self.assertFalse(profile.uses_mrtr)

    def test_supported_versions_order(self):
        """The stateless revision is advertised first."""
        self.assertEqual(
            mcp_protocol.SUPPORTED_VERSIONS[0],
            mcp_protocol.MCP_VERSION_2026_07_28,
        )
        for version in mcp_protocol.SESSION_VERSIONS:
            self.assertIn(version, mcp_protocol.SUPPORTED_VERSIONS)
        self.assertNotIn(
            mcp_protocol.MCP_VERSION_2026_07_28, mcp_protocol.SESSION_VERSIONS
        )

    def test_get_profile_fallback(self):
        """Unknown/empty versions resolve to the default legacy profile."""
        self.assertEqual(
            mcp_protocol.get_profile("1999-01-01").version,
            mcp_protocol.MCP_DEFAULT_VERSION,
        )
        self.assertEqual(
            mcp_protocol.get_profile(None).version,
            mcp_protocol.MCP_DEFAULT_VERSION,
        )

    # -- resolve_profile --------------------------------------------------

    def test_resolve_meta_only(self):
        """The version in _meta selects the profile."""
        profile, error = mcp_protocol.resolve_profile(
            {"_meta": {
                mcp_protocol.META_PROTOCOL_VERSION:
                    mcp_protocol.MCP_VERSION_2026_07_28,
            }},
            {},
        )
        self.assertIsNone(error)
        self.assertTrue(profile.stateless)

    def test_resolve_header_only(self):
        """The MCP-Protocol-Version header selects the profile."""
        profile, error = mcp_protocol.resolve_profile(
            {},
            {mcp_protocol.MCP_PROTOCOL_VERSION_HEADER:
                 mcp_protocol.MCP_VERSION_2026_07_28},
        )
        self.assertIsNone(error)
        self.assertTrue(profile.stateless)

    def test_resolve_meta_and_header_agree(self):
        """_meta and header both present and equal resolve fine."""
        version = mcp_protocol.MCP_VERSION_2026_07_28
        profile, error = mcp_protocol.resolve_profile(
            {"_meta": {mcp_protocol.META_PROTOCOL_VERSION: version}},
            {mcp_protocol.MCP_PROTOCOL_VERSION_HEADER: version},
        )
        self.assertIsNone(error)
        self.assertEqual(profile.version, version)

    def test_resolve_absent_defaults_legacy(self):
        """A request declaring no version gets the legacy default profile:
        the stateless revision must be declared explicitly."""
        profile, error = mcp_protocol.resolve_profile({}, {})
        self.assertIsNone(error)
        self.assertFalse(profile.stateless)
        self.assertEqual(profile.version, mcp_protocol.MCP_DEFAULT_VERSION)

    def test_resolve_mismatch_error(self):
        """Diverging _meta and header versions are rejected with -32020."""
        profile, error = mcp_protocol.resolve_profile(
            {"_meta": {
                mcp_protocol.META_PROTOCOL_VERSION:
                    mcp_protocol.MCP_VERSION_2026_07_28,
            }},
            {mcp_protocol.MCP_PROTOCOL_VERSION_HEADER:
                 mcp_protocol.MCP_VERSION_2025_11_25},
        )
        self.assertIsNone(profile)
        self.assertEqual(
            error["error"]["code"], mcp_protocol.MCP_HEADER_MISMATCH
        )

    def test_resolve_unsupported_error(self):
        """An unknown version is rejected with -32022 and the supported list."""
        profile, error = mcp_protocol.resolve_profile(
            {},
            {mcp_protocol.MCP_PROTOCOL_VERSION_HEADER: "2030-01-01"},
        )
        self.assertIsNone(profile)
        self.assertEqual(
            error["error"]["code"],
            mcp_protocol.MCP_UNSUPPORTED_PROTOCOL_VERSION,
        )
        self.assertEqual(error["error"]["data"]["requested"], "2030-01-01")
        self.assertEqual(
            error["error"]["data"]["supported"],
            list(mcp_protocol.SUPPORTED_VERSIONS),
        )

    # -- make_result_envelope ---------------------------------------------

    def test_envelope_stateless(self):
        """The stateless profile adds resultType, cache hints and serverInfo."""
        envelope = mcp_protocol.make_result_envelope(
            {"tools": []}, self.stateless, "tools/list"
        )
        self.assertEqual(envelope["resultType"], "complete")
        self.assertEqual(envelope["ttlMs"], 60000)
        self.assertEqual(envelope["cacheScope"], "private")
        self.assertEqual(
            envelope["_meta"][mcp_protocol.META_SERVER_INFO],
            mcp_protocol.SERVER_INFO,
        )
        self.assertEqual(envelope["tools"], [])

    def test_envelope_overrides_handler_result_type(self):
        """A handler-set resultType is overridden by the transport - except
        an MRTR input_required, which is preserved so the pending input
        request is not silently dropped."""
        envelope = mcp_protocol.make_result_envelope(
            {"resultType": "input_required", "inputRequests": []},
            self.stateless,
            "tools/call",
        )
        self.assertEqual(envelope["resultType"], "input_required")
        self.assertEqual(envelope["inputRequests"], [])
        envelope = mcp_protocol.make_result_envelope(
            {"resultType": "bogus", "content": []},
            self.stateless,
            "tools/call",
        )
        self.assertEqual(envelope["resultType"], "complete")

    def test_envelope_merges_existing_meta(self):
        """Existing _meta keys are preserved next to serverInfo."""
        envelope = mcp_protocol.make_result_envelope(
            {"_meta": {"custom/key": 1}}, self.stateless, "ping"
        )
        self.assertEqual(envelope["_meta"]["custom/key"], 1)
        self.assertIn(mcp_protocol.META_SERVER_INFO, envelope["_meta"])

    def test_envelope_cache_hints_only_on_listed_methods(self):
        """Cache hints apply only to the cacheable methods."""
        hinted = mcp_protocol.make_result_envelope(
            {}, self.stateless, "server/discover"
        )
        self.assertEqual(hinted["ttlMs"], 300000)
        self.assertEqual(hinted["cacheScope"], "public")
        plain = mcp_protocol.make_result_envelope(
            {}, self.stateless, "tools/call"
        )
        self.assertNotIn("ttlMs", plain)
        self.assertNotIn("cacheScope", plain)

    def test_envelope_legacy_passthrough(self):
        """Legacy profiles get their result back unchanged (identity)."""
        result = {"tools": [], "_meta": {"custom/key": 1}}
        self.assertIs(
            mcp_protocol.make_result_envelope(result, self.legacy, "tools/list"),
            result,
        )

    # -- validate_mirrored_headers ----------------------------------------

    def test_mirrored_headers_match(self):
        """Headers agreeing with the body pass validation."""
        error = mcp_protocol.validate_mirrored_headers(
            "tools/call",
            {"name": "search_read"},
            {mcp_protocol.MCP_METHOD_HEADER: "tools/call",
             mcp_protocol.MCP_NAME_HEADER: "search_read"},
        )
        self.assertIsNone(error)

    def test_mirrored_headers_absent(self):
        """Headers the client did not send are not faulted."""
        self.assertIsNone(
            mcp_protocol.validate_mirrored_headers("tools/call",
                                                   {"name": "search_read"}, {})
        )

    def test_mirrored_headers_mismatch(self):
        """A header contradicting the body is rejected with -32020."""
        error = mcp_protocol.validate_mirrored_headers(
            "tools/call",
            {"name": "search_read"},
            {mcp_protocol.MCP_METHOD_HEADER: "tools/list"},
        )
        self.assertEqual(
            error["error"]["code"], mcp_protocol.MCP_HEADER_MISMATCH
        )
        error = mcp_protocol.validate_mirrored_headers(
            "resources/read",
            {"uri": "odoo://models"},
            {mcp_protocol.MCP_NAME_HEADER: "odoo://other"},
        )
        self.assertEqual(
            error["error"]["code"], mcp_protocol.MCP_HEADER_MISMATCH
        )

    def test_mirrored_headers_base64_sentinel(self):
        """=?base64?...?= sentinel values are decoded before comparing."""
        encoded = "=?base64?%s?=" % base64.b64encode(
            "odoo://models".encode("utf-8")
        ).decode("ascii")
        self.assertIsNone(
            mcp_protocol.validate_mirrored_headers(
                "resources/read",
                {"uri": "odoo://models"},
                {mcp_protocol.MCP_NAME_HEADER: encoded},
            )
        )

    def test_mirrored_headers_malformed_sentinel(self):
        """A malformed base64 sentinel counts as a mismatch."""
        error = mcp_protocol.validate_mirrored_headers(
            "resources/read",
            {"uri": "odoo://models"},
            {mcp_protocol.MCP_NAME_HEADER: "=?base64?!!!not-b64!!!?="},
        )
        self.assertEqual(
            error["error"]["code"], mcp_protocol.MCP_HEADER_MISMATCH
        )

    # -- make_discover_result ----------------------------------------------

    def test_discover_result_content(self):
        """server/discover advertises every served revision, the minimal
        capabilities (no core tasks) and the server identity."""
        result = mcp_protocol.make_discover_result()
        self.assertEqual(
            result["supportedVersions"], list(mcp_protocol.SUPPORTED_VERSIONS)
        )
        self.assertEqual(result["serverInfo"], mcp_protocol.SERVER_INFO)
        self.assertIn("tools", result["capabilities"])
        self.assertIn("resources", result["capabilities"])
        self.assertNotIn("tasks", result["capabilities"])

    def test_discover_advertises_tasks_extension(self):
        """server/discover advertises tasks as the negotiated extension
        io.modelcontextprotocol/tasks with the spec-shaped (empty) object."""
        result = mcp_protocol.make_discover_result()
        extensions = result["capabilities"]["extensions"]
        self.assertEqual(
            extensions, {mcp_protocol.TASKS_EXTENSION_ID: {}}
        )

    # -- tasks extension negotiation (2026-07-28) ---------------------------

    def test_client_supports_tasks_legacy(self):
        """Legacy revisions keep tasks as a core capability: every client is
        assumed to accept them, with or without a declaration."""
        self.assertTrue(mcp_protocol.client_supports_tasks({}, self.legacy))
        self.assertTrue(mcp_protocol.client_supports_tasks(
            {"_meta": {
                mcp_protocol.META_CLIENT_CAPABILITIES: {
                    "extensions": {mcp_protocol.TASKS_EXTENSION_ID: {}},
                },
            }},
            self.legacy,
        ))

    def test_client_supports_tasks_stateless(self):
        """The stateless revision serves tasks only to clients declaring the
        extension in the _meta client capabilities."""
        self.assertFalse(mcp_protocol.client_supports_tasks({}, self.stateless))
        self.assertFalse(mcp_protocol.client_supports_tasks(
            {"_meta": {
                mcp_protocol.META_CLIENT_CAPABILITIES: {"extensions": {}},
            }},
            self.stateless,
        ))
        self.assertFalse(mcp_protocol.client_supports_tasks(
            {"_meta": {
                mcp_protocol.META_CLIENT_CAPABILITIES: {
                    "extensions": {"io.modelcontextprotocol/skills": {}},
                },
            }},
            self.stateless,
        ))
        self.assertTrue(mcp_protocol.client_supports_tasks(
            {"_meta": {
                mcp_protocol.META_CLIENT_CAPABILITIES: {
                    "extensions": {mcp_protocol.TASKS_EXTENSION_ID: {}},
                },
            }},
            self.stateless,
        ))

    def test_task_method_allowed_legacy(self):
        """Legacy revisions route the 2025-11-25 core task method set."""
        for method in ("tasks/list", "tasks/get", "tasks/result",
                       "tasks/cancel"):
            self.assertTrue(
                mcp_protocol.task_method_allowed(method, self.legacy, True)
            )
        # tasks/update does not exist before 2026-07-28.
        self.assertFalse(
            mcp_protocol.task_method_allowed("tasks/update", self.legacy, True)
        )

    def test_task_method_allowed_stateless(self):
        """The stateless revision routes only the polling method set, and
        only when the extension was negotiated."""
        for method in ("tasks/get", "tasks/cancel", "tasks/update"):
            self.assertTrue(
                mcp_protocol.task_method_allowed(method, self.stateless, True)
            )
        # Removed in 2026-07-28: tasks/list and the blocking tasks/result.
        for method in ("tasks/list", "tasks/result"):
            self.assertFalse(
                mcp_protocol.task_method_allowed(method, self.stateless, True)
            )
        # Without the extension no tasks/* method is served at all.
        for method in ("tasks/get", "tasks/cancel", "tasks/update"):
            self.assertFalse(
                mcp_protocol.task_method_allowed(method, self.stateless, False)
            )

    def test_get_tools_list_task_annotation_gating(self):
        """The execution.taskSupport annotation follows the negotiation."""
        from odoo.addons.dub_mcp_server.services.mcp_tools import get_tools_list

        def task_annotations(tools):
            return {
                tool["name"]: tool["execution"]["taskSupport"]
                for tool in tools if "execution" in tool
            }

        # Default (legacy behaviour): task-capable tools are annotated.
        tools = get_tools_list(self.env, config=None)
        self.assertEqual(
            task_annotations(tools),
            {"search": "optional", "call_method": "optional"},
        )
        # A stateless client without the extension gets no annotation.
        tools = get_tools_list(self.env, config=None, tasks_accepted=False)
        self.assertEqual(task_annotations(tools), {})

    # -- tasks extension serialization (2026-07-28) ----------------------

    def _make_task(self, **values):
        """Create a working task record and optionally write extra values."""
        task = self.env["mcp.server.task"].create_task(
            self.env.user.id, "search", {"model": "res.partner"},
        )
        if values:
            task.write(values)
        return task

    def test_task_dict_v2_field_names(self):
        """The 2026 Task object uses the 2026 field names (ttlMs,
        pollIntervalMs); the legacy names do not leak in."""
        task = self._make_task()
        data = task.to_task_dict_v2()
        self.assertEqual(data["taskId"], task.task_id)
        self.assertEqual(data["status"], "working")
        self.assertEqual(data["ttlMs"], task.ttl_ms)
        self.assertEqual(data["pollIntervalMs"], task.poll_interval_ms)
        # No status message on a fresh working task -> omitted.
        self.assertNotIn("statusMessage", data)
        for legacy_name in ("ttl", "pollInterval", "createdAt",
                            "lastUpdatedAt"):
            self.assertNotIn(legacy_name, data)

    def test_task_dict_legacy_shape_unchanged(self):
        """The legacy Task object keeps its 2025-11-25 shape bit-for-bit."""
        task = self._make_task()
        data = task.to_task_dict()
        self.assertEqual(
            set(data),
            {"taskId", "status", "statusMessage", "createdAt",
             "lastUpdatedAt", "ttl", "pollInterval"},
        )
        self.assertEqual(data["ttl"], task.ttl_ms)
        self.assertNotIn("ttlMs", data)

    def test_task_dict_v2_completed_inlines_result(self):
        """A completed task inlines the CallToolResult under ``result``."""
        task = self._make_task(
            status="completed", result="done!", is_error=False,
        )
        data = task.to_task_dict_v2()
        self.assertEqual(
            data["result"]["content"], [{"type": "text", "text": "done!"}]
        )
        self.assertFalse(data["result"]["isError"])
        self.assertNotIn("error", data)

    def test_task_dict_v2_failed_inlines_error(self):
        """A failed task inlines a JSON-RPC error object under ``error``."""
        task = self._make_task(status="failed", status_message="boom")
        data = task.to_task_dict_v2()
        self.assertEqual(data["error"]["code"], -32603)
        self.assertEqual(data["error"]["message"], "boom")
        self.assertEqual(data["statusMessage"], "boom")
        self.assertNotIn("result", data)

    def test_envelope_preserves_task_result_type(self):
        """A handler-set resultType 'task' (CreateTaskResult) survives the
        stateless envelope, like the MRTR input_required."""
        envelope = mcp_protocol.make_result_envelope(
            {"resultType": "task", "task": {"taskId": "abc"}},
            self.stateless,
            "tools/call",
        )
        self.assertEqual(envelope["resultType"], "task")
        self.assertEqual(envelope["task"], {"taskId": "abc"})

    def test_task_method_allowed_stateless_routes_update(self):
        """tasks/update stays routed on the stateless profile once the
        extension is accepted (the callee acknowledges it as a no-op)."""
        self.assertTrue(
            mcp_protocol.task_method_allowed(
                "tasks/update", self.stateless, True
            )
        )
        self.assertFalse(
            mcp_protocol.task_method_allowed(
                "tasks/update", self.stateless, False
            )
        )

    # -- MRTR (elicitation as input_required, 2026-07-28) -------------------

    def test_build_input_required_result_shape(self):
        """URL elicitations become elicitation/create input requests."""
        result = elicitation.build_input_required_result([{
            "mode": "url",
            "elicitationId": "abc123",
            "url": "https://odoo.example/mcp/elicitation/abc123",
            "message": "Provide your demo secret to continue.",
        }])
        self.assertEqual(result["resultType"], "input_required")
        self.assertEqual(len(result["inputRequests"]), 1)
        request = result["inputRequests"][0]
        self.assertEqual(request["method"], "elicitation/create")
        self.assertEqual(request["params"]["mode"], "url")
        self.assertEqual(
            request["params"]["url"],
            "https://odoo.example/mcp/elicitation/abc123",
        )
        self.assertEqual(
            request["params"]["message"],
            "Provide your demo secret to continue.",
        )
        # The elicitationId field was removed in 2026-07-28; correlation goes
        # through requestState instead.
        self.assertNotIn("elicitationId", request["params"])

    def test_request_state_round_trip(self):
        """requestState encodes the elicitation ids opaquely and back."""
        token = elicitation.encode_request_state(["abc", "def"])
        self.assertIsInstance(token, str)
        self.assertNotIn("abc", token)
        self.assertEqual(
            elicitation.decode_request_state(token), ["abc", "def"]
        )

    def test_extract_request_state(self):
        """requestState is read from the request params (or the arguments)."""
        token = elicitation.encode_request_state(["abc"])
        self.assertEqual(
            elicitation.extract_request_state({"requestState": token}),
            ["abc"],
        )
        self.assertEqual(
            elicitation.extract_request_state(
                {"arguments": {"requestState": token}}
            ),
            ["abc"],
        )
        self.assertEqual(elicitation.extract_request_state({}), [])
        self.assertEqual(
            elicitation.extract_request_state({"requestState": "not-ours"}),
            [],
        )

    def test_strip_mrtr_fields(self):
        """MRTR fields echoed on a retry never reach the tool arguments."""
        stripped = elicitation.strip_mrtr_fields({
            "requestState": "xyz",
            "inputResponses": [{"action": "accept"}],
            "model": "res.partner",
        })
        self.assertEqual(stripped, {"model": "res.partner"})

    def test_mrtr_retry_pending(self):
        """A retry correlating to a pending elicitation resolves to a fresh
        input_required result carrying the same URL."""
        rec = self.env["mcp.server.elicitation"].create_pending(
            self.env.user.id, "demo_secret", "Provide your demo secret."
        )
        values, pending = elicitation.resolve_mrtr_retry(
            self.env, self.env.user.id, [rec.elicitation_id]
        )
        self.assertEqual(values, {})
        self.assertEqual(len(pending), 1)
        result = elicitation.build_input_required_result(pending)
        self.assertEqual(result["resultType"], "input_required")
        self.assertEqual(
            elicitation.decode_request_state(result["requestState"]),
            [rec.elicitation_id],
        )
        self.assertTrue(
            result["inputRequests"][0]["params"]["url"].endswith(
                "/mcp/elicitation/%s" % rec.elicitation_id
            )
        )

    def test_mrtr_retry_completed(self):
        """A retry correlating to a completed elicitation resolves its value,
        which the tool then picks up on re-execution."""
        from odoo.addons.dub_mcp_server.services.mcp_tools import execute_tool

        rec = self.env["mcp.server.elicitation"].create_pending(
            self.env.user.id, "demo_secret", "Provide your demo secret."
        )
        rec.write({"status": "completed", "value": "s3cret-value"})
        values, pending = elicitation.resolve_mrtr_retry(
            self.env, self.env.user.id, [rec.elicitation_id]
        )
        self.assertEqual(pending, [])
        self.assertEqual(values, {"demo_secret": "s3cret-value"})
        # The stored value is what demo_external resolves on re-execution.
        config = self.env["mcp.server.config"].create({
            "name": "MRTR Test Config", "active": True,
        })
        result = execute_tool(
            self.env, "demo_external", {},
            config=config, user_id=self.env.user.id,
        )
        self.assertIn("s3****", result)

    def test_mrtr_retry_other_user_invisible(self):
        """An elicitation owned by another user resolves to nothing: the call
        falls through and the tool raises a fresh elicitation of its own."""
        other = self.env["res.users"].create({
            "name": "MRTR Other User", "login": "mrtr_other_user",
        })
        rec = self.env["mcp.server.elicitation"].create_pending(
            other.id, "demo_secret", "Provide your demo secret."
        )
        values, pending = elicitation.resolve_mrtr_retry(
            self.env, self.env.user.id, [rec.elicitation_id]
        )
        self.assertEqual(values, {})
        self.assertEqual(pending, [])

    def test_build_elicitation_error_legacy(self):
        """Legacy profiles keep the -32042 error with elicitations in data."""
        error = elicitation.build_elicitation_error(
            [{
                "mode": "url",
                "elicitationId": "abc123",
                "url": "https://odoo.example/mcp/elicitation/abc123",
                "message": "Provide your demo secret to continue.",
            }],
            request_id=7,
        )
        self.assertEqual(error["jsonrpc"], "2.0")
        self.assertEqual(error["id"], 7)
        self.assertEqual(error["error"]["code"], -32042)
        self.assertIn(
            "https://odoo.example/mcp/elicitation/abc123",
            error["error"]["message"],
        )
        self.assertEqual(
            error["error"]["data"]["elicitations"][0]["elicitationId"],
            "abc123",
        )
