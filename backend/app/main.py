from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_allocation import router as allocation_router
from app.api.routes_auth import router as auth_router
from app.api.routes_debt_leak import router as debt_leak_router
from app.api.routes_events import router as events_router
from app.api.routes_gamification import router as gamification_router
from app.api.routes_onboarding import router as onboarding_router
from app.api.routes_personalization import router as personalization_router
from app.api.routes_risk_profile import config_router as risk_profile_config_router
from app.api.routes_risk_profile import router as risk_profile_router
from app.api.routes_rumour_verification import router as rumour_verification_router
from app.api.routes_transparency import router as transparency_router
from app.config import CORS_ORIGIN_REGEX, CORS_ORIGINS

app = FastAPI(title="Personal Finance App backend")

# Restricted to the deployed frontend plus localhost for Expo web dev. Auth
# is bearer-token (no cookies), so credentials stay disabled.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(events_router)
app.include_router(onboarding_router)
app.include_router(risk_profile_router)
app.include_router(risk_profile_config_router)
app.include_router(allocation_router)
app.include_router(debt_leak_router)
app.include_router(personalization_router)
app.include_router(transparency_router)
app.include_router(gamification_router)
app.include_router(rumour_verification_router)


@app.get("/health")
def health():
    return {"status": "ok"}
