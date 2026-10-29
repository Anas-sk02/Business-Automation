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

export interface LeadDetail extends Lead {
  audit?: WebsiteAudit | null;
  analysis?: Record<string, unknown> | null;
  evidence?: EvidenceItem[];
}

