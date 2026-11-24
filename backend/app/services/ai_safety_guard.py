"""Central AI Safety & Permission Guard: Prompt injection screening, role permissions, and PII masking."""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.models.security_event import SecurityEventCategory, SecuritySeverity
from app.services.security_event_service import SecurityEventService


class AISafetyGuard:
    """Enforces zero-trust safety checks, prompt injection detection, and data minimization across AI workflows."""

    # Known prompt injection & adversarial override patterns
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
        re.compile(r"disregard\s+(all\s+)?(system|earlier)\s+prompts", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(a\s+)?(system\s+admin|administrator|root|developer|god\s+mode)", re.IGNORECASE),
        re.compile(r"system\s+override", re.IGNORECASE),
        re.compile(r"grant\s+(me\s+)?all\s+(permissions|roles)", re.IGNORECASE),
        re.compile(r"escalate\s+(my\s+)?role", re.IGNORECASE),
        re.compile(r"reveal\s+(your\s+)?(system\s+prompt|initial\s+instructions|secret\s+key)", re.IGNORECASE),
        re.compile(r"print\s+(your\s+)?(api_key|token|credentials)", re.IGNORECASE),
        re.compile(r"role\s*:\s*(admin|system|root)", re.IGNORECASE),
    ]

    # Regex patterns for sensitive tokens and keys
    SENSITIVE_PATTERNS = [
        (re.compile(r"Bearer\s+[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_=]*"), "Bearer [REDACTED_JWT]"),
        (re.compile(r"sk_test_[0-9a-zA-Z]{14,}"), "[REDACTED_STRIPE_SECRET]"),
        (re.compile(r"whsec_[0-9a-zA-Z]{20,}"), "[REDACTED_STRIPE_WEBHOOK]"),
        (re.compile(r"AIza[0-9A-Za-z-_]{30,}"), "[REDACTED_GOOGLE_API_KEY]"),
        (re.compile(r"sk-proj-[0-9a-zA-Z\-_]{30,}"), "[REDACTED_OPENAI_KEY]"),
    ]

    @classmethod
    def check_prompt_injection(
        cls,
        text: str,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Scan input text for adversarial prompt injection attempts. Logs security event if detected."""
        if not text:
            return False, None

        for pattern in cls.INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                reason = f"Adversarial prompt injection pattern detected: '{match.group(0)}'"
                SecurityEventService.record_security_event(
                    category=SecurityEventCategory.PROMPT_INJECTION,
                    severity=SecuritySeverity.HIGH,
                    description=reason,
                    actor_id=actor_id,
                    actor_role=actor_role,
                    endpoint=endpoint,
                    metadata={"pattern": pattern.pattern, "matchedSnippet": match.group(0)},
                )
                return True, reason

        return False, None

    @classmethod
    def validate_tool_call(
        cls,
        actor_role: str,
        actor_id: str,
        tool_name: str,
        tool_args: Dict[str, Any],
        authorized_tools: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """Strictly validate actor role permissions and resource ownership before executing any tool."""
        # 1. Tool availability
        if tool_name not in authorized_tools:
            SecurityEventService.record_security_event(
                category=SecurityEventCategory.UNAUTHORIZED_TOOL_CALL,
                severity=SecuritySeverity.MEDIUM,
                description=f"Attempted execution of unregistered tool '{tool_name}'",
                actor_id=actor_id,
                actor_role=actor_role,
                metadata={"toolName": tool_name},
            )
            return False, f"Tool '{tool_name}' does not exist or is not registered."

        tool_spec = authorized_tools[tool_name]
        allowed_roles = getattr(tool_spec, "roles", set())

        # 2. Role permission check
        if actor_role not in allowed_roles:
            SecurityEventService.record_security_event(
                category=SecurityEventCategory.UNAUTHORIZED_TOOL_CALL,
                severity=SecuritySeverity.HIGH,
                description=f"Role '{actor_role}' unauthorized to execute '{tool_name}'",
                actor_id=actor_id,
                actor_role=actor_role,
                metadata={"toolName": tool_name, "allowedRoles": list(allowed_roles)},
            )
            return False, f"Access Denied: Role '{actor_role}' is not authorized to invoke '{tool_name}'."

        # 3. Ownership enforcement for Patients
        if actor_role == "PATIENT":
            # If tool requires patient_id, it MUST strictly match actor_id
            target_patient_id = tool_args.get("patient_id") or tool_args.get("patientUserId")
            if target_patient_id and str(target_patient_id) != str(actor_id):
                SecurityEventService.record_security_event(
                    category=SecurityEventCategory.UNAUTHORIZED_ACCESS,
                    severity=SecuritySeverity.CRITICAL,
                    description=f"Patient {actor_id} attempted cross-patient record access for patient {target_patient_id}",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    metadata={"toolName": tool_name, "targetPatientId": target_patient_id},
                )
                return False, "Access Denied: You cannot view or modify another patient's medical information."

        return True, None

    @classmethod
    def sanitize_sensitive_content(cls, content: str) -> str:
        """Redact tokens, credentials, and API secrets from logs and outbound responses."""
        if not isinstance(content, str):
            return content

        sanitized = content
        for pattern, replacement in cls.SENSITIVE_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    @classmethod
    def enforce_execution_limits(cls, iteration_count: int, max_iterations: int = 5) -> bool:
        """Prevent runaway orchestration loops by capping tool call iterations."""
        return iteration_count <= max_iterations
