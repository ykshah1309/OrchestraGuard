"""
Database Service - Singleton Pattern for Supabase/PostgreSQL interaction
"""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
from supabase import create_client, Client
from functools import wraps
import asyncio
from threading import Lock

class DatabaseService:
    """
    Singleton database client with connection pooling management
    High-performance Supabase/PostgreSQL interaction
    """
    
    _instance = None
    _lock = Lock()
    
    def __init__(self):
        if DatabaseService._instance is not None:
            raise Exception("DatabaseService is a singleton!")
        
        self.supabase: Client = None
        self.is_initialized = False
        self._initialize()
    
    @staticmethod
    def get_instance():
        """Get singleton instance"""
        if DatabaseService._instance is None:
            with DatabaseService._lock:
                if DatabaseService._instance is None:
                    DatabaseService._instance = DatabaseService()
        return DatabaseService._instance
    
    def _initialize(self):
        """Initialize Supabase client"""
        try:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_KEY")
            
            if not supabase_url or not supabase_key:
                raise ValueError("Supabase credentials not configured")
            
            self.supabase = create_client(supabase_url, supabase_key)
            self.is_initialized = True
            
            # Test connection
            self.supabase.table("policies").select("count", count="exact").limit(1).execute()
            
            print("✅ DatabaseService initialized successfully")
            
        except Exception as e:
            print(f"❌ DatabaseService initialization failed: {e}")
            raise
    
    async def log_audit(
        self,
        action_id: str,
        source_agent: str,
        target_tool: str,
        decision: str,
        rationale: str,
        metadata: Optional[Dict] = None
    ):
        """Log decision to audit_logs table"""
        try:
            data = {
                "action_id": action_id,
                "source_agent": source_agent,
                "target_tool": target_tool,
                "decision": decision,
                "rationale": rationale,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }
            
            response = self.supabase.table("audit_logs").insert(data).execute()
            return response.data[0] if response.data else None
            
        except Exception as e:
            print(f"Error logging audit: {e}")
            # Don't raise - audit failures shouldn't break the flow
            return None
    
    async def create_policy(
        self,
        name: str,
        rule_id: str,
        description: str,
        target_tool_regex: str,
        condition_logic: str,
        severity: str,
        action_on_violation: str
    ):
        """Create new policy rule"""
        try:
            # Create JSONB rules object
            rules_json = {
                "rule_id": rule_id,
                "description": description,
                "target_tool_regex": target_tool_regex,
                "condition_logic": condition_logic,
                "severity": severity,
                "action_on_violation": action_on_violation
            }
            
            data = {
                "name": name,
                "rules": rules_json,
                "is_active": True,
                "created_at": datetime.utcnow().isoformat()
            }
            
            response = self.supabase.table("policies").insert(data).execute()
            return response.data[0] if response.data else None
            
        except Exception as e:
            print(f"Error creating policy: {e}")
            raise
    
    async def get_all_policies(self, active_only: bool = True) -> List[Dict]:
        """Retrieve all policies (with GIN index optimization)"""
        try:
            query = self.supabase.table("policies").select("*")
            
            if active_only:
                query = query.eq("is_active", True)
            
            response = query.execute()
            return response.data
            
        except Exception as e:
            print(f"Error fetching policies: {e}")
            return []
    
    async def get_policies_for_tool(self, target_tool: str) -> List[Dict]:
        """
        Get policies for specific tool using JSONB query
        Leverages GIN index for performance
        """
        try:
            # Use Supabase's JSONB query capabilities
            response = self.supabase.rpc(
                'get_policies_by_tool',
                {'tool_pattern': f'%{target_tool}%'}
            ).execute()
            
            return response.data
            
        except Exception as e:
            print(f"Error querying policies for tool: {e}")
            # Fallback to application-side filtering
            all_policies = await self.get_all_policies()
            return [
                p for p in all_policies 
                if target_tool in p.get('rules', {}).get('target_tool_regex', '')
            ]
    
    async def get_audit_count(self) -> int:
        """Get total number of audit logs"""
        try:
            response = self.supabase.table("audit_logs").select("count", count="exact").execute()
            return response.count
        except:
            return 0
    
    async def get_decision_rate(self, decision_type: str) -> float:
        """Get rate of specific decision type"""
        try:
            total = await self.get_audit_count()
            if total == 0:
                return 0.0
            
            response = self.supabase.table("audit_logs") \
                .select("count", count="exact") \
                .eq("decision", decision_type) \
                .execute()
            
            return response.count / total
            
        except:
            return 0.0
    
    async def get_active_policy_count(self) -> int:
        """Count active policies"""
        try:
            response = self.supabase.table("policies") \
                .select("count", count="exact") \
                .eq("is_active", True) \
                .execute()
            
            return response.count
        except:
            return 0
    
    async def get_recent_audits(self, limit: int = 100) -> List[Dict]:
        """Get recent audit logs with indexed query"""
        try:
            response = self.supabase.table("audit_logs") \
                .select("*") \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()
            
            return response.data
            
        except Exception as e:
            print(f"Error fetching recent audits: {e}")
            return []
    
    def close(self):
        """Close database connections"""
        # Supabase client doesn't have explicit close method
        self.supabase = None
        self.is_initialized = False

# Decorator for database operations
def with_db_retry(max_retries=3):
    """Decorator for retrying database operations"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1 * (attempt + 1))
            raise last_error
        return wrapper
    return decorator