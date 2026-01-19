from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PositiveInt


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    vat_number: str | None = Field(default=None, max_length=32)
    plan_name: str = Field(default="Base", min_length=1, max_length=120)
    seats_total: PositiveInt = 3


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    vat_number: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    vat_number: str | None
    is_active: bool


class CompanyCreateOut(BaseModel):
    company_id: int
    plan: str
    seats_total: int


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company_id: int
    plan_id: int
    seats_total: int
    status: str


class SubscriptionUpdate(BaseModel):
    seats_total: PositiveInt | None = None
    status: Literal["active", "canceled", "past_due"] | None = None


class PlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    included_seats: PositiveInt = 3


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    included_seats: int


class CompanyDetailOut(BaseModel):
    company: CompanyOut
    subscription: SubscriptionOut | None
    plan: PlanOut | None


class CompanyUsageOut(BaseModel):
    company_id: int
    active_users: int
    seats_total: int
    available_seats: int


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    role: str = Field(default="hr_user", min_length=1, max_length=32)


class UserUpdate(BaseModel):
    is_active: bool


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
