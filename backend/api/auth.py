"""ADMIN_TOKEN check for admin routes (SPEC §12). With no token configured (or the example value), admin is off."""
from __future__ import annotations

import hmac
import os

from fastapi import HTTPException


def require_admin(token: str | None) -> None:
    want = os.environ.get("ADMIN_TOKEN", "")
    if not want or want == "change-me":
        raise HTTPException(403, "Admin is disabled: set ADMIN_TOKEN on the server.")
    if not token or not hmac.compare_digest(token, want):
        raise HTTPException(401, "Admin token required (header X-Admin-Token).")
