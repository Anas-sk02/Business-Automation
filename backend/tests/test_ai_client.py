"""Unit tests for Stage 4 Task 2: AI Provider Client, Safe Invocation & Cost Tracking.

Validates:
- Unified provider handling for Gemini and Claude
- Secure header authentication for Gemini (no API key in URL query parameters)
- Safety filter detection and timeout error handling
- Pydantic schema validation of structured JSON output
- Automatic 1-time retry on malformed JSON or validation failure
- Cost logging to public.api_costs and user-scoped campaign spent_amount update
- Concurrency limit via asyncio.Semaphore(3)
- Error handling for missing keys, network errors, timeouts, and invalid provider
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from pydantic import BaseModel, Field

from backend.models.analysis import AIAnalysisResult
from backend.services.ai_client import (
    AIClient,
    AIConfigError,
    AIProviderError,
    AIValidationError,
    AIResult,
)


class DummySchema(BaseModel):
    title: str
    score: int = Field(..., ge=0)


class MockPostgrestQuery:
    def __init__(self, data=None):
        self.data = data or []

    def eq(self, key, val):
        self.last_eq = (key, val)
        return self

    def insert(self, payload):
        self.inserted_payload = payload
        return self

    def select(self, fields):
        return self

    def update(self, payload):
        self.updated_payload = payload
        return self

    def execute(self):
        return self


class MockSupabaseClient:
    def __init__(self, campaign_spent=150.0, owned_campaign=True):
        self.api_costs_inserted = []
        self.campaign_updates = []
        self.campaign_spent = campaign_spent
        self.owned_campaign = owned_campaign

    def table(self, table_name: str):
        mock_q = MockPostgrestQuery()
        if table_name == "api_costs":
            def execute_insert():
                self.api_costs_inserted.append(mock_q.inserted_payload)
                return mock_q
            mock_q.execute = execute_insert
            return mock_q
        elif table_name == "campaigns":
            if self.owned_campaign:
                mock_q.data = [{"spent_amount": self.campaign_spent}]
            else:
                mock_q.data = []  # unowned campaign
            def execute_update():
                if hasattr(mock_q, "updated_payload"):
                    self.campaign_updates.append(mock_q.updated_payload)
                return mock_q
            mock_q.execute = execute_update
            return mock_q
        return mock_q


@pytest.fixture
def mock_db():
    return MockSupabaseClient()


@pytest.fixture
def gemini_client(mock_db):
    return AIClient(
        provider="gemini",
        api_key="test-gemini-key",
        model="gemini-2.0-flash",
        db_client=mock_db,
    )


@pytest.fixture
def claude_client(mock_db):
    return AIClient(
        provider="claude",
        api_key="test-claude-key",
        model="claude-3-5-sonnet-20241022",
        db_client=mock_db,
    )


class TestCostCalculation:
    def test_calculate_cost_gemini_flash(self, gemini_client):
        # gemini-2.0-flash: $0.10 input / 1M, $0.40 output / 1M
        # 10,000 input = $0.001, 2,000 output = $0.0008 -> total $0.0018
        cost = gemini_client.calculate_cost(input_tokens=10000, output_tokens=2000)
        assert cost == 0.0018

    def test_calculate_cost_claude_sonnet(self, claude_client):
        # claude-3-5-sonnet: $3.00 input / 1M, $15.00 output / 1M
        # 10,000 input = $0.03, 2,000 output = $0.03 -> total $0.06
        cost = claude_client.calculate_cost(input_tokens=10000, output_tokens=2000)
        assert cost == 0.06

    def test_calculate_cost_fallback_pricing(self, mock_db):
        client = AIClient(provider="gemini", model="unknown-future-model", db_client=mock_db)
        # default: $0.50 input / 1M, $1.50 output / 1M
        cost = client.calculate_cost(input_tokens=10000, output_tokens=10000)
        assert cost == 0.02


class TestApiCostLogging:
    def test_log_api_cost_inserts_and_increments_campaign(self, gemini_client, mock_db):
        payload = gemini_client.log_api_cost(
            campaign_id="camp-123",
            user_id="user-456",
            service="ai_analysis",
            operation="analysis",
            input_tokens=1500,
            output_tokens=300,
            cost_usd=0.0025,
            metadata={"lead_id": "lead-789"},
        )

        assert payload["service"] == "ai_analysis"
        assert payload["cost_usd"] == 0.0025
        assert payload["cost_inr"] > 0
        assert len(mock_db.api_costs_inserted) == 1
        assert mock_db.api_costs_inserted[0]["metadata"]["model"] == "gemini-2.0-flash"
        assert len(mock_db.campaign_updates) == 1
        # initial spent was 150.0 + cost_inr
        assert mock_db.campaign_updates[0]["spent_amount"] > 150.0

    def test_log_api_cost_empty_campaign_id(self, gemini_client, mock_db):
        payload = gemini_client.log_api_cost(
            campaign_id="",
            user_id="user-456",
            service="ai_analysis",
            operation="analysis",
            input_tokens=100,
            output_tokens=10,
            cost_usd=0.001,
        )
        assert payload == {}
        assert len(mock_db.api_costs_inserted) == 0

    def test_log_api_cost_unowned_campaign_no_update(self):
        unowned_db = MockSupabaseClient(owned_campaign=False)
        client = AIClient(provider="gemini", api_key="k", model="gemini-2.0-flash", db_client=unowned_db)

        client.log_api_cost(
            campaign_id="camp-unowned",
            user_id="user-other",
            service="ai_analysis",
            operation="analysis",
            input_tokens=100,
            output_tokens=10,
            cost_usd=0.001,
        )
        # Cost is inserted, but spent_amount update skipped because campaign is not owned by user
        assert len(unowned_db.campaign_updates) == 0


class TestJsonCleaning:
    def test_clean_raw_json(self):
        raw = '{"title": "Test", "score": 90}'
        assert AIClient._clean_json_markdown(raw) == raw

    def test_clean_markdown_fence(self):
        raw = '```json\n{"title": "Test", "score": 90}\n```'
        assert AIClient._clean_json_markdown(raw) == '{"title": "Test", "score": 90}'

    def test_clean_plain_code_fence(self):
        raw = '```\n{"title": "Test", "score": 90}\n```'
        assert AIClient._clean_json_markdown(raw) == '{"title": "Test", "score": 90}'


@pytest.mark.anyio
class TestGeminiProviderCalls:
    async def test_gemini_missing_api_key(self, mock_db):
        client = AIClient(provider="gemini", api_key="", db_client=mock_db)
        with pytest.raises(AIConfigError, match="AI_API_KEY is not configured"):
            await client._call_gemini_raw("Hello")

    async def test_gemini_success_call_and_header_auth(self, gemini_client):
        mock_response_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": '{"title": "Dental Clinic", "score": 85}'}]
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 250,
                "candidatesTokenCount": 45,
            },
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await gemini_client._call_gemini_raw("Analyze lead")

            # Check that header auth was used and key was NOT in URL
            call_url = mock_post.call_args[0][0]
            call_headers = mock_post.call_args[1]["headers"]
            assert "key=" not in call_url
            assert call_headers["x-goog-api-key"] == "test-gemini-key"

            assert 'Dental Clinic' in result["raw_text"]
            assert result["input_tokens"] == 250
            assert result["output_tokens"] == 45

    async def test_gemini_http_error(self, gemini_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Rate limit exceeded"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            with pytest.raises(AIProviderError, match="HTTP 429"):
                await gemini_client._call_gemini_raw("Analyze lead")

    async def test_gemini_safety_block(self, gemini_client):
        mock_response_data = {
            "candidates": [
                {
                    "finishReason": "SAFETY",
                    "content": {"parts": []},
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            with pytest.raises(AIProviderError, match="blocked by provider filters"):
                await gemini_client._call_gemini_raw("Analyze lead")

    async def test_gemini_timeout(self, gemini_client):
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timed out")):
            with pytest.raises(AIProviderError, match="timed out"):
                await gemini_client._call_gemini_raw("Analyze lead")

    async def test_gemini_non_json_response(self, gemini_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "<html>502</html>", 0)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            with pytest.raises(AIProviderError, match="non-JSON response"):
                await gemini_client._call_gemini_raw("Analyze lead")


@pytest.mark.anyio
class TestClaudeProviderCalls:
    async def test_claude_missing_api_key(self, mock_db):
        client = AIClient(provider="claude", api_key="", db_client=mock_db)
        with pytest.raises(AIConfigError, match="AI_API_KEY is not configured"):
            await client._call_claude_raw("Hello")

    async def test_claude_success_call(self, claude_client):
        mock_response_data = {
            "content": [
                {"text": '{"title": "Automotive Dealer", "score": 92}'}
            ],
            "usage": {
                "input_tokens": 400,
                "output_tokens": 60,
            },
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await claude_client._call_claude_raw("Analyze lead")
            assert 'Automotive Dealer' in result["raw_text"]
            assert result["input_tokens"] == 400
            assert result["output_tokens"] == 60

    async def test_claude_timeout(self, claude_client):
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timed out")):
            with pytest.raises(AIProviderError, match="timed out"):
                await claude_client._call_claude_raw("Analyze lead")


@pytest.mark.anyio
class TestStructuredOutputGeneration:
    async def test_generate_structured_output_success_first_try(self, gemini_client):
        valid_json = {
            "business_summary": "Premier salon in Indiranagar.",
            "strengths": ["Active booking"],
            "opportunities": [
                {
                    "issue": "Slow mobile page",
                    "evidence": "4.5s load time",
                    "impact": "May drop customers",
                    "recommendation": "Compress images",
                }
            ],
            "recommended_service": "Speed Optimization",
            "pitch_angle": "Double mobile inquiries with sub-2s speed.",
            "confidence": "high",
        }

        with patch.object(
            gemini_client,
            "_execute_provider_call",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = {
                "raw_text": f"```json\n{json.dumps(valid_json)}\n```",
                "input_tokens": 1200,
                "output_tokens": 300,
            }

            res: AIResult[AIAnalysisResult] = await gemini_client.generate_structured_output(
                prompt="Analyze lead",
                schema_class=AIAnalysisResult,
                campaign_id="camp-123",
                user_id="user-456",
            )

            assert isinstance(res.parsed, AIAnalysisResult)
            assert res.parsed.confidence == "high"
            assert res.input_tokens == 1200
            assert res.output_tokens == 300
            assert res.cost_usd > 0
            assert mock_call.call_count == 1

    async def test_generate_structured_output_retry_on_malformed_json(self, gemini_client):
        valid_json = {
            "title": "Recovered Title",
            "score": 75,
        }

        with patch.object(
            gemini_client,
            "_execute_provider_call",
            new_callable=AsyncMock,
        ) as mock_call:
            # 1st call returns broken JSON, 2nd call returns valid JSON
            mock_call.side_effect = [
                {
                    "raw_text": "Here is the result: {broken json",
                    "input_tokens": 500,
                    "output_tokens": 20,
                },
                {
                    "raw_text": json.dumps(valid_json),
                    "input_tokens": 600,
                    "output_tokens": 30,
                },
            ]

            res = await gemini_client.generate_structured_output(
                prompt="Generate title",
                schema_class=DummySchema,
                campaign_id="camp-123",
                user_id="user-456",
            )

            assert res.parsed.title == "Recovered Title"
            assert res.parsed.score == 75
            assert mock_call.call_count == 2
            # Both attempts logged to total tokens
            assert res.input_tokens == 1100
            assert res.output_tokens == 50

    async def test_generate_structured_output_fails_after_retry(self, gemini_client):
        with patch.object(
            gemini_client,
            "_execute_provider_call",
            new_callable=AsyncMock,
        ) as mock_call:
            # Both calls return invalid JSON
            mock_call.side_effect = [
                {"raw_text": "Not json at all", "input_tokens": 100, "output_tokens": 10},
                {"raw_text": "Still not json", "input_tokens": 150, "output_tokens": 10},
            ]

            with pytest.raises(AIValidationError, match="failed schema validation after 1 retry"):
                await gemini_client.generate_structured_output(
                    prompt="Generate title",
                    schema_class=DummySchema,
                    campaign_id="camp-123",
                    user_id="user-456",
                )

            assert mock_call.call_count == 2

    async def test_unsupported_provider(self, mock_db):
        client = AIClient(provider="openai_unsupported", api_key="test", db_client=mock_db)
        with pytest.raises(AIConfigError, match="Unsupported AI provider"):
            await client.generate_structured_output(
                prompt="test",
                schema_class=DummySchema,
                campaign_id="camp-123",
            )


@pytest.mark.anyio
class TestConcurrencySemaphore:
    async def test_concurrency_limit_semaphore(self, gemini_client):
        concurrent_count = 0
        max_concurrent = 0

        async def slow_mock_call(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            if concurrent_count > max_concurrent:
                max_concurrent = concurrent_count
            await asyncio.sleep(0.05)
            concurrent_count -= 1
            return {"raw_text": '{"title": "Test", "score": 10}', "input_tokens": 10, "output_tokens": 10}

        with patch.object(gemini_client, "_call_gemini_raw", side_effect=slow_mock_call):
            tasks = [
                gemini_client.generate_structured_output(
                    prompt=f"test {i}",
                    schema_class=DummySchema,
                    campaign_id="camp-123",
                )
                for i in range(6)
            ]
            results = await asyncio.gather(*tasks)

            assert len(results) == 6
            # Semaphore(3) should restrict maximum concurrent calls to at most 3
            assert max_concurrent <= 3
