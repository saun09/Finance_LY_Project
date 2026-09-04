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

app = FastAPI(title="Personal Finance App backend")

# Dev-only: the Expo web target runs on its own origin (Metro's dev
# server) and needs CORS to call this API from the browser. There's no
# auth/session and no production deployment of this backend, so an
# unrestricted allow-list is the right tradeoff here rather than hardcoding
# a Metro port that varies by machine/run.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
