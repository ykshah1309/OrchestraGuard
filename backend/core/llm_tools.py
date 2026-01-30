"""
Complete LLM Tool-Calling Implementation for Ethical Reasoner (Agent C)
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime
import json

class ToolType(str, Enum):
    """Types of tools available to the LLM"""
    GET_POLICY_RULES = "get_policy_rules"
    LOG_DECISION = "log_decision"
    ALLOW_ACTION = "allow_action"
    BLOCK_ACTION = "block_action"
    FLAG_ACTION = "flag_action"

class GetPolicyRulesInput(BaseModel):
    """Input schema for get_policy_rules tool"""
    target_tool: str = Field(..., description="The target tool to get policies for")

class GetPolicyRulesOutput(BaseModel):
    """Output schema for get_policy_rules tool"""
    rules: List[Dict[str, Any]] = Field(..., description="List of policy rules for the target tool")
    total_rules: int = Field(..., description="Total number of rules found")

class LogDecisionInput(BaseModel):
    """Input schema for log_decision tool"""
    action_id: str = Field(..., description="Unique identifier for the action")
    decision: str = Field(..., description="Final decision (ALLOW, BLOCK, FLAG)")
    rationale: str = Field(..., description="Explanation for the decision")
    severity: Optional[str] = Field(None, description="Severity level (HIGH, MEDIUM, LOW)")
    applied_rules: List[str] = Field(default_factory=list, description="List of rule IDs that were applied")

class LogDecisionOutput(BaseModel):
    """Output schema for log_decision tool"""
    success: bool = Field(..., description="Whether the log was successful")
    log_id: Optional[str] = Field(None, description="ID of the created audit log")
    timestamp: datetime = Field(..., description="When the log was created")

class AllowActionInput(BaseModel):
    """Input schema for allow_action tool"""
    action_id: str = Field(..., description="Unique identifier for the action")
    rationale: str = Field(..., description="Reason for allowing the action")

class AllowActionOutput(BaseModel):
    """Output schema for allow_action tool"""
    success: bool = Field(..., description="Whether the action was allowed")
    message: str = Field(..., description="Status message")

class BlockActionInput(BaseModel):
    """Input schema for block_action tool"""
    action_id: str = Field(..., description="Unique identifier for the action")
    rationale: str = Field(..., description="Reason for blocking the action")
    severity: str = Field(..., description="Severity level (HIGH, MEDIUM, LOW)")

class BlockActionOutput(BaseModel):
    """Output schema for block_action tool"""
    success: bool = Field(..., description="Whether the action was blocked")
    message: str = Field(..., description="Status message")
    notification_sent: bool = Field(..., description="Whether notification was sent")

class FlagActionInput(BaseModel):
    """Input schema for flag_action tool"""
    action_id: str = Field(..., description="Unique identifier for the action")
    rationale: str = Field(..., description="Reason for flagging the action")
    severity: str = Field(..., description="Severity level (HIGH, MEDIUM, LOW)")

class FlagActionOutput(BaseModel):
    """Output schema for flag_action tool"""
    success: bool = Field(..., description="Whether the action was flagged")
    message: str = Field(..., description="Status message")

class LLMToolkit:
    """
    Toolkit for LLM tool-calling implementation
    Provides the tools and handles tool execution
    """
    
    @staticmethod
    def get_tool_definitions() -> List[Dict[str, Any]]:
        """Get tool definitions for LLM function calling"""
        return [
            {
                "type": "function",
                "function": {
                    "name": ToolType.GET_POLICY_RULES.value,
                    "description": "Retrieve active policy rules for a specific target tool",
                    "parameters": GetPolicyRulesInput.model_json_schema()
                }
            },
            {
                "type": "function",
                "function": {
                    "name": ToolType.LOG_DECISION.value,
                    "description": "Log the final decision and rationale to the audit log",
                    "parameters": LogDecisionInput.model_json_schema()
                }
            },
            {
                "type": "function",
                "function": {
                    "name": ToolType.ALLOW_ACTION.value,
                    "description": "Allow the intercepted action to proceed",
                    "parameters": AllowActionInput.model_json_schema()
                }
            },
            {
                "type": "function",
                "function": {
                    "name": ToolType.BLOCK_ACTION.value,
                    "description": "Block the intercepted action and prevent execution",
                    "parameters": BlockActionInput.model_json_schema()
                }
            },
            {
                "type": "function",
                "function": {
                    "name": ToolType.FLAG_ACTION.value,
                    "description": "Flag the action for review but allow it to proceed",
                    "parameters": FlagActionInput.model_json_schema()
                }
            }
        ]
    
    @staticmethod
    def get_master_prompt_with_tools() -> str:
        """Get the master system prompt with tool-calling instructions"""
        return """You are the Ethical Reasoner for OrchestraGuard, a multi-agent governance system.

CRITICAL RULES:
1. **NEVER** allow an action that violates a policy rule.
2. **ALWAYS** use the provided tools in the correct sequence.
3. **MUST LOG** every decision using the log_decision tool.
4. **PRIORITY**: Security and Compliance override Efficiency. When in doubt, Block.

REQUIRED WORKFLOW (YOU MUST FOLLOW THIS EXACT SEQUENCE):

1. **RECEIVE INTERCEPTION**: You will receive an intercepted action JSON.

2. **GET POLICIES**: Immediately call `get_policy_rules` with the `target_tool` to retrieve relevant policies.

3. **EVALUATE**: Compare the action against each policy rule.

