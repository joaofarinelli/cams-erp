"""Dependency that enforces policy version acceptance."""
from fastapi import Depends, HTTPException

from app.db.models import User
from app.security.cognito import get_current_user

CURRENT_POLICY_VERSION = "v1.0"


def require_accepted_terms(user: User = Depends(get_current_user)) -> User:
    """Raise 412 if the user has not accepted the current policy version.

    Wire this dependency in place of (or chained after) get_current_user on
    any route that must enforce up-to-date term acceptance.  Not wired
    globally to avoid breaking existing behaviour; the web/mobile 412
    interceptors handle the re-acceptance UX.
    """
    if user.policy_version is None or user.policy_version != CURRENT_POLICY_VERSION:
        raise HTTPException(
            status_code=412,
            detail={
                "required_version": CURRENT_POLICY_VERSION,
                "message": "Você deve aceitar os termos atualizados para continuar.",
            },
        )
    return user
