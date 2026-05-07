from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import tenders, bidders, evaluation, audit, vendors, bid as bids, vigil, ai, auth
from app.database import init_db

def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="VIGIL Prototype API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OfficerGuard Phase 4: Auth Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])

# TenderEye Core Routers
app.include_router(tenders.router, prefix="/api/v1/tenders", tags=["tenders"])
app.include_router(bidders.router, prefix="/api/v1", tags=["bidders"])
app.include_router(evaluation.router, prefix="/api/v1/evaluation", tags=["evaluation"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])

# BidShield Phase 1 Routers
app.include_router(vendors.router, prefix="/api/v1", tags=["vendors"])
app.include_router(bids.router, prefix="/api/v1", tags=["bids"])

# VIGIL Phase 3 Routers
app.include_router(vigil.router, prefix="/api/v1/vigil", tags=["vigil"])

# AI/Ollama Routers
app.include_router(ai.router, prefix="/api/v1/ai", tags=["ai"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}
