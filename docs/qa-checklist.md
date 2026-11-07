# SignalForge AI: Comprehensive QA Checklist & Execution Matrix

This document tracks verification across all 7 stages of SignalForge AI, mapping every route, UI control, backend endpoint, background job, and failure mode per `CLAUDE.md`, `docs/decisions.md`, `docs/UI-UX.md`, and `docs/security.md`.

---

## 1. Frontend Routes & Pages Inventory

| Route | Page / View | Expected Behavior | Status |
|---|---|---|---|
| `/login` | Authentication Login | Form with email and password inputs, submit button, Google OAuth button, link to signup. Redirects authenticated users to `/`. | PENDING |
| `/signup` | Authentication Signup | Form with name, email, password inputs, submit button, Google OAuth button, link to login. Validates password length (8+ chars). | PENDING |
| `/` | Today Action Center (Dashboard) | Summary cards (Total Campaigns, Active Leads, Messages Sent, Open Tasks), Next Actions work queue, Recent Activity feed, quick-create buttons. | PENDING |
| `/campaigns` | Campaigns List | Table of campaigns with status chips, search input, status filter, sorting, pagination, "Create Campaign" button, row navigation to detail. | PENDING |
| `/campaigns/new` | Multi-Step Campaign Wizard | 4-step wizard (Basics, Target Audience, Outreach Settings, Review & Launch), industry template selector, budget & throttle controls, sticky footer. | PENDING |
| `/campaigns/[id]` | Campaign Detail & Management | Campaign header with status, metrics bar, pause/resume control, "Run Discovery" trigger, LeadTable with filters/sorting/search/pagination, danger zone delete. | PENDING |
| `/leads/[id]` | Lead 360° Detail View | Breadcrumb navigation, business header with stage chip and fit score, tabs for Website Audit, AI Analysis, WhatsApp Outreach, and Tasks. | PENDING |
| `/pipeline` | Kanban Sales Pipeline | 9 working stage columns, collapsible 4-stage closed rail, drag-and-drop between manual stages, card "Move to" menu, undo toast, deal note dialog. | PENDING |
| `/tasks` | Task Management Queue | Tasks grouped into Overdue, Today, Upcoming, and Completed (collapsed), priority filters, completion checkbox, snooze preset dropdown. | PENDING |
| `/templates` | Outreach Templates | Table of WhatsApp outreach templates with approval statuses (Approved, Pending, Rejected, Draft), purpose tags, variable previews. | PENDING |
| `/analytics` | Performance & Cost Analytics | Funnel conversion bar chart, API & messaging cost tables in INR, delivery & reply metrics, date range selector. | PENDING |
| `/settings` | Account & Compliance Settings | Profile form (name, company, WhatsApp business number), read-only suppression list table with search and pagination. | PENDING |

---

## 2. Interactive UI Components & Controls Inventory

### A. Layout & Global Navigation
| Component | Element | Type | Expected Behavior | Status |
|---|---|---|---|---|
| `Sidebar` | Brand Logo / Title | Link | Navigates to `/` (Today Action Center) | PENDING |
| `Sidebar` | Nav Link: Today | Link | Navigates to `/`, active state highlight | PENDING |
| `Sidebar` | Nav Link: Campaigns | Link | Navigates to `/campaigns`, active state highlight | PENDING |
| `Sidebar` | Nav Link: Pipeline | Link | Navigates to `/pipeline`, active state highlight | PENDING |
| `Sidebar` | Nav Link: Tasks | Link | Navigates to `/tasks`, active state highlight | PENDING |
| `Sidebar` | Nav Link: Templates | Link | Navigates to `/templates`, active state highlight | PENDING |
| `Sidebar` | Nav Link: Analytics | Link | Navigates to `/analytics`, active state highlight | PENDING |
| `Sidebar` | Nav Link: Settings | Link | Navigates to `/settings`, active state highlight | PENDING |
| `Sidebar` | Collapse / Expand Button | Button | Toggles sidebar between expanded (240px) and collapsed (64px) icon rail | PENDING |
| `Sidebar` | Mobile Sheet Drawer | Sheet | Opens navigation sidebar on mobile (<768px) and closes on link click or outside click | PENDING |
| `Header` | Search / Quick Jump | Input / Dialog | Opens quick jump command dialog (`Cmd+K` / `Ctrl+K`), searches campaigns and leads | PENDING |
| `Header` | Notifications Bell | Dropdown | Opens notifications popover with empty state message ("No notifications...") | PENDING |
| `Header` | Theme Toggle | Button | Switches between Light (`#F4F6F7`) and Dark (`#0F161D`) themes | PENDING |
| `Header` | User Avatar Menu | Dropdown | Displays user profile info, links to Settings, and Logout action | PENDING |
| `Header` | Logout Action | MenuItem | Clears Supabase session and redirects immediately to `/login` | PENDING |

