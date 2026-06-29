# Copyright 2025 Dubhe Srls
# License LGPL-3

import time
from collections import defaultdict, deque

from . import authz, errors

# In-process sliding-window buckets: key -> deque[timestamps].
#
# NOTE (multi-worker): counters are per worker process and not shared. With
# N HTTP workers the effective limit is up to N x configured. For strict
# enforcement, terminate the limit at the reverse proxy or move this to a
# shared store (Redis / ir.config_parameter). Acceptable as a per-worker
# safety throttle otherwise.
_BUCKETS = defaultdict(lambda: deque())


def _cfg(env, ctx=None):
    return authz.resolve_config(env, ctx)


def ensure_within_limit(ctx, env, config=None):
    cfg = config if config is not None else _cfg(env, ctx)
    if not cfg:
        # No config resolved → nothing to enforce (deny handled upstream).
        return
    window = max(1, cfg.rate_limit_window_s or 60)
    max_req = max(1, cfg.rate_limit_max_requests or 120)
    now = time.time()
    key = f"{ctx.user_id}:{ctx.ip}"
    q = _BUCKETS[key]
    while q and (now - q[0]) > window:
        q.popleft()
    if len(q) >= max_req:
        raise errors.RateLimited(
            f"Rate limit exceeded. Try later (window={window}s)."
        )
    q.append(now)
