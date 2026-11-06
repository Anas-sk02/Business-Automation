"""Live E2E Verification Script for Stage 6 (Pipeline, Follow-ups, Tasks, Today view).

Tests against running backend at http://127.0.0.1:8000 and frontend at http://localhost:3000.
Account: mdanas12.2007@gmail.com / Anas1234
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

from backend.database import get_supabase_client

BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:3000"

def make_req(path, method="GET", token=None, body=None):
    url = f"{BACKEND_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"raw": err_body}
        return e.code, parsed


def main():
    print("==================================================")
    print("STAGE 6 LIVE E2E REAL-USER VERIFICATION")
    print("==================================================")

    # 1. Authenticate with Supabase
    sb = get_supabase_client()
    print("\n--- 1. Authenticating as mdanas12.2007@gmail.com ---")
    auth_res = sb.auth.sign_in_with_password({
        "email": "mdanas12.2007@gmail.com",
        "password": "Anas1234"
    })
    token = auth_res.session.access_token
    user_id = auth_res.user.id
    print(f"Logged in successfully. User ID: {user_id}")

    # 2. Check campaigns or create one if needed
    print("\n--- 2. Checking Campaigns for User ---")
    status, camps_res = make_req("/api/campaigns", token=token)
    assert status == 200, f"Expected 200, got {status}: {camps_res}"
    campaigns = camps_res.get("data", [])
    print(f"User has {len(campaigns)} existing campaign(s).")

    camp_id = None
    if not campaigns:
        print("Creating a test campaign for Stage 6 pipeline testing...")
        c_status, c_data = make_req("/api/campaigns", method="POST", token=token, body={
            "name": "Pune Dental Clinics Test",
            "industry": "Dentist",
            "city": "Pune",
            "target_leads": 10,
            "max_budget": 500.0,
            "service_offered": "Website redesign and WhatsApp follow-up automation",
        })
        assert c_status == 201, f"Failed to create campaign: {c_data}"
        camp_id = c_data["data"]["id"]
        print(f"Created campaign: {camp_id}")
    else:
        camp_id = campaigns[0]["id"]
        print(f"Using campaign: {camp_id} ('{campaigns[0]['name']}')")

    # 3. Check/Seed leads for pipeline testing
    leads_res = sb.table("leads").select("*").eq("campaign_id", camp_id).execute()
    existing_leads = leads_res.data or []
    print(f"Campaign has {len(existing_leads)} lead(s).")

    lead_qualified = None
    lead_opted_out = None

    if len(existing_leads) < 2:
        print("Seeding test leads for Stage 6 pipeline...")
        # Create a qualified lead
        q_lead = sb.table("leads").insert({
            "campaign_id": camp_id,
            "business_name": "Dentist Dr. Joshi Pune",
            "category": "Dentist",
            "address": "FC Road, Pune",
            "phone": "+919822010001",
            "fit_score": 88,
            "pipeline_stage": "qualified",
            "rating": 4.9,
            "review_count": 45,
            "notes": "Verified prospective client",
        }).execute()
        lead_qualified = q_lead.data[0]

        # Create an opted-out lead
        opt_lead = sb.table("leads").insert({
            "campaign_id": camp_id,
            "business_name": "Stopped Dental Clinic",
            "category": "Dentist",
            "address": "Kothrud, Pune",
            "phone": "+919822010002",
            "fit_score": 50,
            "pipeline_stage": "opted_out",
            "is_suppressed": True,
            "suppression_reason": "Requested STOP",
        }).execute()
        lead_opted_out = opt_lead.data[0]
        print("Seeded qualified lead and opted-out lead.")
    else:
        lead_qualified = next((l for l in existing_leads if l["pipeline_stage"] != "opted_out"), existing_leads[0])
        lead_opted_out = next((l for l in existing_leads if l["pipeline_stage"] == "opted_out"), None)
        if not lead_opted_out:
            opt_lead = sb.table("leads").insert({
                "campaign_id": camp_id,
                "business_name": "Stopped Dental Clinic",
                "category": "Dentist",
                "address": "Kothrud, Pune",
                "phone": "+919822010002",
                "fit_score": 50,
                "pipeline_stage": "opted_out",
                "is_suppressed": True,
                "suppression_reason": "Requested STOP",
            }).execute()
            lead_opted_out = opt_lead.data[0]

    print(f"Qualified lead ID: {lead_qualified['id']}")
    print(f"Opted-out lead ID: {lead_opted_out['id']}")

    # 4. Test GET /api/pipeline (Kanban board)
    print("\n--- 4. Testing GET /api/pipeline ---")
    p_status, p_data = make_req("/api/pipeline", token=token)
    assert p_status == 200, f"Expected 200, got {p_status}: {p_data}"
    board = p_data["data"]
    print("Pipeline board columns received:")
    for col_name, cards in board["columns"].items():
        print(f"  Column '{col_name}': {len(cards)} card(s)")
    print("Closed rail columns received:")
    for col_name, cards in board["closed"].items():
        print(f"  Closed rail '{col_name}': {len(cards)} card(s)")
    print(f"Total active: {board['total_active_leads']}, Total leads: {board['total_leads']}")

    # Test GET /api/pipeline with campaign filter
    p_camp_status, _ = make_req(f"/api/pipeline?campaign_id={camp_id}", token=token)
    assert p_camp_status == 200, f"Expected 200 for campaign filter, got {p_camp_status}"
    print("Filtered pipeline by campaign_id: SUCCESS")

    # Test GET /api/pipeline with invalid UUID format
    p_inv_status, _ = make_req("/api/pipeline?campaign_id=not-a-uuid", token=token)
    assert p_inv_status == 404, f"Expected 404 for invalid UUID, got {p_inv_status}"
    print("Rejected invalid UUID with 404: SUCCESS")

    # Test GET /api/pipeline with unowned campaign
    p_unowned_status, _ = make_req("/api/pipeline?campaign_id=00000000-0000-0000-0000-000000000000", token=token)
    assert p_unowned_status == 404, f"Expected 404 for unowned campaign, got {p_unowned_status}"
    print("Rejected unowned campaign with 404: SUCCESS")

    # 5. Test PUT /api/leads/{id}/stage (Stage transitions)
    print("\n--- 5. Testing PUT /api/leads/{id}/stage ---")
    lead_id = lead_qualified["id"]

    # 5a. Normal transition: move to meeting_scheduled
    move_status, move_data = make_req(f"/api/leads/{lead_id}/stage", method="PUT", token=token, body={
        "stage": "meeting_scheduled",
        "notes": "Discovery demo scheduled via phone call"
    })
    assert move_status == 200, f"Expected 200 for meeting_scheduled, got {move_status}: {move_data}"
    assert move_data["data"]["pipeline_stage"] == "meeting_scheduled"
    print(f"Moved lead {lead_id} to 'meeting_scheduled': SUCCESS")

    # 5b. Normal transition: move to won with deal notes
    won_status, won_data = make_req(f"/api/leads/{lead_id}/stage", method="PUT", token=token, body={
        "stage": "won",
        "notes": "Signed 6-month website & WhatsApp automation retainer"
    })
    assert won_status == 200, f"Expected 200 for won, got {won_status}: {won_data}"
    assert won_data["data"]["pipeline_stage"] == "won"
    print(f"Moved lead {lead_id} to 'won': SUCCESS")

    # 5c. Wrong input: moving to automated stage must be rejected
    auto_status, auto_data = make_req(f"/api/leads/{lead_id}/stage", method="PUT", token=token, body={
        "stage": "contacted"
    })
    assert auto_status == 400, f"Expected 400 for automated stage, got {auto_status}: {auto_data}"
    print("Rejected automated stage 'contacted' with 400 Bad Request: SUCCESS")

    # 5d. Wrong input: invalid stage name must be rejected
    inv_stage_status, _ = make_req(f"/api/leads/{lead_id}/stage", method="PUT", token=token, body={
        "stage": "invented_sales_stage"
    })
    assert inv_stage_status == 400, f"Expected 400 for invalid stage, got {inv_stage_status}"
    print("Rejected invalid stage name with 400 Bad Request: SUCCESS")

    # 5e. Security check: cannot move opted-out lead
    opt_status, opt_err = make_req(f"/api/leads/{lead_opted_out['id']}/stage", method="PUT", token=token, body={
        "stage": "won"
    })
    assert opt_status == 400, f"Expected 400 for opted-out lead move, got {opt_status}: {opt_err}"
    print("Blocked moving opted-out lead with 400 Bad Request: SUCCESS")

    # 5f. Nonexistent lead must return 404
    nonexist_status, _ = make_req("/api/leads/00000000-0000-0000-0000-000000000000/stage", method="PUT", token=token, body={
        "stage": "meeting_scheduled"
    })
    assert nonexist_status == 404, f"Expected 404 for non-existent lead, got {nonexist_status}"
    print("Returned 404 for non-existent lead: SUCCESS")

    # 6. Test Tasks API (GET /api/tasks, GET /api/tasks/upcoming, PUT /api/tasks/{id})
    print("\n--- 6. Testing Tasks API ---")

    # Seed 2 tasks if user has none
    user_tasks = sb.table("tasks").select("*").eq("user_id", user_id).execute().data or []
    if len(user_tasks) < 2:
        print("Seeding test tasks for user...")
        sb.table("tasks").insert([
            {
                "lead_id": lead_id,
                "campaign_id": camp_id,
                "user_id": user_id,
                "task_type": "review_reply",
                "title": f"Review reply from {lead_qualified['business_name']}",
                "description": "Prospect asked about website audit results",
                "priority": "urgent",
                "status": "pending",
                "due_date": "2026-11-05T10:00:00Z",  # overdue
            },
            {
                "lead_id": lead_id,
                "campaign_id": camp_id,
                "user_id": user_id,
                "task_type": "approve_message",
                "title": "Approve WhatsApp outreach draft 1",
                "description": "Audit highlights draft ready for review",
                "priority": "high",
                "status": "pending",
                "due_date": "2026-11-07T09:00:00Z",  # upcoming
            }
        ]).execute()
        user_tasks = sb.table("tasks").select("*").eq("user_id", user_id).execute().data or []

    task_1 = user_tasks[0]
    print(f"Using test task: {task_1['id']} ('{task_1['title']}')")

    # 6a. GET /api/tasks
    t_status, t_data = make_req("/api/tasks", token=token)
    assert t_status == 200, f"Expected 200, got {t_status}: {t_data}"
    tasks_list = t_data["data"]["tasks"]
    counts = t_data["data"]["counts"]
    print(f"Retrieved {len(tasks_list)} tasks. Counts: {counts}")
    assert counts["total"] == len(user_tasks)

    # 6b. Filters
    tf_status, tf_data = make_req("/api/tasks?status=pending", token=token)
    assert tf_status == 200
    tf_prio_status, _ = make_req("/api/tasks?priority=urgent", token=token)
    assert tf_prio_status == 200
    print("Tasks filtering by status and priority: SUCCESS")

    # 6c. GET /api/tasks/upcoming
    up_status, up_data = make_req("/api/tasks/upcoming", token=token)
    assert up_status == 200, f"Expected 200, got {up_status}: {up_data}"
    print(f"Upcoming work queue returned {len(up_data['data'])} task(s): SUCCESS")

    # 6d. PUT /api/tasks/{id} Complete task
    c_status, c_data = make_req(f"/api/tasks/{task_1['id']}", method="PUT", token=token, body={
        "status": "completed"
    })
    assert c_status == 200, f"Expected 200 for completion, got {c_status}: {c_data}"
    assert c_data["data"]["status"] == "completed"
    assert c_data["data"]["completed_at"] is not None
    print(f"Task marked completed with completed_at timestamp: SUCCESS")

    # 6e. PUT /api/tasks/{id} Reopen task
    ro_status, ro_data = make_req(f"/api/tasks/{task_1['id']}", method="PUT", token=token, body={
        "status": "pending"
    })
    assert ro_status == 200
    assert ro_data["data"]["status"] == "pending"
    assert ro_data["data"]["completed_at"] is None
    print(f"Task reopened with status pending: SUCCESS")

    # 6f. PUT /api/tasks/{id} Snooze task with preset 'tomorrow'
    sn_status, sn_data = make_req(f"/api/tasks/{task_1['id']}", method="PUT", token=token, body={
        "snooze_preset": "tomorrow"
    })
    assert sn_status == 200
    assert sn_data["data"]["status"] == "snoozed"
    assert sn_data["data"]["snoozed_until"] is not None
    print(f"Task snoozed for tomorrow: {sn_data['data']['snoozed_until']}: SUCCESS")

    # 6g. Wrong input: snooze in the past must be rejected
    sn_past_status, _ = make_req(f"/api/tasks/{task_1['id']}", method="PUT", token=token, body={
        "snoozed_until": "2020-01-01T00:00:00Z"
    })
    assert sn_past_status == 400, f"Expected 400 for past snooze, got {sn_past_status}"
    print("Rejected past snooze date with 400 Bad Request: SUCCESS")

    # 6h. Reset task back to pending for real use
    make_req(f"/api/tasks/{task_1['id']}", method="PUT", token=token, body={"status": "pending"})

    # 7. Multi-Tenant Isolation Verification
    print("\n--- 7. Testing Multi-Tenant Isolation ---")
    other_email = "test.competitor.dev@signalforge.ai"
    other_pass = "SecurePass123!"
    try:
        sb.auth.admin.create_user({
            "email": other_email,
            "password": other_pass,
            "email_confirm": True
        })
    except Exception:
        try:
            users = sb.auth.admin.list_users()
            for u in users:
                if getattr(u, "email", None) == other_email:
                    sb.auth.admin.update_user_by_id(u.id, {"email_confirm": True, "password": other_pass})
        except Exception:
            pass
    other_auth = sb.auth.sign_in_with_password({"email": other_email, "password": other_pass})
    other_token = other_auth.session.access_token
    other_user_id = other_auth.user.id
    print(f"Created/Signed-in second tenant: {other_user_id}")

    # Second user cannot view User 1's pipeline leads
    sec_p_status, sec_p_data = make_req(f"/api/pipeline?campaign_id={camp_id}", token=other_token)
    assert sec_p_status == 404, f"Expected 404 for unowned campaign pipeline, got {sec_p_status}"
    print("Second user querying User 1's campaign pipeline received 404: SUCCESS")

    # Second user cannot modify User 1's lead stage
    sec_move_status, _ = make_req(f"/api/leads/{lead_id}/stage", method="PUT", token=other_token, body={"stage": "won"})
    assert sec_move_status == 404, f"Expected 404 when moving User 1's lead, got {sec_move_status}"
    print("Second user attempting to move User 1's lead stage received 404: SUCCESS")

    # Second user cannot see User 1's tasks
    sec_t_status, sec_t_data = make_req("/api/tasks", token=other_token)
    assert sec_t_status == 200
    assert len(sec_t_data["data"]["tasks"]) == 0, "Second user saw tasks they do not own!"
    print("Second user tasks isolated (sees 0 tasks): SUCCESS")

    # Second user cannot modify User 1's task
    sec_upd_status, _ = make_req(f"/api/tasks/{task_1['id']}", method="PUT", token=other_token, body={"status": "completed"})
    assert sec_upd_status == 404, f"Expected 404 when modifying User 1's task, got {sec_upd_status}"
    print("Second user attempting to update User 1's task received 404: SUCCESS")

    # 8. Check Frontend Pages
    print("\n--- 8. Checking Frontend Routes ---")
    fe_routes = ["/", "/pipeline", "/tasks", "/campaigns"]
    for route in fe_routes:
        req_fe = urllib.request.urlopen(f"{FRONTEND_URL}{route}")
        assert req_fe.status == 200, f"Route {route} failed with status {req_fe.status}"
        print(f"Frontend route '{route}': 200 OK")

    print("\n==================================================")
    print("ALL LIVE E2E REAL-USER TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    main()
