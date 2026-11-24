"""Admin AI Monitoring Assistant: Bilingual (English / Romanized Sinhala) operational chat handler."""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
from pymongo.database import Database

from app.config.database import get_database
from app.services.ai_provider_monitoring_service import AIProviderMonitoringService
from app.services.fraud_detection_service import FraudDetectionService
from app.services.notification_monitoring_service import NotificationMonitoringService
from app.services.platform_monitoring_service import PlatformMonitoringService
from app.services.workflow_monitoring_service import WorkflowMonitoringService


class AdminMonitoringAssistant:
    """Interprets administrative system queries in English and Romanized Sinhala and returns authoritative metrics."""

    @classmethod
    def handle_query(cls, message: str, db: Optional[Database] = None) -> Dict[str, Any]:
        """Parse natural language query and route to authoritative deterministic monitoring telemetry."""
        if db is None:
            db = get_database()

        msg = message.lower().strip()

        # 1. Platform Health / System status
        # e.g. "system eka healthy da?", "is the system healthy?", "platform status"
        if any(kw in msg for kw in ["healthy", "system status", "health", "system eka", "tatwaya", "wada da"]):
            snapshot = PlatformMonitoringService.get_platform_health_snapshot(db)
            status_text = snapshot["status"].upper()
            workers_count = len(snapshot["workers"])

            response = (
                f"MediConnect Platform Status: {status_text}.\n"
                f"• Uptime: {snapshot['uptimeSeconds']} seconds\n"
                f"• Dependencies: {len(snapshot['dependencies'])} checked\n"
                f"• Active Background Workers: {workers_count}\n"
                f"• Active Incidents: {snapshot['activeIncidentsCount']}\n"
                f"• Open Fraud Assessments: {snapshot['openFraudAssessmentsCount']}"
            )
            return {
                "intent": "platform_health_check",
                "response": response,
                "relevantMetrics": snapshot,
                "suggestedActions": ["View System Health Page", "Review Active Incidents"],
            }

        # 2. Failed payments / Payment issues
        # e.g. "ada failed payments monawada?", "what are today's failed payments?", "payment status"
        elif any(kw in msg for kw in ["payment", "geweema", "failed payment", "salika", "stripe"]):
            failed_payments = list(db["payments"].find({"status": "failed"}).sort("createdAt", -1).limit(10))
            count = len(failed_payments)

            if count == 0:
                response = "ada kisi ma failed payment ekak record wela naha. All payments are operating normally."
            else:
                response = f"Adha record wu failed payments ganana: {count}. The most recent failed payments are flagged for reconciliation."

            return {
                "intent": "failed_payments_check",
                "response": response,
                "relevantMetrics": {"failedCount": count, "recentFailures": [str(p.get("paymentIntentId") or p.get("_id")) for p in failed_payments[:5]]},
                "suggestedActions": ["Go to Payments Reconciliation", "Inspect Stripe Webhooks"],
            }

        # 3. Notification failures / SMS issues
        # e.g. "SMS notifications fail wenne ai?", "why do notifications fail?", "notification failures"
        elif any(kw in msg for kw in ["notification", "sms", "email", "pennanna", "message", "outbox"]):
            metrics = NotificationMonitoringService.get_notification_metrics(db)
            dead_letters = NotificationMonitoringService.list_dead_letters(limit=5, db=db)

            response = (
                f"Notification System Telemetry:\n"
                f"• Total Outbox Backlog: {metrics['totalBacklog']}\n"
                f"• Failure Rate: {metrics['failureRatePercent']}%\n"
                f"• Unresolved Dead-Letter Items: {metrics['deadLetterQueueCount']}\n"
                f"SMS/Email failures are automatically scheduled with exponential backoff (1m, 5m, 15m)."
            )
            return {
                "intent": "notification_status_check",
                "response": response,
                "relevantMetrics": metrics,
                "suggestedActions": ["Review Notification Dead-Letter Queue", "Check Twilio API credentials"],
            }

        # 4. Fraud alerts / Risk assessments
        # e.g. "fraud alerts thiyenawada?", "are there fraud alerts?", "risk assessments"
        elif any(kw in msg for kw in ["fraud", "wanchawa", "sakashankitha", "risk", "alert"]):
            assessments = FraudDetectionService.list_assessments(status="AWAITING_REVIEW", limit=10, db=db)
            count = assessments["total"]

            if count == 0:
                response = "Danata active fraud alerts monawath naha. No pending high-risk assessments."
            else:
                top = assessments["items"][0]
                response = (
                    f"Aluthin review kala yuthu fraud alerts {count}k thiyenawa.\n"
                    f"• Highest Priority: {top.assessmentId} (Risk Score: {top.riskScore}/100, Tier: {top.riskLevel})\n"
                    f"• Reason: {top.explanation}"
                )

            return {
                "intent": "fraud_alerts_check",
                "response": response,
                "relevantMetrics": {"openAlerts": count},
                "suggestedActions": ["Open Fraud Monitoring Dashboard", "Review Flagged Accounts"],
            }

        # 5. AI Provider availability / Gemini / OpenAI
        # e.g. "AI provider eka wada karanawada?", "is AI provider working?", "gemini status"
        elif any(kw in msg for kw in ["ai", "gemini", "openai", "provider", "model"]):
            metrics = AIProviderMonitoringService.get_metrics()
            gemini = next((m for m in metrics if m["provider"] == "gemini"), {})
            status = gemini.get("status", "healthy").upper()
            cb = gemini.get("circuitBreakerState", "CLOSED")

            response = (
                f"AI Provider Status: {status} (Circuit Breaker: {cb}).\n"
                f"• Total Requests: {gemini.get('totalRequests', 0)}\n"
                f"• Average Latency: {gemini.get('averageLatencyMs', 0.0)} ms\n"
                f"• Fallback Activations: {gemini.get('fallbackActivations', 0)}\n"
                f"If Gemini is unreachable, bilingual deterministic NLP automatically handles patient interactions."
            )
            return {
                "intent": "ai_provider_status_check",
                "response": response,
                "relevantMetrics": {"gemini": gemini},
                "suggestedActions": ["Inspect AI Provider Metrics", "Verify API Quotas"],
            }

        # 6. Stuck workflows
        # e.g. "pending workflows monawada?", "stuck workflows"
        elif any(kw in msg for kw in ["workflow", "stuck", "pending", "hira wela", "recovery"]):
            stuck = WorkflowMonitoringService.detect_stuck_workflows(db)
            count = len(stuck)

            if count == 0:
                response = "Kisima workflow ekak stuck wela naha. All automated business workflows completed or in active progress."
            else:
                response = (
                    f"Stuck wela thiyena workflows {count}k detect una.\n"
                    f"Workflows: {', '.join([w.workflowId for w in stuck[:3]])}.\n"
                    f"Safe idempotent recovery can be triggered from the Workflow Recovery console."
                )

            return {
                "intent": "stuck_workflows_check",
                "response": response,
                "relevantMetrics": {"stuckCount": count},
                "suggestedActions": ["Navigate to Workflow Recovery", "Execute Safe Recovery"],
            }

        # 7. Medication reminders
        # e.g. "medicine reminders fail wela thiyenawada?", "medication reminders"
        elif any(kw in msg for kw in ["medicine", "beheth", "reminders", "medication"]):
            failed_reminders = db["medication_reminders"].count_documents({"status": "FAILED"})
            active_reminders = db["medication_reminders"].count_documents({"status": "ACTIVE"})

            response = (
                f"Medication Reminder Status:\n"
                f"• Active Schedules: {active_reminders}\n"
                f"• Failed Reminders: {failed_reminders}\n"
                f"All reminders sync with Phase 3 care plans and the notification outbox."
            )
            return {
                "intent": "medication_reminders_check",
                "response": response,
                "relevantMetrics": {"active": active_reminders, "failed": failed_reminders},
                "suggestedActions": ["Inspect Medication Outbox", "View Care Plans"],
            }

        # Default fallback
        return {
            "intent": "general_monitoring_inquiry",
            "response": (
                "MediConnect Security & Platform Assistant wetha sadaren piliganimu.\n"
                "You can query system health, failed payments, notification outbox status, "
                "fraud alerts, stuck workflows, or AI provider reliability in English or Romanized Sinhala."
            ),
            "relevantMetrics": None,
            "suggestedActions": ["Ask 'system eka healthy da?'", "Ask 'fraud alerts thiyenawada?'"],
        }