### B. Authentication Pages (`/login`, `/signup`)
| Component | Element | Type | Expected Behavior | Status |
|---|---|---|---|---|
| `LoginForm` | Email Input | Input | Validates email format, handles empty input with error message | PENDING |
| `LoginForm` | Password Input | Input | Masked password input, toggle show/hide visibility | PENDING |
| `LoginForm` | Sign In Button | Button | Submits credentials, shows loading spinner, redirects to `/` on success, shows error on failure | PENDING |
| `LoginForm` | Google OAuth Button | Button | Initiates Supabase OAuth redirect to Google | PENDING |
| `LoginForm` | Create Account Link | Link | Navigates to `/signup` | PENDING |
| `SignupForm` | Full Name Input | Input | Captures user's full name, validates non-empty | PENDING |
| `SignupForm` | Email Input | Input | Captures user's email, validates format | PENDING |
| `SignupForm` | Password Input | Input | Enforces min 8 characters, shows helper text | PENDING |
| `SignupForm` | Create Account Button | Button | Submits registration, creates profile record, redirects to dashboard | PENDING |
| `SignupForm` | Google OAuth Button | Button | Initiates Supabase OAuth redirect to Google | PENDING |
| `SignupForm` | Sign In Link | Link | Navigates to `/login` | PENDING |

### C. Dashboard & Today View (`/`)
| Component | Element | Type | Expected Behavior | Status |
|---|---|---|---|---|
| `TodayView` | Create Campaign Button | Button / Link | Navigates to `/campaigns/new` | PENDING |
| `TodayView` | Metric Cards | Stat Cards | Shows total campaigns, active leads, sent messages, and open tasks (real database values) | PENDING |
| `TodayView` | Next Actions Queue | Card List | Displays up to 10 actionable open tasks, links to respective leads, checkbox completes task | PENDING |
| `TodayView` | View All Tasks Link | Link | Navigates to `/tasks` | PENDING |
| `TodayView` | Pipeline Summary Widget | Widget | Shows counts across active stages with link to `/pipeline` | PENDING |

### D. Campaigns List (`/campaigns`)
| Component | Element | Type | Expected Behavior | Status |
|---|---|---|---|---|
| `CampaignList` | New Campaign Button | Button / Link | Navigates to `/campaigns/new` | PENDING |
| `CampaignList` | Search Input | Input | Debounced filter by campaign name, clear button resets query | PENDING |
| `CampaignList` | Status Filter | Select | Filters by `all`, `draft`, `active`, `paused`, `completed`, `archived` | PENDING |
| `CampaignList` | Table Sort Headers | Button | Toggles ascending/descending sort on Name, Status, Leads Found, Created Date | PENDING |
| `CampaignList` | Pagination Controls | Buttons | Next/Previous page buttons, disabled at boundaries, shows total count | PENDING |
| `CampaignList` | Campaign Row Link | Link | Navigates to `/campaigns/[id]` | PENDING |
| `CampaignList` | Empty State CTA | Button | "Create your first campaign" button when no campaigns match | PENDING |

