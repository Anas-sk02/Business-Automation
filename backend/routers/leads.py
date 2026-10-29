"""Leads router for listing, filtering, and retrieving detailed lead records."""

from datetime import datetime, timezone
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status

from backend.database import supabase
from backend.dependencies import get_current_user, get_owned_campaign, get_owned_lead
from backend.models.lead import LeadResponse, LeadDetailResponse, PipelineStage
from backend.models.common import ResponseEnvelope, PaginatedEnvelope
from backend.models.audit import (
    StartAuditResponse,
    FullAuditReportResponse,
    WebsiteAuditResponse,
    EvidenceItemResponse,
)
from backend.services.audit import AuditService

logger = logging.getLogger("signalforge.leads")
router = APIRouter()


@router.get("/campaigns/{id}/leads", response_model=PaginatedEnvelope[LeadResponse])
async def list_campaign_leads(
    campaign: Dict[str, Any] = Depends(get_owned_campaign),
    user: Dict[str, Any] = Depends(get_current_user),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    min_score: Optional[int] = Query(default=None, ge=0, le=100, description="Minimum fit score (0-100)"),
    max_score: Optional[int] = Query(default=None, ge=0, le=100, description="Maximum fit score (0-100)"),
    stage: Optional[PipelineStage] = Query(default=None, description="Pipeline stage filter"),
    has_website: Optional[bool] = Query(default=None, description="Filter leads with/without website"),
    has_phone: Optional[bool] = Query(default=None, description="Filter leads with/without phone"),
    is_suppressed: Optional[bool] = Query(default=None, description="Filter suppressed / active leads"),
    search: Optional[str] = Query(default=None, max_length=100, description="Search by business name"),
    sort_by: str = Query(
        default="created_at",
        pattern=r"^(fit_score|business_name|created_at|rating)$",
        description="Field to sort by",
    ),
    sort_order: str = Query(
        default="desc",
        pattern=r"^(asc|desc)$",
        description="Sort direction (asc or desc)",
    ),
) -> PaginatedEnvelope[LeadResponse]:
    """List leads belonging to an owned campaign with pagination, sorting, and filtering."""
    if min_score is not None and max_score is not None and min_score > max_score:
        raise HTTPException(
            status_code=400,
            detail="min_score cannot be greater than max_score",
        )

    try:
        query = (
            supabase.table("leads")
            .select("*", count="exact")
            .eq("campaign_id", campaign["id"])
        )

        if min_score is not None:
            query = query.gte("fit_score", min_score)
        if max_score is not None:
            query = query.lte("fit_score", max_score)
        if stage is not None:
            query = query.eq("pipeline_stage", stage.value if hasattr(stage, "value") else str(stage))

        if has_website is True:
            query = query.not_.is_("website_url", "null")
        elif has_website is False:
            query = query.is_("website_url", "null")

        if has_phone is True:
            query = query.not_.is_("phone", "null")
        elif has_phone is False:
            query = query.is_("phone", "null")

        if is_suppressed is not None:
            query = query.eq("is_suppressed", is_suppressed)

        if search and search.strip():
            clean_search = search.strip()
            query = query.ilike("business_name", f"%{clean_search}%")

        descending = (sort_order.lower() == "desc")
        start = (page - 1) * page_size
        end = start + page_size - 1

        query = query.order(sort_by, desc=descending).range(start, end)
        response = query.execute()

        total_count = response.count if response.count is not None else len(response.data or [])
        items = [LeadResponse(**row) for row in (response.data or [])]

        return PaginatedEnvelope(
            data=items,
            total=total_count,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            f"Error listing leads for campaign {campaign['id']} (user {user['id']}): {exc}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve leads for campaign",
        ) from exc


