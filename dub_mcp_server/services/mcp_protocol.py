# Copyright 2025 Dubhe Srls
# License LGPL-3

"""
MCP protocol revision registry and message builders.

Centralizes everything that depends on the negotiated MCP protocol revision:
the version constants, the behaviour profile of each served revision
(``ProtocolProfile``), profile resolution from the request ``_meta`` and the
``MCP-Protocol-Version`` header, validation of the mirrored request headers,
and the builders for result envelopes, ``server/discover`` and JSON-RPC
errors. The controller reads behaviour flags from the profile, never version
strings.
"""
import ast
import base64
import os
from dataclasses import dataclass
from typing import Optional, Tuple

# Supported protocol revisions
MCP_VERSION_2024_11_05 = "2024-11-05"
MCP_VERSION_2025_03_26 = "2025-03-26"
MCP_VERSION_2025_06_18 = "2025-06-18"
MCP_VERSION_2025_11_25 = "2025-11-25"
MCP_VERSION_2026_07_28 = "2026-07-28"

MCP_DEFAULT_VERSION = MCP_VERSION_2025_11_25

# Transport / _meta keys
MCP_PROTOCOL_VERSION_HEADER = "MCP-Protocol-Version"
MCP_METHOD_HEADER = "Mcp-Method"
MCP_NAME_HEADER = "Mcp-Name"

# Methods whose tool/prompt/resource name is mirrored in the Mcp-Name header
MCP_NAME_METHODS = frozenset({"tools/call", "resources/read", "prompts/get"})

MCP_HEADER_BASE64_PREFIX = "=?base64?"
MCP_HEADER_BASE64_SUFFIX = "?="

META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CLIENT_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"

# Negotiated extensions (MCP 2026-07-28): declared by the client in the
# ``extensions`` field of its _meta client capabilities, advertised by the
# server under ``capabilities.extensions`` in server/discover.
TASKS_EXTENSION_ID = "io.modelcontextprotocol/tasks"

# Protocol-level JSON-RPC error codes (MCP 2026-07-28)
MCP_HEADER_MISMATCH = -32020
MCP_MISSING_CAPABILITY = -32021
MCP_UNSUPPORTED_PROTOCOL_VERSION = -32022

# Result types (MCP 2026-07-28): every result names its outcome kind.
RESULT_TYPE_COMPLETE = "complete"
RESULT_TYPE_INPUT_REQUIRED = "input_required"
RESULT_TYPE_TASK = "task"

# Handler-set result types the stateless envelope preserves as-is: an MRTR
# ``input_required`` carries a pending input request and a ``task`` result
# carries the durable task handle - overriding either would silently drop it.
PRESERVED_RESULT_TYPES = frozenset({
    RESULT_TYPE_INPUT_REQUIRED, RESULT_TYPE_TASK,
})

# Caching hints the 2026-07-28 revision requires on cacheable results
CACHE_HINTS = {
    "server/discover": {"ttlMs": 300000, "cacheScope": "public"},
    "tools/list": {"ttlMs": 60000, "cacheScope": "private"},
    "resources/list": {"ttlMs": 60000, "cacheScope": "private"},
    "resources/templates/list": {"ttlMs": 60000, "cacheScope": "private"},
    "resources/read": {"ttlMs": 0, "cacheScope": "private"},
}

# Task RPC method sets per revision family. Legacy revisions serve the
# 2025-11-25 core set; on the stateless revision (2026-07-28) tasks are a
# negotiated extension whose polling set drops ``tasks/list`` and the
# blocking ``tasks/result``, and adds ``tasks/update``.
TASK_METHODS_LEGACY = frozenset({
    "tasks/list", "tasks/get", "tasks/result", "tasks/cancel",
})
TASK_METHODS_STATELESS = frozenset({
    "tasks/get", "tasks/cancel", "tasks/update",
})


@dataclass(frozen=True)
class ProtocolProfile:
    """Behaviour flags describing a single MCP protocol revision."""

    version: str
    stateless: bool
    result_type: Optional[str] = None
    supports_sessions: bool = True
    has_tasks_extension: bool = False
    uses_mrtr: bool = False


PROFILES = {
    MCP_VERSION_2026_07_28: ProtocolProfile(
        version=MCP_VERSION_2026_07_28,
        stateless=True,
        result_type="complete",
        supports_sessions=False,
        has_tasks_extension=True,
        uses_mrtr=True,
    ),
    MCP_VERSION_2025_11_25: ProtocolProfile(
        version=MCP_VERSION_2025_11_25,
        stateless=False,
    ),
    MCP_VERSION_2025_06_18: ProtocolProfile(
        version=MCP_VERSION_2025_06_18,
        stateless=False,
    ),
    MCP_VERSION_2025_03_26: ProtocolProfile(
        version=MCP_VERSION_2025_03_26,
        stateless=False,
    ),
    MCP_VERSION_2024_11_05: ProtocolProfile(
        version=MCP_VERSION_2024_11_05,
        stateless=False,
    ),
}

