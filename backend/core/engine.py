"""
FIXED: Complete ReasoningEngine with proper policy parsing and LLM retry logic
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
    4. Improved applied rules logic and JSON parsing
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

        # Master System Prompt with strict applied rules requirement
        self.master_prompt = """You are the Ethical Reasoner for OrchestraGuard. Your job is to evaluate intercepted agent actions against enterprise policies.

CRITICAL RULES:
1. **NEVER** allow an action that violates a rule in the EPKB.
2. **NEVER** use external knowledge or common sense; rely only on the EPKB rule.
3. **MUST SPECIFY APPLIED RULES**: You MUST explicitly list which rules were applied in your decision.
4. **PRIORITY**: Security and Compliance override Efficiency. When in doubt, Block.
5. **OUTPUT FORMAT**: Your final response MUST be a single, valid JSON object.

CORE LOGIC FLOW:
1. **RECEIVE INTERCEPTION**: Analyze the intercepted action JSON.
2. **RETRIEVE POLICY**: Apply relevant policy rules for the target_tool.
3. **REASON & EVALUATE**: Compare tool_arguments and user_context against rules.
4. **DECIDE**: Determine if action is compliant (ALLOW/BLOCK/FLAG).
5. **SPECIFY RULES**: List the specific rule IDs that were applied.
6. **LOG**: Record decision with rationale and severity.

IMPORTANT: If the action is ALLOWED, you must still specify which rules were evaluated (even if none were violated).

POLICY RULES TO APPLY:
{policy_rules}