4. **DECIDE & EXECUTE**:
   - If NO RULES VIOLATED: Call `allow_action` then `log_decision`
   - If RULES VIOLATED: 
     - If rule says "BLOCK": Call `block_action` then `log_decision`
     - If rule says "FLAG": Call `flag_action` then `log_decision`

5. **LOG**: Always call `log_decision` as the final step to record the outcome.

TOOL USAGE RULES:
- You MUST call tools in the correct sequence
- You MUST provide all required parameters
- You MUST log every decision
- You MUST respect the rule's action_on_violation

OUTPUT FORMAT:
Your final output should be a confirmation of the executed workflow, NOT raw JSON."""
    
    @staticmethod
    def validate_tool_call(tool_name: str, arguments: Dict[str, Any]) -> bool:
        """Validate tool call parameters"""
        try:
            if tool_name == ToolType.GET_POLICY_RULES.value:
                GetPolicyRulesInput(**arguments)
            elif tool_name == ToolType.LOG_DECISION.value:
                LogDecisionInput(**arguments)
            elif tool_name == ToolType.ALLOW_ACTION.value:
                AllowActionInput(**arguments)
            elif tool_name == ToolType.BLOCK_ACTION.value:
                BlockActionInput(**arguments)
            elif tool_name == ToolType.FLAG_ACTION.value:
                FlagActionInput(**arguments)
            else:
                return False
            return True
        except Exception:
            return False
    
    @staticmethod
    def execute_tool(
        tool_name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool call and return results"""
        from backend.services.db import DatabaseService
        from backend.services.notify import NotificationService
        
        db_service = context.get("db_service")
        notify_service = context.get("notify_service")
        action_data = context.get("action_data", {})
        
        try:
            if tool_name == ToolType.GET_POLICY_RULES.value:
                return LLMToolkit._execute_get_policy_rules(arguments, db_service)
            elif tool_name == ToolType.LOG_DECISION.value:
                return LLMToolkit._execute_log_decision(arguments, db_service)
            elif tool_name == ToolType.ALLOW_ACTION.value:
                return LLMToolkit._execute_allow_action(arguments, action_data)
            elif tool_name == ToolType.BLOCK_ACTION.value:
                return LLMToolkit._execute_block_action(arguments, action_data, notify_service)
            elif tool_name == ToolType.FLAG_ACTION.value:
                return LLMToolkit._execute_flag_action(arguments, action_data)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    async def _execute_get_policy_rules(
        arguments: Dict[str, Any],
        db_service
    ) -> Dict[str, Any]:
        """Execute get_policy_rules tool"""
        if not db_service:
            raise ValueError("Database service not available")
        
        target_tool = arguments.get("target_tool", "")
        
        # Get active policies
        policies = await db_service.get_active_policies()
        
        # Filter policies for target tool
        relevant_rules = []
        for policy in policies:
            rules = policy.get("rules", {})
            if isinstance(rules, dict):
                target_regex = rules.get("target_tool_regex", "")
                
                # Simple regex matching (in production, use proper regex)
                if target_regex in target_tool or target_tool in target_regex:
                    relevant_rules.append({
                        "rule_id": rules.get("rule_id"),
                        "description": rules.get("description"),
                        "condition_logic": rules.get("condition_logic"),
                        "severity": rules.get("severity"),
                        "action_on_violation": rules.get("action_on_violation")
                    })
        
        return {
            "rules": relevant_rules,
            "total_rules": len(relevant_rules),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    async def _execute_log_decision(
        arguments: Dict[str, Any],
        db_service
    ) -> Dict[str, Any]:
        """Execute log_decision tool"""
        if not db_service:
            raise ValueError("Database service not available")
        
        # Log to database
        log_result = await db_service.log_audit(
            action_id=arguments.get("action_id"),
            source_agent="llm_toolkit",  # Would be from context
            target_tool="unknown",  # Would be from context
            decision=arguments.get("decision"),
            rationale=arguments.get("rationale"),
            severity=arguments.get("severity"),
            applied_rules=arguments.get("applied_rules", [])
        )
        
        return {
            "success": log_result is not None,
            "log_id": log_result.get("id") if log_result else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _execute_allow_action(
        arguments: Dict[str, Any],
        action_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute allow_action tool"""
        # In production, this would trigger the actual allowance
        print(f"✅ ALLOWED action {arguments.get('action_id')}: {arguments.get('rationale')}")
        
        return {
            "success": True,
            "message": f"Action {arguments.get('action_id')} allowed",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _execute_block_action(
        arguments: Dict[str, Any],
        action_data: Dict[str, Any],
        notify_service
    ) -> Dict[str, Any]:
        """Execute block_action tool"""
        # Block the action
        print(f"🚫 BLOCKED action {arguments.get('action_id')}: {arguments.get('rationale')}")
        
        # Send notification if service available
        notification_sent = False
        if notify_service:
            try:
                notify_service.send_immediate_alert({
                    "type": "BLOCK_ALERT",
                    "action_id": arguments.get("action_id"),
                    "rationale": arguments.get("rationale"),
                    "severity": arguments.get("severity"),
                    "timestamp": datetime.utcnow().isoformat()
                })
                notification_sent = True
            except Exception:
                pass
        
        return {
            "success": True,
            "message": f"Action {arguments.get('action_id')} blocked",
            "notification_sent": notification_sent,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _execute_flag_action(
        arguments: Dict[str, Any],
        action_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute flag_action tool"""
        # Flag the action (allow but with warning)
        print(f"⚠️ FLAGGED action {arguments.get('action_id')}: {arguments.get('rationale')}")
        
        return {
            "success": True,
            "message": f"Action {arguments.get('action_id')} flagged for review",
            "timestamp": datetime.utcnow().isoformat()
        }