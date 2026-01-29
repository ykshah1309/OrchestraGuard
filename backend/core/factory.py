"""
FIXED: Proper LLM Factory with working Watsonx and LMStudio providers
"""
import os
import json
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Conditional imports based on availability
try:
    from ibm_watsonx_ai import Credentials, WatsonxAI
    WATSONX_AVAILABLE = True
except ImportError:
    WATSONX_AVAILABLE = False

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

@dataclass
class LLMResponse:
    """Standardized response from any LLM"""
    content: str
    tool_calls: Optional[List[Dict]] = None
    finish_reason: Optional[str] = None

class BaseLLMProvider(ABC):
    """Abstract LLM provider interface"""
    
    @abstractmethod
    async def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.1
    ) -> LLMResponse:
        """Invoke the LLM with given parameters"""
        pass
    
    @abstractmethod
    async def close(self):
        """Clean up resources"""
        pass

class WatsonxProvider(BaseLLMProvider):
    """FIXED: Working IBM Watsonx provider"""
    
    def __init__(self):
        if not WATSONX_AVAILABLE:
            raise ImportError("ibm-watsonx-ai not installed. Run: pip install ibm-watsonx-ai")
        
        self.client = None
        self.model_id = os.getenv("WATSONX_MODEL_ID", "ibm/granite-13b-chat-v2")
        self.project_id = os.getenv("WATSONX_PROJECT_ID")
        
    async def _initialize(self):
        """Initialize Watsonx client"""
        if self.client is None:
            credentials = Credentials(
                api_key=os.getenv("WATSONX_API_KEY"),
                url=os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
            )
            self.client = WatsonxAI(
                credentials=credentials,
                project_id=self.project_id
            )
    
    async def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.1
    ) -> LLMResponse:
        """Invoke Watsonx LLM with proper error handling"""
        await self._initialize()
        
        try:
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Prepare parameters
            params = {
                "temperature": temperature,
                "max_tokens": 1000,
                "top_p": 0.9,
            }
            
            # Add tools if provided (Watsonx format)
            if tools:
                params["tools"] = tools
            
            # Make the API call
            response = self.client.chat.create(
                model_id=self.model_id,
                messages=messages,
                **params
            )
            
            # Parse response
            if hasattr(response, 'choices') and response.choices:
                choice = response.choices[0]
                content = choice.message.content if hasattr(choice.message, 'content') else ""
                
                # Extract tool calls if present
                tool_calls = None
                if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                    tool_calls = []
                    for tc in choice.message.tool_calls:
                        tool_calls.append({
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        })
                
                return LLMResponse(
                    content=content,
                    tool_calls=tool_calls,
                    finish_reason=choice.finish_reason
                )
            else:
                raise ValueError("No response from Watsonx")
                
        except Exception as e:
            raise Exception(f"Watsonx API error: {str(e)}")
    
    async def close(self):
        """Cleanup - Watsonx client doesn't need explicit close"""
        self.client = None

class LMStudioProvider(BaseLLMProvider):
    """FIXED: Working LM Studio provider using OpenAI-compatible API"""
    
    def __init__(self):
        if not OPENAI_AVAILABLE:
            raise ImportError("openai not installed. Run: pip install openai")
        
        self.client = None
        self.base_url = os.getenv("LMSTUDIO_URL", "http://localhost:1234/v1")
        self.model = os.getenv("LMSTUDIO_MODEL", "local-model")
        
    async def _initialize(self):
        """Initialize OpenAI-compatible client"""
        if self.client is None:
            self.client = AsyncOpenAI(
                base_url=self.base_url,
                api_key="lm-studio"  # LM Studio doesn't require a real key
            )
    
    async def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.1
    ) -> LLMResponse:
        """Invoke LM Studio using OpenAI-compatible API"""
        await self._initialize()
        
        try:
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Prepare parameters
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 1000,
            }
            
            # Add tools if provided (OpenAI format)
            if tools:
                params["tools"] = tools
                params["tool_choice"] = "auto"
            
            # Make the API call
            response = await self.client.chat.completions.create(**params)
            
            # Parse response
            if response.choices:
                choice = response.choices[0]
                message = choice.message
                
                # Extract tool calls
                tool_calls = None
                if message.tool_calls:
                    tool_calls = []
                    for tc in message.tool_calls:
                        tool_calls.append({
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        })
                
                return LLMResponse(
                    content=message.content or "",
                    tool_calls=tool_calls,
                    finish_reason=choice.finish_reason
                )
            else:
                raise ValueError("No response from LM Studio")
                
        except Exception as e:
            raise Exception(f"LM Studio API error: {str(e)}")
    
    async def close(self):
        """Cleanup - close OpenAI client"""
        if self.client:
            await self.client.close()

class LLMFactory:
    """Factory for creating LLM provider instances with lazy loading"""
    
    _instances = {}
    
    @staticmethod
    async def get_provider(provider_name: str = None) -> BaseLLMProvider:
        """Get LLM provider instance with automatic fallback"""
        if not provider_name:
            # Auto-detect provider
            if os.getenv("WATSONX_API_KEY"):
                provider_name = "watsonx"
            elif os.getenv("OPENAI_API_KEY"):
                provider_name = "openai"
            else:
                provider_name = "lmstudio"
        
        provider_name = provider_name.lower()
        
        # Return cached instance
        if provider_name in LLMFactory._instances:
            return LLMFactory._instances[provider_name]
        
        # Create new instance based on provider
        if provider_name == "watsonx":
            provider = WatsonxProvider()
        elif provider_name in ["lmstudio", "local"]:
            provider = LMStudioProvider()
        elif provider_name == "openai":
            # OpenAI is just LMStudio with different URL
            os.environ["LMSTUDIO_URL"] = "https://api.openai.com/v1"
            os.environ["LMSTUDIO_MODEL"] = "gpt-4"
            provider = LMStudioProvider()
        else:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        # Cache and return
        LLMFactory._instances[provider_name] = provider
        return provider
    
    @staticmethod
    async def close_all():
        """Close all provider instances"""
        for provider in LLMFactory._instances.values():
            await provider.close()
        LLMFactory._instances.clear()