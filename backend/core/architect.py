"""
FIXED: Policy Architect with improved conflict detection and flexible LLM provider
"""
import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import hashlib
from datetime import datetime
import logging

from backend.core.factory import LLMFactory
from backend.schemas.models import PolicyRule, EPKBSchema, PolicyArchitectRequest
from backend.services.db import DatabaseService

logger = logging.getLogger(__name__)

@dataclass
class PolicyAnalysisResult:
    """Result of policy analysis"""
    policy_id: str
    policy_name: str
    rules_created: int
    conflicts_detected: List[Dict]
    timestamp: datetime

class PolicyArchitect:
    """
    Agent A: Policy Architect
    Converts natural language governance requirements to structured JSON policies
    """
    
    def __init__(self):
        self.llm_provider = None
        self.db_service = None
        self.is_initialized = False
        
        # Policy Architect system prompt
        self.architect_prompt = """You are the Policy Architect for OrchestraGuard, a multi-agent governance system.

Your task is to convert natural language governance requirements into structured, executable JSON policy rules.

CRITICAL RULES:
1. Output MUST be valid JSON matching the exact schema below
2. Each rule MUST have a unique rule_id in format "XX-###" (e.g., "DP-001" for Data Protection)
3. Target tool regex MUST be specific enough to match relevant tools but not over-broad
4. Condition logic MUST be valid Python that can evaluate to True/False
5. Severity MUST be HIGH, MEDIUM, or LOW based on potential impact

OUTPUT SCHEMA:
{
  "policy_name": "string (concise descriptive name)",
  "version": "1.0",
  "rules": [
    {
      "rule_id": "string (e.g., DP-001)",
      "description": "string (human-readable rule)",
      "target_tool_regex": "string (e.g., 'Slack_API_.*' or 'GitHub_API_Create.*')",
      "condition_logic": "string (Python-evaluatable, e.g.: \"tool_arguments.get('channel') == '#general'\")",
      "severity": "HIGH|MEDIUM|LOW",
      "action_on_violation": "BLOCK|FLAG"
    }
  ]
}

EXAMPLES:
1. "Don't allow posting to public channels" becomes:
   {
     "rule_id": "COM-001",
     "description": "Prevent posting to public Slack channels",
     "target_tool_regex": "Slack_API_PostMessage",
     "condition_logic": "tool_arguments.get('channel') in ['#general', '#random', '#public']",
     "severity": "MEDIUM",
     "action_on_violation": "BLOCK"
   }

2. "No production database writes without approval" becomes:
   {
     "rule_id": "DB-001",
     "description": "Prevent unauthorized writes to production databases",
     "target_tool_regex": "SQL_DB_Write.*",
     "condition_logic": "'production' in str(tool_arguments.get('database', '')).lower() and user_context.get('approval_level') < 2",
     "severity": "HIGH",
     "action_on_violation": "BLOCK"
   }

Now convert the following governance requirement:"""
    
    async def initialize(self):
        """Initialize the Policy Architect"""
        # FIXED: Use default provider instead of hardcoded "watsonx"
        self.llm_provider = await LLMFactory.get_provider()
        self.db_service = DatabaseService.get_instance()
        self.is_initialized = True
        logger.info("✅ Policy Architect (Agent A) initialized")
    
    async def analyze_policy(
        self,
        policy_text: str,
        existing_policy_ids: Optional[List[str]] = None
    ) -> PolicyAnalysisResult:
        """
        Analyze natural language policy and convert to executable rules
        with improved conflict detection
        """
        if not self.is_initialized:
            await self.initialize()
        
        try:
            # Step 1: Convert policy text to structured rules using LLM
            structured_rules = await self._convert_to_structured_rules(policy_text)
            
            # Step 2: Validate the rules
            validated_policy = EPKBSchema(**structured_rules)
            
            # Step 3: Check for conflicts with existing policies using database
            conflicts = []
            for rule in validated_policy.rules:
                rule_dict = rule.dict()
                rule_conflicts = await self.db_service.check_policy_conflicts(rule_dict)
                conflicts.extend(rule_conflicts)
            
            # Step 4: Generate policy ID
            policy_id = self._generate_policy_id(validated_policy.policy_name, policy_text)
            
            # Step 5: Store in database (if no critical conflicts)
            rules_created = 0
            if not self._has_critical_conflicts(conflicts):
                rules_created = await self._store_policy(validated_policy)
            else:
                logger.warning(f"Policy '{validated_policy.policy_name}' has critical conflicts, not storing")
            
            return PolicyAnalysisResult(
                policy_id=policy_id,
                policy_name=validated_policy.policy_name,
                rules_created=rules_created,
                conflicts_detected=conflicts,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Policy analysis failed: {e}")
            raise Exception(f"Policy analysis failed: {str(e)}")
    
    async def _convert_to_structured_rules(self, policy_text: str) -> Dict[str, Any]:
        """Use LLM to convert natural language to structured rules"""
        full_prompt = f"{self.architect_prompt}\n\n{policy_text}\n\nOutput ONLY valid JSON:"
        
        try:
            response = await self.llm_provider.invoke(
                prompt=full_prompt,
                system_prompt="You are a precise policy architect. Output only valid JSON.",
                temperature=0.1  # Low temperature for consistent output
            )
            
            # Parse JSON response
            # Sometimes LLMs add markdown code blocks
            content = response.content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            
            if content.endswith("```"):
                content = content[:-3]
            
            # Clean up any leading/trailing whitespace
            content = content.strip()
            
            # Parse JSON
            structured_data = json.loads(content)
            
            # Validate basic structure
            if "policy_name" not in structured_data or "rules" not in structured_data:
                raise ValueError("LLM output missing required fields: 'policy_name' or 'rules'")
            
            # Ensure version exists
            if "version" not in structured_data:
                structured_data["version"] = "1.0"
            
            logger.info(f"Successfully parsed policy with {len(structured_data['rules'])} rules")
            return structured_data
            
        except json.JSONDecodeError as e:
            logger.error(f"LLM output is not valid JSON: {e}")
            raise ValueError(f"LLM output is not valid JSON: {e}")
        except Exception as e:
            logger.error(f"LLM conversion failed: {str(e)}")
            raise Exception(f"LLM conversion failed: {str(e)}")
    
    def _has_critical_conflicts(self, conflicts: List[Dict]) -> bool:
        """Check if there are critical conflicts that should block policy creation"""
        for conflict in conflicts:
            if conflict.get("conflict_type") == "action_conflict":
                # High severity conflicts are critical
                if conflict.get("severity") == "HIGH":
                    return True
                # BLOCK vs ALLOW conflicts are always critical
                if conflict.get("action") == "BLOCK":
                    return True
        return False
    
    async def _store_policy(self, policy: EPKBSchema) -> int:
        """Store policy rules in database"""
        rules_created = 0
        
        for rule in policy.rules:
            # Prepare policy data
            policy_data = {
                "name": f"{policy.policy_name} - {rule.rule_id}",
                "rules": rule.dict(),
                "is_active": True
            }
            
            try:
                # Store in database
                result = await self.db_service.create_policy(policy_data)
                if result:
                    rules_created += 1
                    logger.info(f"Created policy rule: {rule.rule_id}")
                else:
                    logger.warning(f"Failed to create policy rule: {rule.rule_id}")
            except Exception as e:
                logger.error(f"Error storing policy rule {rule.rule_id}: {e}")
        
        logger.info(f"Successfully stored {rules_created} rules from policy '{policy.policy_name}'")
        return rules_created
    
    def _generate_policy_id(self, policy_name: str, policy_text: str) -> str:
        """Generate unique policy ID"""
        # Create hash from policy name and text
        hash_input = f"{policy_name}:{policy_text}"
        hash_digest = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        
        # Create readable ID
        name_slug = re.sub(r'[^a-z0-9]', '', policy_name.lower())[:10]
        return f"pol_{name_slug}_{hash_digest}"
    
    async def close(self):
        """Cleanup"""
        if self.llm_provider:
            await self.llm_provider.close()
        logger.info("👋 Policy Architect shutdown")