### E. New Campaign Wizard (`/campaigns/new`)
| Component | Element | Type | Expected Behavior | Status |
|---|---|---|---|---|
| `Wizard` | Step 1: Campaign Name | Input | Required text input (max 200 chars) | PENDING |
| `Wizard` | Step 1: Industry Selector | Select | Pre-populates keyword signals from selected industry template | PENDING |
| `Wizard` | Step 1: Location Input | Input | Target city or area (e.g., "Pune, Maharashtra") | PENDING |
| `Wizard` | Step 1: Keywords Input | Input / Tag | Comma-separated or tag-based search keywords | PENDING |
| `Wizard` | Step 2: Target Lead Limit | Input | Numeric input (1 to 200), defaults to 50 | PENDING |
| `Wizard` | Step 2: Min Lead Score | Slider / Input | Threshold for automated qualification (defaults to 60) | PENDING |
| `Wizard` | Step 3: Daily Send Limit | Input | Max messages per day (default 50, capped per decisions.md) | PENDING |
| `Wizard` | Step 3: Quiet Hours Pickers | Inputs | Start (21:00) and End (09:00) quiet hours in IST | PENDING |
| `Wizard` | Step 3: Max Budget Input | Input | Campaign budget cap in INR (0 = no limit with warning) | PENDING |
| `Wizard` | Step Navigation Buttons | Buttons | "Next", "Back", and "Cancel" buttons with validation checks | PENDING |
| `Wizard` | Step 4: Launch Button | Button | Creates campaign in database and redirects to `/campaigns/[id]` | PENDING |
| `Wizard` | Step 4: Save Draft Button | Button | Saves as draft without initiating discovery | PENDING |

### F. Campaign Detail (`/campaigns/[id]`)
| Component | Element | Type | Expected Behavior | Status |
|---|---|---|---|---|
| `CampaignHeader` | Pause / Resume Button | Button | Toggles status between `active` and `paused`, confirms state change | PENDING |
| `CampaignHeader` | Run Discovery Button | Button | Triggers background place discovery (`POST /api/campaigns/{id}/start-discovery`), shows progress bar | PENDING |
| `DiscoveryProgress` | Polling Progress Bar | Card | Polls `/api/campaigns/{id}/status` every 3s, updates queries completed and leads found | PENDING |
| `LeadTable` | Search Bar | Input | Filters leads by business name or phone number | PENDING |
| `LeadTable` | Pipeline Stage Filter | Select | Filters leads by any of the 16 stages or "All stages" | PENDING |
| `LeadTable` | Fit Score Filter | Select | Filters by Qualified (>=60), Needs Review (<60), or All | PENDING |
| `LeadTable` | Select All Checkbox | Checkbox | Selects all leads on current page for batch actions | PENDING |
| `LeadTable` | Batch Audit Button | Button | Triggers background audit for all selected leads | PENDING |
| `LeadTable` | Batch Analyze Button | Button | Triggers AI analysis for all selected leads | PENDING |
| `LeadTable` | Lead Row Link | Link | Navigates to `/leads/[id]` | PENDING |
| `LeadTable` | External Website Link | Link | Opens lead website in a new tab with `rel="noopener noreferrer"` | PENDING |
| `LeadTable` | Score Ledger Trigger | Button / Badge | Opens ScoreLedger drawer breaking down the 100-point deterministic score | PENDING |
| `CampaignDangerZone`| Delete Campaign Button | Button / Dialog | Requires confirmation typing or confirmation dialog, deletes campaign and cascades cleanly | PENDING |

