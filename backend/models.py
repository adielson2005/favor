from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str = Field(min_length=8)
    city_id: str
    neighborhood_id: Optional[str] = None
    preference: Optional[str] = None  # client | worker | both
    accept_terms: bool = False


class LoginIn(BaseModel):
    identifier: str  # email or phone (E.164 or typed with punctuation)
    password: str


class VerifyPhoneIn(BaseModel):
    code: str


class ChangePhoneIn(BaseModel):
    phone: str
    # Optional: a user completing their profile for the first time (e.g. a new Google
    # account with no phone yet) has no existing phone to protect, so no reauth is
    # required. Required once the account already has a phone — see change_phone().
    password: Optional[str] = None


class ChangeEmailIn(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthIn(BaseModel):
    id_token: str
    nonce: Optional[str] = None  # replay protection — checked against the token's own nonce claim
    city_id: str = "city-parauapebas"  # used only when this Google sign-in creates a brand-new account


class GoogleLinkIn(BaseModel):
    id_token: str
    nonce: Optional[str] = None


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
    # Optional so a Google-only account (no password_hash yet) can set its FIRST
    # password through this same endpoint — there's no "current" one to check yet.
    current_password: Optional[str] = None
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
    # Only required the first time this user deposits via a real gateway (ASAAS
    # needs a CPF/CNPJ to create a customer) — omitted on every deposit after that.
    document: Optional[str] = None


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


class AdminWithdrawalApproveIn(BaseModel):
    # Only checked/required when the withdrawal amount is >= the configured
    # admin_reauth_threshold — see admin_auth.py's require_step_up_totp.
    totp_code: Optional[str] = None


class AdminDisputeActionIn(BaseModel):
    status: str  # UNDER_REVIEW | WAITING_CUSTOMER | WAITING_PROVIDER | RESOLVED | REJECTED | CANCELLED
    resolution: str = ""
    resolution_action: str = "none"  # refund_client | release_worker | none


class AdminAccountStatusIn(BaseModel):
    status: str  # ACTIVE | SUSPENDED | BLOCKED


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
    # Only checked/required when abs(amount) >= admin_reauth_threshold.
    totp_code: Optional[str] = None


class CommissionConfigIn(BaseModel):
    commission_percent: Optional[float] = Field(default=None, ge=0, le=50)
    min_withdrawal: Optional[float] = Field(default=None, ge=0)
    max_withdrawal_per_day: Optional[float] = Field(default=None, ge=0)
    max_deposit_per_transaction: Optional[float] = Field(default=None, ge=0)
    admin_reauth_threshold: Optional[float] = Field(default=None, ge=0)


# ---------- admin panel (RBAC) ----------

class AdminLoginIn(BaseModel):
    email: EmailStr
    password: str
    totp_code: Optional[str] = None


class AdminUserCreateIn(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    role: str  # OWNER | MANAGER | SUPPORT | MAINTENANCE


class AdminUserPatchIn(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None


class Admin2FAVerifyIn(BaseModel):
    code: str


class FeatureFlagPatchIn(BaseModel):
    enabled: bool


# ---------- support / feedback tickets ----------

TICKET_CATEGORIES = ("BUG", "IDEIA", "SUGESTAO", "RECLAMACAO", "PAGAMENTO", "CONTA", "SEGURANCA", "OUTRO")
TICKET_STATUSES = ("OPEN", "IN_PROGRESS", "WAITING_USER", "RESOLVED", "CLOSED")


class TicketCreate(BaseModel):
    category: str
    subject: str = Field(min_length=3, max_length=140)
    description: str = Field(min_length=1, max_length=4000)


class TicketMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class AdminTicketActionIn(BaseModel):
    status: Optional[str] = None
    category: Optional[str] = None
    assigned_to: Optional[str] = None
    transfer_to_maintenance: Optional[bool] = None


class NotificationSendIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=1000)
    target: str  # "all" | "user:{id}" | "city:{id}" | "category:{client|worker|both}"
