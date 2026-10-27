import os
import re
import pytest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MIGRATION_001 = os.path.join(WORKSPACE_ROOT, "supabase", "migrations", "001_initial_schema.sql")
MIGRATION_002 = os.path.join(WORKSPACE_ROOT, "supabase", "migrations", "002_decisions.sql")
GITIGNORE_FILE = os.path.join(WORKSPACE_ROOT, ".gitignore")
BACKEND_ENV_EX = os.path.join(WORKSPACE_ROOT, "backend", ".env.example")
FRONTEND_ENV_EX = os.path.join(WORKSPACE_ROOT, "frontend", ".env.example")

EXPECTED_TABLES = {
    "profiles",
    "campaigns",
    "leads",
    "website_audits",
    "evidence_items",
    "ai_analyses",
    "whatsapp_messages",
    "tasks",
    "followup_schedules",
    "notifications",
    "api_costs",
}

EXPECTED_PIPELINE_STAGES = {
    "discovered",
    "research_pending",
    "researched",
    "qualified",
    "contacted",
    "followup_due",
    "replied",
    "interested",
    "meeting_scheduled",
    "proposal_sent",
    "negotiation",
    "won",
    "closed_lost",
    "not_interested",
    "no_response",
    "opted_out",
}

EXPECTED_REPLY_CLASSIFICATIONS = {
    "interested",
    "wants_info",
    "pricing_request",
    "meeting_request",
    "not_interested",
    "not_now",
    "wrong_number",
    "opt_out",
    "unclear",
}


def read_file(path: str) -> str:
    assert os.path.exists(path), f"File not found: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_migration_files_exist_and_readable():
    """Verify migration files exist and are not empty."""
    content_001 = read_file(MIGRATION_001)
    content_002 = read_file(MIGRATION_002)
    assert len(content_001.strip()) > 500
    assert len(content_002.strip()) > 200


def test_schema_table_coverage():
    """Verify all 11 core tables are created in 001_initial_schema.sql."""
    content = read_file(MIGRATION_001)
    found_tables = set(re.findall(r"CREATE\s+TABLE\s+public\.([a-z_]+)", content, re.IGNORECASE))
    missing = EXPECTED_TABLES - found_tables
    assert not missing, f"Missing tables in initial schema: {missing}"


def test_rls_enabled_on_all_tables():
    """Verify Row Level Security is explicitly enabled on all 11 tables."""
    content = read_file(MIGRATION_001)
    rls_tables = set(re.findall(r"ALTER\s+TABLE\s+public\.([a-z_]+)\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY", content, re.IGNORECASE))
    missing = EXPECTED_TABLES - rls_tables
    assert not missing, f"Tables missing RLS enablement: {missing}"


def test_user_isolation_policies_present():
    """Verify user ownership/isolation RLS policies exist for all tables."""
    content = read_file(MIGRATION_001)
    # Check policies defined
    policy_pattern = r'CREATE\s+POLICY\s+"([^"]+)"\s+ON\s+public\.([a-z_]+)'
    policies = re.findall(policy_pattern, content, re.IGNORECASE)
    tables_with_policy = {table for _, table in policies}
    missing = EXPECTED_TABLES - tables_with_policy
    assert not missing, f"Tables missing RLS policies: {missing}"
    # Verify auth.uid() is used in all policies
    assert content.count("auth.uid()") >= len(EXPECTED_TABLES)


def test_idempotent_triggers_and_policies():
    """Verify triggers and policies use DROP IF EXISTS to allow safe re-runs."""
    content_001 = read_file(MIGRATION_001)
    assert "DROP TRIGGER IF EXISTS on_auth_user_created" in content_001
    assert "DROP TRIGGER IF EXISTS set_updated_at" in content_001
    assert content_001.count("DROP POLICY IF EXISTS") >= 12

    content_002 = read_file(MIGRATION_002)
    assert "DROP POLICY IF EXISTS" in content_002


def test_pipeline_stages_conformity():
    """Verify pipeline_stage CHECK constraint exactly contains the 16 stages from decisions.md."""
    content = read_file(MIGRATION_001)
    match = re.search(r"pipeline_stage\s+TEXT[^\)]+CHECK\s*\(\s*pipeline_stage\s+IN\s*\((.*?)\)\s*\)", content, re.DOTALL | re.IGNORECASE)
    assert match is not None, "pipeline_stage CHECK constraint not found"
    raw_stages = match.group(1)
    stages = set(re.findall(r"'([a-z_]+)'", raw_stages))
    assert stages == EXPECTED_PIPELINE_STAGES, f"Pipeline stages mismatch. Diff: {stages ^ EXPECTED_PIPELINE_STAGES}"


def test_reply_classification_conformity():
    """Verify reply_classification CHECK constraint matches decisions.md."""
    content = read_file(MIGRATION_001)
    match = re.search(r"reply_classification\s+TEXT[^\)]+CHECK\s*\(\s*reply_classification\s+IN\s*\((.*?)\)\s*\)", content, re.DOTALL | re.IGNORECASE)
    assert match is not None, "reply_classification CHECK constraint not found"
    raw_classes = match.group(1)
    classifications = set(re.findall(r"'([a-z_]+)'", raw_classes))
    assert classifications == EXPECTED_REPLY_CLASSIFICATIONS, f"Reply classification mismatch. Diff: {classifications ^ EXPECTED_REPLY_CLASSIFICATIONS}"


def test_decisions_overrides_in_migration_002():
    """Verify decisions.md Section 14 overrides are in 002_decisions.sql."""
    content = read_file(MIGRATION_002)
    assert "verification_status SET DEFAULT 'unverified'" in content, "Safe unverified default missing"
    assert "uq_messages_one_live_per_attempt" in content, "Outbound attempt deduplication index missing"
    assert "uq_messages_wa_message_id" in content, "Webhook message id deduplication index missing"
    assert "'screenshots'" in content, "Screenshots bucket configuration missing"
    assert "public = false" in content, "Screenshots bucket must be private"


def test_security_gitignore_coverage():
    """Verify sensitive files, env files, and secrets are in .gitignore."""
    content = read_file(GITIGNORE_FILE)
    assert ".env" in content
    assert ".env.*" in content
    assert "!.env.example" in content
    assert "*.pem" in content
    assert "*.key" in content
    assert "docs/" in content


def test_env_examples_contain_no_secrets():
    """Verify example files contain only placeholders and no real secrets."""
    b_env = read_file(BACKEND_ENV_EX)
    f_env = read_file(FRONTEND_ENV_EX)

    # Neither should have live keys
    for content in [b_env, f_env]:
        assert "eyJ" not in content, "Found suspected real JWT in example file"
        assert "AIzaSy" not in content, "Found suspected Google key in example file"

    # Frontend must NEVER have SUPABASE_SERVICE_KEY defined as a variable
    assert not re.search(r"^\s*SUPABASE_SERVICE_KEY\s*=", f_env, re.MULTILINE), (
        "SUPABASE_SERVICE_KEY must NEVER be defined in frontend .env"
    )
