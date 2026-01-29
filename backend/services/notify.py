"""
FIXED: Notification Service with async webhook calls
"""

import asyncio
import httpx
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import json
from enum import Enum
from threading import Lock
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Notification types."""

    BLOCK_ALERT = "block_alert"
    FLAG_ALERT = "flag_alert"
    SYSTEM_ALERT = "system_alert"
    POLICY_UPDATE = "policy_update"
    SECURITY_BREACH = "security_breach"


class NotificationService:
    """
    Enhanced Notification Service with async webhook calls.
    Uses asyncio.create_task for non-blocking notifications.
    """

    _instance: Optional["NotificationService"] = None
    _lock = Lock()

    def __init__(self):
        if NotificationService._instance is not None:
            raise Exception("NotificationService is a singleton!")

        self.webhook_urls: Dict[NotificationType, List[str]] = {
            NotificationType.BLOCK_ALERT: [],
            NotificationType.FLAG_ALERT: [],
            NotificationType.SYSTEM_ALERT: [],
            NotificationType.POLICY_UPDATE: [],
            NotificationType.SECURITY_BREACH: [],
        }

        self.http_client: Optional[httpx.AsyncClient] = None
        self._pending_tasks: Set[asyncio.Task] = set()
        self._initialize_http_client()

    @staticmethod
    def get_instance() -> "NotificationService":
        """Get singleton instance."""
        if NotificationService._instance is None:
            with NotificationService._lock:
                if NotificationService._instance is None:
                    NotificationService._instance = NotificationService()
        return NotificationService._instance

    def _initialize_http_client(self) -> None:
        """Initialize HTTP client with connection pooling."""
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            follow_redirects=True,
        )

    def register_webhook(self, notification_type: NotificationType, url: str) -> None:
        """Register webhook URL for specific notification type."""
        if url not in self.webhook_urls[notification_type]:
            self.webhook_urls[notification_type].append(url)
            logger.info(f"Registered webhook for {notification_type.value}: {url}")

    def unregister_webhook(self, notification_type: NotificationType, url: str) -> None:
        """Unregister webhook URL."""
        if url in self.webhook_urls[notification_type]:
            self.webhook_urls[notification_type].remove(url)
            logger.info(f"Unregistered webhook for {notification_type.value}: {url}")

    async def send_alert(self, decision: Dict, action: Dict) -> None:
        """
        Send alert notification based on decision.
        Uses asyncio.create_task for non-blocking async calls.
        """
        notification_type = None

        if decision.get("decision") == "BLOCK":
            notification_type = NotificationType.BLOCK_ALERT
        elif decision.get("decision") == "FLAG":
            notification_type = NotificationType.FLAG_ALERT

        if notification_type:
            # Create async task for non-blocking notification
            task = asyncio.create_task(
                self._send_webhook_notification_async(
                    notification_type=notification_type,
                    payload={
                        "decision": decision,
                        "action": action,
                        "timestamp": datetime.utcnow().isoformat(),
                        "severity": decision.get("severity", "MEDIUM"),
                        "urgency": "HIGH"
                        if notification_type == NotificationType.BLOCK_ALERT
                        else "MEDIUM",
                    },
                )
            )

            # Track the task
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)

            logger.info(
                f"Created async notification task for {notification_type.value}"
            )

    async def send_immediate_alert(self, payload: Dict[str, Any]) -> None:
        """
        Send immediate alert (synchronous, waits for completion).
        Used for critical BLOCK notifications that must complete before response.
        """
        try:
            notification_type = NotificationType(payload.get("type", "block_alert"))

            # Send immediately (not async)
            await self._send_webhook_notification_sync(
                notification_type=notification_type, payload=payload
            )

        except Exception as e:
            logger.error(f"Immediate alert failed: {e}")
            # Re-raise for critical errors
            raise

    async def send_system_alert(
        self, message: str, severity: str = "MEDIUM"
    ) -> None:
        """Send system-level alert as async task."""
        task = asyncio.create_task(
            self._send_webhook_notification_async(
                notification_type=NotificationType.SYSTEM_ALERT,
                payload={
                    "message": message,
                    "severity": severity,
                    "timestamp": datetime.utcnow().isoformat(),
                    "service": "OrchestraGuard",
                    "component": "notification_service",
                },
            )
        )

        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _send_webhook_notification_async(
        self, notification_type: NotificationType, payload: Dict[str, Any]
    ) -> None:
        """
        Async webhook notification - runs in background.
        Uses asyncio.create_task for each webhook call.
        """
        urls = self.webhook_urls.get(notification_type, [])

        if not urls:
            logger.debug(f"No webhooks registered for {notification_type.value}")
            return

        # Create tasks for each webhook URL
        tasks = []
        for url in urls:
            task = asyncio.create_task(self._send_single_webhook_async(url, payload))
            tasks.append(task)

        # Wait for all tasks with timeout
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Webhook to {urls[i]} failed: {result}")
                else:
                    logger.debug(f"Webhook to {urls[i]} succeeded")

        except asyncio.TimeoutError:
            logger.warning("Webhook notification timed out")
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")

    async def _send_webhook_notification_sync(
        self, notification_type: NotificationType, payload: Dict[str, Any]
    ) -> None:
        """
        Synchronous webhook notification - waits for completion.
        Used for critical notifications.
        """
        urls = self.webhook_urls.get(notification_type, [])

        if not urls:
            logger.warning(f"No webhooks registered for {notification_type.value}")
            return

        # Send to all URLs sequentially (for immediate notifications)
        for url in urls:
            try:
                success = await self._send_single_webhook_sync(url, payload)
                if success:
                    logger.info(f"Immediate webhook to {url} succeeded")
                else:
                    logger.warning(f"Immediate webhook to {url} failed")
            except Exception as e:
                logger.error(f"Immediate webhook to {url} error: {e}")

    async def _send_single_webhook_async(
        self, url: str, payload: Dict[str, Any]
    ) -> bool:
        """Send single webhook request with retry logic (async)."""
        max_retries = 2  # Fewer retries for async notifications

        for attempt in range(max_retries):
            try:
                response = await self.http_client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "OrchestraGuard/2.0",
                        "X-Notification-Type": payload.get("type", "alert"),
                    },
                )

                if 200 <= response.status_code < 300:
                    return True

                # Log non-2xx responses
                logger.warning(
                    f"Webhook to {url} returned {response.status_code}"
                )

            except Exception as e:
                if attempt == max_retries - 1:
                    raise  # Re-raise on last attempt

                await asyncio.sleep(1 * (attempt + 1))

        return False

    async def _send_single_webhook_sync(
        self, url: str, payload: Dict[str, Any]
    ) -> bool:
        """Send single webhook request with retry logic (sync)."""
        max_retries = 3  # More retries for synchronous notifications

        for attempt in range(max_retries):
            try:
                response = await self.http_client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "OrchestraGuard/2.0",
                        "X-Notification-Type": payload.get("type", "alert"),
                        "X-Notification-Urgency": "HIGH",
                    },
                    timeout=5.0,  # Shorter timeout for sync calls
                )

                response.raise_for_status()
                return True

            except httpx.TimeoutException:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Webhook to {url} timed out after {max_retries} attempts"
                    )
                    return False
                await asyncio.sleep(1)

            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Webhook to {url} failed: {e}")
                    return False
                await asyncio.sleep(1 * (attempt + 1))

        return False

    async def wait_for_pending_tasks(self, timeout: Optional[float] = None) -> None:
        """Wait for all pending notification tasks to complete."""
        if not self._pending_tasks:
            return

        try:
            await asyncio.wait_for(
                asyncio.gather(*self._pending_tasks, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Timeout waiting for {len(self._pending_tasks)} pending tasks"
            )

    async def close(self) -> None:
        """Close HTTP client and wait for pending tasks."""
        # Wait for pending tasks with timeout
        await self.wait_for_pending_tasks(timeout=5.0)

        # Close HTTP client
        if self.http_client:
            await self.http_client.aclose()
            logger.info("NotificationService HTTP client closed")

        # Clear pending tasks
        self._pending_tasks.clear()