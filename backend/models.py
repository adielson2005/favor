from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    city_id: str
    neighborhood_id: Optional[str] = None
    preference: Optional[str] = None  # client | worker | both


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthIn(BaseModel):
    id_token: str
    city_id: str = "city-parauapebas"  # used only when this Google sign-in creates a brand-new account


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    email: EmailStr
    code: str
    password: str = Field(min_length=8)


class SendVerificationIn(BaseModel):
    pass


class VerifyEmailIn(BaseModel):
    code: str


class PreferenceIn(BaseModel):
    preference: str  # client | worker | both


class OrderCreate(BaseModel):
    title: str
    description: str = ""
    type: str = "favor"  # favor | servico
    category_id: str
    subcategory_id: Optional[str] = None
    city_id: str
    neighborhood_id: Optional[str] = None
    date_label: str = "Hoje"
    time_label: str = ""
    budget: float = 0
    photos: list[str] = []
    fields: dict = {}


class ProposalCreate(BaseModel):
    amount: float
    message: str = ""
    eta: str = ""


class MessageCreate(BaseModel):
    text: str = ""
    image_b64: Optional[str] = None


class ReviewCreate(BaseModel):
    order_id: str
    to_id: str
    stars: int = Field(ge=1, le=5)
    comment: str = ""


class ReportCreate(BaseModel):
    target_type: str  # user | order
    target_id: str
    reason: str
    details: str = ""


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    city_id: Optional[str] = None
    neighborhood_id: Optional[str] = None


class BlockCreate(BaseModel):
    blocked_user_id: str


class FavoriteToggle(BaseModel):
    order_id: str


class CategoryIn(BaseModel):
    name: str
    icon: str = "sparkles-outline"
    active: bool = True


class SubcategoryIn(BaseModel):
    category_id: str
    name: str
    active: bool = True


class GeoStateIn(BaseModel):
    name: str
    uf: str
    active: bool = True


class GeoCityIn(BaseModel):
    state_id: str
    name: str
    active: bool = True


class GeoNeighborhoodIn(BaseModel):
    city_id: str
    name: str
    kind: str = "bairro"  # bairro | complexo | regiao | distrito | localidade
    active: bool = True


class ActivePatch(BaseModel):
    active: Optional[bool] = None
    name: Optional[str] = None
    icon: Optional[str] = None
    kind: Optional[str] = None
