// Central TypeScript types matching backend Pydantic models & database schema

export type CampaignStatus =
  | "draft"
  | "discovering"
  | "discovery_complete"
  | "auditing"
  | "active"
  | "paused"
  | "completed";

export type PipelineStage =
  | "discovered"
  | "research_pending"
  | "researched"
  | "qualified"
  | "contacted"
  | "followup_due"
  | "replied"
  | "interested"
  | "meeting_scheduled"
  | "proposal_sent"
  | "negotiation"
  | "won"
  | "closed_lost"
  | "not_interested"
  | "no_response"
  | "opted_out";

export interface StartDiscoveryResponse {
  campaign_id: string;
  status: CampaignStatus;
  queries_total: number;
  target_leads: number;
  estimated_duration_seconds: number;
  message?: string | null;
}

export interface DiscoveryStatus {
  campaign_id: string;
  status: CampaignStatus;
  discovery_queries_total: number;
  discovery_queries_completed: number;
  total_leads_found: number;
  target_leads: number;
  spent_amount: number;
  max_budget: number;
  is_near_budget: boolean;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface WhatsAppSettings {
  auto_send_after_approval: boolean;
  followup_gap_days: number;
  max_followups: number;
  quiet_hours_start: string;
  quiet_hours_end: string;
}

export interface Campaign {
  id: string;
  user_id: string;
  name: string;
  industry: string;
  industry_label: string;
  location: string;
  keywords: string[];
  target_leads: number;
  min_rating: number;
  service_offered: string;
  signals: string[];
  whatsapp_settings: WhatsAppSettings;
  max_budget: number;
  spent_amount: number;
  status: CampaignStatus;
  discovery_queries_total: number;
  discovery_queries_completed: number;
  total_leads_found: number;
  created_at?: string;
  updated_at?: string;
  started_at?: string;
  completed_at?: string;
}

export interface CreateCampaignInput {
  name: string;
  industry: string;
  industry_label: string;
  location: string;
  keywords: string[];
  target_leads: number;
  min_rating: number;
  service_offered: string;
  signals: string[];
  whatsapp_settings?: Partial<WhatsAppSettings>;
  max_budget?: number;
}

export interface UpdateCampaignInput {
  name?: string;
  industry?: string;
  industry_label?: string;
  location?: string;
  keywords?: string[];
  target_leads?: number;
  min_rating?: number;
  service_offered?: string;
  signals?: string[];
  whatsapp_settings?: Partial<WhatsAppSettings>;
  max_budget?: number;
}

export interface Lead {
  id: string;
  campaign_id: string;
  place_id?: string | null;
  business_name: string;
  category?: string | null;
  subcategories?: string[];
  address?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  phone?: string | null;
  email?: string | null;
  website_url?: string | null;
  rating?: number | null;
  review_count?: number | null;
  business_status?: string | null;
  opening_hours?: Record<string, unknown>;
  fit_score?: number | null;
  score_breakdown?: Record<string, unknown>;
  score_reasons?: string[];
  pipeline_stage: PipelineStage;
  source?: string | null;
  is_duplicate?: boolean;
  duplicate_of?: string | null;
  notes?: string | null;
  is_suppressed?: boolean;
  suppression_reason?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface LeadQueryParams {
  page?: number;
  page_size?: number;
  min_score?: number;
  max_score?: number;
  stage?: PipelineStage;
  has_website?: boolean;
  has_phone?: boolean;
  is_suppressed?: boolean;
  search?: string;
  sort_by?: "fit_score" | "business_name" | "created_at" | "rating";
  sort_order?: "asc" | "desc";
}

export interface UserProfile {
  id: string;
  email: string;
  full_name?: string | null;
  company_name?: string | null;
  whatsapp_number?: string | null;
  service_descriptions: string[];
  pricing_info: Record<string, unknown>;
  timezone: string;
  created_at?: string;
  updated_at?: string;
}

export interface UpdateProfileInput {
  full_name?: string;
  company_name?: string;
  whatsapp_number?: string;
  service_descriptions?: string[];
  pricing_info?: Record<string, unknown>;
  timezone?: string;
}

// API Envelope Types matching backend ResponseEnvelope and PaginatedEnvelope
export interface ResponseEnvelope<T> {
  data: T;
  message: string;
}

export interface PaginatedEnvelope<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiError {
  detail: string;
  error_code?: string;
}

// Stage 3 Audit & Evidence Types
export type AuditStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "timeout";

export type EvidenceType =
  | "audit_check"
  | "screenshot"
  | "lighthouse_report"
  | "link_check"
  | "content_scan"
  | "industry_check";

export type SeverityLevel = "critical" | "high" | "medium" | "low" | "info";

export type VerificationStatus = "verified" | "unverified" | "contradicted";

export interface EvidenceItem {
  id: string;
  lead_id: string;
  audit_id?: string | null;
  finding_title: string;
  description: string;
  evidence_type: EvidenceType;
  evidence_data?: Record<string, unknown>;
  severity: SeverityLevel;
  verification_status: VerificationStatus;
  detected_at: string;
}

export interface WebsiteAudit {
  id: string;
  lead_id: string;
  tested_url: string;
  dns_resolves?: boolean | null;
  http_status_code?: number | null;
  ssl_valid?: boolean | null;
  page_loads: boolean;
  load_time_seconds?: number | null;
  final_url?: string | null;
  mobile_overflow?: boolean | null;
  mobile_overflow_pixels?: number;
  has_contact_form?: boolean;
  has_phone_on_site?: boolean;
  has_email_on_site?: boolean;
  has_whatsapp_link?: boolean;
  has_social_links?: boolean;
  social_links?: Array<Record<string, unknown>>;
  page_title?: string | null;
  meta_description?: string | null;
  h1_headings?: string[];
  has_alt_texts?: boolean | null;
  missing_alt_count?: number;
  total_internal_links?: number;
  broken_links?: Array<Record<string, unknown>>;
  broken_link_count?: number;
  lighthouse_performance?: number | null;
  lighthouse_seo?: number | null;
  lighthouse_accessibility?: number | null;
  lighthouse_best_practices?: number | null;
  screenshot_desktop_url?: string | null;
  screenshot_mobile_url?: string | null;
  industry_checks?: Record<string, unknown>;
  status: AuditStatus;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface StartAuditResponse {
  audit_id?: string | null;
  lead_id: string;
  status: string;
  message: string;
}

export interface FullAuditReport {
  audit?: WebsiteAudit | null;
  evidence: EvidenceItem[];
  signed_screenshot_desktop_url?: string | null;
  signed_screenshot_mobile_url?: string | null;
}

export interface BatchAuditResponse {
  campaign_id: string;
  total_eligible_leads: number;
  audits_enqueued: number;
  status: string;
  message: string;
}

export type ConfidenceLevel = "high" | "medium" | "low";

export interface AnalysisOpportunity {
  issue: string;
  evidence: string;
  impact: string;
  recommendation: string;
}

export interface AIAnalysisResult {
  business_summary: string;
  strengths: string[];
  opportunities: AnalysisOpportunity[];
  recommended_service: string;
  pitch_angle: string;
  confidence: ConfidenceLevel;
}

export interface ClaimVerificationItem {
  claim: string;
  status: VerificationStatus;
  evidence_id?: string | null;
  matched_finding?: string | null;
}

export interface AIAnalysis {
  id: string;
  lead_id: string;
  model_used: string;
  prompt_version: string;
  analysis_result: AIAnalysisResult;
  recommended_service?: string | null;
  pitch_angle?: string | null;
  confidence: ConfidenceLevel;
  claim_verifications: ClaimVerificationItem[];
  total_claims: number;
  verified_claims: number;
  unverified_claims: number;
  contradicted_claims: number;
  input_tokens: number;
  output_tokens: number;
  api_cost_usd: number;
  analyzed_at: string;
}

export interface StartAnalysisResponse {
  analysis_id?: string | null;
  lead_id: string;
  status: string;
  message: string;
}

export interface BatchAnalysisResponse {
  campaign_id: string;
  total_eligible_leads: number;
  analyses_enqueued: number;
  status: string;
  message: string;
}

export interface LeadDetail extends Lead {
  audit?: WebsiteAudit | null;
  analysis?: AIAnalysis | null;
  evidence?: EvidenceItem[];
}

// ============================================================
// WhatsApp Integration Types (Stage 5)
// ============================================================

export type MessageDirection = "outbound" | "inbound";

export type MessageType = "text" | "template" | "image" | "document";

export type MessageStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "queued"
  | "sent"
  | "delivered"
  | "read"
  | "failed"
  | "cancelled";

export type ReplyClassification =
  | "interested"
  | "wants_info"
  | "pricing_request"
  | "meeting_request"
  | "not_interested"
  | "not_now"
  | "wrong_number"
  | "opt_out"
  | "unclear";

export interface WhatsAppMessage {
  id: string;
  lead_id: string;
  campaign_id: string;
  wa_message_id?: string | null;
  direction: MessageDirection;
  from_number?: string | null;
  to_number?: string | null;
  template_name?: string | null;
  template_variables?: Record<string, unknown>;
  message_body: string;
  message_type: MessageType;
  status: MessageStatus;
  error_message?: string | null;
  reply_classification?: ReplyClassification | null;
  classification_confidence?: number | null;
  followup_attempt: number;
  is_followup: boolean;
  conversation_cost: number;
  created_at: string;
  sent_at?: string | null;
  delivered_at?: string | null;
  read_at?: string | null;
  failed_at?: string | null;
}

export interface WhatsAppDraftResponse {
  message: WhatsAppMessage;
  lead_id: string;
  lead_name: string;
  recipient_phone?: string | null;
  evidence_cited: string[];
  estimated_cost_inr: number;
  status: MessageStatus;
}

export interface SendMessageResponse {
  message: WhatsAppMessage;
  lead_id: string;
  recipient_phone: string;
  provider: string;
  wa_message_id: string;
  sent_at: string;
  cost_inr: number;
}

export interface GenerateDraftRequest {
  instructions?: string;
  template_name?: string;
}

export interface UpdateDraftRequest {
  message_body: string;
  template_variables?: Record<string, unknown>;
  status?: MessageStatus;
}

export interface SendMessageRequest {
  message_id?: string;
  ignore_quiet_hours?: boolean;
}

// ============================================================
// Stage 6: Pipeline & Kanban Board Types
// ============================================================

export type ManualPipelineStage =
  | "meeting_scheduled"
  | "proposal_sent"
  | "negotiation"
  | "won"
  | "closed_lost"
  | "not_interested";

export const ALLOWED_MANUAL_STAGES: readonly ManualPipelineStage[] = [
  "meeting_scheduled",
  "proposal_sent",
  "negotiation",
  "won",
  "closed_lost",
  "not_interested",
] as const;

export const ACTIVE_PIPELINE_COLUMNS: readonly PipelineStage[] = [
  "qualified",
  "contacted",
  "followup_due",
  "replied",
  "interested",
  "meeting_scheduled",
  "proposal_sent",
  "negotiation",
  "won",
] as const;

export const CLOSED_RAIL_COLUMNS: readonly PipelineStage[] = [
  "not_interested",
  "no_response",
  "closed_lost",
  "opted_out",
] as const;

export interface PipelineLeadCard {
  id: string;
  campaign_id: string;
  campaign_name?: string | null;
  business_name: string;
  category?: string | null;
  address?: string | null;
  phone?: string | null;
  website_url?: string | null;
  fit_score: number;
  pipeline_stage: PipelineStage;
  rating?: number | null;
  review_count: number;
  notes?: string;
  is_suppressed: boolean;
  last_contacted_at?: string | null;
  next_followup_at?: string | null;
  created_at?: string | null;
}

export interface PipelineBoardResponse {
  columns: Record<string, PipelineLeadCard[]>;
  closed: Record<string, PipelineLeadCard[]>;
  stage_counts: Record<string, number>;
  total_active_leads: number;
  total_leads: number;
}

export interface UpdateLeadStageRequest {
  stage: ManualPipelineStage | string;
  notes?: string;
}

// ============================================================
// Stage 6: Tasks Management Types
// ============================================================

export type TaskType =
  | "followup"
  | "callback"
  | "review_lead"
  | "review_reply"
  | "approve_message"
  | "send_info"
  | "send_pricing"
  | "schedule_meeting"
  | "meeting_followup"
  | "send_proposal"
  | "general";

export type TaskStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "snoozed"
  | "cancelled";

export type TaskPriority = "urgent" | "high" | "medium" | "low";

export interface TaskResponse {
  id: string;
  lead_id?: string | null;
  lead_name?: string | null;
  campaign_id?: string | null;
  campaign_name?: string | null;
  user_id: string;
  task_type: TaskType | string;
  title: string;
  description?: string;
  status: TaskStatus | string;
  priority: TaskPriority | string;
  due_date?: string | null;
  snoozed_until?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TaskGroupCounts {
  overdue: number;
  today: number;
  upcoming: number;
  completed: number;
  total: number;
}

export interface TaskListResponse {
  tasks: TaskResponse[];
  counts: TaskGroupCounts;
}

export interface UpdateTaskRequest {
  status?: TaskStatus | string;
  priority?: TaskPriority | string;
  title?: string;
  description?: string;
  due_date?: string | null;
  snoozed_until?: string | null;
  snooze_preset?: "later_today" | "tomorrow" | "next_week" | string;
}

// Stage 7 Analytics Types per docs/decisions.md (Sections 4, 11) & docs/UI-UX.md (Section 6.11)
export interface FunnelStep {
  name: string;
  count: number;
  conversion_rate: number;
  overall_rate: number;
}

export interface MessagingMetrics {
  total_sent: number;
  total_delivered: number;
  total_read: number;
  total_replied: number;
  total_failed: number;
  total_opted_out: number;
  delivery_rate: number;
  read_rate: number;
  reply_rate: number;
}

export interface ServiceCostItem {
  service: string;
  api_calls: number;
  cost_usd: number;
  cost_inr: number;
}

export interface CostBreakdown {
  services: ServiceCostItem[];
  total_spend_usd: number;
  total_spend_inr: number;
  cost_per_qualified_lead_inr?: number | null;
  cost_per_won_deal_inr?: number | null;
}

export interface AnalyticsKPIs {
  total_campaigns: number;
  total_leads_found: number;
  total_audited: number;
  total_qualified: number;
  total_messages_sent: number;
  total_deals_won: number;
  total_spend_usd: number;
  total_spend_inr: number;
}

export interface AnalyticsOverviewResponse {
  has_sent_messages: boolean;
  kpis: AnalyticsKPIs;
  funnel: FunnelStep[];
  messaging: MessagingMetrics;
  costs: CostBreakdown;
}

export interface CampaignAnalyticsResponse {
  campaign_id: string;
  campaign_name: string;
  has_sent_messages: boolean;
  kpis: AnalyticsKPIs;
  funnel: FunnelStep[];
  messaging: MessagingMetrics;
  costs: CostBreakdown;
}

export interface CostsOverviewResponse {
  services: ServiceCostItem[];
  total_spend_usd: number;
  total_spend_inr: number;
  total_businesses_processed: number;
  cost_per_qualified_lead_inr?: number | null;
  cost_per_won_deal_inr?: number | null;
  cost_per_acquired_lead_inr?: number | null;
}

// Settings & Suppression Audit Types matching backend/models/settings.py
export interface SuppressionRecord {
  id: string;
  phone: string;
  business_name?: string | null;
  campaign_id: string;
  campaign_name: string;
  suppression_reason?: string | null;
  opted_out_at: string;
}

export interface SuppressionListResponse {
  suppressed_contacts: SuppressionRecord[];
  total: number;
  page: number;
  page_size: number;
}

// Notification Types
export type NotificationType =
  | "info"
  | "success"
  | "warning"
  | "error"
  | "action_required";

export interface AppNotification {
  id: string;
  user_id: string;
  title: string;
  message: string;
  type: NotificationType;
  link_url?: string | null;
  lead_id?: string | null;
  campaign_id?: string | null;
  is_read: boolean;
  created_at: string;
  read_at?: string | null;
}

export interface NotificationListResponse {
  notifications: AppNotification[];
  unread_count: number;
  total: number;
}

// Multi-Tenant WhatsApp Session Types
export type WhatsAppSessionState =
  | "WORKING"
  | "SCAN_QR_CODE"
  | "STARTING"
  | "STOPPED"
  | "FAILED"
  | "NOT_CONNECTED"
  | "SERVICE_UNAVAILABLE"
  | "UNKNOWN";

export interface WhatsAppSessionStatus {
  session_name: string;
  status: WhatsAppSessionState;
  connected: boolean;
  phone_number?: string | null;
  push_name?: string | null;
}

export interface WhatsAppSessionQRResponse {
  session_name: string;
  qr_code?: string | null;
  status: string;
}







