"""
ENHANCED: Reasoning Engine with active policy fetching and immediate notification on BLOCK
"""

import asyncio
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict
import logging

from backend.core.factory import LLMFactory
from backend.schemas.models import (
    InterceptedAction,
    Decision,
    PolicyRule,
    EPKBSchema,
    DecisionEnum,
    SeverityEnum,
)
from backend.services.db import DatabaseService
from backend.services.notify import NotificationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReasoningEngine:
    """
    Enhanced Reasoning Engine with:
    1. Active policy fetching from database
    2. Immediate notification on BLOCK decisions
    3. Comprehensive caching and conflict resolution
    """

    def __init__(self):
        self.llm_provider = None
        self.db_service: Optional[DatabaseService] = None
        self.notify_service: Optional[NotificationService] = None

        # Cache for policies with TTL
        self._policy_cache: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 60  # Cache policies for 60 seconds

        # Decision statistics
        self._decision_stats = {
            "total": 0,
            "allow": 0,
            "block": 0,
            "flag": 0,
        }

        # Master System Prompt
        self.master_prompt = """You are the Ethical Reasoner for OrchestraGuard. Your job is to evaluate intercepted agent actions against enterprise policies.

CRITICAL RULES:
1. NEVER allow an action that violates a rule in the EPKB.
2. NEVER use external knowledge or common sense; rely only on the EPKB rule.
3. ALWAYS provide a clear rationale for your decision.
4. PRIORITY: Security and Compliance override Efficiency. When in doubt, Block.
5. OUTPUT FORMAT: Your final response MUST be a single, valid JSON object.

CORE LOGIC FLOW:
1. RECEIVE INTERCEPTION: Analyze the intercepted action JSON.
2. RETRIEVE POLICY: Apply relevant policy rules for the target_tool.
3. REASON & EVALUATE: Compare tool_arguments and user_context against rules.
4. DECIDE: Determine if action is compliant (ALLOW/BLOCK/FLAG).
5. LOG: Record decision with rationale and severity.

POLICY RULES TO APPLY:
{policy_rules}

OUTPUT JSON FORMAT:
{{
  "decision": "ALLOW|BLOCK|FLAG",
  "rationale": "concise explanation of why this decision was made",
  "severity": "HIGH|MEDIUM|LOW|null",
  "applied_rules": ["rule_id_1", "rule_id_2"]
}}

Remember: When a rule is violated, you MUST set decision to the rule's action_on_violation."""

    async def initialize(self) -> None:
        """Initialize engine with dependencies and load policies."""
        self.llm_provider = await LLMFactory.get_provider()
        self.db_service = DatabaseService.get_instance()
        self.notify_service = NotificationService.get_instance()

        # Load active policies on initialization
        await self._load_active_policies()
        logger.info("Enhanced ReasoningEngine initialized")

    async def _load_active_policies(self) -> None:
        """Load active policies from database into cache."""
        try:
            policies = await self.db_service.get_active_policies()

            # Clear cache
            self._policy_cache.clear()

            # Organize policies by target tool regex
            for policy in policies:
                if policy.get("is_active", False):
                    rules = policy.get("rules", {})
                    target_regex = rules.get("target_tool_regex", "")

                    if target_regex:
                        try:
                            rule_obj = PolicyRule(
                                rule_id=rules.get("rule_id", ""),
                                description=rules.get("description", ""),
                                target_tool_regex=target_regex,
                                condition_logic=rules.get("condition_logic", ""),
                                severity=rules.get("severity", "MEDIUM"),
                                action_on_violation=rules.get(
                                    "action_on_violation", "BLOCK"
                                ),
                            )
                            self._policy_cache[target_regex].append(
                                {
                                    "policy_id": policy.get("id"),
                                    "policy_name": policy.get("name"),
                                    "rule": rule_obj,
                                }
                            )
                        except Exception as e:
                            logger.warning(f"Skipping invalid policy rule: {e}")

            self._cache_timestamp = datetime.utcnow()
            logger.info(f"Loaded {len(policies)} active policies into cache")

        except Exception as e:
            logger.error(f"Failed to load active policies: {e}")
            # Keep existing cache if available

    async def _ensure_fresh_policies(self) -> None:
        """Ensure policy cache is fresh (within TTL)."""
        if (
            self._cache_timestamp is None
            or (datetime.utcnow() - self._cache_timestamp).seconds > self._cache_ttl
        ):
            await self._load_active_policies()

    async def process_action(self, action: InterceptedAction) -> Decision:
        """
        Process intercepted action with enhanced logic:
        1. Fetch active policies from database
        2. Make decision using LLM
        3. Immediately notify on BLOCK decisions
        4. Update statistics
        """
        start_time = datetime.utcnow()

        try:
            # 1. Ensure we have fresh policies
            await self._ensure_fresh_policies()

            # 2. Retrieve relevant policies
            relevant_rules = await self._get_relevant_policies(action.target_tool)

            if not relevant_rules:
                # No policies exist for this tool - default to ALLOW with logging
                decision = Decision(
                    action_id=action.action_id,
                    source_agent=action.source_agent,
                    target_tool=action.target_tool,
                    decision=DecisionEnum.ALLOW,
                    rationale="No active policies defined for this tool",
                    severity=None,
                    applied_rules=[],
                    timestamp=datetime.utcnow(),
                )
                await self._log_decision(decision, action)
                self._update_stats(decision)
                return decision

            # 3. Construct dynamic prompt with injected rules
            policy_text = self._format_policies_for_prompt(relevant_rules)
            full_prompt = self.master_prompt.format(policy_rules=policy_text)

            # 4. Prepare action context for LLM
            action_context = {
                "action_id": action.action_id,
                "source_agent": action.source_agent,
                "target_tool": action.target_tool,
                "tool_arguments": action.tool_arguments,
                "user_context": action.user_context or {},
                "timestamp": action.timestamp.isoformat()
                if action.timestamp
                else datetime.utcnow().isoformat(),
            }

            user_prompt = (
                "Evaluate this intercepted action against the provided policies:\n\n"
                "```json\n"
                f"{json.dumps(action_context, indent=2)}\n"
                "```\n"
                "Provide your decision in the required JSON format."
            )

            # 5. Call LLM with retry logic
            llm_response = await self._call_llm_with_retry(
                prompt=user_prompt,
                system_prompt=full_prompt,
            )

            # 6. Parse LLM response
            decision_data = self._parse_llm_response(
                llm_response, action, relevant_rules
            )

            # 7. Immediate notification for BLOCK decisions
            if decision_data.decision == DecisionEnum.BLOCK:
                await self._immediate_block_notification(decision_data, action)

            # 8. Log decision
            await self._log_decision(decision_data, action)

            # 9. Update statistics
            self._update_stats(decision_data)

            processing_time = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Action {action.action_id} processed in {processing_time:.2f}s: "
                f"{decision_data.decision}"
            )

            return decision_data

        except Exception as e:
            logger.error(f"Error processing action {action.action_id}: {e}")
            # Create emergency BLOCK decision
            emergency_decision = Decision(
                action_id=action.action_id,
                source_agent=action.source_agent,
                target_tool=action.target_tool,
                decision=DecisionEnum.BLOCK,
                rationale=f"System error in policy evaluation: {str(e)}",
                severity=SeverityEnum.HIGH,
                applied_rules=["SYSTEM-ERROR"],
                timestamp=datetime.utcnow(),
            )

            # Notify about system error
            await self._immediate_block_notification(emergency_decision, action)
            await self._log_decision(emergency_decision, action)

            return emergency_decision

    async def _immediate_block_notification(
        self, decision: Decision, action: InterceptedAction
    ) -> None:
        """
        IMMEDIATE notification for BLOCK decisions.
        This runs synchronously to ensure notification is sent before response.
        """
        try:
            notification_payload = {
                "type": "BLOCK_ALERT",
                "decision": decision.dict(),
                "action": action.dict(),
                "timestamp": datetime.utcnow().isoformat(),
                "urgency": "HIGH",
            }

            # Send immediate notification (not async fire-and-forget)
            await self.notify_service.send_immediate_alert(notification_payload)

            logger.warning(f"🚨 BLOCK notification sent for action {decision.action_id}")

        except Exception as e:
            logger.error(f"Failed to send BLOCK notification: {e}")
            # Don't raise - notification failure shouldn't break the flow

    async def _get_relevant_policies(self, target_tool: str) -> List[Dict[str, Any]]:
        """
        Retrieve policies for target tool using regex matching.
        Returns list of policy rules with their metadata.
        """
        relevant: List[Dict[str, Any]] = []

        # Check cache for matching regex patterns
        for regex_pattern, policy_entries in self._policy_cache.items():
            try:
                if re.match(regex_pattern, target_tool):
                    relevant.extend(policy_entries)
            except re.error:
                # If regex is invalid, do simple string match
                if regex_pattern in target_tool:
                    relevant.extend(policy_entries)

        return relevant

    def _format_policies_for_prompt(self, policies: List[Dict[str, Any]]) -> str:
        """Format policies for injection into prompt."""
        formatted: List[str] = []
        for policy_entry in policies:
            rule: PolicyRule = policy_entry["rule"]
            formatted.append(
                f"Rule ID: {rule.rule_id}\n"
                f"Policy: {policy_entry['policy_name']}\n"
                f"Description: {rule.description}\n"
                f"Target Tool Pattern: {rule.target_tool_regex}\n"
                f"Condition: {rule.condition_logic}\n"
                f"Severity: {rule.severity}\n"
                f"Action on Violation: {rule.action_on_violation}\n"
            )
        return "\n---\n".join(formatted)

    def _parse_llm_response(
        self,
        llm_response: Any,
        action: InterceptedAction,
        relevant_rules: List[Dict[str, Any]],
    ) -> Decision:
        """Parse and validate LLM response."""
        try:
            decision_data = json.loads(llm_response.content)

            # Validate decision format
            if not self._validate_decision_format(decision_data):
                raise ValueError("Invalid decision format from LLM")

            # Extract applied rules
            applied_rules = decision_data.get("applied_rules", [])
            if not applied_rules:
                applied_rules = [entry["rule"].rule_id for entry in relevant_rules]

            decision = Decision(
                action_id=action.action_id,
                source_agent=action.source_agent,
                target_tool=action.target_tool,
                decision=decision_data["decision"],
                rationale=decision_data["rationale"],
                severity=decision_data.get("severity"),
                applied_rules=applied_rules,
                timestamp=datetime.utcnow(),
            )

            return decision

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(
                f"LLM output parsing failed: {e}, Content: {llm_response.content}"
            )

            # Default to BLOCK for safety
            return Decision(
                action_id=action.action_id,
                source_agent=action.source_agent,
                target_tool=action.target_tool,
                decision=DecisionEnum.BLOCK,
                rationale=f"Failed to parse LLM response: {str(e)}",
                severity=SeverityEnum.HIGH,
                applied_rules=["PARSE-ERROR"],
                timestamp=datetime.utcnow(),
            )

    def _validate_decision_format(self, data: dict) -> bool:
        """Validate LLM decision output format."""
        required = ["decision", "rationale"]
        if not all(key in data for key in required):
            return False

        try:
            DecisionEnum(data["decision"])
        except ValueError:
            return False

        if "severity" in data and data["severity"] is not None:
            try:
                SeverityEnum(data["severity"])
            except ValueError:
                return False

        return True

    async def _call_llm_with_retry(
        self,
        prompt: str,
        system_prompt: str,
    ) -> Any:
        """Call LLM with exponential backoff retry logic."""
        for attempt in range(3):
            try:
                response = await self.llm_provider.invoke(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.1,  # Low temperature for consistent decisions
                )
                return response

            except Exception as e:
                if attempt == 2:
                    raise Exception(f"LLM call failed after 3 attempts: {e}")

                delay = 1.0 * (2**attempt)
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}): {e}. "
                    f"Retrying in {delay}s"
                )
                await asyncio.sleep(delay)

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
            decision=decision.decision.value,
            rationale=decision.rationale,
            metadata={
                "tool_arguments": action.tool_arguments,
                "user_context": action.user_context,
                "severity": decision.severity.value
                if decision.severity
                else None,
                "processing_time_ms": int(
                    (datetime.utcnow() - decision.timestamp).total_seconds() * 1000
                ),
            },
            applied_rules=decision.applied_rules,
        )

    def _update_stats(self, decision: Decision) -> None:
        """Update decision statistics."""
        self._decision_stats["total"] += 1

        if decision.decision == DecisionEnum.ALLOW:
            self._decision_stats["allow"] += 1
        elif decision.decision == DecisionEnum.BLOCK:
            self._decision_stats["block"] += 1
        elif decision.decision == DecisionEnum.FLAG:
            self._decision_stats["flag"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get current decision statistics."""
        total = self._decision_stats["total"]
        return {
            "total_decisions": total,
            "allow_count": self._decision_stats["allow"],
            "block_count": self._decision_stats["block"],
            "flag_count": self._decision_stats["flag"],
            "allow_rate": self._decision_stats["allow"] / total if total > 0 else 0,
            "block_rate": self._decision_stats["block"] / total if total > 0 else 0,
            "flag_rate": self._decision_stats["flag"] / total if total > 0 else 0,
            "cache_timestamp": self._cache_timestamp.isoformat()
            if self._cache_timestamp
            else None,
            "cache_size": len(self._policy_cache),
        }

    async def close(self) -> None:
        """Cleanup resources."""
        if self.llm_provider:
            await self.llm_provider.close()

        logger.info(f"ReasoningEngine shutdown. Final stats: {self.get_stats()}")