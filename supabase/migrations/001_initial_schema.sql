-- ============================================================
-- SignalForge AI — Database Schema
-- Migration 001: Initial Schema
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. USERS (extends Supabase auth.users)
-- ============================================================
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT NOT NULL DEFAULT '',
    company_name TEXT DEFAULT '',
    whatsapp_number TEXT DEFAULT '',
    service_descriptions JSONB DEFAULT '[]'::jsonb,
    -- Stores array of service strings the user offers
    -- e.g., ["Website Development", "SEO", "AI Automation"]
    pricing_info JSONB DEFAULT '{}'::jsonb,
    -- Stores pricing templates for AI reply assistant
    -- e.g., {"website_redesign": "₹25,000 - ₹50,000", ...}
    timezone TEXT DEFAULT 'Asia/Kolkata',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auto-create profile on user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================================
-- 2. CAMPAIGNS
-- ============================================================
CREATE TABLE public.campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    
    -- Campaign identity
    name TEXT NOT NULL,
    
    -- Targeting
    industry TEXT NOT NULL,
    -- e.g., "coaching_institutes", "electronics_shops", "clinics"
    industry_label TEXT NOT NULL,
    -- Human-readable: "Coaching Institutes", "Electronics Shops"
    location TEXT NOT NULL,
    -- e.g., "Nagpur, Maharashtra"
    keywords JSONB DEFAULT '[]'::jsonb,
    -- Additional search keywords: ["tuition", "classes", "academy"]
    target_leads INTEGER NOT NULL DEFAULT 50,
    min_rating DECIMAL(2,1) DEFAULT 0.0,
    
    -- Service offering
    service_offered TEXT NOT NULL,
    -- e.g., "Website Development", "Digital Marketing"
    
    -- Opportunity signals to investigate
    signals JSONB DEFAULT '[]'::jsonb,
    -- e.g., ["no_website", "mobile_issues", "missing_form", "poor_performance"]
    
    -- WhatsApp settings
    whatsapp_settings JSONB NOT NULL DEFAULT '{
        "auto_send_after_approval": false,
        "followup_gap_days": 3,
        "max_followups": 3,
        "quiet_hours_start": "21:00",
        "quiet_hours_end": "09:00"
    }'::jsonb,
    
    -- Budget
    max_budget DECIMAL(10,2) DEFAULT 0.00,
    -- 0 means no limit
    spent_amount DECIMAL(10,2) DEFAULT 0.00,
    
    -- Status
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN (
            'draft',
            'discovering',
            'discovery_complete',
            'auditing',
            'active',
            'paused',
            'completed'
        )),
    
    -- Discovery progress
    discovery_queries_total INTEGER DEFAULT 0,
    discovery_queries_completed INTEGER DEFAULT 0,
    total_leads_found INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_campaigns_user_id ON public.campaigns(user_id);
CREATE INDEX idx_campaigns_status ON public.campaigns(status);

