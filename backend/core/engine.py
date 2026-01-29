"""
FIXED: Complete ReasoningEngine with proper policy parsing and LLM retry logic
"""

import asyncio
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict
import logging

from backend.core.factory import LLMFactory, LLMResponse
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
    Complete Reasoning Engine with:
    1. Proper policy parsing from database
    2. Complete LLM retry logic
    3. Immediate notification on BLOCK decisions
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
        logger.info("✅ Enhanced ReasoningEngine initialized")

    async def _load_active_policies(self) -> None:
        """FIXED: Properly load active policies from database."""
        try:
            policies = await self.db_service.get_active_policies()

            # Clear cache
            self._policy_cache.clear()

            logger.info(f"Processing {len(policies)} active policies")

            # FIXED: Proper policy parsing
            for policy in policies:
                if not policy.get("is_active", False):
                    continue

                # Extract rule data - the rules are stored as JSONB
                rules_data = policy.get("rules", {})

                # Handle both direct rule dict and nested structure
                if isinstance(rules_data, dict):
                    try:
                        rule_obj = PolicyRule(
                            rule_id=rules_data.get("rule_id", f"rule_{policy['id']}"),
                            description=rules_data.get(
                                "description", "No description"
                            ),
                            target_tool_regex=rules_data.get(
                                "target_tool_regex", ".*"
                            ),
                            condition_logic=rules_data.get("condition_logic", "True"),
                            severity=rules_data.get("severity", "MEDIUM"),
                            action_on_violation=rules_data.get(
                                "action_on_violation", "BLOCK"
                            ),
                        )

                        target_regex = rule_obj.target_tool_regex
                        self._policy_cache[target_regex].append(
                            {
                                "policy_id": policy.get("id"),
                                "policy_name": policy.get("name", "Unnamed Policy"),
                                "rule": rule_obj,
                            }
                        )

                        logger.debug(
                            f"Loaded rule: {rule_obj.rule_id} for {target_regex}"
                        )

                    except Exception as e:
                        logger.warning(
                            f"Skipping invalid policy {policy.get('id')}: {e}"
                        )

            self._cache_timestamp = datetime.utcnow()
            logger.info(
                f"Loaded {sum(len(rules) for rules in self._policy_cache.values())} "
                f"rules into cache"
            )

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
        """Process intercepted action with complete logic."""
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
                prompt=user_prompt, system_prompt=full_prompt
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

    async def _call_llm_with_retry(
        self,
        prompt: str,
        system_prompt: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> LLMResponse:
        """FIXED: Complete LLM retry logic with exponential backoff."""
        last_error = None

        for attempt in range(max_retries):
            try:
                logger.debug(f"LLM call attempt {attempt + 1}/{max_retries}")
                response = await self.llm_provider.invoke(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.1,  # Low temperature for consistent decisions
                )

                # Validate response has content
                if not response.content:
                    raise ValueError("LLM returned empty response")

                logger.debug(f"LLM call successful on attempt {attempt + 1}")
                return response

            except Exception as e:
                last_error = e
                logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")

                if attempt == max_retries - 1:
                    logger.error(f"LLM call failed after {max_retries} attempts")
                    raise Exception(
                        f"LLM call failed after {max_retries} attempts: {str(e)}"
                    )

                # Exponential backoff
                delay = base_delay * (2**attempt)
                logger.info(f"Retrying LLM call in {delay:.1f} seconds...")
                await asyncio.sleep(delay)

        # This should never be reached due to raise above
        raise Exception(f"LLM call failed: {str(last_error)}")

    def _parse_llm_response(
        self,
        llm_response: LLMResponse,
        action: InterceptedAction,
        relevant_rules: List[Dict],
    ) -> Decision:
        """Parse and validate LLM response with comprehensive error handling."""
        try:
            # Try to parse JSON
            content = llm_response.content.strip()

            # Clean up markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]

            if content.endswith("```"):
                content = content[:-3]

            content = content.strip()

            decision_data = json.loads(content)

            # Validate decision format
            if not self._validate_decision_format(decision_data):
                raise ValueError("Invalid decision format from LLM")

            # Extract applied rules
            applied_rules = decision_data.get("applied_rules", [])
            if not applied_rules:
                # Try to infer from relevant rules if LLM didn't specify
                applied_rules = [
                    rule_entry["rule"].rule_id for rule_entry in relevant_rules
                ]

            # Parse severity
            severity = None
            if "severity" in decision_data and decision_data["severity"]:
                try:
                    severity = SeverityEnum(decision_data["severity"].upper())
                except ValueError:
                    logger.warning(
                        f"Invalid severity value: {decision_data['severity']}"
                    )

            decision = Decision(
                action_id=action.action_id,
                source_agent=action.source_agent,
                target_tool=action.target_tool,
                decision=DecisionEnum(decision_data["decision"].upper()),
                rationale=decision_data["rationale"][:1000],  # Truncate if too long
                severity=severity,
                applied_rules=applied_rules,
                timestamp=datetime.utcnow(),
            )

            logger.debug(
                f"Parsed decision: {decision.decision} with {len(applied_rules)} applied rules"
            )
            return decision

        except json.JSONDecodeError as e:
            logger.error(f"LLM output is not valid JSON: {e}")
            logger.error(f"LLM output was: {llm_response.content}")

            # Try to extract JSON from malformed response
            json_match = re.search(r"\{.*\}", llm_response.content, re.DOTALL)
            if json_match:
                try:
                    decision_data = json.loads(json_match.group())
                    if self._validate_decision_format(decision_data):
                        # Use the extracted JSON
                        return self._parse_llm_response(
                            LLMResponse(
                                content=json.dumps(decision_data),
                                tool_calls=None,
                                finish_reason=None,
                            ),
                            action,
                            relevant_rules,
                        )
                except:
                    pass

            # Default to BLOCK for safety
            return Decision(
                action_id=action.action_id,
                source_agent=action.source_agent,
                target_tool=action.target_tool,
                decision=DecisionEnum.BLOCK,
                rationale=f"Failed to parse LLM response as JSON: {str(e)}",
                severity=SeverityEnum.HIGH,
                applied_rules=["PARSE-ERROR"],
                timestamp=datetime.utcnow(),
            )
        except (KeyError, ValueError) as e:
            logger.error(f"LLM output parsing failed: {e}")
            logger.error(f"LLM output was: {llm_response.content}")

            # Default to BLOCK for safety
            return Decision(
                action_id=action.action_id,
                source_agent=action.source_agent,
                target_tool=action.target_tool,
                decision=DecisionEnum.BLOCK,
                rationale=f"LLM output validation failed: {str(e)}",
                severity=SeverityEnum.HIGH,
                applied_rules=["VALIDATION-ERROR"],
                timestamp=datetime.utcnow(),
            )

    def _validate_decision_format(self, data: dict) -> bool:
        """Validate LLM decision output format."""
        try:
            # Check required fields
            if "decision" not in data or "rationale" not in data:
                return False

            # Validate decision enum
            DecisionEnum(data["decision"].upper())

            # Validate severity if present
            if "severity" in data and data["severity"] is not None:
                SeverityEnum(data["severity"].upper())

            # Validate applied_rules if present
            if "applied_rules" in data and not isinstance(
                data["applied_rules"], list
            ):
                return False

            return True

        except (ValueError, KeyError):
            return False

    async def _get_relevant_policies(self, target_tool: str) -> List[Dict[str, Any]]:
        """Retrieve policies for target tool using regex matching."""
        relevant: List[Dict[str, Any]] = []

        # Check cache for matching regex patterns
        for regex_pattern, policy_entries in self._policy_cache.items():
            try:
                # Compile regex and check match
                pattern = re.compile(regex_pattern)
                if pattern.match(target_tool):
                    relevant.extend(policy_entries)
                    logger.debug(
                        f"Matched tool '{target_tool}' with pattern '{regex_pattern}'"
                    )
            except re.error as e:
                # If regex is invalid, do simple string match
                logger.warning(f"Invalid regex pattern '{regex_pattern}': {e}")
                if regex_pattern in target_tool:
                    relevant.extend(policy_entries)
                    logger.debug(
                        f"Matched tool '{target_tool}' with substring '{regex_pattern}'"
                    )

        logger.debug(f"Found {len(relevant)} relevant rules for tool '{target_tool}'")
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

    async def _immediate_block_notification(
        self, decision: Decision, action: InterceptedAction
    ) -> None:
        """IMMEDIATE notification for BLOCK decisions."""
        try:
            notification_payload = {
                "type": "BLOCK_ALERT",
                "decision": decision.dict(),
                "action": action.dict(),
                "timestamp": datetime.utcnow().isoformat(),
                "urgency": "HIGH",
            }

            # Send immediate notification
            await self.notify_service.send_immediate_alert(notification_payload)

            logger.warning(f"🚨 BLOCK notification sent for action {decision.action_id}")

        except Exception as e:
            logger.error(f"Failed to send BLOCK notification: {e}")
            # Don't raise - notification failure shouldn't break the flow

    async def _log_decision(
        self, decision: Decision, action: InterceptedAction
    ) -> None:
        """Log decision to audit database."""
        try:
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
            logger.debug(f"Logged decision for action {decision.action_id}")
        except Exception as e:
            logger.error(f"Failed to log decision: {e}")

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