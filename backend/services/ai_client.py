"""AI Client Abstraction for Stage 4: AI Analysis & Multi-Provider Invocations.

Implements provider switching (Gemini default, Claude supported), strict JSON output
validation with Pydantic, concurrency limits (asyncio.Semaphore(3)), automatic
1-time retry on malformed JSON, token counting, and cost logging to public.api_costs.

Conforms to docs/decisions.md Sections 2, 7, 9, 11 and docs/prompts.md.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Generic, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel, ValidationError

from backend.config import settings
from backend.database import get_supabase_client

logger = logging.getLogger("signalforge.ai_client")

# Global semaphore restricting concurrent AI calls per docs/decisions.md Section 9
AI_SEMAPHORE = asyncio.Semaphore(3)

T = TypeVar("T", bound=BaseModel)


class AIClientError(Exception):
    """Base exception for all AI client errors."""
    pass


class AIConfigError(AIClientError):
    """Raised when provider configuration or API keys are missing or invalid."""
    pass


class AIProviderError(AIClientError):
    """Raised when the remote AI provider API returns an error or fails."""
    pass


class AIValidationError(AIClientError):
    """Raised when AI response fails JSON parsing or Pydantic validation after retry."""
    pass


@dataclass
class AIResult(Generic[T]):
    """Result container returned by AIClient after successful generation and validation."""

    parsed: T
    raw_text: str
    model_used: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cost_inr: float


class AIClient:
    """Unified client for Gemini and Claude AI provider operations."""

    # Pricing constants per 1,000,000 tokens (USD)
    PRICING_PER_1M = {
        "gemini-2.5-flash": {"input": 0.10, "output": 0.40},
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    }
    DEFAULT_PRICING = {"input": 0.50, "output": 1.50}

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        db_client: Optional[Any] = None,
        timeout: float = 45.0,
    ):
        self.provider = (provider if provider is not None else settings.AI_PROVIDER).lower()
        self.api_key = api_key if api_key is not None else settings.AI_API_KEY
        self.model = model if model is not None else settings.AI_MODEL
        self._db = db_client or get_supabase_client()
        self.timeout = timeout

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost in USD based on model pricing table."""
        rates = self.PRICING_PER_1M.get(self.model, self.DEFAULT_PRICING)
        cost = (input_tokens * rates["input"] / 1_000_000.0) + (output_tokens * rates["output"] / 1_000_000.0)
        return round(cost, 6)

    def log_api_cost(
        self,
        campaign_id: Optional[str],
        user_id: Optional[str],
        service: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record external AI API cost to public.api_costs and update campaign spent_amount.

        Per docs/decisions.md Section 11 & CLAUDE.md:
        - Every paid call writes a row to api_costs with USD and INR costs.
        - Campaign queries are scoped to user_id when provided.
        """
        if not campaign_id:
            logger.warning("log_api_cost called with empty campaign_id; skipping DB cost logging")
            return {}

        cost_inr = round(cost_usd * settings.USD_TO_INR_RATE, 2)
        meta = {
            "model": self.model,
            "provider": self.provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            **(metadata or {}),
        }

        cost_payload = {
            "campaign_id": campaign_id,
            "service": service,
            "operation": operation,
            "api_calls": 1,
            "cost_usd": float(cost_usd),
            "cost_inr": float(cost_inr),
            "metadata": meta,
        }

        # 1. Insert into api_costs
        try:
            self._db.table("api_costs").insert(cost_payload).execute()
        except Exception as e:
            logger.error(f"Failed to record api_costs for campaign {campaign_id}: {e}")

        # 2. Increment campaign spent_amount (user-scoped if user_id present)
        try:
            camp_query = self._db.table("campaigns").select("spent_amount").eq("id", campaign_id)
            if user_id:
                camp_query = camp_query.eq("user_id", user_id)
            camp_res = camp_query.execute()

            if camp_res.data:
                current_spent = float(camp_res.data[0].get("spent_amount") or 0.0)
                new_spent = round(current_spent + cost_inr, 2)
                update_query = (
                    self._db.table("campaigns")
                    .update({"spent_amount": new_spent})
                    .eq("id", campaign_id)
                )
                if user_id:
                    update_query = update_query.eq("user_id", user_id)
                update_query.execute()
            elif user_id:
                logger.warning(
                    f"Campaign {campaign_id} not found or unowned for user {user_id}; spent_amount was not updated"
                )
        except Exception as e:
            logger.error(f"Failed to increment spent_amount for campaign {campaign_id}: {e}")

        return cost_payload

    @staticmethod
    def _clean_json_markdown(raw_text: str) -> str:
        """Strip markdown fences (```json ... ```) or surrounding whitespace."""
        text = raw_text.strip()
        # Remove opening ```json or ```
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        # Remove closing ```
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    async def _call_gemini_raw(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute raw HTTP POST call to Google Gemini REST API using secure header authentication."""
        if not self.api_key:
            raise AIConfigError("AI_API_KEY is not configured for Gemini provider")

        # Use header authentication rather than query parameter to prevent key leakage in URLs/logs
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        headers = {
            "x-goog-api-key": self.api_key,
            "content-type": "application/json",
        }

        body: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2,
            },
        }

        if system_instruction:
            body["systemInstruction"] = {
                "parts": [{"text": system_instruction}],
            }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, headers=headers, json=body)
            except httpx.TimeoutException:
                raise AIProviderError(f"Gemini API request timed out after {self.timeout}s")
            except httpx.RequestError as exc:
                safe_msg = str(exc).replace(self.api_key, "[REDACTED]") if self.api_key else str(exc)
                raise AIProviderError(f"Gemini API network connection error: {safe_msg}") from exc

        if response.status_code != 200:
            safe_text = response.text[:500]
            if self.api_key:
                safe_text = safe_text.replace(self.api_key, "[REDACTED]")
            raise AIProviderError(
                f"Gemini API returned HTTP {response.status_code}: {safe_text}"
            )

        try:
            data = response.json()
        except Exception as e:
            raise AIProviderError(f"Gemini API returned non-JSON response payload: {e}") from e

        try:
            candidates = data.get("candidates") or []
            if not candidates:
                raise AIProviderError("Gemini API returned no candidates")

            candidate = candidates[0]
            finish_reason = candidate.get("finishReason")
            parts = candidate.get("content", {}).get("parts") or []
            if not parts:
                if finish_reason:
                    raise AIProviderError(
                        f"Gemini generation was blocked by provider filters (finishReason: {finish_reason})"
                    )
                raise AIProviderError("Gemini candidate contains no content parts")

            raw_text = parts[0].get("text") or ""
            usage = data.get("usageMetadata") or {}
            input_tokens = usage.get("promptTokenCount") or 0
            output_tokens = usage.get("candidatesTokenCount") or 0

            return {
                "raw_text": raw_text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        except Exception as e:
            if isinstance(e, AIProviderError):
                raise
            raise AIProviderError(f"Failed to parse Gemini response payload: {e}") from e

    async def _call_claude_raw(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute raw HTTP POST call to Anthropic Claude REST API."""
        if not self.api_key:
            raise AIConfigError("AI_API_KEY is not configured for Claude provider")

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        body: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": 0.2,
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }

        if system_instruction:
            body["system"] = system_instruction

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, headers=headers, json=body)
            except httpx.TimeoutException:
                raise AIProviderError(f"Claude API request timed out after {self.timeout}s")
            except httpx.RequestError as exc:
                safe_msg = str(exc).replace(self.api_key, "[REDACTED]") if self.api_key else str(exc)
                raise AIProviderError(f"Claude API network connection error: {safe_msg}") from exc

        if response.status_code != 200:
            safe_text = response.text[:500]
            if self.api_key:
                safe_text = safe_text.replace(self.api_key, "[REDACTED]")
            raise AIProviderError(
                f"Claude API returned HTTP {response.status_code}: {safe_text}"
            )

        try:
            data = response.json()
        except Exception as e:
            raise AIProviderError(f"Claude API returned non-JSON response payload: {e}") from e

        try:
            content = data.get("content") or []
            if not content:
                raise AIProviderError("Claude API returned no content blocks")

            raw_text = content[0].get("text") or ""
            usage = data.get("usage") or {}
            input_tokens = usage.get("input_tokens") or 0
            output_tokens = usage.get("output_tokens") or 0

            return {
                "raw_text": raw_text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        except Exception as e:
            if isinstance(e, AIProviderError):
                raise
            raise AIProviderError(f"Failed to parse Claude response payload: {e}") from e

    async def _execute_provider_call(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Route to appropriate provider under the global concurrency semaphore."""
        async with AI_SEMAPHORE:
            if self.provider == "gemini":
                return await self._call_gemini_raw(prompt, system_instruction)
            elif self.provider == "claude":
                return await self._call_claude_raw(prompt, system_instruction)
            else:
                raise AIConfigError(f"Unsupported AI provider: {self.provider}")

    async def generate_structured_output(
        self,
        prompt: str,
        schema_class: Type[T],
        campaign_id: str,
        user_id: Optional[str] = None,
        system_instruction: Optional[str] = None,
        service: str = "ai_analysis",
        operation: str = "analysis",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AIResult[T]:
        """Generate structured output validated against a Pydantic schema.

        Per docs/decisions.md Section 7:
        - Output is JSON, validated with Pydantic before use.
        - Invalid JSON gets ONE retry, then the step fails with a clear status.
        - Every AI call writes a row to api_costs.
        """
        current_prompt = prompt
        last_error = ""
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost_usd = 0.0
        final_raw_text = ""

        # Attempt up to 2 times (1 initial attempt + 1 retry per decisions.md Section 7)
        for attempt in range(1, 3):
            raw_response = await self._execute_provider_call(current_prompt, system_instruction)

            raw_text = raw_response["raw_text"]
            final_raw_text = raw_text
            in_tokens = raw_response["input_tokens"]
            out_tokens = raw_response["output_tokens"]
            call_cost = self.calculate_cost(in_tokens, out_tokens)

            total_input_tokens += in_tokens
            total_output_tokens += out_tokens
            total_cost_usd += call_cost

            # Log external API call cost to api_costs table
            if campaign_id:
                self.log_api_cost(
                    campaign_id=campaign_id,
                    user_id=user_id,
                    service=service,
                    operation=operation,
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    cost_usd=call_cost,
                    metadata={
                        **(metadata or {}),
                        "attempt": attempt,
                    },
                )

            cleaned_text = self._clean_json_markdown(raw_text)

            try:
                data_dict = json.loads(cleaned_text)
                if not isinstance(data_dict, dict):
                    raise ValueError(f"Expected JSON object, got {type(data_dict).__name__}")
                validated = schema_class.model_validate(data_dict)

                cost_inr = round(total_cost_usd * settings.USD_TO_INR_RATE, 2)
                return AIResult(
                    parsed=validated,
                    raw_text=final_raw_text,
                    model_used=self.model,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    cost_usd=round(total_cost_usd, 6),
                    cost_inr=cost_inr,
                )
            except (json.JSONDecodeError, ValueError, ValidationError) as err:
                last_error = str(err)
                logger.warning(
                    f"AI structured generation attempt {attempt} failed validation for campaign {campaign_id}: {err}"
                )
                if attempt == 1:
                    # Construct 1 retry prompt per decisions.md Section 7
                    current_prompt = (
                        f"{prompt}\n\n"
                        f"CRITICAL FORMATTING INSTRUCTION:\n"
                        f"Your previous response failed parsing with error: {last_error}\n"
                        f"Produce ONLY valid, raw JSON conforming strictly to the requested schema. "
                        f"Do NOT wrap in markdown code blocks or add any conversational text."
                    )

        raise AIValidationError(
            f"AI response failed schema validation after 1 retry. Last error: {last_error}. Raw output: {final_raw_text[:200]}"
        )
