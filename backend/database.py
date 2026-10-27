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