-- ============================================================
-- 3. LEADS
-- ============================================================
CREATE TABLE public.leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES public.campaigns(id) ON DELETE CASCADE,
    
    -- Google Places data
    place_id TEXT,
    -- Google Places unique identifier
    business_name TEXT NOT NULL,
    category TEXT DEFAULT '',
    -- Primary business category from Google
    subcategories JSONB DEFAULT '[]'::jsonb,
    -- Additional categories/types
    
    -- Location
    address TEXT DEFAULT '',
    city TEXT DEFAULT '',
    state TEXT DEFAULT '',
    postal_code TEXT DEFAULT '',
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    
    -- Contact
    phone TEXT,
    email TEXT,
    website_url TEXT,
    
    -- Google data
    rating DECIMAL(2,1),
    review_count INTEGER DEFAULT 0,
    business_status TEXT DEFAULT 'OPERATIONAL',
    opening_hours JSONB DEFAULT '{}'::jsonb,
    
    -- Scoring
    fit_score INTEGER DEFAULT 0
        CHECK (fit_score >= 0 AND fit_score <= 100),
    score_breakdown JSONB DEFAULT '{}'::jsonb,
    -- e.g., {"industry_match": 20, "location_match": 15, ...}
    score_reasons JSONB DEFAULT '[]'::jsonb,
    -- e.g., ["Industry matches campaign", "Website has mobile issues"]
    
    -- Pipeline
    pipeline_stage TEXT NOT NULL DEFAULT 'discovered'
        CHECK (pipeline_stage IN (
            'discovered',
            'research_pending',
            'researched',
            'qualified',
            'contacted',
            'followup_due',
            'replied',
            'interested',
            'meeting_scheduled',
            'proposal_sent',
            'negotiation',
            'won',
            'closed_lost',
            'not_interested',
            'no_response',
            'opted_out'
        )),
    
    -- Meta
    source TEXT DEFAULT 'google_places',
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of UUID REFERENCES public.leads(id),
    notes TEXT DEFAULT '',
    
    -- Suppression
    is_suppressed BOOLEAN DEFAULT FALSE,
    suppression_reason TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_contacted_at TIMESTAMPTZ,
    next_followup_at TIMESTAMPTZ
);

CREATE INDEX idx_leads_campaign_id ON public.leads(campaign_id);
CREATE INDEX idx_leads_place_id ON public.leads(place_id);
CREATE INDEX idx_leads_phone ON public.leads(phone);
CREATE INDEX idx_leads_website_url ON public.leads(website_url);
CREATE INDEX idx_leads_pipeline_stage ON public.leads(pipeline_stage);
CREATE INDEX idx_leads_fit_score ON public.leads(fit_score DESC);
CREATE INDEX idx_leads_next_followup ON public.leads(next_followup_at);
CREATE UNIQUE INDEX idx_leads_campaign_place ON public.leads(campaign_id, place_id)
    WHERE place_id IS NOT NULL;

-- ============================================================
-- 4. WEBSITE AUDITS
-- ============================================================
CREATE TABLE public.website_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    
    -- What was tested
    tested_url TEXT NOT NULL,
    
    -- Availability
    dns_resolves BOOLEAN,
    http_status_code INTEGER,
    ssl_valid BOOLEAN,
    page_loads BOOLEAN DEFAULT FALSE,
    load_time_seconds DECIMAL(6,2),
    final_url TEXT,
    -- After redirects
    
    -- Mobile test
    mobile_overflow BOOLEAN,
    mobile_overflow_pixels INTEGER DEFAULT 0,
    
    -- Content detection
    has_contact_form BOOLEAN DEFAULT FALSE,
    has_phone_on_site BOOLEAN DEFAULT FALSE,
    has_email_on_site BOOLEAN DEFAULT FALSE,
    has_whatsapp_link BOOLEAN DEFAULT FALSE,
    has_social_links BOOLEAN DEFAULT FALSE,
    social_links JSONB DEFAULT '[]'::jsonb,
    -- e.g., [{"platform": "facebook", "url": "..."}]
    
    -- SEO basics
    page_title TEXT,
    meta_description TEXT,
    h1_headings JSONB DEFAULT '[]'::jsonb,
    has_alt_texts BOOLEAN,
    missing_alt_count INTEGER DEFAULT 0,
    
    -- Links
    total_internal_links INTEGER DEFAULT 0,
    broken_links JSONB DEFAULT '[]'::jsonb,
    -- e.g., [{"url": "/gallery", "status": 404}]
    broken_link_count INTEGER DEFAULT 0,
    
    -- Lighthouse scores (0-100)
    lighthouse_performance INTEGER,
    lighthouse_seo INTEGER,
    lighthouse_accessibility INTEGER,
    lighthouse_best_practices INTEGER,
    
    -- Screenshots (Supabase Storage paths)
    screenshot_desktop_url TEXT,
    screenshot_mobile_url TEXT,
    
    -- Industry-specific results
    industry_checks JSONB DEFAULT '{}'::jsonb,
    -- e.g., {"has_menu": false, "has_booking": true} for restaurants
    
    -- Status
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'timeout')),
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_audits_lead_id ON public.website_audits(lead_id);
CREATE INDEX idx_audits_status ON public.website_audits(status);