### G. Lead Detail (`/leads/[id]`)
| Component | Element | Type | Expected Behavior | Status |
|---|---|---|---|---|
| `LeadHeader` | Breadcrumb Trail | Links | `Campaigns / {campaign.name} / {lead.business_name}`, handles 390px responsive truncation | PENDING |
| `LeadHeader` | Pipeline Stage Chip | Badge | Shows current stage badge with color-coded token | PENDING |
| `LeadHeader` | Primary Action Button | Button | Context-sensitive next action (e.g. "Start Website Audit", "Run AI Analysis", "Draft WhatsApp Message") | PENDING |
| `Tabs` | Audit Tab | Tab | Switches to website audit report, screenshot preview, and Lighthouse metrics | PENDING |
| `Tabs` | Analysis Tab | Tab | Switches to AI opportunity analysis, verified evidence items, value angles | PENDING |
| `Tabs` | WhatsApp Tab | Tab | Switches to WhatsApp message composer, draft approval, and conversation timeline | PENDING |
| `Tabs` | Tasks Tab | Tab | Switches to tasks associated with this lead | PENDING |
| `AuditReport` | Re-run Audit Button | Button | Triggers re-audit (`POST /api/leads/{id}/start-audit`), disables during run | PENDING |
| `AuditReport` | Screenshot Lightbox | Dialog | Clicking screenshot opens full-res private signed URL image modal | PENDING |
| `AIAnalysis` | Run Analysis Button | Button | Calls `POST /api/leads/{id}/analyze`, polls for completion | PENDING |
| `WhatsAppChat` | Generate Draft Button | Button | Calls `POST /api/leads/{id}/whatsapp/draft`, populates draft editor with evidence-backed copy | PENDING |
| `WhatsAppChat` | Draft Editor Textarea | Textarea | Allows editing message before approval | PENDING |
| `WhatsAppChat` | Save Draft Button | Button | Calls `PUT /api/leads/{id}/whatsapp/draft` with updated text | PENDING |
| `WhatsAppChat` | Approve & Send Button | Button | Moves message from draft to queued/sent, validates opt-out footer and phone presence | PENDING |
| `WhatsAppChat` | Message Timeline | Chat Feed | Displays sent/delivered/read status badges, timestamps, incoming replies | PENDING |
| `ScoreLedger` | Open Drawer Button | Button | Slides out deterministic breakdown (Industry, Location, Issues, Evidence, Contact, Phone, Rating) | PENDING |

### H. Pipeline Board (`/pipeline`)
| Component | Element | Type | Expected Behavior | Status |
|---|---|---|---|---|
| `PipelineBoard` | Campaign Filter Dropdown | Select | Filters Kanban leads by campaign or "All Campaigns" | PENDING |
| `PipelineBoard` | Active Leads Counter | Badge | Displays total active leads in board columns | PENDING |
| `PipelineBoard` | Closed Rail Toggle | Button | Expands/collapses the 4 closed stages (`Not interested`, `No response`, `Closed lost`, `Opted out`) | PENDING |
| `PipelineBoard` | Drag and Drop Cards | DnD | Cards draggable into manual stages (`Meeting scheduled`, `Proposal sent`, `Negotiation`, `Won`, `Closed lost`, `Not interested`) | PENDING |
| `PipelineBoard` | Card Move-To Menu | Dropdown | Keyboard/touch accessible dropdown on card (`⋮`) to move stage without dragging | PENDING |
| `PipelineBoard` | Automated Stage Lock | Tooltip | Hovering locked column header shows tooltip: "Moves automatically when a message is sent." | PENDING |
| `PipelineBoard` | Opted-Out Card Lock | Icon / State | Opted-out leads cannot be moved; shows shield alert | PENDING |
| `PipelineBoard` | Deal Note Modal | Dialog | Prompts for optional note when moving to `Won` or `Closed lost` | PENDING |
| `PipelineBoard` | Undo Toast | Toast | Appears after every move with an "Undo" action button to revert transition | PENDING |

