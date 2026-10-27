-- ============================================================
-- SignalForge AI — Overriding Decisions Migration
-- Migration 002: Decisions & Guardrails
-- (Overrides per docs/decisions.md)
-- ============================================================

-- 1. Safe default: AI/unchecked evidence is never assumed verified
ALTER TABLE public.evidence_items
  ALTER COLUMN verification_status SET DEFAULT 'unverified';

-- 2. At most one live outbound message per lead per attempt number (prevents double-sends)
CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_one_live_per_attempt
  ON public.whatsapp_messages (lead_id, followup_attempt)
  WHERE direction = 'outbound' AND status NOT IN ('failed', 'cancelled');

-- 3. Provider message id is unique, so duplicate webhook payloads are ignored idempotently
CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_wa_message_id
  ON public.whatsapp_messages (wa_message_id)
  WHERE wa_message_id IS NOT NULL;

-- 4. Storage: Ensure private 'screenshots' bucket exists
INSERT INTO storage.buckets (id, name, public)
VALUES ('screenshots', 'screenshots', false)
ON CONFLICT (id) DO UPDATE SET public = false;

-- 5. Storage RLS: Private bucket accessed via service role or user-isolated path {user_id}/{lead_id}/*
CREATE POLICY "Users can access their own screenshots"
ON storage.objects FOR ALL
USING (
  bucket_id = 'screenshots' AND (
    (storage.foldername(name))[1] = auth.uid()::text
  )
)
WITH CHECK (
  bucket_id = 'screenshots' AND (
    (storage.foldername(name))[1] = auth.uid()::text
  )
);
