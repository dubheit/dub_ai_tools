# Copyright 2025 Dubhe Srls
# License OPL-1

import time
from collections import defaultdict, deque

from . import errors

_BUCKETS = defaultdict(lambda: deque())


def _cfg(env):
    return env["mcp.server.config"].sudo().get_singleton()


def ensure_within_limit(ctx, env, config=None):
    cfg = config if config is not None else _cfg(env)
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
