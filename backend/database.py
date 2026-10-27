from supabase import create_client, Client
from backend.config import settings

# Initialize Supabase client using service role key (bypasses RLS on backend queries)
supabase: Client = create_client(
    supabase_url=settings.SUPABASE_URL,
    supabase_key=settings.SUPABASE_SERVICE_KEY,
)


def get_supabase_client() -> Client:
    """Dependency helper to return the initialized Supabase client."""
    return supabase


def check_database_connection() -> bool:
    """Verify Supabase database connectivity by performing a lightweight query."""
    try:
        response = supabase.table("profiles").select("id").limit(1).execute()
        return response is not None
    except Exception:
        return False
