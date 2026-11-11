"""FastAPI Router for WhatsApp Outreach, Draft Management, and Webhooks.

Implements endpoints conforming to:
- docs/decisions.md Sections 3, 4, 10, 11
- docs/implementation.md Stage 5 (Task 4)
- docs/api-reference.md Section 4
- docs/security.md
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from backend.database import get_supabase_client
from backend.dependencies import get_current_user, get_owned_lead
from backend.models.common import ResponseEnvelope
from backend.models.whatsapp import (
    GenerateDraftRequest,
    SendMessageRequest,
    SendMessageResponse,
    UpdateDraftRequest,
    WhatsAppDraftResponse,
    WhatsAppMessageResponse,
    WhatsAppSessionQRResponse,
    WhatsAppSessionStatus,
)
from backend.services.message_generator import (
    CampaignBudgetExceededError as DraftBudgetError,
    LeadNotFoundError,
    LeadSuppressedError as DraftSuppressedError,
    MessageGenerationError,
    MessageGeneratorService,
)
from backend.services.webhook_processor import WebhookProcessorService
from backend.services.whatsapp import (
    CampaignBudgetExceededError as DeliveryBudgetError,
    DailyLimitExceededError,
    LeadSuppressedError as DeliverySuppressedError,
    MessageAlreadySentError,
    MessageNotApprovedError,
    MessageNotFoundError,
    QuietHoursError,
    WhatsAppDeliveryError,
    WhatsAppService,
)

logger = logging.getLogger("signalforge.whatsapp_router")

router = APIRouter()


# ============================================================================
# Authenticated Outreach & Draft Endpoints
# ============================================================================

@router.post(
    "/leads/{id}/whatsapp/draft",
    response_model=ResponseEnvelope[WhatsAppDraftResponse],
    summary="Generate personalized WhatsApp outreach draft",
)
async def generate_outreach_draft(
    id: str,
    body: Optional[GenerateDraftRequest] = None,
    lead: Dict[str, Any] = Depends(get_owned_lead),
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[WhatsAppDraftResponse]:
    """Generate a high-converting, evidence-grounded WhatsApp message draft for an owned lead."""
    service = MessageGeneratorService()
    instructions = body.instructions if body else None
    template_name = body.template_name if body else None

    try:
        draft = await service.generate_draft(
            lead_id=lead["id"],
            user_id=user["id"],
            instructions=instructions,
            template_name=template_name,
        )
        return ResponseEnvelope(
            data=draft,
            message="Outreach draft generated successfully",
        )
    except LeadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (DraftSuppressedError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except DraftBudgetError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc))
    except MessageGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.get(
    "/leads/{id}/whatsapp/draft",
    response_model=ResponseEnvelope[Optional[WhatsAppDraftResponse]],
    summary="Retrieve current active draft message",
)
async def get_outreach_draft(
    id: str,
    lead: Dict[str, Any] = Depends(get_owned_lead),
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[Optional[WhatsAppDraftResponse]]:
    """Fetch the active attempt-0 outreach message draft for an owned lead."""
    service = MessageGeneratorService()
    try:
        draft = await service.get_draft(lead_id=lead["id"], user_id=user["id"])
        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active draft found for lead '{lead['id']}'",
            )
        return ResponseEnvelope(
            data=draft,
            message="Draft retrieved successfully",
        )
    except HTTPException:
        raise
    except LeadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put(
    "/leads/{id}/whatsapp/draft",
    response_model=ResponseEnvelope[WhatsAppDraftResponse],
    summary="Update draft message text or approval status",
)
async def update_outreach_draft(
    id: str,
    body: UpdateDraftRequest,
    lead: Dict[str, Any] = Depends(get_owned_lead),
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[WhatsAppDraftResponse]:
    """Manually edit draft text or advance status to 'pending_approval' or 'approved'."""
    service = MessageGeneratorService()
    try:
        updated = await service.update_draft(
            lead_id=lead["id"],
            user_id=user["id"],
            request=body,
        )
        return ResponseEnvelope(
            data=updated,
            message="Draft updated successfully",
        )
    except LeadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/leads/{id}/whatsapp/send",
    response_model=ResponseEnvelope[SendMessageResponse],
    summary="Send approved WhatsApp message",
)
async def send_whatsapp_message(
    id: str,
    body: Optional[SendMessageRequest] = None,
    lead: Dict[str, Any] = Depends(get_owned_lead),
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[SendMessageResponse]:
    """Dispatch an approved WhatsApp message with full guardrails and anti-double-send safety."""
    db = get_supabase_client()
    whatsapp_service = WhatsAppService(db_client=db)

    # 1. Resolve target message UUID
    target_msg_id: Optional[str] = body.message_id if body else None
    ignore_quiet_hours: bool = body.ignore_quiet_hours if body else False

    if target_msg_id:
        # Cross-lead / multi-tenant ownership check: verify message belongs to this lead & campaign
        chk_res = (
            db.table("whatsapp_messages")
            .select("id, status")
            .eq("id", target_msg_id)
            .eq("lead_id", lead["id"])
            .eq("campaign_id", lead["campaign_id"])
            .execute()
        )
        if not chk_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message '{target_msg_id}' not found for lead '{lead['id']}'",
            )
    else:
        # Look for the active approved draft for this lead
        active_res = (
            db.table("whatsapp_messages")
            .select("id, status")
            .eq("lead_id", lead["id"])
            .eq("campaign_id", lead["campaign_id"])
            .eq("direction", "outbound")
            .eq("followup_attempt", 0)
            .execute()
        )
        active_rows = active_res.data or []
        approved_rows = [r for r in active_rows if r.get("status") == "approved"]

        if approved_rows:
            target_msg_id = approved_rows[0]["id"]
        elif any(r.get("status") in ("draft", "pending_approval") for r in active_rows):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot send message: Draft has not been approved yet. Explicit approval is required before sending.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No approved message found for lead '{lead['id']}' to send",
            )

    # 2. Dispatch via WhatsApp service
    try:
        sent_response = await whatsapp_service.send_message(
            message_id=target_msg_id,
            user_id=user["id"],
            ignore_quiet_hours=ignore_quiet_hours,
        )
        return ResponseEnvelope(
            data=sent_response,
            message="Message sent successfully",
        )
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (MessageNotApprovedError, DeliverySuppressedError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except MessageAlreadySentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except QuietHoursError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except DailyLimitExceededError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
    except DeliveryBudgetError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc))
    except WhatsAppDeliveryError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.get(
    "/leads/{id}/whatsapp/messages",
    response_model=ResponseEnvelope[List[WhatsAppMessageResponse]],
    summary="Retrieve lead WhatsApp conversation history",
)
async def get_lead_whatsapp_messages(
    id: str,
    lead: Dict[str, Any] = Depends(get_owned_lead),
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[List[WhatsAppMessageResponse]]:
    """Retrieve chronological conversation history for the lead's WhatsApp timeline."""
    db = get_supabase_client()
    try:
        res = (
            db.table("whatsapp_messages")
            .select("*")
            .eq("lead_id", lead["id"])
            .eq("campaign_id", lead["campaign_id"])
            .order("created_at", desc=False)
            .execute()
        )
        raw_records = res.data or []
        validated_messages = [WhatsAppMessageResponse.model_validate(r) for r in raw_records]

        return ResponseEnvelope(
            data=validated_messages,
            message="Conversation history retrieved successfully",
        )
    except Exception as exc:
        logger.error(f"Failed to retrieve conversation history for lead {lead['id']}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve WhatsApp conversation history",
        ) from exc


