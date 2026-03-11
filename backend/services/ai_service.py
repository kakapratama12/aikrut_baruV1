import httpx
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import HTTPException
from backend.config import db

logger = logging.getLogger(__name__)

class AISettings(BaseModel):
    openrouter_api_key: Optional[str] = ""
    model_name: str = "openai/gpt-4o-mini"
    language: str = "en"  # en or id

async def get_ai_settings(user_id: str) -> AISettings:
    settings = await db.settings.find_one({"user_id": user_id}, {"_id": 0})
    if settings:
        return AISettings(**settings)
    return AISettings()

async def call_openrouter(api_key: str, model: str, messages: List[Dict], temperature: float = 0.7) -> str:
    """Legacy function for backward compatibility - returns only content."""
    result = await call_openrouter_with_usage(api_key, model, messages, temperature)
    return result["content"]

async def call_openrouter_with_usage(
    api_key: str, 
    model: str, 
    messages: List[Dict], 
    temperature: float = 0.7
) -> Dict[str, Any]:
    """
    Call OpenRouter API and return detailed usage information.
    Returns: {
        "content": str,
        "tokens_used": int,
        "cost": float (estimated from OpenRouter response)
    }
    """
    logger.info(f"call_openrouter_with_usage called - has_key: {bool(api_key)}, key_length: {len(api_key) if api_key else 0}, model: {model}")
    
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenRouter API key not configured. Please configure in admin settings.")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://aikrut.app",
                "X-Title": "Aikrut CV Screening"
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 4000
            }
        )
        
        if response.status_code != 200:
            error_detail = response.text
            logger.error(f"OpenRouter API error: {error_detail}")
            raise HTTPException(status_code=response.status_code, detail=f"AI API error: {error_detail}")
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # Extract usage information
        usage = result.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        
        # Extract cost if available (OpenRouter sometimes provides this)
        # Otherwise estimate based on model
        cost = 0.0
        if "cost" in result:
            cost = float(result["cost"])
        else:
            # Rough estimation based on tokens (conservative)
            # For gpt-4o-mini: ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            
            # Conservative estimate
            if "gpt-4o-mini" in model.lower():
                cost = (prompt_tokens / 1_000_000 * 0.15) + (completion_tokens / 1_000_000 * 0.60)
            elif "gpt-4o" in model.lower():
                cost = (prompt_tokens / 1_000_000 * 2.50) + (completion_tokens / 1_000_000 * 10.00)
            else:
                # Generic fallback
                cost = (total_tokens / 1_000_000) * 0.50
        
        return {
            "content": content,
            "tokens_used": total_tokens,
            "cost": cost,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0)
        }
