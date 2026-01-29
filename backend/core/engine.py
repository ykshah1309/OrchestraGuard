"""
Reasoning Engine (Agent C) - Orchestrates the Ethical Reasoner workflow
"""

import asyncio
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib
from collections import defaultdict
import logging

from backend.core.factory import LLMFactory, LLMResponse
from backend.schemas.models import (
    InterceptedAction,
    Decision,
    PolicyRule,
    EPKBSchema,
    PolicyOutput,
)
from backend.services.db import DatabaseService
from backend.services.notify import NotificationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReasoningEngine:
    """
    Core reasoning engine using DAG-based tool-calling logic.
    Implements exponential backoff and caching.
    """

    def __init__(self):
        self.llm_provider: Optional[LLMResponse] = None
        self.db_service: Optional[DatabaseService] = None
        self.notify_service: Optional[NotificationService] = None

        # Cache for policies (hash map for O(1) lookup)
        self._policy_cache: Dict[str, List[PolicyRule]] = defaultdict(list)
        self._policy_hash: Dict[str, PolicyRule] = {}

        # Retry configuration
        self.max_retries = 3
        self.base_delay = 1.0  # seconds

        # Master System Prompt
        self.master_prompt = """You are the Ethical Reasoner for OrchestraGuard. Your job is to evaluate intercepted agent actions against enterprise policies.

RULES YOU MUST FOLLOW:
1. NEVER allow an action that violates a rule in the EPKB.
2. NEVER use external knowledge or common sense; rely only on the EPKB rule.
3. ALWAYS log every decision (Allow or Block).
4. PRIORITY: Security and Compliance override Efficiency. When in doubt, Block.
5. OUTPUT FORMAT: Your final response MUST be a single, valid JSON object.

CORE LOGIC FLOW:
1. RECEIVE INTERCEPTION: Analyze the intercepted action JSON.
2. RETRIEVE POLICY: Apply relevant policy rules for the target_tool.
3. REASON & EVALUATE: Compare tool_arguments and user_context against rules.
4. DECIDE: Determine if action is compliant (ALLOW/BLOCK/FLAG).
5. LOG: Record decision with rationale and severity.

POLICY RULES:
{policy_rules}

OUTPUT JSON FORMAT:
{{
  "decision": "ALLOW|BLOCK|FLAG",
  "rationale": "concise explanation",
  "severity": "HIGH|MEDIUM|LOW|null"
}}"""

    async def initialize(self) -> None:
        """Initialize engine with dependencies."""
        self.llm_provider = LLMFactory.get_provider()
        self.db_service = DatabaseService.get_instance()
        self.notify_service = NotificationService.get_instance()

        # Pre-load policies into cache
        await self._load_policies_to_cache()
        logger.info("ReasoningEngine initialized")

    async def _load_policies_to_cache(self) -> None:
        """Load policies from DB into memory cache."""
        policies = await self.db_service.get_all_policies()

        for policy in policies:
            if policy.is_active:
                # Create hash key for caching
                cache_key = policy.name + policy.target_tool_regex
                hash_key = hashlib.md5(cache_key.encode()).hexdigest()

                # Store in cache
                self._policy_cache[policy.target_tool_regex].append(policy)
                self._policy_hash[hash_key] = policy

        logger.info(f"Loaded {len(policies)} policies into cache")

    async def process_action(self, action: InterceptedAction) -> Decision:
        """
        Main processing method for intercepted actions.
        Implements DAG-based decision flow with early exit.
        """
        start_time = datetime.utcnow()

        try:
            # 1. Retrieve relevant policies (O(1) cache lookup)
            relevant_rules = await self._get_relevant_policies(action.target_tool)

            if not relevant_rules:
                # No policies exist for this tool - default to ALLOW with logging
                decision = Decision(
                    action_id=action.action_id,
                    source_agent=action.source_agent,
                    target_tool=action.target_tool,
                    decision="ALLOW",
                    rationale="No policies defined for this tool",
                    severity=None,
                    timestamp=datetime.utcnow(),
                )
                await self._log_decision(decision, action)
                return decision

            # 2. Construct dynamic prompt with injected rules
            policy_text = self._format_policies_for_prompt(relevant_rules)
            full_prompt = self.master_prompt.format(policy_rules=policy_text)

            # 3. Prepare action context for LLM
            action_context = {
                "action_id": action.action_id,
                "source_agent": action.source_agent,
                "target_tool": action.target_tool,
                "tool_arguments": action.tool_arguments,
                "user_context": action.user_context,
                "timestamp": action.timestamp.isoformat()
                if action.timestamp
                else None,
            }

            user_prompt = (
                "Evaluate this intercepted action against the provided policies:\n\n"
                "```json\n"
                f"{json.dumps(action_context, indent=2)}\n"
                "```\n\n"
                "Provide your decision in the required JSON format."
            )

            # 4. Call LLM with retry logic
            llm_response = await self._call_llm_with_retry(
                prompt=user_prompt,
                system_prompt=full_prompt,
            )

            # 5. Parse LLM response
            try:
                decision_data = json.loads(llm_response.content)

                # Validate decision format
                if not self._validate_decision_format(decision_data):
                    raise ValueError("Invalid decision format from LLM")

                decision = Decision(
                    action_id=action.action_id,
                    source_agent=action.source_agent,
                    target_tool=action.target_tool,
                    decision=decision_data["decision"],
                    rationale=decision_data["rationale"],
                    severity=decision_data.get("severity"),
                    timestamp=datetime.utcnow(),
                )

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                # Fallback decision if LLM output is invalid
                logger.error(f"LLM output parsing failed: {e}")
                decision = Decision(
                    action_id=action.action_id,
                    source_agent=action.source_agent,
                    target_tool=action.target_tool,
                    decision="BLOCK",
                    rationale=f"Policy evaluation failed: {str(e)}",
                    severity="HIGH",
                    timestamp=datetime.utcnow(),
                )

            # 6. Early exit for BLOCK decisions
            if decision.decision == "BLOCK":
                await self._execute_block_action(action, decision)

            # 7. Log decision
            await self._log_decision(decision, action)

            # 8. Notify if needed
            if decision.decision in ["BLOCK", "FLAG"]:
                await self.notify_service.send_alert(decision, action)

            processing_time = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Action {action.action_id} processed in {processing_time}s: {decision.decision}"
            )

            return decision

        except Exception as e:
            logger.error(f"Error processing action {action.action_id}: {e}")
            # Create emergency decision
            return Decision(
                action_id=action.action_id,
                source_agent=action.source_agent,
                target_tool=action.target_tool,
                decision="BLOCK",
                rationale=f"System error: {str(e)}",
                severity="HIGH",
                timestamp=datetime.utcnow(),
            )

    async def _get_relevant_policies(self, target_tool: str) -> List[PolicyRule]:
        """
        Retrieve policies for target tool using regex matching.
        Optimized with hash map cache.
        """
        relevant: List[PolicyRule] = []

        # Check cache for matching regex patterns
        for regex_pattern, policies in self._policy_cache.items():
            try:
                if re.match(regex_pattern, target_tool):
                    relevant.extend(policies)
            except re.error:
                # If regex is invalid, do simple string match
                if regex_pattern in target_tool:
                    relevant.extend(policies)

        return relevant

    def _format_policies_for_prompt(self, policies: List[PolicyRule]) -> str:
        """Format policies for injection into prompt."""
        formatted: List[str] = []
        for policy in policies:
            formatted.append(
                f"- Rule ID: {policy.rule_id}\n"
                f"  Description: {policy.description}\n"
                f"  Target: {policy.target_tool_regex}\n"
                f"  Condition: {policy.condition_logic}\n"
                f"  Severity: {policy.severity}\n"
                f"  Action: {policy.action_on_violation}"
            )
        return "\n\n".join(formatted)

    async def _call_llm_with_retry(
        self,
        prompt: str,
        system_prompt: str,
    ) -> LLMResponse:
        """Call LLM with exponential backoff retry logic."""
        for attempt in range(self.max_retries):
            try:
                response = await self.llm_provider.invoke(
                    prompt=prompt,
                    system_prompt=system_prompt,
                )
                return response

            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise

                # Exponential backoff
                delay = self.base_delay * (2 ** attempt)
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}): {e}. Retrying in {delay}s"
                )
                await asyncio.sleep(delay)

    async def _execute_block_action(
        self,
        action: InterceptedAction,
        decision: Decision,
    ) -> None:
        """Execute block action - prevent tool execution."""
        # In production, this would call the actual blocking mechanism
        logger.warning(
            f"BLOCKED Action {action.action_id}: "
            f"{action.source_agent} -> {action.target_tool}. "
            f"Reason: {decision.rationale}"
        )

    async def _log_decision(
        self,
        decision: Decision,
        action: InterceptedAction,
    ) -> None:
        """Log decision to audit database."""
        await self.db_service.log_audit(
            action_id=decision.action_id,
            source_agent=decision.source_agent,
            target_tool=decision.target_tool,
            decision=decision.decision,
            rationale=decision.rationale,
            metadata={
                "tool_arguments": action.tool_arguments,
                "user_context": action.user_context,
                "severity": decision.severity,
            },
        )

    def _validate_decision_format(self, data: dict) -> bool:
        """Validate LLM decision output format."""
        required = ["decision", "rationale"]
        if not all(key in data for key in required):
            return False

        if data["decision"] not in ["ALLOW", "BLOCK", "FLAG"]:
            return False

        if "severity" in data and data["severity"] not in [
            "HIGH",
            "MEDIUM",
            "LOW",
            None,
        ]:
            return False

        return True

    async def analyze_policy(self, policy_text: str) -> Dict[str, Any]:
        """
        Policy Architect mode - Convert human policies to executable rules.
        """
        architect_prompt = """You are the Policy Architect for OrchestraGuard. Convert the following policy document into executable JSON rules.
Follow this schema for each rule:
{
  "policy_name": "string",
  "version": "1.0",
  "rules": [
    {
      "rule_id": "string (e.g., DP-001)",
      "description": "human-readable rule",
      "target_tool_regex": "string (e.g., 'SQL_DB_API.*')",
      "condition_logic": "python-evaluatable string",
      "severity": "HIGH|MEDIUM|LOW",
      "action_on_violation": "BLOCK|FLAG"
    }
  ]
}
Policy Document:
{policy_text}
Output ONLY valid JSON following the schema above.""".format(
            policy_text=policy_text
        )

        try:
            response = await self.llm_provider.invoke(
                prompt=policy_text,
                system_prompt=architect_prompt,
            )

            # Parse and validate the JSON
            policy_data = json.loads(response.content)

            # Validate against EPKB schema
            validated = EPKBSchema(**policy_data)

            # Save to database
            for rule in validated.rules:
                await self.db_service.create_policy(
                    name=validated.policy_name,
                    rule_id=rule.rule_id,
                    description=rule.description,
                    target_tool_regex=rule.target_tool_regex,
                    condition_logic=rule.condition_logic,
                    severity=rule.severity,
                    action_on_violation=rule.action_on_violation,
                )

            # Refresh cache
            await self._load_policies_to_cache()

            # For Pydantic v2 you can also use model_dump(), but dict() remains available.
            return validated.dict()

        except Exception as e:
            logger.error(f"Policy analysis failed: {e}")
            raise

    async def close(self) -> None:
        """Cleanup resources."""
        if self.llm_provider:
            await self.llm_provider.close()
        logger.info("ReasoningEngine shut down")