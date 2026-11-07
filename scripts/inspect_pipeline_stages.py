import httpx

SUPABASE_URL = "https://pfccofklivdxncpeabln.supabase.co"
SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmY2NvZmtsaXZkeG5jcGVhYmxuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTMwOTc4MDksImV4cCI6MjEwODY3MzgwOX0."
    "jMdhWVafB5atMXtMvkaohLilz0Ezouh_F2clsW2S1bI"
)

res = httpx.post(
    f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
    json={"email": "mdanas12.2007@gmail.com", "password": "Anas1234"},
    headers={"apikey": SUPABASE_ANON_KEY},
)
token = res.json()["access_token"]
b = httpx.get("http://localhost:8000/api/pipeline", headers={"Authorization": f"Bearer {token}"})
data = b.json()["data"]

print("ACTIVE COLUMNS:")
for k, v in data["columns"].items():
    if v:
        print(f"  {k} ({len(v)}):")
        for card in v:
            print(f"    - {card['id']}: {card['business_name']} (stage: {card['pipeline_stage']})")

print("\nCLOSED COLUMNS:")
for k, v in data["closed"].items():
    if v:
        print(f"  {k} ({len(v)}):")
        for card in v:
            print(f"    - {card['id']}: {card['business_name']} (stage: {card['pipeline_stage']})")

