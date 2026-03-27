"""
Methods handler for MCP Server.

Provides intelligent method discovery and documentation.
"""
import inspect
import re
from typing import Dict, List, Any, Optional
from odoo import models
import logging

_logger = logging.getLogger(__name__)

# Common Odoo method patterns with descriptions
METHOD_PATTERNS = {
    # Action methods
    r'^action_confirm$': 'Confirm the document/record',
    r'^action_cancel$': 'Cancel the document/record',
    r'^action_draft$': 'Set the document/record to draft state',
    r'^action_done$': 'Mark the document/record as done',
    r'^action_validate$': 'Validate the document/record',
    r'^action_approve$': 'Approve the document/record',
    r'^action_refuse$': 'Refuse/Reject the document/record',
    r'^action_archive$': 'Archive the record',
    r'^action_unarchive$': 'Unarchive the record',
    r'^action_duplicate$': 'Duplicate the record',
    r'^action_send$': 'Send the document (e.g., by email)',
    r'^action_post$': 'Post the document (for accounting)',
    r'^action_invoice$': 'Create invoice from the document',
    r'^action_ship$': 'Ship/Deliver the order',
    r'^action_close$': 'Close the document/record',
    r'^action_reopen$': 'Reopen the document/record',
    r'^action_reset$': 'Reset the document to initial state',

    # Button methods
    r'^button_': 'Execute button action: {method_name}',

    # Compute methods (usually internal)
    r'^_compute_': 'Compute field value: {method_name}',
    r'^_inverse_': 'Inverse compute method: {method_name}',
    r'^_search_': 'Search method for computed field: {method_name}',

    # Onchange methods
    r'^_onchange_': 'Handle field change: {method_name}',
    r'^onchange_': 'Handle field change: {method_name}',

    # State transition methods
    r'^set_to_': 'Set state to: {method_name}',
    r'^mark_as_': 'Mark as: {method_name}',

    # Workflow methods
    r'^do_': 'Perform action: {method_name}',
    r'^process_': 'Process: {method_name}',
    r'^check_': 'Check/Validate: {method_name}',
    r'^compute_': 'Compute: {method_name}',
    r'^generate_': 'Generate: {method_name}',
    r'^prepare_': 'Prepare: {method_name}',
    r'^send_': 'Send: {method_name}',
    r'^print_': 'Print: {method_name}',
}

# Model-specific common methods with descriptions
MODEL_SPECIFIC_METHODS = {
    'sale.order': {
        'action_quotation_send': 'Send quotation by email to the customer',
        'action_confirm': 'Confirm the sale order and generate SO number',
        'action_cancel': 'Cancel the sale order',
        'action_draft': 'Set sale order back to draft/quotation state',
        'action_done': 'Mark the sale order as done',
        'action_unlock': 'Unlock a locked sale order for editing',
        '_prepare_invoice': 'Prepare invoice values from sale order',
        '_create_invoices': 'Create invoices for the sale order',
        'print_quotation': 'Print the quotation/sale order report',
    },
    'purchase.order': {
        'action_rfq_send': 'Send RFQ by email to the vendor',
        'button_confirm': 'Confirm the purchase order',
        'button_approve': 'Approve the purchase order',
        'button_cancel': 'Cancel the purchase order',
        'button_draft': 'Set purchase order back to draft state',
        'button_done': 'Manually close the purchase order',
        'action_create_invoice': 'Create vendor bill from purchase order',
    },
    'account.move': {
        'action_post': 'Post/Validate the journal entry or invoice',
        'button_draft': 'Reset to draft',
        'button_cancel': 'Cancel the entry',
        'action_invoice_sent': 'Mark invoice as sent',
        'action_invoice_paid': 'Register payment for the invoice',
        'action_reverse': 'Reverse the journal entry',
        'action_register_payment': 'Open payment registration wizard',
        '_compute_amount': 'Compute invoice totals',
    },
    'stock.picking': {
        'action_confirm': 'Confirm the picking/transfer',
        'action_assign': 'Check availability and reserve products',
        'button_validate': 'Validate the transfer',
        'action_cancel': 'Cancel the transfer',
        'action_done': 'Force transfer to done state',
        'do_print_picking': 'Print picking slip',
        'action_generate_backorder_wizard': 'Open backorder creation wizard',
    },
    'project.task': {
        'action_assign_to_me': 'Assign task to current user',
        'action_open_parent_task': 'Open parent task form',
        'action_subtask': 'Create a subtask',
        'action_timer_start': 'Start timesheet timer',
        'action_timer_stop': 'Stop timesheet timer',
        'action_timer_pause': 'Pause timesheet timer',
    },
    'mrp.production': {
        'action_confirm': 'Confirm the manufacturing order',
        'button_plan': 'Plan the manufacturing order',
        'button_mark_done': 'Mark manufacturing as done',
        'action_cancel': 'Cancel the manufacturing order',
        'action_toggle_is_locked': 'Lock/Unlock manufacturing order',
        'action_generate_serial': 'Generate serial numbers for produced items',
        'button_scrap': 'Scrap products',
    },
    'hr.expense': {
        'action_submit_expenses': 'Submit expense for approval',
        'approve_expense_sheets': 'Approve expense',
        'refuse_expense': 'Refuse expense',
        'action_sheet_move_create': 'Create journal entries for expense',
        'action_get_attachment_view': 'View expense attachments',
    },
    'hr.leave': {
        'action_approve': 'Approve time off request',
        'action_refuse': 'Refuse time off request',
        'action_draft': 'Set time off back to draft',
        'action_validate': 'Validate time off request',
        'action_confirm': 'Confirm time off request',
    }
}

