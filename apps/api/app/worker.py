import inngest
import inngest.fast_api
from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()

inngest_client = inngest.Inngest(
    app_id="jobtracker",
    is_production=not settings.inngest_dev,
    event_key=settings.inngest_event_key,
    signing_key=settings.inngest_signing_key,
)

app = FastAPI(title="Job Tracker Worker")

# Workflows are registered here as they land (S2-07).
inngest.fast_api.serve(app, inngest_client, [])
