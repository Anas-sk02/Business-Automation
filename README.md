# SignalForge AI

Evidence-driven business intelligence, lead generation, and WhatsApp outreach automation platform.

## Overview

SignalForge AI helps web developers, software/AI agencies, and B2B sales teams find potential customers, perform automated technical audits of their digital presence, and conduct personalized, evidence-backed outreach via WhatsApp.

### Core Workflow
1. **Discover**: Find businesses via Google Places API (New).
2. **Audit**: Headless browser technical audits (Playwright + Lighthouse).
3. **Analyze**: AI opportunity detection strictly grounded in verified audit evidence.
4. **Score**: Deterministic, rule-based lead scoring (0–100).
5. **Outreach**: Personalized WhatsApp message templates with explicit human approval.
6. **Track**: Webhook event processing, reply classification, and pipeline stage updates.
7. **Manage**: Kanban sales pipeline, tasks, and follow-up schedules.

## Tech Stack
- **Frontend**: Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: Python 3.11+, FastAPI, Pydantic, Supabase, Playwright
- **Database & Auth**: Supabase (PostgreSQL, Supabase Auth, Storage)
- **Providers**: Twilio (WhatsApp), Gemini / Claude (AI), Google Places API (New)
