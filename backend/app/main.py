from fastapi import FastAPI

from app.api.routes_allocation import router as allocation_router
from app.api.routes_debt_leak import router as debt_leak_router
from app.api.routes_events import router as events_router
from app.api.routes_gamification import router as gamification_router
from app.api.routes_onboarding import router as onboarding_router
from app.api.routes_personalization import router as personalization_router
from app.api.routes_risk_profile import router as risk_profile_router
from app.api.routes_transparency import router as transparency_router

app = FastAPI(title="Personal Finance App backend")
app.include_router(events_router)
app.include_router(onboarding_router)
app.include_router(risk_profile_router)
app.include_router(allocation_router)
app.include_router(debt_leak_router)
app.include_router(personalization_router)
app.include_router(transparency_router)
app.include_router(gamification_router)


@app.get("/health")
def health():
    return {"status": "ok"}