@router.get("/leads/{id}", response_model=ResponseEnvelope[LeadDetailResponse])
async def get_lead_detail(
    lead: Dict[str, Any] = Depends(get_owned_lead),
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[LeadDetailResponse]:
    """Retrieve full details for an owned lead, including latest audit, analysis, and evidence."""
    lead_id = lead["id"]

    try:
        # Fetch latest website audit if available
        audit_res = (
            supabase.table("website_audits")
            .select("*")
            .eq("lead_id", lead_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        audit_data = audit_res.data[0] if audit_res.data else None

        # Fetch latest AI analysis if available
        analysis_res = (
            supabase.table("ai_analyses")
            .select("*")
            .eq("lead_id", lead_id)
            .order("analyzed_at", desc=True)
            .limit(1)
            .execute()
        )
        analysis_data = analysis_res.data[0] if analysis_res.data else None

        # Fetch evidence items if available
        evidence_res = (
            supabase.table("evidence_items")
            .select("*")
            .eq("lead_id", lead_id)
            .order("detected_at", desc=True)
            .execute()
        )
        evidence_data = evidence_res.data or []

        # Strip internal joined columns (e.g. 'campaigns' from get_owned_lead inner join)
        lead_dict = {k: v for k, v in lead.items() if k != "campaigns"}

        return ResponseEnvelope(
            data=LeadDetailResponse(
                **lead_dict,
                audit=audit_data,
                analysis=analysis_data,
                evidence=evidence_data,
            ),
            message="Lead retrieved successfully",
        )
    except Exception as exc:
        logger.error(
            f"Error retrieving lead detail for lead {lead_id} (user {user['id']}): {exc}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve lead details",
        ) from exc


@router.post(
    "/leads/{id}/start-audit",
    response_model=ResponseEnvelope[StartAuditResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_lead_audit(
    background_tasks: BackgroundTasks,
    lead: Dict[str, Any] = Depends(get_owned_lead),
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[StartAuditResponse]:
    """Initiate an automated website audit for an owned lead in the background.

    Per decisions.md Sections 4 & 5:
    - Path: POST /api/leads/{id}/start-audit (202 Accepted).
    - Advances lead pipeline stage to 'research_pending'.
    - Dispatches async audit pipeline in background.
    """
    lead_id = lead["id"]
    user_id = user["id"]

    try:
        # Check if audit is already running
        running_audit = (
            supabase.table("website_audits")
            .select("id, status")
            .eq("lead_id", lead_id)
            .eq("status", "running")
            .limit(1)
            .execute()
        )
        if running_audit.data:
            existing_id = running_audit.data[0]["id"]
            return ResponseEnvelope(
                data=StartAuditResponse(
                    audit_id=existing_id,
                    lead_id=lead_id,
                    status="running",
                    message="Website audit is already in progress",
                ),
                message="Audit already running",
            )

        # Transition lead stage to research_pending immediately
        supabase.table("leads").update({
            "pipeline_stage": "research_pending",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", lead_id).execute()

        audit_service = AuditService(db_client=supabase)
        background_tasks.add_task(audit_service.audit_lead_website, lead_id, user_id)

        return ResponseEnvelope(
            data=StartAuditResponse(
                audit_id=None,
                lead_id=lead_id,
                status="accepted",
                message="Website audit started in background",
            ),
            message="Audit initiated successfully",
        )
    except Exception as exc:
        logger.error(f"Error initiating audit for lead {lead_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to initiate website audit",
        ) from exc


@router.get(
    "/leads/{id}/audit",
    response_model=ResponseEnvelope[FullAuditReportResponse],
    status_code=status.HTTP_200_OK,
)
async def get_lead_audit_report(
    lead: Dict[str, Any] = Depends(get_owned_lead),
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[FullAuditReportResponse]:
    """Retrieve full website audit report and verified evidence items for an owned lead.

    Per decisions.md Section 8:
    - Screenshots are stored in private bucket.
    - API response returns signed URLs expiring after 1 hour (3600 seconds).
    """
    lead_id = lead["id"]
    audit_service = AuditService(db_client=supabase)

    try:
        # Fetch latest website audit
        audit_res = (
            supabase.table("website_audits")
            .select("*")
            .eq("lead_id", lead_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        audit_row = audit_res.data[0] if audit_res.data else None

        if not audit_row:
            return ResponseEnvelope(
                data=FullAuditReportResponse(
                    audit=None,
                    evidence=[],
                    signed_screenshot_desktop_url=None,
                    signed_screenshot_mobile_url=None,
                ),
                message="No audit has been performed for this lead",
            )

        # Fetch associated evidence items
        evidence_res = (
            supabase.table("evidence_items")
            .select("*")
            .eq("lead_id", lead_id)
            .order("detected_at", desc=True)
            .execute()
        )
        evidence_rows = evidence_res.data or []

        # Generate 1-hour signed URLs for screenshots per decisions.md Section 8
        signed_desktop = audit_service.get_signed_screenshot_url(
            audit_row.get("screenshot_desktop_url"), expires_in=3600
        )
        signed_mobile = audit_service.get_signed_screenshot_url(
            audit_row.get("screenshot_mobile_url"), expires_in=3600
        )

        audit_model = WebsiteAuditResponse(**audit_row)
        evidence_models = [EvidenceItemResponse(**row) for row in evidence_rows]

        return ResponseEnvelope(
            data=FullAuditReportResponse(
                audit=audit_model,
                evidence=evidence_models,
                signed_screenshot_desktop_url=signed_desktop,
                signed_screenshot_mobile_url=signed_mobile,
            ),
            message="Audit report retrieved successfully",
        )
    except Exception as exc:
        logger.error(f"Error fetching audit report for lead {lead_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve website audit report",
        ) from exc