-- ============================================================
-- 5. EVIDENCE ITEMS
-- ============================================================
CREATE TABLE public.evidence_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    audit_id UUID REFERENCES public.website_audits(id) ON DELETE CASCADE,
    
    -- Finding details
    finding_title TEXT NOT NULL,
    -- e.g., "Mobile layout has horizontal overflow"
    description TEXT NOT NULL,
    -- Detailed description of the finding
    
    -- Evidence
    evidence_type TEXT NOT NULL DEFAULT 'audit_check'
        CHECK (evidence_type IN (
            'audit_check',
            'screenshot',
            'lighthouse_report',
            'link_check',
            'content_scan',
            'industry_check'
        )),
    evidence_data JSONB DEFAULT '{}'::jsonb,
    -- Structured evidence data specific to the type
    -- For audit_check: {"check": "mobile_overflow", "value": true, "pixels": 240}
    -- For screenshot: {"url": "...", "viewport": "mobile"}
    -- For lighthouse: {"category": "performance", "score": 45}
    
    tested_url TEXT,
    screenshot_url TEXT,
    -- Supabase Storage path for screenshot evidence
    
    -- Classification
    severity TEXT NOT NULL DEFAULT 'medium'
        CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    category TEXT DEFAULT 'general',
    -- e.g., "mobile", "seo", "contact", "performance", "content", "industry"
    
    -- Verification
    verification_status TEXT NOT NULL DEFAULT 'verified'
        CHECK (verification_status IN (
            'verified',
            'unverified',
            'contradicted',
            'manual_review'
        )),
    
    -- Recommendation
    recommendation TEXT,
    -- e.g., "Fix responsive CSS to prevent horizontal scrolling"
    
    -- Timestamps
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_evidence_lead_id ON public.evidence_items(lead_id);
CREATE INDEX idx_evidence_audit_id ON public.evidence_items(audit_id);
CREATE INDEX idx_evidence_severity ON public.evidence_items(severity);

-- ============================================================
-- 6. AI ANALYSES
-- ============================================================
CREATE TABLE public.ai_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    
    -- AI configuration
    model_used TEXT NOT NULL,
    -- e.g., "gemini-2.0-flash", "claude-3-5-sonnet"
    prompt_version TEXT DEFAULT 'v1',
    
    -- Analysis result (structured JSON)
    analysis_result JSONB NOT NULL,
    
    recommended_service TEXT,
    pitch_angle TEXT,
    confidence TEXT DEFAULT 'medium'
        CHECK (confidence IN ('high', 'medium', 'low')),
    
    -- Claim verification results
    claim_verifications JSONB DEFAULT '[]'::jsonb,
    total_claims INTEGER DEFAULT 0,
    verified_claims INTEGER DEFAULT 0,
    unverified_claims INTEGER DEFAULT 0,
    contradicted_claims INTEGER DEFAULT 0,
    
    -- Cost tracking
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    api_cost_usd DECIMAL(8,4) DEFAULT 0.0,
    
    -- Timestamps
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_analyses_lead_id ON public.ai_analyses(lead_id);

