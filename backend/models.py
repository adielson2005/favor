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


class NotificationPrefsIn(BaseModel):
    prefs: dict[str, bool]  # notification type -> enabled


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
    urgent: bool = False
    recurrence: str = "none"  # none | weekly | biweekly | monthly


class OrderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    subcategory_id: Optional[str] = None
    neighborhood_id: Optional[str] = None
    date_label: Optional[str] = None
    time_label: Optional[str] = None
    budget: Optional[float] = None
    photos: Optional[list[str]] = None
    fields: Optional[dict] = None
    urgent: Optional[bool] = None
    recurrence: Optional[str] = None


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
    target_type: str  # user | order | message
    target_id: str
    reason: str
    details: str = ""


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    city_id: Optional[str] = None
    neighborhood_id: Optional[str] = None
    avatar_b64: Optional[str] = None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


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


# ---------- financial ----------

class DepositIn(BaseModel):
    amount: float = Field(gt=0)
    method: str = "pix"  # pix | card (card reserved for future use)


class BankAccountIn(BaseModel):
    holder_name: str
    document: str = Field(min_length=11, max_length=14)  # CPF or CNPJ, digits only
    bank_code: str
    agency: str
    account_number: str
    account_type: str = "checking"  # checking | savings
    password: str  # reauthentication — adding a payout destination is high-risk


class BankAccountRemoveIn(BaseModel):
    password: str


class WithdrawalIn(BaseModel):
    amount: float = Field(gt=0)
    bank_account_id: str
    password: str  # reauthentication


class PayOrderIn(BaseModel):
    method: str = "wallet"  # wallet is the only method that can actually settle today
    password: Optional[str] = None  # only required/checked when payment risk comes back MEDIUM


class DisputeIn(BaseModel):
    target_type: str  # service | payment | worker | client
    order_id: str
    reason: str
    description: str = ""
    evidence: list[str] = []


class AdminWithdrawalActionIn(BaseModel):
    reason: str = ""


class AdminDisputeActionIn(BaseModel):
    status: str  # UNDER_REVIEW | WAITING_CUSTOMER | WAITING_PROVIDER | RESOLVED | REJECTED | CANCELLED
    resolution: str = ""
    resolution_action: str = "none"  # refund_client | release_worker | none


class AdminRiskFlagActionIn(BaseModel):
    status: str  # RESOLVED | DISMISSED
    note: str = ""


class AdminReportActionIn(BaseModel):
    status: str  # UNDER_REVIEW | RESOLVED | REJECTED
    resolution: str = ""


class AdminAdjustmentIn(BaseModel):
    user_id: str
    amount: float  # positive = credit, negative = debit
    reason: str = Field(min_length=3)


class CommissionConfigIn(BaseModel):
    commission_percent: Optional[float] = Field(default=None, ge=0, le=50)
    min_withdrawal: Optional[float] = Field(default=None, ge=0)
    max_withdrawal_per_day: Optional[float] = Field(default=None, ge=0)
    max_deposit_per_transaction: Optional[float] = Field(default=None, ge=0)
