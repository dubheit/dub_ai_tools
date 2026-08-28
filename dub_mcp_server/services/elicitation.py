# Copyright 2025 Dubhe Srls
# License LGPL-3

"""URL-mode elicitation helpers (MCP 2025-11-25 and 2026-07-28).

A tool that needs an out-of-band value from the user creates a pending
elicitation and raises errors.UrlElicitationRequired. On the session-based
revisions the controller turns it into a JSON-RPC -32042 error carrying the
URL; on the stateless revision (2026-07-28) it becomes an MRTR
``input_required`` result whose ``requestState`` correlates the retried
request with the pending elicitation. Either way the user opens the URL (a
web page served by Odoo), the value is stored bound to their identity, and
the client retries the original tools/call.
"""
import base64
import binascii
import json

# JSON-RPC error code carrying URL elicitations on the legacy revisions.
ELICITATION_REQUIRED_CODE = -32042

# MRTR (MCP 2026-07-28) wire names.
MRTR_RESULT_TYPE = "input_required"
MRTR_REQUEST_FIELDS = ("requestState", "inputResponses")


def create_url_elicitation(env, user_id, purpose, message):
    """Create a pending elicitation and return its url-mode descriptor dict."""
    elicitation = env["mcp.server.elicitation"].sudo().create_pending(
        user_id, purpose, message
    )
    base_url = env["ir.config_parameter"].sudo().get_param("web.base.url", "")
    return {
        "mode": "url",
        "elicitationId": elicitation.elicitation_id,
        "url": "%s/mcp/elicitation/%s" % (base_url, elicitation.elicitation_id),
        "message": message,
    }


def get_completed_value(env, user_id, purpose):
    """Return the value of the latest completed elicitation for user+purpose."""
    from odoo import fields
    rec = env["mcp.server.elicitation"].sudo().search([
        ("user_id", "=", user_id),
        ("purpose", "=", purpose),
        ("status", "=", "completed"),
    ], limit=1, order="create_date desc")
    if not rec:
        return None
    if rec.expiry and rec.expiry < fields.Datetime.now():
        return None
    return rec.value


def build_elicitation_error(elicitations, request_id=None):
    """Build the legacy (pre-2026-07-28) JSON-RPC error response carrying the
    URL-mode elicitations in its error data (-32042)."""
    urls = ", ".join(el.get("url", "") for el in elicitations)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": ELICITATION_REQUIRED_CODE,
            "message": (
                "More information required. Open this link while logged into "
                "Odoo (as yourself), provide the value, then retry: %s" % urls
            ),
            "data": {"elicitations": elicitations},
        },
    }


# -- MRTR (MCP 2026-07-28) --------------------------------------------------
#
# The stateless revision removes server-initiated elicitation requests, the
# elicitationId field and the notifications/elicitation/complete
# notification. Instead, a call that needs input returns an
# InputRequiredResult (resultType "input_required") holding the
# elicitation/create input requests, and the client retries the original call
# echoing requestState (and inputResponses). requestState is an opaque string
# the client never parses; here it encodes the pending elicitation ids as
# base64url(JSON) so any worker can correlate the retry.


def encode_request_state(elicitation_ids):
    """Encode elicitation ids into the opaque MRTR ``requestState`` string."""
    payload = json.dumps({"elicitation_ids": list(elicitation_ids)})
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_request_state(token):
    """Decode an MRTR ``requestState`` back into a list of elicitation ids.

    :return: the list of ids, or an empty list when the token is missing or
        malformed (an opaque value we did not issue is simply ignored).
    """
    if not isinstance(token, str) or not token:
        return []
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        )
    except (binascii.Error, ValueError):
        return []
    ids = payload.get("elicitation_ids") if isinstance(payload, dict) else None
    if not isinstance(ids, list):
        return []
    return [str(elicitation_id) for elicitation_id in ids]


def build_input_required_result(elicitations):
    """Build the MRTR InputRequiredResult for URL-mode elicitation dicts.

    Each elicitation becomes an ``elicitation/create`` input request (the
    2026-07-28 shape: ``mode``/``url``/``message``; the elicitationId field
    no longer exists), and the pending elicitation ids ride in
    ``requestState`` for correlation.
    """
    return {
        "resultType": MRTR_RESULT_TYPE,
        "inputRequests": [
            {
                "method": "elicitation/create",
                "params": {
                    "mode": "url",
                    "url": elicitation.get("url", ""),
                    "message": elicitation.get("message", ""),
                },
            }
            for elicitation in elicitations
        ],
        "requestState": encode_request_state(
            elicitation.get("elicitationId") for elicitation in elicitations
        ),
    }


def extract_request_state(params):
    """Pull the elicitation ids a retried call correlates to, if any.

    ``requestState`` lives on the request params (CallToolRequestParams); the
    tool ``arguments`` are also scanned defensively since a client may echo
    the field there.
    """
    if not isinstance(params, dict):
        return []
    token = params.get("requestState")
    if token is None:
        arguments = params.get("arguments")
        if isinstance(arguments, dict):
            token = arguments.get("requestState")
    return decode_request_state(token)


def strip_mrtr_fields(arguments):
    """Return ``arguments`` without the MRTR fields, so a retried call that
    echoed requestState/inputResponses never leaks them into the tool's
    argument validation."""
    if not isinstance(arguments, dict):
        return arguments
    return {
        key: value for key, value in arguments.items()
        if key not in MRTR_REQUEST_FIELDS
    }


def resolve_mrtr_retry(env, user_id, elicitation_ids):
    """Resolve the elicitations referenced by a retried MRTR call.

    :return: a ``(values, pending)`` pair. ``values`` maps the purpose of
        every completed elicitation to its stored value (on re-execution the
        tool picks it up through its own get_completed_value lookup).
        ``pending`` holds fresh url-mode descriptors for the elicitations
        still awaiting user input, to be turned into another input_required
        result. Records of other users are invisible to the search, so an id
        that is not ours resolves to neither.
    """
    from odoo import fields
    values = {}
    pending = []
    elicitations = env["mcp.server.elicitation"].sudo()
    now = fields.Datetime.now()
    for elicitation_id in elicitation_ids:
        rec = elicitations.search([
            ("elicitation_id", "=", elicitation_id),
            ("user_id", "=", user_id),
        ], limit=1)
        if not rec:
            continue
        if (
            rec.status == "completed" and rec.value
            and (not rec.expiry or rec.expiry >= now)
        ):
            values[rec.purpose] = rec.value
        else:
            pending.append({
                "mode": "url",
                "elicitationId": rec.elicitation_id,
                "url": rec.url,
                "message": rec.message or "",
            })
    return values, pending