-- ============================================================
-- 7. WHATSAPP MESSAGES
-- ============================================================
CREATE TABLE public.whatsapp_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    campaign_id UUID NOT NULL REFERENCES public.campaigns(id) ON DELETE CASCADE,
    
    -- WhatsApp identifiers
    wa_message_id TEXT,
    -- Provider message ID (wamid_xxx for Twilio)
    
    -- Direction
    direction TEXT NOT NULL DEFAULT 'outbound'
        CHECK (direction IN ('outbound', 'inbound')),
    
    -- Recipient/Sender
    from_number TEXT,
    to_number TEXT,
    
    -- Template (for outbound)
    template_name TEXT,
    template_variables JSONB DEFAULT '{}'::jsonb,
    
    -- Message content
    message_body TEXT NOT NULL,
    message_type TEXT DEFAULT 'text'
        CHECK (message_type IN ('text', 'template', 'image', 'document')),
    
    -- Status (for outbound)
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN (
            'draft',
            'pending_approval',
            'approved',
            'queued',
            'sent',
            'delivered',
            'read',
            'failed',
            'cancelled'
        )),
    error_message TEXT,
    
    -- Reply classification (for inbound)
    reply_classification TEXT
        CHECK (reply_classification IN (
            NULL,
            'interested',
            'wants_info',
            'pricing_request',
            'meeting_request',
            'not_interested',
            'not_now',
            'wrong_number',
            'opt_out',
            'unclear'
        )),
    classification_confidence DECIMAL(3,2),
    
    -- Follow-up tracking
    followup_attempt INTEGER DEFAULT 0,
    -- 0 = initial message, 1 = first follow-up, etc.
    is_followup BOOLEAN DEFAULT FALSE,
    
    -- Cost
    conversation_cost DECIMAL(8,4) DEFAULT 0.0,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ
);

CREATE INDEX idx_messages_lead_id ON public.whatsapp_messages(lead_id);
CREATE INDEX idx_messages_campaign_id ON public.whatsapp_messages(campaign_id);
CREATE INDEX idx_messages_wa_id ON public.whatsapp_messages(wa_message_id);
CREATE INDEX idx_messages_direction ON public.whatsapp_messages(direction);
CREATE INDEX idx_messages_status ON public.whatsapp_messages(status);
CREATE INDEX idx_messages_to_number ON public.whatsapp_messages(to_number);

-- ============================================================
-- 8. TASKS
-- ============================================================
CREATE TABLE public.tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES public.leads(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES public.campaigns(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    
    -- Task details
    task_type TEXT NOT NULL
        CHECK (task_type IN (
            'followup',
            'callback',
            'review_lead',
            'review_reply',
            'approve_message',
            'send_info',
            'send_pricing',
            'schedule_meeting',
            'meeting_followup',
            'send_proposal',
            'general'
        )),
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    
    -- Status
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'snoozed', 'cancelled')),
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('urgent', 'high', 'medium', 'low')),
    
    -- Dates
    due_date TIMESTAMPTZ,
    snoozed_until TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tasks_user_id ON public.tasks(user_id);
CREATE INDEX idx_tasks_lead_id ON public.tasks(lead_id);
CREATE INDEX idx_tasks_status ON public.tasks(status);
CREATE INDEX idx_tasks_due_date ON public.tasks(due_date);
CREATE INDEX idx_tasks_type ON public.tasks(task_type);

-- ============================================================
-- 9. FOLLOWUP SCHEDULES
-- ============================================================
CREATE TABLE public.followup_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    campaign_id UUID NOT NULL REFERENCES public.campaigns(id) ON DELETE CASCADE,
    
    -- Schedule
    attempt_number INTEGER NOT NULL,
    -- 1 = first follow-up, 2 = second, etc.
    
    -- Status
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'sent', 'cancelled', 'skipped')),
    cancellation_reason TEXT,
    -- e.g., "lead_replied", "opted_out", "max_attempts", "manual"
    
    -- Timestamps
    scheduled_for TIMESTAMPTZ NOT NULL,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_followups_lead_id ON public.followup_schedules(lead_id);
CREATE INDEX idx_followups_status_schedule ON public.followup_schedules(status, scheduled_for);
CREATE INDEX idx_followups_campaign ON public.followup_schedules(campaign_id);

-- ============================================================
-- 10. NOTIFICATIONS
-- ============================================================
CREATE TABLE public.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    
    -- Content
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'info'
        CHECK (type IN ('info', 'success', 'warning', 'error', 'action_required')),
    
    -- Links
    link_url TEXT,
    lead_id UUID REFERENCES public.leads(id) ON DELETE SET NULL,
    campaign_id UUID REFERENCES public.campaigns(id) ON DELETE SET NULL,
    
    -- Status
    is_read BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at TIMESTAMPTZ
);

