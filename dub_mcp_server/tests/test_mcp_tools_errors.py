# Copyright 2026 Dubhe Srls
# License LGPL-3

"""
Test the error messages and the audit of refused and failed tool calls.
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.dub_mcp_server.services.mcp_tools import execute_tool


@tagged("post_install", "-at_install")
class TestMCPToolErrors(TransactionCase):
    """Refusals point to the right tool, missing records are not reported as
    access errors, invalid fields are named, and refusals reach the audit log."""

    def setUp(self):
        super().setUp()
        partner_model = self.env["ir.model"]._get("res.partner")
        self.config = self.env["mcp.server.config"].create({
            "name": "Tool Errors Test Config",
            "active": True,
            "enable_audit_log": True,
            "rule_ids": [(0, 0, {
                "model_id": partner_model.id,
                "allow_read": True,
                "allow_write": True,
                "allow_unlink": True,
            })],
        })
        self.partner = self.env["res.partner"].create({"name": "MCP Tool Errors Partner"})
        self.missing_id = self.env["res.partner"].search([], order="id desc", limit=1).id + 1000

    def _call(self, tool, arguments):
        return execute_tool(self.env, tool, arguments, config=self.config, user_id=self.env.user.id)

    def _audits(self, status):
        return self.env["mcp.server.audit"].search([
            ("status", "=", status), ("model_name", "=", "res.partner"),
        ])

    def test_call_method_crud_points_to_tool(self):
        """write through call_method is refused, names the update tool and is audited as denied."""
        result = self._call("call_method", {"model": "res.partner", "method": "write", "ids": [self.partner.id]})
        self.assertTrue(result.startswith("Access denied: Method 'write' not allowed on res.partner"))
        self.assertIn("'update' tool", result)
        result = self._call("call_method", {"model": "res.partner", "method": "action_archive", "ids": [self.partner.id]})
        self.assertIn('{"active": false}', result)
        denied = self._audits("denied")
        self.assertEqual(len(denied), 2)
        self.assertEqual(set(denied.mapped("operation")), {"call_method"})
        self.assertIn(str(self.partner.id), denied[0].record_ids)

    def test_call_method_other_method_has_no_hint(self):
        """A business method that is not enabled gets the plain refusal."""
        result = self._call("call_method", {"model": "res.partner", "method": "_compute_display_name"})
        self.assertEqual(result, "Access denied: Method '_compute_display_name' not allowed on res.partner")

    def test_missing_records_are_not_access_errors(self):
        """update, delete and read on an id that does not exist say so."""
        expected = f"Error: res.partner records not found: [{self.missing_id}]"
        self.assertEqual(
            self._call("update", {"model": "res.partner", "ids": [self.missing_id], "values": {"name": "x"}}),
            expected)
        self.assertEqual(self._call("delete", {"model": "res.partner", "ids": [self.missing_id]}), expected)
        self.assertEqual(self._call("read", {"model": "res.partner", "ids": [self.missing_id]}), expected)
        self.assertFalse(self._audits("denied"))

    def test_existing_record_update_still_works(self):
        """The update tool writes when the record exists and the rule allows it."""
        result = self._call("update", {"model": "res.partner", "ids": [self.partner.id], "values": {"name": "Renamed"}})
        self.assertTrue(result.startswith("Updated 1 res.partner record(s)"))
        self.assertEqual(self.partner.name, "Renamed")

    @mute_logger("odoo.addons.dub_mcp_server.services.mcp_tools")
    def test_invalid_field_is_named(self):
        """An unknown field returns the ORM message instead of a generic error, and is audited as failed."""
        result = self._call("search", {"model": "res.partner", "fields": ["id", "no_such_field"]})
        self.assertIn("Invalid field 'no_such_field'", result)
        self.assertIn("list_fields", result)
        failed = self._audits("fail")
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed.operation, "search")

    def test_refusal_without_rule_is_audited(self):
        """A model without a rule is refused and the refusal is audited."""
        result = execute_tool(
            self.env, "search", {"model": "res.country"}, config=self.config, user_id=self.env.user.id)
        self.assertTrue(result.startswith("Access denied"))
        denied = self.env["mcp.server.audit"].search([("status", "=", "denied"), ("model_name", "=", "res.country")])
        self.assertEqual(len(denied), 1)