### I. Tasks Management (`/tasks`)
| Component | Element | Type | Expected Behavior | Status |
|---|---|---|---|---|
| `TaskList` | Priority Filter Tabs | Buttons | Filters by `all`, `urgent`, `high`, `medium`, `low` | PENDING |
| `TaskList` | Overdue Group | Section | Lists open tasks with due dates in the past with red indicator | PENDING |
| `TaskList` | Today Group | Section | Lists tasks due today in IST | PENDING |
| `TaskList` | Upcoming Group | Section | Lists future tasks and snoozed tasks | PENDING |
| `TaskList` | Completed Accordion | Accordion | Collapsed by default; toggles display of finished tasks | PENDING |
| `TaskRow` | Completion Checkbox | Checkbox | Toggles task between `completed` and `pending`, updates counters | PENDING |
| `TaskRow` | Lead Name Link | Link | Navigates directly to `/leads/{lead_id}` | PENDING |
| `TaskRow` | Snooze Menu | Dropdown | Allows snoozing: `Later today (+4h)`, `Tomorrow (9:00 AM)`, `Next week (+7d)` | PENDING |

### J. Settings & Suppression (`/settings`)
| Component | Element | Type | Expected Behavior | Status |
|---|---|---|---|---|
| `ProfileForm` | Full Name Input | Input | Updates user profile name via `PUT /api/auth/profile` | PENDING |
| `ProfileForm` | Company Name Input | Input | Updates agency/business name | PENDING |
| `ProfileForm` | WhatsApp Number Input | Input | Normalizes and stores user's sending WhatsApp number | PENDING |
| `ProfileForm` | Service Descriptions | Textarea | Stores default services offered for message generation context | PENDING |
| `ProfileForm` | Save Changes Button | Button | Submits profile update, shows success toast | PENDING |
| `SuppressionTable` | Search Input | Input | Filters suppressed phone numbers | PENDING |
| `SuppressionTable` | Pagination Controls | Buttons | Paginated browsing of suppressed records (phone, reason, date, source lead) | PENDING |

---

## 3. Backend Endpoints Inventory

