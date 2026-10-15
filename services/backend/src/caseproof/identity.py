"""Identity adapters and organisation membership.

Hosted: Identity-Aware Proxy. The web server forwards the signed IAP assertion; the API verifies its audience
and subject and resolves membership server-side on every request (revocation takes effect immediately).
Local: seeded development personas, loopback only, refused when the environment is `cloud`.
A plain email or organisation header is never trusted.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select

from .actors import Actor
from .config import get_settings
from .db import global_session
from .errors import Forbidden, Unauthenticated
from .models import Membership, Organisation, User

SESSION_COOKIE = "cp_session"
SESSION_MAX_AGE = 12 * 3600
IAP_HEADER = "x-goog-iap-jwt-assertion"


@dataclass
class SessionData:
    subject: str
    sid: str
    org_id: str | None


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret, salt="caseproof-session")


def sign_session(data: SessionData) -> str:
    return _serializer().dumps({"sub": data.subject, "sid": data.sid, "org": data.org_id})


def read_session(token: str | None) -> SessionData | None:
    if not token:
        return None
    try:
        raw = _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None
    return SessionData(raw["sub"], raw["sid"], raw.get("org"))


def new_session(subject: str, org_id: str | None) -> SessionData:
    return SessionData(subject, secrets.token_urlsafe(18), org_id)


def csrf_token(session: SessionData) -> str:
    return hmac.new(
        get_settings().session_secret.encode(), f"csrf:{session.sid}".encode(), hashlib.sha256
    ).hexdigest()


def verify_iap(assertion: str) -> dict[str, Any]:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    settings = get_settings()
    claims = id_token.verify_token(
        assertion,
        google_requests.Request(),
        audience=settings.iap_audience,
        certs_url="https://www.gstatic.com/iap/verify/public_key",
    )
    if claims.get("iss") != "https://cloud.google.com/iap":
        raise Unauthenticated("BAD_ASSERTION", "Identity assertion issuer is not IAP.")
    return claims


def is_loopback(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost", "testclient")


def resolve_subject(request: Request) -> tuple[str, SessionData | None]:
    """Return the verified identity subject for this request."""
    settings = get_settings()
    assertion = request.headers.get(IAP_HEADER)
    if settings.environment == "cloud":
        if not assertion:
            raise Unauthenticated("NO_IDENTITY", "A verified identity is required.")
        claims = verify_iap(assertion)
        session = read_session(request.cookies.get(SESSION_COOKIE))
        # The email inside the signed, verified assertion (never a plain header) maps to a seeded account.
        subject = f"iap:{str(claims.get('email', claims['sub'])).lower()}"
        return subject, session if session and session.subject == subject else None
    if not settings.dev_identity or not is_loopback(request):
        raise Unauthenticated("NO_IDENTITY", "Development identities are only available on loopback.")
    session = read_session(request.cookies.get(SESSION_COOKIE))
    if session is None:
        raise Unauthenticated("NO_SESSION", "Sign in to continue.")
    return session.subject, session


def memberships_for(subject: str) -> tuple[User, list[tuple[Membership, Organisation]]]:
    with global_session() as session:
        user = session.execute(select(User).where(User.subject == subject)).scalar_one_or_none()
        if user is None:
            raise Unauthenticated("UNKNOWN_USER", "This identity has no CaseProof account.")
        rows = session.execute(
            select(Membership, Organisation)
            .join(Organisation, Organisation.id == Membership.org_id)
            .where(Membership.user_id == user.id, Membership.revoked_at.is_(None))
            .order_by(Organisation.name)
        ).all()
        return user, [(m, o) for m, o in rows]


def actor_for(
    request: Request,
) -> tuple[Actor, SessionData | None, User, list[tuple[Membership, Organisation]]]:
    subject, session = resolve_subject(request)
    user, memberships = memberships_for(subject)
    if not memberships:
        raise Forbidden("NO_MEMBERSHIP", "Your access to CaseProof has been revoked.")
    chosen = None
    if session and session.org_id:
        chosen = next(((m, o) for m, o in memberships if str(o.id) == session.org_id), None)
    if chosen is None:
        chosen = memberships[0]
    membership, org = chosen
    actor = Actor(
        "person", f"user:{user.id}", user.display_name, org.id, frozenset(membership.roles), user.id
    )
    return actor, session, user, memberships
