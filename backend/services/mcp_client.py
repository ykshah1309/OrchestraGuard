"""
FIXED: Added missing hashlib import and improved error handling
"""
import httpx
import json
import hashlib  # FIXED: Added missing import
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ContextType(Enum):
    """Types of context that can be fetched"""
    RECENT_ACTIVITY = "recent_activity"
    PERMISSIONS = "permissions"
    METADATA = "metadata"
    HISTORY = "history"
    USAGE_STATS = "usage_stats"

@dataclass
class MCPContextResult:
    """Result from MCP context fetch"""
    tool_name: str
    context_type: ContextType
    results: List[Dict[str, Any]]
    total_results: int
    metadata: Dict[str, Any]
    fetched_at: datetime

class MCPClient:
    """
    Model Context Protocol Client
    Fetches external context for decision making
    """
    
    # MCP server configurations for common tools
    MCP_SERVERS = {
        "slack": {
            "base_url": "http://localhost:3001/mcp",
            "endpoints": {
                "recent_activity": "/slack/channels/{channel}/messages",
                "permissions": "/slack/users/{user_id}/permissions",
                "metadata": "/slack/channels/{channel}/metadata"
            }
        },
        "github": {
            "base_url": "http://localhost:3002/mcp",
            "endpoints": {
                "recent_activity": "/github/repos/{repo}/commits",
                "permissions": "/github/repos/{repo}/collaborators/{user}/permission",
                "metadata": "/github/repos/{repo}"
            }
        },
        "jira": {
            "base_url": "http://localhost:3003/mcp",
            "endpoints": {
                "recent_activity": "/jira/projects/{project}/issues",
                "permissions": "/jira/users/{user}/permissions",
                "metadata": "/jira/projects/{project}"
            }
        },
        "sql_database": {
            "base_url": "http://localhost:3004/mcp",
            "endpoints": {
                "recent_activity": "/database/{db_name}/query_history",
                "permissions": "/database/{db_name}/user_permissions/{user}",
                "metadata": "/database/{db_name}/schema"
            }
        }
    }
    
    def __init__(self):
        self.http_client = None
        self.cache = {}  # Simple cache for frequent requests
        self._initialize_http_client()
    
    def _initialize_http_client(self):
        """Initialize HTTP client with connection pooling"""
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            follow_redirects=True
        )
    
    async def fetch_context(
        self,
        tool_name: str,
        tool_arguments: Dict[str, Any],
        context_type: str = "recent_activity",
        max_results: int = 10
    ) -> MCPContextResult:
        """
        Fetch context from external tool via MCP
        
        Args:
            tool_name: Name of the tool (slack, github, jira, etc.)
            tool_arguments: Arguments passed to the tool
            context_type: Type of context to fetch
            max_results: Maximum number of results to return
        """
        # Check cache first
        cache_key = self._create_cache_key(tool_name, tool_arguments, context_type)
        cached = self.cache.get(cache_key)
        
        if cached and (datetime.utcnow() - cached.fetched_at).seconds < 60:
            # Return cached result if less than 60 seconds old
            logger.debug(f"Returning cached result for {cache_key}")
            return cached
        
        # Get MCP server config
        server_config = self.MCP_SERVERS.get(tool_name.lower())
        if not server_config:
            # Try to auto-detect tool type
            server_config = self._detect_tool_config(tool_name)
            if not server_config:
                # Return empty result for unknown tools
                logger.warning(f"No MCP server configured for tool: {tool_name}")
                return MCPContextResult(
                    tool_name=tool_name,
                    context_type=ContextType(context_type),
                    results=[],
                    total_results=0,
                    metadata={"error": f"Tool '{tool_name}' not configured in MCP", "status": "not_configured"},
                    fetched_at=datetime.utcnow()
                )
        
        try:
            # Build endpoint URL
            endpoint_template = server_config["endpoints"].get(context_type)
            if not endpoint_template:
                logger.error(f"Context type {context_type} not supported for {tool_name}")
                raise ValueError(f"Context type {context_type} not supported for {tool_name}")
            
            # Replace placeholders in endpoint
            endpoint = endpoint_template
            for key, value in tool_arguments.items():
                placeholder = f"{{{key}}}"
                if placeholder in endpoint:
                    endpoint = endpoint.replace(placeholder, str(value))
            
            # Make request to MCP server
            url = f"{server_config['base_url']}{endpoint}"
            
            # Add query parameters
            params = {
                "limit": max_results,
                "sort": "desc" if context_type == "recent_activity" else "asc"
            }
            
            logger.info(f"Fetching MCP context from {url}")
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            # Create result object
            result = MCPContextResult(
                tool_name=tool_name,
                context_type=ContextType(context_type),
                results=data.get("items", [])[:max_results],
                total_results=data.get("total_count", len(data.get("items", []))),
                metadata={
                    "source": "mcp",
                    "server": server_config["base_url"],
                    "endpoint": endpoint,
                    "response_time_ms": response.elapsed.total_seconds() * 1000,
                    "status": "success"
                },
                fetched_at=datetime.utcnow()
            )
            
            # Cache the result
            self.cache[cache_key] = result
            logger.debug(f"Cached result for {cache_key}")
            
            return result
            
        except httpx.RequestError as e:
            # Handle network errors
            logger.error(f"MCP network error for {tool_name}: {e}")
            return MCPContextResult(
                tool_name=tool_name,
                context_type=ContextType(context_type),
                results=[],
                total_results=0,
                metadata={"error": f"Network error: {str(e)}", "status": "network_error"},
                fetched_at=datetime.utcnow()
            )
        except Exception as e:
            # Handle other errors
            logger.error(f"MCP error for {tool_name}: {e}")
            return MCPContextResult(
                tool_name=tool_name,
                context_type=ContextType(context_type),
                results=[],
                total_results=0,
                metadata={"error": str(e), "status": "error"},
                fetched_at=datetime.utcnow()
            )
    
    def _create_cache_key(
        self,
        tool_name: str,
        tool_arguments: Dict[str, Any],
        context_type: str
    ) -> str:
        """Create cache key from request parameters"""
        # Sort arguments to ensure consistent keys
        sorted_args = json.dumps(tool_arguments, sort_keys=True)
        # FIXED: Now hashlib is imported
        return f"{tool_name}:{context_type}:{hashlib.md5(sorted_args.encode()).hexdigest()}"
    
    def _detect_tool_config(self, tool_name: str) -> Optional[Dict]:
        """Auto-detect tool configuration based on name patterns"""
        tool_lower = tool_name.lower()
        
        if any(keyword in tool_lower for keyword in ["slack", "chat", "message"]):
            return self.MCP_SERVERS["slack"]
        elif any(keyword in tool_lower for keyword in ["github", "git", "repo"]):
            return self.MCP_SERVERS["github"]
        elif any(keyword in tool_lower for keyword in ["jira", "ticket", "issue"]):
            return self.MCP_SERVERS["jira"]
        elif any(keyword in tool_lower for keyword in ["sql", "database", "db"]):
            return self.MCP_SERVERS["sql_database"]
        
        return None
    
    async def fetch_multiple_contexts(
        self,
        contexts: List[Dict[str, Any]],
        parallel: bool = True
    ) -> Dict[str, MCPContextResult]:
        """Fetch multiple contexts in parallel or sequentially"""
        results = {}
        
        if parallel:
            # Fetch all contexts in parallel
            tasks = []
            for context in contexts:
                task = self.fetch_context(
                    tool_name=context["tool_name"],
                    tool_arguments=context["tool_arguments"],
                    context_type=context.get("context_type", "recent_activity"),
                    max_results=context.get("max_results", 10)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            fetched_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(fetched_results):
                context_key = contexts[i].get("key", f"context_{i}")
                if isinstance(result, Exception):
                    logger.error(f"Error fetching context {context_key}: {result}")
                    results[context_key] = MCPContextResult(
                        tool_name=contexts[i]["tool_name"],
                        context_type=ContextType(contexts[i].get("context_type", "recent_activity")),
                        results=[],
                        total_results=0,
                        metadata={"error": str(result), "status": "error"},
                        fetched_at=datetime.utcnow()
                    )
                else:
                    results[context_key] = result
        else:
            # Fetch sequentially
            for context in contexts:
                result = await self.fetch_context(
                    tool_name=context["tool_name"],
                    tool_arguments=context["tool_arguments"],
                    context_type=context.get("context_type", "recent_activity"),
                    max_results=context.get("max_results", 10)
                )
                context_key = context.get("key", f"context_{len(results)}")
                results[context_key] = result
        
        return results
    
    def clear_cache(self, older_than: Optional[int] = None):
        """Clear the cache, optionally only entries older than X seconds"""
        if older_than:
            cutoff = datetime.utcnow() - timedelta(seconds=older_than)
            old_keys = [k for k, v in self.cache.items() if v.fetched_at <= cutoff]
            for key in old_keys:
                del self.cache[key]
            logger.info(f"Cleared {len(old_keys)} old cache entries")
        else:
            self.cache.clear()
            logger.info("Cleared all cache entries")
    
    async def close(self):
        """Close HTTP client"""
        if self.http_client:
            await self.http_client.aclose()
            logger.info("MCPClient HTTP client closed")