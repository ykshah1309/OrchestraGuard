"""
FIXED: Updated to Pydantic V2 syntax with @field_validator
"""
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import re
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
    """Schema for intercepted agent actions"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    action_id: Optional[str] = None
    source_agent: str = Field(min_length=1, max_length=200)
    target_tool: str = Field(min_length=1, max_length=100)
    tool_arguments: Dict[str, Any] = Field(default_factory=dict)
    user_context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    
    @field_validator('tool_arguments')
    @classmethod
    def validate_tool_arguments(cls, v):
        """Ensure tool_arguments is JSON serializable"""
        try:
            json.dumps(v)
            return v
        except TypeError as e:
            raise ValueError(f"tool_arguments must be JSON serializable: {e}")
    
    @field_validator('timestamp', mode='before')
    @classmethod
    def set_timestamp(cls, v):
        """Set timestamp if not provided"""
        return v or datetime.utcnow()
    
    @model_validator(mode='after')
    def validate_action(self):
        """Validate the complete action"""
        if not self.source_agent.startswith("agent_"):
            self.source_agent = f"agent_{self.source_agent}"
        return self

class PolicyRule(BaseModel):
    """Individual policy rule"""
    rule_id: str = Field(pattern=r'^[A-Z]{2}-\d{3}$')  # e.g., DP-001
    description: str = Field(min_length=10, max_length=500)
    target_tool_regex: str = Field(min_length=1, max_length=200)
    condition_logic: str = Field(min_length=1, max_length=1000)
    severity: SeverityEnum
    action_on_violation: ActionOnViolationEnum
    
    @field_validator('condition_logic')
    @classmethod
    def validate_python_logic(cls, v):
        """Basic validation for Python-evaluatable logic"""
        dangerous_keywords = [
            'import', 'exec', 'eval', '__', 'open(', 'os.', 'sys.', 
            'subprocess', 'compile', 'execfile', 'input'
        ]
        
        for keyword in dangerous_keywords:
            if keyword in v.lower():
                raise ValueError(f"Condition contains dangerous keyword: {keyword}")
        
        # Try to compile to ensure it's valid Python
        try:
            # Wrap in a lambda for safety
            code = f"lambda tool_arguments, user_context: {v}"
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            raise ValueError(f"Invalid Python syntax in condition: {e}")
        
        return v

class EPKBSchema(BaseModel):
    """Enterprise Policy Knowledge Base"""
    policy_name: str = Field(min_length=1, max_length=100)
    version: str = Field(default="1.0", pattern=r'^\d+\.\d+$')
    rules: List[PolicyRule] = Field(min_length=1)
    
    @field_validator('rules')
    @classmethod
    def validate_unique_rule_ids(cls, v):
        """Ensure rule IDs are unique within the policy"""
        rule_ids = [rule.rule_id for rule in v]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Duplicate rule_ids found in policy")
        return v

class Decision(BaseModel):
    """Decision from Ethical Reasoner"""
    action_id: str
    source_agent: str
    target_tool: str
    decision: DecisionEnum
    rationale: str = Field(min_length=10, max_length=1000)
    severity: Optional[SeverityEnum] = None
    timestamp: datetime
    applied_rules: List[str] = Field(default_factory=list)  # New: Track which rules were applied
    
    @field_validator('severity')
    @classmethod
    def validate_severity_decision(cls, v, info):
        """Validate severity based on decision"""
        values = info.data
        decision = values.get('decision')
        
        if decision == DecisionEnum.BLOCK and not v:
            raise ValueError("BLOCK decisions must have a severity")
        
        if decision == DecisionEnum.ALLOW and v:
            # Allow can have severity if it was flagged but overridden
            # For now, we'll allow it but warn
            pass
            
        return v

class PolicyArchitectRequest(BaseModel):
    """Request for Policy Architect"""
    policy_text: str = Field(min_length=10, max_length=10000)
    source_document_type: Optional[str] = Field(default=None)
    existing_policy_ids: Optional[List[str]] = Field(default_factory=list)

class MCPContextRequest(BaseModel):
    """Request for MCP context fetching"""
    tool_name: str
    tool_arguments: Dict[str, Any]
    context_type: str = Field(default="recent_activity")  # recent_activity, permissions, metadata
    max_results: int = Field(default=10, ge=1, le=100)

class AgentHealth(BaseModel):
    """Health status of each agent"""
    agent_a: bool = Field(default=False)  # Policy Architect
    agent_b: bool = Field(default=False)  # Sentinel Interceptor
    agent_c: bool = Field(default=False)  # Ethical Reasoner
    agent_d: bool = Field(default=False)  # Logger
    timestamp: datetime = Field(default_factory=datetime.utcnow)