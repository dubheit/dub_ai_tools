# Copyright 2025 Dubhe Srls
# License LGPL-3
"""
Custom FastAPI dependencies for MCP authentication.
Uses OAuth2 tokens from dub_oauth2_provider.
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env

_logger = logging.getLogger(__name__)


def get_bearer_token(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def oauth2_user_env(
    request: Request,
    env: Environment = Depends(odoo_env),
) -> Environment:
    """
    Get environment with user context from OAuth2 token.
    Supports both OAuth2 access tokens and personal tokens.
    Falls back to public user if no valid token provided.
    """
    token_string = get_bearer_token(request)

    if not token_string:
        _logger.debug("No Bearer token provided, using public user")
        return env

    ip_address = request.client.host if request.client else None

    # Try OAuth2 access token first
    try:
        AccessToken = env["oauth2.access_token"].sudo()
        token = AccessToken.search([
            ("token", "=", token_string),
            ("revoked", "=", False)
        ], limit=1)

        if token and token.is_valid():
            user = token.user_id
            _logger.debug(
                "Authenticated via OAuth2 token: user=%s", user.login
            )
            token.update_last_used(ip_address)
            return env(user=user.id)
    except KeyError:
        _logger.debug("oauth2.access_token model not available")
    except Exception as e:
        _logger.warning("Error validating OAuth2 token: %s", e)

    # Try personal token
    try:
        PersonalToken = env["oauth2.personal_token"].sudo()
        personal = PersonalToken.find_by_token(token_string)

        if personal and personal.is_valid():
            user = personal.user_id
            _logger.debug(
                "Authenticated via personal token: user=%s", user.login
            )
            personal.update_last_used(ip_address)
            return env(user=user.id)
    except KeyError:
        _logger.debug("oauth2.personal_token model not available")
    except Exception as e:
        _logger.warning("Error validating personal token: %s", e)

    _logger.warning("Invalid or expired token")
    # Return default env (public user)
    return env


def require_oauth2_user(
    request: Request,
    env: Environment = Depends(odoo_env),
) -> Environment:
    """
    Require valid OAuth2 authentication.
    Raises 401 if no valid token provided.
    """
    token_string = get_bearer_token(request)

    if not token_string:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        AccessToken = env["oauth2.access_token"].sudo()
        token = AccessToken.search([
            ("token", "=", token_string),
            ("revoked", "=", False)
        ], limit=1)

        if token and token.is_valid():
            user = token.user_id
            token.update_last_used(
                request.client.host if request.client else None
            )
            return env(user=user.id)

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth2 module not installed",
        )
    except Exception as e:
        _logger.exception("Error validating token")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal authentication error",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
