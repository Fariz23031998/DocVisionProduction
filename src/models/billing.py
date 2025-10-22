from datetime import datetime
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


class Subscription(BaseModel):
    id: str
    user_id: str
    plan: Literal['free-trial', 'standard', 'pro']
    status: Literal['active', 'cancelled', 'expired']
    ai_processing: int = 0
    last_monthly_regen: Optional[datetime] = None
    last_daily_regen: Optional[datetime] = None
    started_at: datetime
    expires_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

class SubscriptionCreate(BaseModel):
    plan: Literal['free-trial', 'standard', 'pro']
    months: Optional[int] = Field(None, ge=1, le=24, description="Number of months for subscription (1-24)")

class SubscriptionUpdate(BaseModel):
    plan: Optional[Literal['free-trial', 'standard', 'pro']] = None
    status: Optional[Literal['active', 'cancelled', 'expired']] = None

class SubscriptionActivate(BaseModel):
    """Model for activating/extending subscription"""
    plan: Literal['standard', 'pro']
    months: int = Field(..., ge=1, le=24, description="Number of months to activate/extend (1-24)")

class SubscriptionResponse(BaseModel):
    subscription: Subscription
    limits: dict

class PlanLimits(BaseModel):
    plan: Literal['free-trial', 'standard', 'pro']
    max_ai_file_processing: int
    features: list[str]

class Order(BaseModel):
    id: str
    user_id: str
    plan: Literal['standard', 'pro']
    months: int
    amount: float
    currency: str = "UZS"
    status: Literal['pending', 'paid', 'failed', 'cancelled', 'expired']
    payment_provider: Optional[str] = None
    payment_transaction_id: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[str] = None

class UserOrderResponse(BaseModel):
    order_info: Order
    payment_url: str = None

class OrderCreate(BaseModel):
    plan: Literal['standard', 'pro']
    months: int = Field(..., ge=1, le=24, description="Number of months (1-24)")
    payment_provider: Optional[str] = Field(None, description="Payment provider (stripe, paypal, etc.)")

class OrderResponse(BaseModel):
    order: Order
    message: str
    payment_url: str = None

class PaymentWebhook(BaseModel):
    """Webhook payload from payment provider"""
    order_id: str = Field(..., description="Order ID from your system")
    transaction_id: str = Field(..., description="Transaction ID from payment provider")
    status: Literal['paid', 'failed'] = Field(..., description="Payment status")
    payment_provider: str = Field(..., description="Payment provider name (stripe, paypal, etc.)")
    amount: Optional[float] = Field(None, description="Amount paid")
    currency: Optional[str] = Field(None, description="Currency code")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata from payment provider")

class ActivateSubscriptionWithOrder(BaseModel):
    order_id: str = Field(..., description="Order ID to use for activation")

class AIProcessingOperation(BaseModel):
    id: int
    subscription_id: str
    amount: int
    is_positive: bool
    created_at: datetime

class SubscriptionInfo(BaseModel):
    id: str
    user_id: str
    plan: str
    status: str
    ai_processing: int
    last_monthly_regen: datetime
    last_daily_regen: Optional[datetime] = None
    started_at: datetime
    expires_at: datetime
    cancelled_at: Optional[datetime] = None


class SubscriptionSummary(BaseModel):
    subscription_info: Optional[SubscriptionInfo] = None
    used_credits: int
    remaining_credits: int
    monthly_regeneration: int
    daily_regeneration: int
    last_monthly_regen: datetime
    last_daily_regen: Optional[datetime] = None
    price: int