OUTPUT JSON FORMAT:
{{
  "decision": "ALLOW|BLOCK|FLAG",
  "rationale": "concise explanation of why this decision was made",
  "severity": "HIGH|MEDIUM|LOW|null",
  "applied_rules": ["rule_id_1", "rule_id_2"]  // LIST OF SPECIFIC RULE IDs THAT WERE APPLIED
}}"""

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
        """
        FIXED: Improved LLM response parsing with better applied rules logic
        """
        try:
            content = llm_response.content.strip()

            # Try to extract JSON using improved heuristics
            json_content = self._extract_json_from_response(content)

            if not json_content:
                logger.error(f"Could not extract JSON from LLM response: {content[:200]}...")
                raise ValueError("No JSON found in LLM response")

            decision_data = json.loads(json_content)

            # Validate decision format
            if not self._validate_decision_format(decision_data):
                raise ValueError("Invalid decision format from LLM")

            # FIXED: Improved applied rules logic
            applied_rules = self._determine_applied_rules(decision_data, relevant_rules)

            # Parse severity
            severity = None
            if "severity" in decision_data and decision_data["severity"]:
                try:
                    severity = SeverityEnum(decision_data["severity"].upper())
                except ValueError:
                    logger.warning(f"Invalid severity value: {decision_data['severity']}")

            decision = Decision(
                action_id=action.action_id,
                source_agent=action.source_agent,
                target_tool=action.target_tool,
                decision=DecisionEnum(decision_data["decision"].upper()),
                rationale=decision_data["rationale"][:1000],
                severity=severity,
                applied_rules=applied_rules,
                timestamp=datetime.utcnow()
            )

            return decision

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return self._create_error_decision(action, f"JSON parsing error: {str(e)}")
        except (KeyError, ValueError) as e:
            logger.error(f"LLM output validation failed: {e}")
            return self._create_error_decision(action, f"LLM output validation failed: {str(e)}")

    def _extract_json_from_response(self, content: str) -> Optional[str]:
        """
        FIXED: Improved JSON extraction with multiple strategies
        """
        strategies = [
            # Strategy 1: Look for complete JSON object
            lambda: self._extract_complete_json(content),
            # Strategy 2: Look for JSON between markers
            lambda: self._extract_json_between_markers(content, "```json", "```"),
            lambda: self._extract_json_between_markers(content, "```", "```"),
            # Strategy 3: Look for JSON after key phrases
            lambda: self._extract_json_after_phrase(content, "Output:"),
            lambda: self._extract_json_after_phrase(content, "Decision:"),
            # Strategy 4: Try to find any JSON-like structure
            lambda: self._find_json_like_structure(content)
        ]

        for strategy in strategies:
            result = strategy()
            if result:
                logger.debug(f"Successfully extracted JSON using strategy: {strategy.__name__}")
                return result

        return None

    def _extract_complete_json(self, content: str) -> Optional[str]:
        """Extract a complete JSON object from content"""
        # Look for JSON object at the beginning
        if content.startswith('{'):
            # Find matching closing brace
            stack = []
            for i, char in enumerate(content):
                if char == '{':
                    stack.append('{')
                elif char == '}':
                    if stack:
                        stack.pop()
                        if not stack:
                            return content[:i+1]
        return None

    def _extract_json_between_markers(self, content: str, start_marker: str, end_marker: str) -> Optional[str]:
        """Extract JSON between markers"""
        start_idx = content.find(start_marker)
        if start_idx == -1:
            return None

        start_idx += len(start_marker)
        end_idx = content.find(end_marker, start_idx)

        if end_idx == -1:
            return None

        return content[start_idx:end_idx].strip()

    def _extract_json_after_phrase(self, content: str, phrase: str) -> Optional[str]:
        """Extract JSON after a specific phrase"""
        phrase_idx = content.find(phrase)
        if phrase_idx == -1:
            return None

        # Look for JSON after the phrase
        substr = content[phrase_idx + len(phrase):]
        return self._extract_complete_json(substr.strip())

    def _find_json_like_structure(self, content: str) -> Optional[str]:
        """Find JSON-like structure using regex"""
        # Look for something that looks like a JSON object
        pattern = r'\{[^{}]*\{[^{}]*\}[^{}]*\}|\{[^{}]*\}'
        matches = re.findall(pattern, content, re.DOTALL)

        for match in matches:
            try:
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue

        return None

    def _determine_applied_rules(
        self,
        decision_data: Dict,
        relevant_rules: List[Dict]
    ) -> List[str]:
        """
        FIXED: Intelligent applied rules determination
        """
        # If LLM provided applied_rules, use them
        if "applied_rules" in decision_data and isinstance(decision_data["applied_rules"], list):
            provided_rules = [str(rule).upper() for rule in decision_data["applied_rules"]]

            # Validate that provided rules exist in relevant rules
            relevant_rule_ids = [rule_entry["rule"].rule_id for rule_entry in relevant_rules]
            valid_rules = [rule for rule in provided_rules if rule in relevant_rule_ids]

            if valid_rules:
                logger.info(f"LLM provided applied rules: {valid_rules}")
                return valid_rules
            else:
                logger.warning("LLM provided applied rules, but none matched relevant rules")

        # Determine applied rules based on decision
        decision = decision_data.get("decision", "").upper()

        if decision == "ALLOW":
            # For ALLOW decisions, include rules that were evaluated but not violated
            # This is less critical, so we can be conservative
            rule_ids = [rule_entry["rule"].rule_id for rule_entry in relevant_rules]
            if rule_ids:
                logger.info(f"ALLOW decision: including evaluated rules: {rule_ids}")
                return rule_ids
            else:
                return []

        elif decision in ["BLOCK", "FLAG"]:
            # For BLOCK/FLAG decisions, we need to identify which rules were violated
            rationale = decision_data.get("rationale", "").lower()
            applied_rules = []

            # Try to extract rule IDs from rationale
            for rule_entry in relevant_rules:
                rule_id = rule_entry["rule"].rule_id
                # Check if rule ID is mentioned in rationale
                if rule_id.lower() in rationale or rule_entry["rule"].description.lower() in rationale:
                    applied_rules.append(rule_id)

            # If no rules found in rationale, use all relevant rules as fallback
            if not applied_rules:
                logger.warning(f"{decision} decision: no rules found in rationale, using all relevant rules")
                applied_rules = [rule_entry["rule"].rule_id for rule_entry in relevant_rules]

            logger.info(f"{decision} decision: determined applied rules: {applied_rules}")
            return applied_rules

        else:
            logger.error(f"Unknown decision type: {decision}")
            return []

    def _create_error_decision(self, action: InterceptedAction, error_message: str) -> Decision:
        """Create an error decision when parsing fails"""
        logger.error(f"Creating error decision: {error_message}")

        return Decision(
            action_id=action.action_id,
            source_agent=action.source_agent,
            target_tool=action.target_tool,
            decision=DecisionEnum.BLOCK,
            rationale=f"System error: {error_message}",
            severity=SeverityEnum.HIGH,
            applied_rules=["SYSTEM-ERROR"],
            timestamp=datetime.utcnow()
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