# Core Odoo methods that should always be available
CORE_METHODS = {
    'create': 'Create new record(s) with given values',
    'write': 'Update existing record(s) with given values',
    'unlink': 'Delete record(s) permanently',
    'read': 'Read field values from record(s)',
    'search': 'Search for records matching domain criteria',
    'search_read': 'Search and read records in a single call',
    'search_count': 'Count records matching domain criteria',
    'copy': 'Duplicate record(s) with option to override values',
    'default_get': 'Get default values for fields',
    'name_get': 'Get display name for record(s)',
    'name_search': 'Search records by name/display_name',
    'name_create': 'Quick create record with just a name',
    'fields_get': 'Get field definitions and metadata',
    'fields_view_get': 'Get view definition with fields',
    'read_group': 'Read aggregated data grouped by fields',
    'export_data': 'Export record data in various formats',
    'load': 'Import data from external sources',
    'browse': 'Get record set from IDs',
    'exists': 'Check if record(s) still exist',
    'ensure_one': 'Ensure recordset contains exactly one record',
    'filtered': 'Filter recordset with a function',
    'mapped': 'Map recordset to field values or function results',
    'sorted': 'Sort recordset by field or function',
}


def get_method_description(model_name: str, method_name: str) -> str:
    """Get description for a method based on patterns."""
    # Check model-specific methods first
    if model_name in MODEL_SPECIFIC_METHODS:
        if method_name in MODEL_SPECIFIC_METHODS[model_name]:
            return MODEL_SPECIFIC_METHODS[model_name][method_name]

    # Check core methods
    if method_name in CORE_METHODS:
        return CORE_METHODS[method_name]

    # Check pattern matching
    for pattern, description in METHOD_PATTERNS.items():
        if re.match(pattern, method_name):
            # Replace {method_name} placeholder with actual method name
            readable = method_name.replace('_', ' ')
            return description.replace('{method_name}', readable)

    # Default description based on method name structure
    if method_name.startswith('_'):
        return f"Internal method: {method_name}"
    elif '_' in method_name:
        # Convert snake_case to readable format
        readable = method_name.replace('_', ' ').title()
        return f"Method: {readable}"
    else:
        return f"Method: {method_name}"


def categorize_method(method_name: str) -> str:
    """Categorize method based on its name pattern"""

    if method_name in CORE_METHODS:
        return "core"
    elif method_name.startswith('action_'):
        return "action"
    elif method_name.startswith('button_'):
        return "button"
    elif method_name.startswith('_compute_'):
        return "compute"
    elif (method_name.startswith('_onchange_')
          or method_name.startswith('onchange_')):
        return "onchange"
    elif method_name.startswith('_'):
        return "internal"
    elif any(method_name.startswith(p) for p in [
        'do_', 'process_', 'check_', 'prepare_', 'send_', 'print_', 'generate_'
    ]):
        return "workflow"
    else:
        return "custom"


def is_callable_method(obj: Any, method_name: str) -> bool:
    """Check if a method is callable and not a property or field"""

    try:
        attr = getattr(obj, method_name, None)
        if attr is None:
            return False

        # Skip properties and fields
        if isinstance(attr, property):
            return False
        if hasattr(attr, '_field'):  # Odoo field
            return False

        # Check if it's callable
        return callable(attr)
    except Exception:
        return False


def get_model_methods(env, model_name: str) -> List[Dict[str, Any]]:
    """
    Get all available methods for a specific Odoo model with descriptions
    """

    try:
        if model_name not in env:
            return []

        model = env[model_name]
        methods = []
        seen = set()

        # Get all attributes from the model class
        model_class = type(model)

        # Iterate through all attributes
        for attr_name in dir(model_class):
            # Skip already seen methods
            if attr_name in seen:
                continue
            seen.add(attr_name)

            # Skip special Python methods (except __init__)
            if attr_name.startswith('__') and attr_name.endswith('__'):
                continue

            # Check if it's a callable method
            if not is_callable_method(model, attr_name):
                continue

            # Get method info
            method_info = {
                'name': attr_name,
                'description': get_method_description(model_name, attr_name),
                'category': categorize_method(attr_name),
            }

            # Try to get method signature
            try:
                method = getattr(model_class, attr_name)
                if hasattr(method, '__func__'):
                    sig = inspect.signature(method.__func__)
                    params = []
                    for param_name, param in sig.parameters.items():
                        if param_name not in ['self', 'cls']:
                            param_info = {'name': param_name}
                            if param.default != inspect.Parameter.empty:
                                param_info['optional'] = True
                                if param.default is not None:
                                    param_info['default'] = str(param.default)
                            params.append(param_info)
                    if params:
                        method_info['parameters'] = params
            except Exception:
                pass  # Signature extraction failed, continue without it

            methods.append(method_info)

        # Sort methods by category and name
        category_order = [
            'core', 'action', 'button', 'workflow',
            'custom', 'compute', 'onchange', 'internal'
        ]
        methods.sort(key=lambda x: (
            category_order.index(x['category'])
            if x['category'] in category_order else 99,
            x['name']
        ))

        return methods

    except Exception as e:
        _logger.error(f"Error getting methods for {model_name}: {e}")
        return []


def filter_methods_by_category(
    methods: List[Dict],
    categories: Optional[List[str]] = None
) -> List[Dict]:
    """Filter methods by category"""
    if not categories:
        return methods
    return [m for m in methods if m.get('category') in categories]


def search_methods(methods: List[Dict], query: str) -> List[Dict]:
    """Search methods by name or description"""
    query = query.lower()
    results = []
    for method in methods:
        name_match = query in method['name'].lower()
        desc_match = query in method.get('description', '').lower()
        if name_match or desc_match:
            results.append(method)
    return results
