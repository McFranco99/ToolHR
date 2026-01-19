from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from .crud import active_users_count, can_add_user, get_active_subscription
from .db import get_db
from .models import Company, Plan, Subscription, User
from .schemas import (
    CompanyCreate,
    CompanyCreateOut,
    CompanyDetailOut,
    CompanyOut,
    CompanyUpdate,
    CompanyUsageOut,
    PlanCreate,
    PlanOut,
    SubscriptionUpdate,
    UserCreate,
    UserOut,
    UserUpdate,
)

app = FastAPI(title="Tool HR Backend")


# =========================
# Helpers DB
# =========================

def get_or_create_plan(db: Session, plan_name: str, included_seats: int) -> Plan:
    plan = db.query(Plan).filter(Plan.name == plan_name).first()
    if plan:
        return plan

    plan = Plan(name=plan_name, included_seats=included_seats)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


# =========================
# Routes
# =========================
@app.get("/health")
def health():
    return {"ok": True}


@app.post("/seed")
def seed(db: Session = Depends(get_db)):
    """
    Seed idempotente:
    - crea plan "Base" se non esiste
    - crea company "Demo Srl" se non esiste
    - crea subscription per Demo Srl se non esiste
    """
    plan = get_or_create_plan(db, "Base", included_seats=3)

    company = db.query(Company).filter(Company.name == "Demo Srl").first()
    if not company:
        company = Company(name="Demo Srl", vat_number="IT00000000000", is_active=True)
        db.add(company)
        db.commit()
        db.refresh(company)

    sub = db.query(Subscription).filter(Subscription.company_id == company.id).first()
    if not sub:
        sub = Subscription(company_id=company.id, plan_id=plan.id, seats_total=3, status="active")
        db.add(sub)
        db.commit()

    return {"company_id": company.id, "plan": plan.name}


@app.post("/plans", response_model=PlanOut)
def create_plan(payload: PlanCreate, db: Session = Depends(get_db)):
    existing = db.query(Plan).filter(Plan.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Plan già esistente con questo nome.")

    plan = Plan(name=payload.name, included_seats=payload.included_seats)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@app.get("/plans", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    return db.query(Plan).order_by(Plan.id.asc()).all()


@app.post("/companies", response_model=CompanyCreateOut)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    """
    Crea una nuova azienda + subscription.
    - 409 se esiste già un'azienda con lo stesso nome
    """
    existing = db.query(Company).filter(Company.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Company già esistente con questo nome.")

    # piano
    plan = get_or_create_plan(db, payload.plan_name, included_seats=payload.seats_total)
    if payload.seats_total < plan.included_seats:
        raise HTTPException(
            status_code=409,
            detail="I posti non possono essere inferiori ai posti inclusi nel piano.",
        )

    # company
    company = Company(name=payload.name, vat_number=payload.vat_number, is_active=True)
    db.add(company)
    db.commit()
    db.refresh(company)

    # subscription
    sub = Subscription(
        company_id=company.id,
        plan_id=plan.id,
        seats_total=payload.seats_total,
        status="active",
    )
    db.add(sub)
    db.commit()

    return {"company_id": company.id, "plan": plan.name, "seats_total": payload.seats_total}


@app.get("/companies", response_model=list[CompanyOut])
def list_companies(
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
    q: str | None = None,
):
    query = db.query(Company)
    if q:
        query = query.filter(Company.name.ilike(f"%{q}%"))

    return query.order_by(Company.id.asc()).offset(offset).limit(limit).all()


@app.patch("/companies/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company non trovata.")

    if payload.name is not None:
        existing = (
            db.query(Company)
            .filter(Company.name == payload.name, Company.id != company_id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Company già esistente con questo nome.")
        company.name = payload.name

    if payload.vat_number is not None:
        company.vat_number = payload.vat_number

    if payload.is_active is not None:
        company.is_active = payload.is_active

    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@app.get("/companies/{company_id}", response_model=CompanyDetailOut)
def get_company(company_id: int, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company non trovata.")

    sub = get_active_subscription(db, company_id)
    plan = None
    if sub:
        plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()

    return {"company": company, "subscription": sub, "plan": plan}


@app.get("/companies/{company_id}/usage", response_model=CompanyUsageOut)
def get_company_usage(company_id: int, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company non trovata.")

    seats = 0
    sub = get_active_subscription(db, company_id)
    if sub:
        seats = sub.seats_total

    active_users = active_users_count(db, company_id)
    available_seats = max(seats - active_users, 0)
    return {
        "company_id": company_id,
        "active_users": active_users,
        "seats_total": seats,
        "available_seats": available_seats,
    }


@app.patch("/companies/{company_id}/subscription", response_model=CompanyDetailOut)
def update_subscription(
    company_id: int,
    payload: SubscriptionUpdate,
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company non trovata.")

    sub = get_active_subscription(db, company_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription attiva non trovata.")

    if payload.seats_total is not None:
        active_users = active_users_count(db, company_id)
        if payload.seats_total < active_users:
            raise HTTPException(
                status_code=409,
                detail="I posti non possono essere inferiori agli utenti attivi.",
            )
        sub.seats_total = payload.seats_total

    if payload.status is not None:
        sub.status = payload.status

    db.add(sub)
    db.commit()
    db.refresh(sub)

    plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
    return {"company": company, "subscription": sub, "plan": plan}


@app.post("/companies/{company_id}/users", response_model=UserOut)
def create_user(company_id: int, payload: UserCreate, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company non trovata.")

    # email unica globale (se vuoi unica per company, dimmelo e lo cambiamo)
    existing = db.query(User).filter(User.email == str(payload.email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email già registrata.")

    if not can_add_user(db, company_id):
        raise HTTPException(status_code=409, detail="Limite licenze raggiunto. Acquista posti aggiuntivi.")

    user = User(
        company_id=company_id,
        email=str(payload.email),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.patch("/companies/{company_id}/users/{user_id}", response_model=UserOut)
def update_user(
    company_id: int,
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company non trovata.")

    user = db.query(User).filter(User.id == user_id, User.company_id == company_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato.")

    if payload.is_active and not user.is_active:
        if not can_add_user(db, company_id):
            raise HTTPException(status_code=409, detail="Limite licenze raggiunto. Acquista posti aggiuntivi.")

    user.is_active = payload.is_active
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/companies/{company_id}/users", response_model=list[UserOut])
def list_users(
    company_id: int,
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company non trovata.")

    return (
        db.query(User)
        .filter(User.company_id == company_id)
        .order_by(User.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
