"""
FIXED: Main application with secure CORS configuration
"""

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import uuid
import json
from datetime import datetime
import os
import logging

from backend.core.engine import ReasoningEngine
from backend.core.architect import PolicyArchitect
from backend.core.security import validate_jwt_token
from backend.schemas.models import (
    InterceptedAction,
    DecisionResponse,
    PolicyArchitectRequest,
    MCPContextRequest,
    AgentHealth,
)
from backend.services.db import DatabaseService
from backend.services.notify import NotificationService
from backend.services.mcp_client import MCPClient

logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for startup/shutdown events."""
    # Initialize services on startup
    try:
        # Initialize database
        db = await DatabaseService.get_instance()
        await db.health_check()

        # Initialize reasoning engine
        app.state.engine = ReasoningEngine()
        await app.state.engine.initialize()

        # Initialize policy architect
        app.state.architect = PolicyArchitect()
        await app.state.architect.initialize()

        # Initialize MCP client
        app.state.mcp_client = MCPClient()

        # Initialize notification service
        app.state.notify = NotificationService.get_instance()

        logger.info("🚀 OrchestraGuard V2 initialized successfully")

    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        raise

    yield

    # Cleanup on shutdown
    if hasattr(app.state, "engine"):
        await app.state.engine.close()
    if hasattr(app.state, "architect"):
        await app.state.architect.close()
    if hasattr(app.state, "mcp_client"):
        await app.state.mcp_client.close()

    logger.info("👋 OrchestraGuard V2 shutdown complete")


def get_cors_origins():
    """Get CORS origins from environment variable or use defaults for development."""
    cors_origins = os.getenv("CORS_ORIGINS", "")
    if cors_origins:
        # Split by comma and strip whitespace
        return [origin.strip() for origin in cors_origins.split(",")]
    else:
        # Development defaults
        return ["http://localhost:3000", "http://localhost:8000"]


app = FastAPI(
    title="OrchestraGuard V2 API",
    description="Multi-Agent Governance Mesh - Complete Implementation",
    version="2.0.0",
    lifespan=lifespan,
)

# FIXED: Secure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),  # Configurable origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # 10 minutes for preflight cache
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Validate JWT token and return user."""
    payload = validate_jwt_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "OrchestraGuard V2",
        "version": "2.0.0",
        "status": "operational",
        "agents": [
            "A (Policy Architect)",
            "B (Interceptor)",
            "C (Ethical Reasoner)",
            "D (Logger)",
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development"),
    }


@app.post("/intercept", response_model=DecisionResponse)
async def intercept_action(
    action: InterceptedAction,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Main interception endpoint - Receives agent actions for ethical review."""
    try:
        # Log the interception
        logger.info(
            f"🛡️ Intercepted action from {action.source_agent} to {action.target_tool}"
        )

        # Generate action ID if not provided
        if not action.action_id:
            action.action_id = str(uuid.uuid4())

        # Add request metadata
        action.metadata = action.metadata or {}
        action.metadata.update(
            {
                "intercepted_by": "sentinel_b",
                "interceptor_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent"),
                "auth_user": current_user.get("sub", "system"),
                "timestamp_utc": datetime.utcnow().isoformat(),
            }
        )

        # Process through reasoning engine (Agent C)
        decision = await app.state.engine.process_action(action)

        # Create response
        response = DecisionResponse(
            action_id=decision.action_id,
            decision=decision.decision,
            rationale=decision.rationale,
            severity=decision.severity,
            timestamp=decision.timestamp,
            applied_rules=decision.applied_rules,
        )

        # Log to console
        logger.info(f"✅ Decision: {decision.decision} for action {action.action_id}")
        if decision.decision == "BLOCK":
            logger.warning(f"   Reason: {decision.rationale}")
            logger.warning(f"   Severity: {decision.severity}")

        return response

    except Exception as e:
        logger.error(f"❌ Error in /intercept: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing action: {str(e)}",
        )


@app.post("/policy/analyze")
async def analyze_policy(
    request: PolicyArchitectRequest,
    current_user: dict = Depends(get_current_user),
):
    """Policy Architect endpoint - Agent A converts human policies to executable rules."""
    try:
        logger.info(
            f"📋 Policy analysis requested by {current_user.get('sub', 'unknown')}"
        )

        # Analyze policy using Agent A
        result = await app.state.architect.analyze_policy(
            policy_text=request.policy_text,
            existing_policy_ids=request.existing_policy_ids,
        )

        return {
            "status": "success",
            "policy_id": result.policy_id,
            "policy_name": result.policy_name,
            "rules_created": result.rules_created,
            "conflicts_detected": result.conflicts_detected,
            "message": f"Created {result.rules_created} rules from policy",
        }

    except Exception as e:
        logger.error(f"Policy analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Policy analysis failed: {str(e)}",
        )


@app.post("/mcp/context")
async def get_mcp_context(
    request: MCPContextRequest,
    current_user: dict = Depends(get_current_user),
):
    """MCP Context endpoint - Fetch external context for decision making."""
    try:
        logger.info(f"🌐 MCP context requested for {request.tool_name}")

        # Fetch context using MCP client
        context = await app.state.mcp_client.fetch_context(
            tool_name=request.tool_name,
            tool_arguments=request.tool_arguments,
            context_type=request.context_type,
            max_results=request.max_results,
        )

        return {
            "status": "success",
            "tool_name": request.tool_name,
            "context_type": request.context_type,
            "results": context.results,
            "total_results": context.total_results,
            "metadata": context.metadata,
        }

    except Exception as e:
        logger.error(f"MCP context fetch failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCP context fetch failed: {str(e)}",
        )


@app.get("/health")
async def health_check():
    """Health check endpoint with agent status."""
    try:
        db = await DatabaseService.get_instance()
        db_health = await db.health_check()

        # Check agent status
        agent_health = AgentHealth(
            agent_a=hasattr(app.state, "architect")
            and app.state.architect.is_initialized,
            agent_b=True,  # This API itself is Agent B
            agent_c=hasattr(app.state, "engine") and app.state.engine.is_initialized,
            agent_d=True,  # Logger is integrated
        )

        return {
            "status": "healthy" if db_health.get("status") == "healthy" else "degraded",
            "service": "OrchestraGuard V2",
            "timestamp": datetime.utcnow().isoformat(),
            "database": db_health,
            "agents": agent_health.dict(),
            "version": "2.0.0",
            "environment": os.getenv("ENVIRONMENT", "development"),
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@app.get("/metrics")
async def get_metrics(current_user: dict = Depends(get_current_user)):
    """Get system metrics."""
    try:
        db = await DatabaseService.get_instance()
        metrics = await db.get_metrics()

        # Add engine stats if available
        if hasattr(app.state, "engine"):
            engine_stats = app.state.engine.get_stats()
            metrics["engine_stats"] = engine_stats

        return {
            "status": "success",
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metrics: {str(e)}",
        )


@app.get("/audit/recent")
async def get_recent_audits(
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    """Get recent audit logs."""
    try:
        db = await DatabaseService.get_instance()

        # Use direct database query
        response = (
            db.supabase.table("audit_logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        return {"status": "success", "count": len(response.data), "logs": response.data}

    except Exception as e:
        logger.error(f"Failed to get audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit logs: {str(e)}",
        )


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)

    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Only add HSTS in production
    if os.getenv("ENVIRONMENT") == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")