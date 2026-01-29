"""
Notification Service - Webhook & Alerting Service
"""
import asyncio
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from enum import Enum
from threading import Lock

class NotificationType(Enum):
    """Notification types"""
    BLOCK_ALERT = "block_alert"
    FLAG_ALERT = "flag_alert"
    SYSTEM_ALERT = "system_alert"
    POLICY_UPDATE = "policy_update"

class NotificationService:
    """
    Webhook and alerting service for real-time notifications
    """
    
    _instance = None
    _lock = Lock()
    
    def __init__(self):
        if NotificationService._instance is not None:
            raise Exception("NotificationService is a singleton!")
        
        self.webhook_urls = {
            NotificationType.BLOCK_ALERT: [],
            NotificationType.FLAG_ALERT: [],
            NotificationType.SYSTEM_ALERT: [],
            NotificationType.POLICY_UPDATE: []
        }
        
        self.http_client = None
        self._initialize_http_client()
    
    @staticmethod
    def get_instance():
        """Get singleton instance"""
        if NotificationService._instance is None:
            with NotificationService._lock:
                if NotificationService._instance is None:
                    NotificationService._instance = NotificationService()
        return NotificationService._instance
    
    def _initialize_http_client(self):
        """Initialize HTTP client with timeout settings"""
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
    
    def register_webhook(self, notification_type: NotificationType, url: str):
        """Register webhook URL for specific notification type"""
        if url not in self.webhook_urls[notification_type]:
            self.webhook_urls[notification_type].append(url)
    
    def unregister_webhook(self, notification_type: NotificationType, url: str):
        """Unregister webhook URL"""
        if url in self.webhook_urls[notification_type]:
            self.webhook_urls[notification_type].remove(url)
    
    async def send_alert(self, decision: Dict, action: Dict):
        """
        Send alert notification based on decision
        Non-blocking fire-and-forget
        """
        notification_type = None
        
        if decision.get("decision") == "BLOCK":
            notification_type = NotificationType.BLOCK_ALERT
        elif decision.get("decision") == "FLAG":
            notification_type = NotificationType.FLAG_ALERT
        
        if notification_type:
            await self._send_webhook_notification(
                notification_type=notification_type,
                payload={
                    "decision": decision,
                    "action": action,
                    "timestamp": datetime.utcnow().isoformat(),
                    "severity": decision.get("severity", "MEDIUM")
                }
            )
    
    async def send_system_alert(self, message: str, severity: str = "MEDIUM"):
        """Send system-level alert"""
        await self._send_webhook_notification(
            notification_type=NotificationType.SYSTEM_ALERT,
            payload={
                "message": message,
                "severity": severity,
                "timestamp": datetime.utcnow().isoformat(),
                "service": "OrchestraGuard"
            }
        )
    
    async def send_policy_update(self, policy_name: str, change_type: str):
        """Notify about policy updates"""
        await self._send_webhook_notification(
            notification_type=NotificationType.POLICY_UPDATE,
            payload={
                "policy_name": policy_name,
                "change_type": change_type,
                "timestamp": datetime.utcnow().isoformat(),
                "updated_by": "system"  # In production, would be user ID
            }
        )
    
    async def _send_webhook_notification(
        self, 
        notification_type: NotificationType, 
        payload: Dict[str, Any]
    ):
        """
        Send webhook notification to all registered URLs for type
        Runs in background, errors are logged but don't block
        """
        urls = self.webhook_urls.get(notification_type, [])
        
        if not urls:
            return
        
        tasks = []
        for url in urls:
            task = self._send_single_webhook(url, payload)
            tasks.append(task)
        
        # Run all webhook calls concurrently
        if tasks:
            asyncio.create_task(self._execute_webhooks(tasks))
    
    async def _send_single_webhook(self, url: str, payload: Dict[str, Any]):
        """Send single webhook request with retry logic"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "OrchestraGuard/1.0"
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.http_client.post(
                    url,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code >= 200 and response.status_code < 300:
                    return True
                
                # Log non-successful responses
                print(f"Webhook to {url} failed with status {response.status_code}")
                
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"Webhook to {url} failed after {max_retries} attempts: {e}")
                else:
                    await asyncio.sleep(1 * (attempt + 1))
        
        return False
    
    async def _execute_webhooks(self, tasks: List):
        """Execute all webhook tasks and gather results"""
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log any failures
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"Webhook task {i} failed: {result}")
                    
        except Exception as e:
            print(f"Error executing webhooks: {e}")
    
    async def close(self):
        """Close HTTP client"""
        if self.http_client:
            await self.http_client.aclose()