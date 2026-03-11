import uuid
from datetime import datetime, timezone
from pydantic import BaseModel
from fastapi import HTTPException
from backend.config import db

# Credit rates for different operations (cost multiplier of OpenRouter)
# These rates can be configured by admin
DEFAULT_CREDIT_RATES = {
    # Legacy operations (do not change):
    "company_values_generation": 1.5,
    "job_description_generation": 1.5,
    "playbook_generation": 1.5,
    "cv_parsing_ai": 1.3,
    "candidate_analysis": 2.0,
    "tag_extraction": 1.5,
    # Assessment OS operations (Phase 2 integration points):
    "evidence_analysis": 2.0,    # CV + knowledge test analysis
    "roleplay_session": 5.0,     # Multi-turn roleplay (token-heavy)
    "competency_scoring": 1.5,   # AI narrative + gap analysis
}

class CreditUsageLog(BaseModel):
    id: str
    user_id: str
    operation_type: str
    tokens_used: int
    openrouter_cost: float  # Actual cost from OpenRouter
    credits_charged: float  # Cost to user (with margin)
    model_used: str
    created_at: str

class CreditCheckResult(BaseModel):
    has_credits: bool
    current_balance: float
    required_credits: float
    message: str

async def get_credit_rate(operation_type: str) -> float:
    """Get credit rate multiplier for an operation type."""
    # Try to get from admin settings, otherwise use default
    admin_settings = await db.admin_settings.find_one({"type": "credit_rates"}, {"_id": 0})
    if admin_settings and operation_type in admin_settings.get("rates", {}):
        return admin_settings["rates"][operation_type]
    return DEFAULT_CREDIT_RATES.get(operation_type, 1.5)

async def check_user_credits(user_id: str, estimated_credits: float = 0.0) -> CreditCheckResult:
    """
    Check if user has sufficient credits and a valid (non-expired) account.
    Returns 403 for expired accounts, 402 for insufficient credits.
    """
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        return CreditCheckResult(
            has_credits=False,
            current_balance=0.0,
            required_credits=estimated_credits,
            message="User not found"
        )

    # Expiry date check — raises 403 immediately (hard block)
    expiry_date_str = user.get("expiry_date")
    if expiry_date_str:
        try:
            expiry = datetime.fromisoformat(expiry_date_str)
            # Ensure expiry is timezone-aware for comparison
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expiry:
                raise HTTPException(
                    status_code=403,
                    detail="Account expired. Please contact your administrator to renew access."
                )
        except ValueError:
            pass  # Malformed date — skip check, don't block

    current_credits = user.get("credits", 0.0)

    # If current balance is already negative or zero, block with 402
    if current_credits <= 0:
        return CreditCheckResult(
            has_credits=False,
            current_balance=current_credits,
            required_credits=estimated_credits,
            message=f"Insufficient credits. Current balance: {current_credits:.2f}. Please top up to continue using AI features."
        )

    # If this operation would make balance negative but user hasn't gone negative yet, allow it once
    return CreditCheckResult(
        has_credits=True,
        current_balance=current_credits,
        required_credits=estimated_credits,
        message="Credits available"
    )

async def deduct_credits(
    user_id: str, 
    operation_type: str, 
    tokens_used: int,
    openrouter_cost: float,
    model_used: str
) -> dict:
    """
    Deduct credits from user account and log the usage.
    Allows balance to go negative once.
    """
    # Get credit rate
    rate = await get_credit_rate(operation_type)
    credits_to_deduct = openrouter_cost * rate
    
    # Update user credits
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    current_credits = user.get("credits", 0.0)
    new_balance = current_credits - credits_to_deduct
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"credits": new_balance}}
    )
    
    # Log usage
    usage_log = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "operation_type": operation_type,
        "tokens_used": tokens_used,
        "openrouter_cost": openrouter_cost,
        "credits_charged": credits_to_deduct,
        "model_used": model_used,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.credit_usage_logs.insert_one(usage_log)
    
    return {
        "previous_balance": current_credits,
        "credits_deducted": credits_to_deduct,
        "new_balance": new_balance,
        "tokens_used": tokens_used
    }

async def estimate_credits_for_operation(operation_type: str, estimated_tokens: int = 1000) -> float:
    """
    Estimate credits needed for an operation.
    Used for pre-checks before expensive operations.
    """
    rate = await get_credit_rate(operation_type)
    # Rough estimate: $0.10 per 1M tokens for gpt-4o-mini input
    estimated_cost = (estimated_tokens / 1_000_000) * 0.10
    return estimated_cost * rate
