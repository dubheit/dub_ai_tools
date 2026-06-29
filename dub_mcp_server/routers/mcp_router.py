# Copyright 2025 Dubhe Srls
# License LGPL-3

import logging
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env

from ..services import adapter, authz, errors, ratelimit, validate
from . import methods_handler
from .dependencies import get_bearer_token, require_oauth2_user

_logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp"])


def _auth_ctx(request: Request, env) -> "authz.AuthContext":
    """Build the auth context, carrying the bearer token so the MCP
    config can be resolved per-principal (deny-by-default otherwise)."""
    return authz.AuthContext(
        user_id=env.user.id,
        login=env.user.login,
        ip=_get_client_ip(request),
        token=get_bearer_token(request),
    )


def _get_client_ip(request: Request) -> str:
    """Extract real client IP from request headers or connection."""
    # Check X-Forwarded-For header (for reverse proxies)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP (original client)
        return forwarded.split(",")[0].strip()
    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    # Fallback to direct connection
    if request.client:
        return request.client.host
    return "unknown"


# Pydantic models for requests and responses
class HealthResponse(BaseModel):
    status: str


class VersionResponse(BaseModel):
    odoo_version: str
    module_version: str


class McpResponse(BaseModel):
    ok: bool
    result: Optional[Any] = None  # Accept both dict and list
    meta: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class SearchReadRequest(BaseModel):
    model: str
    domain: List = Field(default_factory=list)
    fields: Optional[List[str]] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    order: Optional[str] = None


class ReadRequest(BaseModel):
    model: str
    ids: List[int]
    fields: Optional[List[str]] = None


class CreateRequest(BaseModel):
    model: str
    values: Dict[str, Any]


class WriteRequest(BaseModel):
    model: str
    ids: List[int]
    values: Dict[str, Any]


class UnlinkRequest(BaseModel):
    model: str
    ids: List[int]


class MethodsRequest(BaseModel):
    model: str
    # Filter by category (core, action, button, etc.)
    categories: Optional[List[str]] = None
    # Search in method name or description
    search: Optional[str] = None


