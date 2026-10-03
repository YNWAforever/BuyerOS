"""One current membership predicate for owner lookup and submission."""
from sqlalchemy import String, cast, or_
from ..db.models import Membership, User


def eligible_owner_predicate(workspace_id):
    # Existing owner submission permits every active workspace member, including viewers.
    return (Membership.workspace_id == workspace_id) & Membership.active.is_(True)


def directory_search(q: str):
    literal=q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern=f"%{literal}%"
    return or_(User.display_name.ilike(pattern,escape="\\"),
               cast(Membership.user_id,String).ilike(pattern,escape="\\"),
               cast(Membership.id,String).ilike(pattern,escape="\\"))


def member_display_name(name: str | None, user_id) -> str:
    clean=" ".join((name or "").split())
    return clean or str(user_id)
