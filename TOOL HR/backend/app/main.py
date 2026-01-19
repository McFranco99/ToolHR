from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from .db import get_db
from .models import Company, Plan, Subscription, User
from .crud import can_add_user

app = FastAPI(title="Tool HR Backend")


# =========================
# Pydantic Schemas (locali a main.py)
# =========================
class CompanyCreate(BaseModel):
    name: str
    vat_number: str | None = None
    plan_name: str = "Base"
    seats_total: int = 3


class CompanyOut(BaseModel):
    id: int
    name: str
    vat_number: str | None
    is_active: bool

    class Config:
        from_attributes = True


class SubscriptionOut(BaseModel):
    company_id: int
    plan_id: int
    seats_total: int
    status: str

    class Config:
        from_attributes = True


class PlanOut(BaseModel):
    id: int
    name: str
    included_seats: int

    class Config:
        from_attributes = True


class CompanyDetailOut(BaseModel):
    company: CompanyOut
    subscription: SubscriptionOut | None
    plan: PlanOut | None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "hr_user"


class UserOut(BaseModel):
    id: int
    company_id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


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


def get_active_subscription(db: Session, company_id: int) -> Subscription | None:
   
    return (
        db.query(Subscription)
        .filter(Subscription.company_id == company_id)
        .order_by(Subscription.id.desc())
        .first()
    )


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


@app.post("/companies")
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
def list_companies(db: Session = Depends(get_db)):
    return db.query(Company).order_by(Company.id.asc()).all()


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


@app.get("/companies/{company_id}/users", response_model=list[UserOut])
def list_users(company_id: int, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company non trovata.")

    return (
        db.query(User)
        .filter(User.company_id == company_id)
        .order_by(User.id.asc())
        .all()
    )