SUPPORTED_VERSIONS = (
    MCP_VERSION_2026_07_28,
    MCP_VERSION_2025_11_25,
    MCP_VERSION_2025_06_18,
    MCP_VERSION_2025_03_26,
    MCP_VERSION_2024_11_05,
)

# Revisions the ``initialize`` handshake may negotiate: only the session-based
# ones, as the stateless revision has no handshake at all.
SESSION_VERSIONS = tuple(
    candidate for candidate in SUPPORTED_VERSIONS
    if not PROFILES[candidate].stateless
)


def _read_module_version() -> str:
    """Read the module version from ``__manifest__.py`` (a plain dict literal)."""
    manifest_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), os.pardir, "__manifest__.py"
    )
    try:
        with open(manifest_path, "r", encoding="utf-8") as manifest_file:
            manifest = ast.literal_eval(manifest_file.read())
        if isinstance(manifest, dict):
            return str(manifest.get("version") or "1.0.0")
    except (OSError, SyntaxError, ValueError):
        pass
    return "1.0.0"


MODULE_VERSION = _read_module_version()

MCP_SERVER_NAME = "dub-mcp-server"

SERVER_INFO = {"name": MCP_SERVER_NAME, "version": MODULE_VERSION}


def is_supported(version: Optional[str]) -> bool:
    """Report whether ``version`` is a revision this server serves."""
    return version in SUPPORTED_VERSIONS


def get_profile(version: Optional[str]) -> ProtocolProfile:
    """Return the behaviour profile for ``version``, defaulting when unknown."""
    return PROFILES.get(version or "", PROFILES[MCP_DEFAULT_VERSION])


