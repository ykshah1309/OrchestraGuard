"""
Data Models using Pydantic V2 for 10x faster validation
"""
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import json

class DecisionEnum(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    FLAG = "FLAG"

class SeverityEnum(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class ActionOnViolationEnum(str, Enum):
    BLOCK = "BLOCK"
    FLAG = "FLAG"

class InterceptedAction(BaseModel):
    """
    Schema for intercepted agent actions from Sentinel (Agent B)
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    action_id: Optional[str] = None
    source_agent: str = Field(..., min_length=1, max_length=200)
    target_tool: str = Field(..., min_length=1, max_length=100)
    tool_arguments: Dict[str, Any] = Field(default_factory=dict)
    user_context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    
    @validator('tool_arguments')
    def validate_tool_arguments(cls, v):
        """Ensure tool_arguments is JSON serializable"""
        try:
            json.dumps(v)
            return v
        except TypeError:
            raise ValueError("tool_arguments must be JSON serializable")
    
    @validator('timestamp', pre=True, always=True)
    def set_timestamp(cls, v):
        """Set timestamp if not provided"""
        return v or datetime.utcnow()

class PolicyRule(BaseModel):
    """
    Individual policy rule schema
    """
    rule_id: str = Field(..., pattern=r'^[A-Z]{2}-\d{3}$')  # e.g., DP-001
    description: str = Field(..., min_length=10, max_length=500)
    target_tool_regex: str = Field(..., min_length=1, max_length=200)
    condition_logic: str = Field(..., min_length=1, max_length=1000)
    severity: SeverityEnum
    action_on_violation: ActionOnViolationEnum
    
    @validator('condition_logic')
    def validate_python_logic(cls, v):
        """Basic validation for Python-evaluatable logic"""
        # Check for dangerous operations
        dangerous_keywords = ['import', 'exec', 'eval', '__', 'open', 'os.', 'sys.', 'subprocess']
        for keyword in dangerous_keywords:
            if keyword in v:
                raise ValueError(f"Condition logic contains dangerous keyword: {keyword}")
        return v

class EPKBSchema(BaseModel):
    """
    Enterprise Policy Knowledge Base Schema
    Output of Policy Architect (Agent A)
    """
    policy_name: str = Field(..., min_length=1, max_length=100)
    version: str = Field(default="1.0", pattern=r'^\d+\.\d+$')
    rules: List[PolicyRule] = Field(..., min_items=1)

class Decision(BaseModel):
    """
    Decision schema from Ethical Reasoner (Agent C)
    """
    action_id: str
    source_agent: str
    target_tool: str
    decision: DecisionEnum
    rationale: str = Field(..., min_length=10, max_length=1000)
    severity: Optional[SeverityEnum] = None
    timestamp: datetime
    
    @validator('severity')
    def validate_severity(cls, v, values):
        """Validate severity based on decision"""
        if values.get('decision') == DecisionEnum.BLOCK and not v:
            raise ValueError("BLOCK decisions must have a severity")
        if values.get('decision') == DecisionEnum.ALLOW and v:
            raise ValueError("ALLOW decisions should not have severity")
        return v

class DecisionRequest(BaseModel):
    """Request schema for decision endpoint"""
    action: InterceptedAction

class DecisionResponse(BaseModel):
    """Response schema for decision endpoint"""
    action_id: str
    decision: DecisionEnum
    rationale: str
    severity: Optional[SeverityEnum]
    timestamp: datetime
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action_id": "a4b2c8d9-e0f1-4a2b-8c3d-4e5f6a7b8c9d",
                "decision": "BLOCK",
                "rationale": "SSN sharing violates PII policy DP-001",
                "severity": "HIGH",
                "timestamp": "2024-01-29T10:30:00Z"
            }
        }
    )

class PolicyOutput(BaseModel):
    """Policy creation output"""
    policy_id: str
    policy_name: str
    rule_count: int
    created_at: datetime
    
class AuditLogQuery(BaseModel):
    """Query parameters for audit logs"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    decision: Optional[DecisionEnum] = None
    source_agent: Optional[str] = None
    target_tool: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    timestamp: datetime
    database: Optional[bool] = None
    llm_provider: Optional[bool] = None