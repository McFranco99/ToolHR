from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import Subscription, User


def get_active_subscription(db: Session, company_id: int) -> Subscription | None:
    return (
        db.query(Subscription)
        .filter(
            Subscription.company_id == company_id,
            Subscription.status == "active",
        )
        .order_by(Subscription.id.desc())
        .first()
    )


def active_users_count(db: Session, company_id: int) -> int:
    return (
        db.query(func.count(User.id))
        .filter(
            User.company_id == company_id,
            User.is_active == True,
        )
        .scalar()
        or 0
    )


def seats_total(db: Session, company_id: int) -> int:
    sub = get_active_subscription(db, company_id)
    return sub.seats_total if sub else 0


def can_add_user(db: Session, company_id: int) -> bool:
    return active_users_count(db, company_id) < seats_total(db, company_id)
