"""
FastAPI Entry Point for OrchestraGuard - Sentinel Interceptor (Agent B)
"""
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import uuid
import json

from backend.core.engine import ReasoningEngine
from backend.core.security import validate_jwt_token
from backend.schemas.models import InterceptedAction, DecisionRequest, DecisionResponse
from backend.services.db import DatabaseService
from backend.services.notify import NotificationService

# Security
security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for startup/shutdown events"""
    # Initialize services
    DatabaseService.get_instance()
    NotificationService.get_instance()
    yield
    # Cleanup
    if hasattr(app.state, 'engine'):
        await app.state.engine.close()

app = FastAPI(
    title="OrchestraGuard API",
    description="Multi-Agent Governance Mesh",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency for auth
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Validate JWT token and return user"""
    payload = validate_jwt_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

@app.on_event("startup")
async def startup_event():
    """Initialize the reasoning engine on startup"""
    app.state.engine = ReasoningEngine()
    await app.state.engine.initialize()

@app.post("/intercept", response_model=DecisionResponse)
async def intercept_action(
    action: InterceptedAction,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Main interception endpoint - Receives agent actions for ethical review
    """
    try:
        # Generate action ID if not provided
        if not action.action_id:
            action.action_id = str(uuid.uuid4())
        
        # Add request metadata
        action.metadata = action.metadata or {}
        action.metadata.update({
            "interceptor_ip": request.client.host,
            "user_agent": request.headers.get("user-agent"),
            "auth_user": current_user.get("sub", "system")
        })
        
        # Process through reasoning engine
        decision = await app.state.engine.process_action(action)
        
        return DecisionResponse(
            action_id=action.action_id,
            decision=decision.decision,
            rationale=decision.rationale,
            severity=decision.severity,
            timestamp=decision.timestamp
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/policy/analyze")
async def analyze_policy(
    policy_text: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Policy Architect endpoint - Converts human policies to executable rules
    """
    try:
        # Switch to Policy Architect mode
        rules = await app.state.engine.analyze_policy(policy_text)
        
        return {
            "status": "success",
            "rules": rules,
            "message": f"Generated {len(rules)} rules from policy"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "OrchestraGuard",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/metrics")
async def get_metrics(current_user: dict = Depends(get_current_user)):
    """Get system metrics"""
    db = DatabaseService.get_instance()
    
    metrics = {
        "total_decisions": await db.get_audit_count(),
        "allow_rate": await db.get_decision_rate("ALLOW"),
        "block_rate": await db.get_decision_rate("BLOCK"),
        "flag_rate": await db.get_decision_rate("FLAG"),
        "active_policies": await db.get_active_policy_count()
    }
    
    return metrics

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)