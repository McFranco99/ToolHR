from sqlalchemy.orm import Session
from sqlalchemy import func
from .models import User, Subscription

def active_users_count(db: Session, company_id: int) -> int:
    return db.query(func.count(User.id)).filter(
        User.company_id == company_id,
        User.is_active == True
    ).scalar() or 0

def seats_total(db: Session, company_id: int) -> int:
    sub = db.query(Subscription).filter(Subscription.company_id == company_id).first()
    return sub.seats_total if sub else 0

def can_add_user(db: Session, company_id: int) -> bool:
    return active_users_count(db, company_id) < seats_total(db, company_id)