| Method | Endpoint Path | Auth Required | Expected Status | Ownership Check | Idempotent | Status |
|---|---|---|---|---|---|---|
| `GET` | `/health` | No | 200 OK | N/A | Yes | PENDING |
| `GET` | `/api/auth/me` | JWT | 200 OK | Authenticated user profile | Yes | PENDING |
| `PUT` | `/api/auth/profile` | JWT | 200 OK | Updates own profile only | Yes | PENDING |
| `POST` | `/api/campaigns` | JWT | 201 Created | Creates campaign under `user.id` | No | PENDING |
| `GET` | `/api/campaigns` | JWT | 200 OK | Lists current user's campaigns only | Yes | PENDING |
| `GET` | `/api/campaigns/{id}` | JWT | 200 OK | 404 if not owned by user | Yes | PENDING |
| `PUT` | `/api/campaigns/{id}` | JWT | 200 OK | 404 if not owned by user | Yes | PENDING |
| `DELETE`| `/api/campaigns/{id}` | JWT | 200 OK | 404 if not owned by user, cascades leads | Yes | PENDING |
| `POST` | `/api/campaigns/{id}/pause` | JWT | 200 OK | 404 if not owned by user, pauses scheduler | Yes | PENDING |
| `POST` | `/api/campaigns/{id}/resume`| JWT | 200 OK | 404 if not owned by user, resumes scheduler | Yes | PENDING |
| `POST` | `/api/campaigns/{id}/start-discovery` | JWT | 202 Accepted | 404 if not owned; starts background discovery | Yes | PENDING |
| `GET` | `/api/campaigns/{id}/status` | JWT | 200 OK | 404 if not owned; returns discovery status | Yes | PENDING |
| `POST` | `/api/campaigns/{id}/start-audit` | JWT | 202 Accepted | 404 if not owned; batch audits un-audited leads | Yes | PENDING |
| `POST` | `/api/campaigns/{id}/analyze` | JWT | 202 Accepted | 404 if not owned; batch analyzes researched leads | Yes | PENDING |
| `GET` | `/api/campaigns/{id}/leads` | JWT | 200 OK | 404 if not owned; paginated lead listing | Yes | PENDING |
| `GET` | `/api/leads/{id}` | JWT | 200 OK | 404 if lead's campaign not owned | Yes | PENDING |
| `POST` | `/api/leads/{id}/start-audit` | JWT | 202 Accepted | 404 if not owned; single-site audit background | Yes | PENDING |
| `GET` | `/api/leads/{id}/audit` | JWT | 200 OK | 404 if not owned; signed 1h screenshot URLs | Yes | PENDING |
| `POST` | `/api/leads/{id}/analyze` | JWT | 202 Accepted | 404 if not owned; AI analysis & scoring | Yes | PENDING |
| `GET` | `/api/leads/{id}/analysis` | JWT | 200 OK | 404 if not owned; returns AI opportunities | Yes | PENDING |
| `POST` | `/api/leads/{id}/whatsapp/draft` | JWT | 200 OK | 404 if not owned; creates evidence-backed draft | Yes | PENDING |
| `GET` | `/api/leads/{id}/whatsapp/draft` | JWT | 200 OK | 404 if not owned; returns active draft | Yes | PENDING |
| `PUT` | `/api/leads/{id}/whatsapp/draft` | JWT | 200 OK | 404 if not owned; edits draft content | Yes | PENDING |
| `POST` | `/api/leads/{id}/whatsapp/send` | JWT | 200 OK | 404 if not owned; validates suppression & sends | No | PENDING |
| `GET` | `/api/leads/{id}/whatsapp/messages` | JWT | 200 OK | 404 if not owned; returns chat timeline | Yes | PENDING |
| `POST` | `/api/webhooks/whatsapp` | Signature | 200 OK | Validates WAHA/Twilio signature, deduplicates | Yes | PENDING |
| `GET` | `/api/pipeline` | JWT | 200 OK | Scoped to user's campaigns only | Yes | PENDING |
| `PUT` | `/api/leads/{id}/stage` | JWT | 200 OK | 404 if not owned; validates manual stages | Yes | PENDING |
| `GET` | `/api/tasks` | JWT | 200 OK | Filtered by status/priority/user | Yes | PENDING |
| `GET` | `/api/tasks/upcoming` | JWT | 200 OK | Returns open tasks ordered by urgency/due date | Yes | PENDING |
| `PUT` | `/api/tasks/{id}` | JWT | 200 OK | 404 if not owned; completes or snoozes task | Yes | PENDING |
| `GET` | `/api/analytics/overview` | JWT | 200 OK | Aggregated pipeline funnel and metrics | Yes | PENDING |
| `GET` | `/api/analytics/campaign/{id}` | JWT | 200 OK | 404 if not owned; campaign specific metrics | Yes | PENDING |
| `GET` | `/api/analytics/costs` | JWT | 200 OK | Total and breakdown of API spending in INR/USD | Yes | PENDING |
| `GET` | `/api/settings/suppression` | JWT | 200 OK | Paginated suppression table for user | Yes | PENDING |

---

## 4. Background Jobs & Scheduled Workers