def decode_header_value(value: str) -> Optional[str]:
    """Decode the Base64 sentinel a mirrored request header value may carry.

    :return: the decoded value, or ``None`` when the sentinel payload is
        malformed (which the caller must treat as a mismatch).
    """
    if not (
        value.startswith(MCP_HEADER_BASE64_PREFIX)
        and value.endswith(MCP_HEADER_BASE64_SUFFIX)
    ):
        return value
    payload = value[len(MCP_HEADER_BASE64_PREFIX):-len(MCP_HEADER_BASE64_SUFFIX)]
    try:
        return base64.b64decode(payload, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def resolve_profile(
    params: dict, headers,
) -> Tuple[Optional[ProtocolProfile], Optional[dict]]:
    """Resolve the protocol profile governing one request.

    The version is taken from ``params['_meta'][.../protocolVersion]`` first,
    then from the ``MCP-Protocol-Version`` header; when both are present they
    must agree. A request declaring nothing gets the legacy default profile:
    the stateless revision is only ever served when explicitly declared.

    :return: a ``(profile, None)`` pair, or ``(None, error_response)`` with a
        ready-to-send JSON-RPC error on mismatch (-32020) or unsupported
        version (-32022).
    """
    meta = params.get("_meta") if isinstance(params, dict) else None
    meta_version = None
    if isinstance(meta, dict):
        value = meta.get(META_PROTOCOL_VERSION)
        meta_version = value if isinstance(value, str) else None
    header_version = headers.get(MCP_PROTOCOL_VERSION_HEADER) if headers else None
    if meta_version and header_version and meta_version != header_version:
        return None, make_header_mismatch_error(
            "Protocol version mismatch between the %s header (%s) and the "
            "request _meta (%s)" % (
                MCP_PROTOCOL_VERSION_HEADER, header_version, meta_version,
            )
        )
    requested = meta_version or header_version
    if not requested:
        return get_profile(None), None
    if not is_supported(requested):
        return None, make_unsupported_version_error(requested)
    return get_profile(requested), None


def validate_mirrored_headers(method: str, params: dict, headers) -> Optional[dict]:
    """Verify the mirrored request headers agree with the request body.

    The transport mirrors the method (and, for ``tools/call``,
    ``resources/read`` and ``prompts/get``, the tool/resource/prompt name) into
    ``Mcp-Method``/``Mcp-Name`` so an intermediary can route without parsing
    the body; a value that disagrees is rejected. A header the client did not
    send is not faulted. Values may arrive as a ``=?base64?...?=`` sentinel.

    :return: a JSON-RPC error response (-32020) on mismatch, else ``None``.
    """
    mirrored = [(MCP_METHOD_HEADER, method)]
    if method in MCP_NAME_METHODS:
        mirrored.append((MCP_NAME_HEADER, params.get("name") or params.get("uri")))
    for header, expected in mirrored:
        sent = headers.get(header)
        if sent is None or expected is None:
            continue
        if decode_header_value(sent) != expected:
            return make_header_mismatch_error(
                "Header mismatch: the %s header does not match the request "
                "body" % header
            )
    return None


def client_supports_tasks(params: dict, profile: ProtocolProfile) -> bool:
    """Report whether the client may be served MCP tasks on this profile.

    On the legacy revisions tasks are a core capability advertised on
    ``initialize``, so every client is assumed to accept them (the historical
    behaviour). On the stateless revision tasks are an opt-in extension: the
    client must declare ``io.modelcontextprotocol/tasks`` in the
    ``extensions`` field of the client capabilities it carries in ``_meta``.
    """
    if not profile.has_tasks_extension:
        return True
    meta = params.get("_meta") if isinstance(params, dict) else None
    capabilities = (
        meta.get(META_CLIENT_CAPABILITIES) if isinstance(meta, dict) else None
    )
    extensions = (
        capabilities.get("extensions")
        if isinstance(capabilities, dict) else None
    )
    return isinstance(extensions, dict) and TASKS_EXTENSION_ID in extensions


def task_method_allowed(
    method: str, profile: ProtocolProfile, tasks_accepted: bool
) -> bool:
    """Report whether a ``tasks/*`` method is routed on this profile.

    Legacy revisions serve the 2025-11-25 core method set to every client.
    The stateless revision serves tasks only when the client negotiated the
    extension, and only the polling method set survived there: ``tasks/list``
    and the blocking ``tasks/result`` were removed in 2026-07-28.
    ``tasks/update`` is routed but acknowledged as a no-op by the callee
    (this module's tasks never enter ``input_required``, so per spec there
    is nothing to satisfy).
    """
    if profile.has_tasks_extension:
        return tasks_accepted and method in TASK_METHODS_STATELESS
    return method in TASK_METHODS_LEGACY


def make_result_envelope(result: dict, profile: ProtocolProfile, method: str) -> dict:
    """Add the result fields the negotiated revision requires.

    Revision 2026-07-28 names the outcome kind on every result
    (``resultType``), requires caching hints on the operations it defines as
    cacheable, and carries the server identity in ``_meta``. The revisions
    before it define none of these, so their results pass through untouched.
    The values are the transport's to set and override anything a handler put
    under those keys - with one exception: the handler-set result types in
    ``PRESERVED_RESULT_TYPES`` (MRTR ``input_required``, tasks-extension
    ``task``) are preserved, as overriding them would silently drop a pending
    input request or the durable task handle.
    """
    if not profile.result_type:
        return result
    result_type = result.get("resultType")
    if result_type not in PRESERVED_RESULT_TYPES:
        result_type = profile.result_type
    envelope = {**result, "resultType": result_type}
    envelope.update(CACHE_HINTS.get(method, {}))
    envelope["_meta"] = {
        **(result.get("_meta") or {}),
        META_SERVER_INFO: dict(SERVER_INFO),
    }
    return envelope


def make_discover_result() -> dict:
    """Build the MCP ``server/discover`` result advertising every served revision.

    Capabilities are the minimal 2026-07-28 shape: no ``listChanged`` (the
    stateless revision has no server-initiated notification channel here) and
    no core ``tasks`` - on this revision tasks are the negotiated extension
    ``io.modelcontextprotocol/tasks``, advertised under
    ``capabilities.extensions``.
    """
    return {
        "supportedVersions": list(SUPPORTED_VERSIONS),
        "capabilities": {
            "tools": {},
            "resources": {},
            "extensions": {TASKS_EXTENSION_ID: {}},
        },
        "serverInfo": dict(SERVER_INFO),
    }


def make_jsonrpc_error(
    code: int, message: str, request_id=None, data=None,
) -> dict:
    """Build a JSON-RPC error response with the given code, message, and data."""
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def make_header_mismatch_error(message: str, request_id=None) -> dict:
    """Build the JSON-RPC error returned when mirrored headers contradict the body."""
    return make_jsonrpc_error(MCP_HEADER_MISMATCH, message, request_id=request_id)


def make_missing_capability_error(request_id=None) -> dict:
    """Build the JSON-RPC error returned when a stateless request omits the
    ``_meta`` client capabilities block every method but ``server/discover``
    must carry."""
    return make_jsonrpc_error(
        MCP_MISSING_CAPABILITY,
        "Missing required _meta field: %s" % META_CLIENT_CAPABILITIES,
        request_id=request_id,
    )


def make_unsupported_version_error(requested, request_id=None) -> dict:
    """Build the JSON-RPC error returned for a protocol revision we do not serve."""
    return make_jsonrpc_error(
        MCP_UNSUPPORTED_PROTOCOL_VERSION,
        "Unsupported protocol version: %s" % requested,
        request_id=request_id,
        data={"supported": list(SUPPORTED_VERSIONS), "requested": requested},
    )
