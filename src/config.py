from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    KLAVIYO_API_KEY: str = os.environ["KLAVIYO_API_KEY"]
    SUPABASE_URL: str = os.environ["SUPABASE_URL"]
    SUPABASE_ANON_KEY: str = os.environ["SUPABASE_ANON_KEY"]
    SUPABASE_SERVICE_ROLE_KEY: str = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    EXTRACTION_START_DATE: str = os.environ.get("EXTRACTION_START_DATE", "2026-06-01")
    EXTRACTION_END_DATE: str = os.environ.get("EXTRACTION_END_DATE", "2026-06-09")

settings = Settings()