| Job Name | Schedule / Trigger | Service / Module | Expected Behavior | Status |
|---|---|---|---|---|
| `run_followup_check_job` | Every 1 hour (APScheduler) | `backend/services/followup.py` | Queries pending followups, checks quiet hours and replies, generates draft / schedules task | PENDING |
| `run_stale_jobs_recovery_job` | Every 15 minutes (APScheduler) | `backend/scheduler.py` | Detects jobs stuck in `discovering` or `running` >15 min, marks `failed` with recoverable message | PENDING |
| `run_unsnooze_tasks_job` | Every 5 minutes (APScheduler) | `backend/scheduler.py` | Finds tasks where `status = 'snoozed'` and `snoozed_until <= now`, transitions to `pending` | PENDING |
| `run_discovery` | BackgroundTasks (`/start-discovery`) | `backend/services/discovery.py` | Queries Geoapify/Places, deduplicates by place_id/phone/domain, creates leads | PENDING |
| `audit_lead_website` | BackgroundTasks (`/start-audit`) | `backend/services/audit.py` | Playwright crawl + Lighthouse CLI, captures screenshots, stores private signed images | PENDING |
| `analyze_lead` | BackgroundTasks (`/analyze`) | `backend/services/analysis.py` | Calls Gemini/Claude with untrusted text sanitization, verifies claims, computes 100-pt score | PENDING |
| `send_approved_message` | Triggered on approval | `backend/services/whatsapp.py` | Enforces suppression check, rate limits, quiet hours, dispatches to WAHA/Twilio | PENDING |

---

## 5. Failure Scenarios & Edge Cases Verification Matrix

| Test Scenario | Test Target | Expected Response / Behavior | Status |
|---|---|---|---|
| **Empty Input** | Login / Signup forms | Form displays required field validation, prevents submission | PENDING |
| **Empty Input** | New Campaign wizard | Disables next/launch button, highlights missing fields | PENDING |
| **Empty Input** | Task Title update | Backend returns `400 Bad Request` ("Task title cannot be empty") | PENDING |
| **Invalid Input** | Malformed Phone Number | E.164 parser rejects invalid numbers, flags uncontactable | PENDING |
| **Invalid Input** | Malformed Website URL | Sanitizer safely rejects javascript: or invalid protocols | PENDING |
| **Double Click** | Message Approve & Send | Conditional DB lock (`WHERE status = 'approved'`), sends at most once | PENDING |
| **Double Click** | Campaign Launch | Idempotent transition, avoids spawning duplicate background workers | PENDING |
| **Backend Down** | Any frontend view | Displays clean error banner with "Try Again" retry button | PENDING |
| **500 Server Error**| API Client | Displays user-friendly error message, logs stack trace to server only | PENDING |
| **Network Timeout** | Website Audit | Audit times out after 60s, records `status = 'timeout'`, no unhandled crash | PENDING |
| **Expired Session**| Frontend routes | API client detects 401, clears invalid tokens, redirects to `/login` | PENDING |
| **Cross-Tenant Access**| `/api/leads/{unowned_id}` | Returns `404 Not Found` (never 403 or data leakage) | PENDING |
| **Cross-Tenant Access**| `/api/campaigns/{unowned_id}`| Returns `404 Not Found` (strict user isolation) | PENDING |
| **Brand New Account**| All dashboard pages | Shows honest empty states with actionable CTA buttons | PENDING |
| **Devanagari Text** | Hindi Business Name | Correctly renders in Hanken Grotesk / Noto Sans Devanagari without overflow | PENDING |
| **Very Long Text** | 200+ char Business Name | Truncates with ellipsis or wraps with `break-words` without layout break | PENDING |
| **Responsive (1440px)**| Desktop Layout | Clean 2-column or full-width layouts, ample whitespace | PENDING |
| **Responsive (1024px)**| Tablet Layout | Sidebar collapses to icon rail, 2-column stacks with sticky next-step bar | PENDING |
| **Responsive (390px)** | Mobile Layout | Mobile sheet drawer, single column, tabular horizontally scrollable | PENDING |
| **Color Contrast** | Light Mode (`#F4F6F7`) | All text/background combinations meet WCAG AA (>= 4.5:1) | PENDING |
| **Color Contrast** | Dark Mode (`#0F161D`) | All text/background combinations meet WCAG AA (>= 4.5:1) | PENDING |
| **Keyboard Access** | Entire Interface | All interactive controls reachable via Tab, focused with 2px ring | PENDING |
| **Banned List Check**| Interface | Zero emoji, zero glassmorphism/blur, zero gradients, zero sparkles | PENDING |
