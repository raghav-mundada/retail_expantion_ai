"""
Auth dependencies for FastAPI routes.

Two flavors:
  • optional_user — extracts user_id if a valid Bearer token is present,
                    else returns None. Use on public-by-default routes
                    that should still attribute runs to logged-in users.
  • require_user  — same but raises 401 when missing or invalid. Use on
                    /me/* routes that don't make sense without a session.

Both rely on Supabase Auth's JWT — we don't decode/verify the signature
ourselves. Instead we hand the token to supabase.auth.get_user(token),
which calls the Auth API and returns a User if the JWT is valid and
unexpired. This is a one-network-hop check per request; cache externally
if you ever need to scale.
"""

from typing import Optional

from fastapi import Header, HTTPException, status

from backend.db.client import get_client


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


def optional_user(
    authorization: Optional[str] = Header(default=None),
) -> Optional[str]:
    """Return Supabase user_id if a valid token is attached, else None."""
    token = _extract_token(authorization)
    if not token:
        return None
    try:
        db = get_client()
        resp = db.auth.get_user(token)
        user = getattr(resp, "user", None)
        return user.id if user else None
    except Exception:
        # Bad/expired token — treat as anonymous, don't blow up the request.
        return None


def require_user(
    authorization: Optional[str] = Header(default=None),
) -> str:
    """Same as optional_user but enforces a logged-in caller."""
    user_id = optional_user(authorization)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id