# ============================================================================
# Multi-Tenant WhatsApp Session Management Endpoints
# ============================================================================

@router.get(
    "/whatsapp/session/status",
    response_model=ResponseEnvelope[WhatsAppSessionStatus],
    summary="Get user's isolated WhatsApp session status",
    tags=["WhatsApp"],
)
async def get_whatsapp_session_status(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve the real-time WAHA session connection status for the authenticated user."""
    db = get_supabase_client()
    svc = WhatsAppService(db_client=db)
    user_id = user["id"]

    try:
        status_info = await svc.get_session_status(user_id)

        # Sync detected phone number to user's profile if connected
        if status_info.get("connected") and status_info.get("phone_number"):
            phone = status_info["phone_number"]
            formatted_phone = f"+{phone}" if not phone.startswith("+") else phone
            try:
                db.table("profiles").update({"whatsapp_number": formatted_phone}).eq("id", user_id).execute()
            except Exception as e:
                logger.debug(f"Profile whatsapp sync notice: {e}")

        return {
            "data": WhatsAppSessionStatus(**status_info),
            "message": "WhatsApp session status retrieved",
        }
    except Exception as exc:
        logger.error(f"Error fetching WhatsApp session status for user {user_id}: {exc}", exc_info=True)
        return {
            "data": WhatsAppSessionStatus(
                session_name=svc.get_user_session_name(user_id),
                status="SERVICE_UNAVAILABLE",
                connected=False,
            ),
            "message": "WhatsApp service is currently offline or unreachable",
        }


@router.post(
    "/whatsapp/session/start",
    response_model=ResponseEnvelope[WhatsAppSessionStatus],
    summary="Initialize or start user's isolated WhatsApp session",
    tags=["WhatsApp"],
)
async def start_whatsapp_session(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Start or create an isolated WAHA session for the current user to prepare for QR scanning."""
    db = get_supabase_client()
    svc = WhatsAppService(db_client=db)
    user_id = user["id"]

    try:
        res = await svc.start_session(user_id)
        return {
            "data": WhatsAppSessionStatus(**res),
            "message": "WhatsApp session started",
        }
    except Exception as exc:
        logger.error(f"Error starting WhatsApp session for user {user_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start WhatsApp session: {exc}",
        ) from exc


@router.get(
    "/whatsapp/session/qr",
    response_model=ResponseEnvelope[WhatsAppSessionQRResponse],
    summary="Get WhatsApp QR pairing code",
    tags=["WhatsApp"],
)
async def get_whatsapp_qr_code(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Fetch QR code as base64 data URL for display on user's Settings screen."""
    db = get_supabase_client()
    svc = WhatsAppService(db_client=db)
    user_id = user["id"]

    try:
        session_name = svc.get_user_session_name(user_id)
        qr_code = await svc.get_session_qr(user_id)
        status_info = await svc.get_session_status(user_id)

        return {
            "data": WhatsAppSessionQRResponse(
                session_name=session_name,
                qr_code=qr_code,
                status=status_info.get("status", "SCAN_QR_CODE"),
            ),
            "message": "QR code retrieved successfully" if qr_code else "QR code not yet available. Please wait a moment.",
        }
    except Exception as exc:
        logger.error(f"Error retrieving QR code for user {user_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve QR code",
        ) from exc


@router.post(
    "/whatsapp/session/logout",
    response_model=ResponseEnvelope[Dict[str, Any]],
    summary="Disconnect user's WhatsApp session",
    tags=["WhatsApp"],
)
async def logout_whatsapp_session(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Disconnect and logout the authenticated user's WAHA session."""
    db = get_supabase_client()
    svc = WhatsAppService(db_client=db)
    user_id = user["id"]

    try:
        success = await svc.logout_session(user_id)
        # Clear whatsapp_number from profile
        try:
            db.table("profiles").update({"whatsapp_number": ""}).eq("id", user_id).execute()
        except Exception:
            pass

        return {
            "data": {"success": success, "session_name": svc.get_user_session_name(user_id)},
            "message": "WhatsApp session disconnected successfully",
        }
    except Exception as exc:
        logger.error(f"Error logging out WhatsApp session for user {user_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disconnect WhatsApp session",
        ) from exc


# ============================================================================
# Public Webhook Endpoints (Unauthenticated per security.md)
# ============================================================================

@router.post(
    "/webhooks/whatsapp",
    summary="WhatsApp provider webhook receiver",
    tags=["Webhooks"],
)
async def receive_whatsapp_webhook(request: Request) -> Dict[str, Any]:
    """Receive real-time delivery receipts and prospect inbound replies from WAHA or Twilio."""
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
    elif "application/x-www-form-urlencoded" in content_type:
        try:
            form_data = await request.form()
            payload = dict(form_data)
        except Exception:
            payload = {}
    else:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    service = WebhookProcessorService()

    try:
        if isinstance(payload, dict) and "event" in payload:
            # WAHA Container format
            result = await service.process_waha_webhook(payload)
        else:
            # Twilio format
            result = await service.process_twilio_webhook(payload if isinstance(payload, dict) else {})

        return {
            "status": "received",
            "data": result.model_dump(),
        }
    except Exception as exc:
        logger.error(f"Error handling WhatsApp webhook: {exc}", exc_info=True)
        return {
            "status": "error",
            "message": str(exc),
        }


@router.get(
    "/webhooks/whatsapp",
    summary="Meta webhook handshake challenge",
    tags=["Webhooks"],
)
async def verify_meta_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    """Respond to Meta/WhatsApp webhook verification challenge."""
    if hub_challenge:
        return PlainTextResponse(content=hub_challenge)
    return {"status": "active"}