CREATE INDEX idx_notifications_user_id ON public.notifications(user_id);
CREATE INDEX idx_notifications_unread ON public.notifications(user_id, is_read)
    WHERE is_read = FALSE;

-- ============================================================
-- 11. COST TRACKING
-- ============================================================
CREATE TABLE public.api_costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES public.campaigns(id) ON DELETE CASCADE,
    
    -- Service
    service TEXT NOT NULL
        CHECK (service IN (
            'google_places',
            'ai_analysis',
            'ai_classification',
            'ai_message_gen',
            'whatsapp',
            'lighthouse'
        )),
    
    -- Details
    operation TEXT NOT NULL,
    -- e.g., "text_search", "place_details", "analysis", "send_message"
    api_calls INTEGER DEFAULT 1,
    cost_usd DECIMAL(8,4) DEFAULT 0.0,
    cost_inr DECIMAL(10,2) DEFAULT 0.0,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_costs_campaign_id ON public.api_costs(campaign_id);
CREATE INDEX idx_costs_service ON public.api_costs(service);

-- ============================================================
-- 12. UPDATED_AT TRIGGER
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.campaigns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- 13. ROW LEVEL SECURITY (RLS)
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.website_audits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.whatsapp_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.followup_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_costs ENABLE ROW LEVEL SECURITY;

-- Profiles: users can only see/edit their own
CREATE POLICY "Users can view own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = id);

-- Campaigns: users can only access their own
CREATE POLICY "Users can CRUD own campaigns"
    ON public.campaigns FOR ALL
    USING (auth.uid() = user_id);

-- Leads: users access through their campaigns
CREATE POLICY "Users can access leads in own campaigns"
    ON public.leads FOR ALL
    USING (
        campaign_id IN (
            SELECT id FROM public.campaigns WHERE user_id = auth.uid()
        )
    );

-- Website audits: through leads → campaigns
CREATE POLICY "Users can access audits for own leads"
    ON public.website_audits FOR ALL
    USING (
        lead_id IN (
            SELECT l.id FROM public.leads l
            JOIN public.campaigns c ON l.campaign_id = c.id
            WHERE c.user_id = auth.uid()
        )
    );

-- Evidence items: through leads → campaigns
CREATE POLICY "Users can access evidence for own leads"
    ON public.evidence_items FOR ALL
    USING (
        lead_id IN (
            SELECT l.id FROM public.leads l
            JOIN public.campaigns c ON l.campaign_id = c.id
            WHERE c.user_id = auth.uid()
        )
    );

-- AI analyses: through leads → campaigns
CREATE POLICY "Users can access analyses for own leads"
    ON public.ai_analyses FOR ALL
    USING (
        lead_id IN (
            SELECT l.id FROM public.leads l
            JOIN public.campaigns c ON l.campaign_id = c.id
            WHERE c.user_id = auth.uid()
        )
    );

-- WhatsApp messages: through campaigns
CREATE POLICY "Users can access messages in own campaigns"
    ON public.whatsapp_messages FOR ALL
    USING (
        campaign_id IN (
            SELECT id FROM public.campaigns WHERE user_id = auth.uid()
        )
    );

-- Tasks: user's own tasks
CREATE POLICY "Users can access own tasks"
    ON public.tasks FOR ALL
    USING (auth.uid() = user_id);

-- Follow-up schedules: through campaigns
CREATE POLICY "Users can access followups in own campaigns"
    ON public.followup_schedules FOR ALL
    USING (
        campaign_id IN (
            SELECT id FROM public.campaigns WHERE user_id = auth.uid()
        )
    );

-- Notifications: user's own
CREATE POLICY "Users can access own notifications"
    ON public.notifications FOR ALL
    USING (auth.uid() = user_id);

-- API costs: through campaigns
CREATE POLICY "Users can view costs for own campaigns"
    ON public.api_costs FOR SELECT
    USING (
        campaign_id IN (
            SELECT id FROM public.campaigns WHERE user_id = auth.uid()
        )
    );