class ExecuteRequest(BaseModel):
    model: str
    method: str
    ids: List[int]
    args: Optional[List[Any]] = Field(default_factory=list)
    kwargs: Optional[Dict[str, Any]] = Field(default_factory=dict)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint"""
    return HealthResponse(status="ok")


@router.get("/version", response_model=VersionResponse)
async def version(
    env: Annotated[Environment, Depends(odoo_env)]
) -> VersionResponse:
    """Get version information"""
    domain = [("name", "=", "dub_mcp_server")]
    module = env["ir.module.module"].sudo().search(domain, limit=1)
    mod_ver = module.installed_version or module.latest_version
    module_version = mod_ver or "unknown"
    odoo_version = (
        env["ir.config_parameter"].sudo()
        .get_param("web.base.version", "19.0")
    )
    return VersionResponse(
        odoo_version=odoo_version, module_version=module_version
    )


@router.post("/models", response_model=McpResponse)
async def list_models(
    request: Request,
    env: Annotated[Environment, Depends(require_oauth2_user)]
) -> McpResponse:
    """List available models"""
    ctx = _auth_ctx(request, env)

    try:
        authz.ensure_enabled(ctx, env)
        ratelimit.ensure_within_limit(ctx, env)
        payload = adapter.list_models(ctx, env)
        authz.audit(
            ctx, operation="discover", model=None,
            status="success", env=env, request_excerpt={}
        )
        return McpResponse(ok=True, result=payload)
    except errors.McpError as e:
        authz.audit(
            ctx, operation="discover", model=None,
            status="fail", env=env, request_excerpt={},
            error_excerpt=str(e)
        )
        return McpResponse(ok=False, error=e.to_dict())


@router.post("/search_read", response_model=McpResponse)
async def search_read(
    request: Request,
    request_data: SearchReadRequest,
    env: Annotated[Environment, Depends(require_oauth2_user)]
) -> McpResponse:
    """Search and read records"""
    ctx = _auth_ctx(request, env)

    data = request_data.model_dump()

    try:
        authz.ensure_enabled(ctx, env)
        ratelimit.ensure_within_limit(ctx, env)
        validated_data = validate.parse_search_read(data)
        res, meta = adapter.search_read(ctx, validated_data, env)
        authz.audit(
            ctx, operation="search", model=data.get("model"),
            status="success", env=env, request_excerpt=data
        )
        return McpResponse(ok=True, result=res, meta=meta)
    except errors.McpError as e:
        authz.audit(
            ctx, operation="search", model=data.get("model"),
            status="fail", env=env, request_excerpt=data,
            error_excerpt=str(e)
        )
        return McpResponse(ok=False, error=e.to_dict())


@router.post("/read", response_model=McpResponse)
async def read(
    request: Request,
    request_data: ReadRequest,
    env: Annotated[Environment, Depends(require_oauth2_user)]
) -> McpResponse:
    """Read records by IDs"""
    ctx = _auth_ctx(request, env)

    data = request_data.model_dump()

    try:
        authz.ensure_enabled(ctx, env)
        ratelimit.ensure_within_limit(ctx, env)
        validated_data = validate.parse_read(data)
        res = adapter.read(ctx, validated_data, env)
        authz.audit(
            ctx, operation="read", model=data.get("model"),
            status="success", env=env, request_excerpt=data,
            record_ids=data.get("ids")
        )
        return McpResponse(ok=True, result=res)
    except errors.McpError as e:
        authz.audit(
            ctx, operation="read", model=data.get("model"),
            status="fail", env=env, request_excerpt=data,
            error_excerpt=str(e)
        )
        return McpResponse(ok=False, error=e.to_dict())


@router.post("/create", response_model=McpResponse)
async def create(
    request: Request,
    request_data: CreateRequest,
    env: Annotated[Environment, Depends(require_oauth2_user)]
) -> McpResponse:
    """Create a new record"""
    ctx = _auth_ctx(request, env)

    data = request_data.model_dump()

    try:
        authz.ensure_enabled(ctx, env)
        ratelimit.ensure_within_limit(ctx, env)
        validated_data = validate.parse_create(data)
        res_id = adapter.create(ctx, validated_data, env)
        authz.audit(
            ctx, operation="create", model=data.get("model"),
            status="success", env=env, request_excerpt=data,
            record_ids=[res_id]
        )
        return McpResponse(ok=True, result={"id": res_id})
    except errors.McpError as e:
        authz.audit(
            ctx, operation="create", model=data.get("model"),
            status="fail", env=env, request_excerpt=data,
            error_excerpt=str(e)
        )
        return McpResponse(ok=False, error=e.to_dict())


@router.post("/write", response_model=McpResponse)
async def write(
    request: Request,
    request_data: WriteRequest,
    env: Annotated[Environment, Depends(require_oauth2_user)]
) -> McpResponse:
    """Update existing records"""
    ctx = _auth_ctx(request, env)

    data = request_data.model_dump()

    try:
        authz.ensure_enabled(ctx, env)
        ratelimit.ensure_within_limit(ctx, env)
        validated_data = validate.parse_write(data)
        count = adapter.write(ctx, validated_data, env)
        authz.audit(
            ctx, operation="write", model=data.get("model"),
            status="success", env=env, request_excerpt=data,
            record_ids=data.get("ids")
        )
        return McpResponse(ok=True, result={"updated": count})
    except errors.McpError as e:
        authz.audit(
            ctx, operation="write", model=data.get("model"),
            status="fail", env=env, request_excerpt=data,
            error_excerpt=str(e)
        )
        return McpResponse(ok=False, error=e.to_dict())


@router.post("/unlink", response_model=McpResponse)
async def unlink(
    request: Request,
    request_data: UnlinkRequest,
    env: Annotated[Environment, Depends(require_oauth2_user)]
) -> McpResponse:
    """Delete records"""
    ctx = _auth_ctx(request, env)

    data = request_data.model_dump()

    try:
        authz.ensure_enabled(ctx, env)
        ratelimit.ensure_within_limit(ctx, env)
        validated_data = validate.parse_unlink(data)
        count = adapter.unlink(ctx, validated_data, env)
        authz.audit(
            ctx, operation="unlink", model=data.get("model"),
            status="success", env=env, request_excerpt=data,
            record_ids=data.get("ids")
        )
        return McpResponse(ok=True, result={"deleted": count})
    except errors.McpError as e:
        authz.audit(
            ctx, operation="unlink", model=data.get("model"),
            status="fail", env=env, request_excerpt=data,
            error_excerpt=str(e)
        )
        return McpResponse(ok=False, error=e.to_dict())


@router.post("/methods", response_model=McpResponse)
async def list_methods(
    request: Request,
    request_data: MethodsRequest,
    env: Annotated[Environment, Depends(require_oauth2_user)]
) -> McpResponse:
    """List available methods for a model with descriptions."""
    ctx = _auth_ctx(request, env)

    data = request_data.model_dump()
    model_name = data.get("model")

    try:
        authz.ensure_enabled(ctx, env)
        ratelimit.ensure_within_limit(ctx, env)

        # Get all methods for the model
        methods = methods_handler.get_model_methods(env, model_name)

        # Apply category filter if provided
        if data.get("categories"):
            cats = data["categories"]
            methods = methods_handler.filter_methods_by_category(
                methods, cats
            )

        # Apply search filter if provided
        if data.get("search"):
            methods = methods_handler.search_methods(methods, data["search"])

        result = {
            "model": model_name,
            "methods": methods,
            "total": len(methods)
        }

        authz.audit(
            ctx, operation="list_methods", model=model_name,
            status="success", env=env, request_excerpt=data
        )
        return McpResponse(ok=True, result=result)
    except Exception as e:
        authz.audit(
            ctx, operation="list_methods", model=model_name,
            status="fail", env=env, request_excerpt=data,
            error_excerpt=str(e)
        )
        return McpResponse(
            ok=False,
            error={"message": "Internal server error", "type": "method_list_error"}
        )


# Blocked methods that could be dangerous
BLOCKED_METHODS = frozenset({
    'sudo', 'with_user', 'with_context', 'with_company', 'with_env',
    'unlink', 'write', 'create', 'copy',  # Use dedicated endpoints
    'execute', 'execute_kw', '_execute', '_read', '_write', '_create',
    'shell', 'eval', 'exec', 'compile', 'open', 'import_module',
    'grant_access', 'revoke_access', 'set_password', 'change_password',
})

# Allowed method prefixes (safe action methods)
ALLOWED_PREFIXES = (
    'action_', 'button_', 'do_', 'process_', 'send_', 'print_',
    'generate_', 'compute_', 'get_', 'check_', 'validate_',
    'confirm_', 'cancel_', 'reset_', 'refresh_', 'toggle_',
)


def _is_method_allowed(method_name: str) -> tuple:
    """
    Check if method is allowed for execution.
    Returns (allowed: bool, reason: str)
    """
    # Block internal methods (start with _)
    if method_name.startswith('_'):
        return False, "Internal methods not allowed"

    # Block dangerous methods
    if method_name in BLOCKED_METHODS:
        return False, f"Method '{method_name}' is blocked for security"

    # Allow only methods with safe prefixes
    if not method_name.startswith(ALLOWED_PREFIXES):
        return False, (
            f"Method must start with: {', '.join(ALLOWED_PREFIXES)}"
        )

    return True, ""


@router.post("/execute", response_model=McpResponse)
async def execute_method(
    request: Request,
    request_data: ExecuteRequest,
    env: Annotated[Environment, Depends(require_oauth2_user)]
) -> McpResponse:
    """Execute a method on specific records"""
    ctx = _auth_ctx(request, env)

    data = request_data.model_dump()
    model_name = data.get("model")
    method_name = data.get("method")
    ids = data.get("ids", [])

    try:
        authz.ensure_enabled(ctx, env)
        ratelimit.ensure_within_limit(ctx, env)

        # SECURITY: Validate method is allowed
        allowed, reason = _is_method_allowed(method_name)
        if not allowed:
            raise errors.McpError(
                type="method_not_allowed", message=reason
            )

        # Check if model exists
        if model_name not in env:
            raise errors.McpError(
                type="model_not_found",
                message=f"Model '{model_name}' not found"
            )

        # Get the records
        records = env[model_name].browse(ids)

        # Check if records exist
        if not records.exists():
            msg = f"Records {ids} not found in '{model_name}'"
            raise errors.McpError(
                type="records_not_found", message=msg
            )

        # Check if method exists
        if not hasattr(records, method_name):
            msg = f"Method '{method_name}' not found in '{model_name}'"
            raise errors.McpError(
                type="method_not_found", message=msg
            )

        method = getattr(records, method_name)
        if not callable(method):
            msg = f"'{method_name}' is not callable in '{model_name}'"
            raise errors.McpError(type="not_callable", message=msg)

        # Execute the method
        args = data.get("args", [])
        kwargs = data.get("kwargs", {})

        # Execute method (may need sudo for access rights)
        result = method(*args, **kwargs)

        # Format result based on type
        if result is None:
            formatted_result = {"success": True, "result": None}
        elif isinstance(result, bool):
            formatted_result = {"success": result, "result": result}
        elif hasattr(result, 'id'):
            # It's a recordset
            if hasattr(result, 'ids'):
                res_ids = result.ids
            else:
                res_ids = [result.id]
            if hasattr(result, '_name'):
                res_model = result._name
            else:
                res_model = model_name
            formatted_result = {
                "success": True,
                "result": {"ids": res_ids, "model": res_model}
            }
        elif isinstance(result, (dict, list, str, int, float)):
            formatted_result = {"success": True, "result": result}
        else:
            formatted_result = {"success": True, "result": str(result)}

        authz.audit(
            ctx,
            operation="execute",
            model=model_name,
            status="success",
            env=env,
            request_excerpt={"method": method_name, "ids": ids},
            record_ids=ids
        )
        return McpResponse(ok=True, result=formatted_result)

    except errors.McpError as e:
        authz.audit(
            ctx,
            operation="execute",
            model=model_name,
            status="fail",
            env=env,
            request_excerpt=data,
            error_excerpt=str(e)
        )
        return McpResponse(ok=False, error=e.to_dict())
    except Exception as e:
        error_msg = str(e)
        authz.audit(
            ctx,
            operation="execute",
            model=model_name,
            status="fail",
            env=env,
            request_excerpt=data,
            error_excerpt=error_msg
        )
        return McpResponse(
            ok=False,
            error={
                "message": "Internal server error",
                "type": "execution_error",
                "details": {"method": method_name, "model": model_name}
            }
        )
