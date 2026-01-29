"""
Abstract Factory Pattern for LLM Providers - Decoupled provider implementation
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import asyncio
from functools import lru_cache
import os

from ibm_watsonx_ai import Credentials, WatsonxAI
from openai import AsyncOpenAI
from pydantic import BaseModel

class ToolCall(BaseModel):
    """Schema for LLM tool calls"""
    name: str
    arguments: Dict[str, Any]

class LLMResponse(BaseModel):
    """Standardized LLM response"""
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: str
    usage: Optional[Dict[str, int]] = None

class AbstractLLM(ABC):
    """Abstract interface for LLM providers"""
    
    @abstractmethod
    async def invoke(
        self, 
        prompt: str, 
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None
    ) -> LLMResponse:
        """Invoke the LLM with prompt and optional tools"""
        pass
    
    @abstractmethod
    async def close(self):
        """Clean up resources"""
        pass

class WatsonxProvider(AbstractLLM):
    """IBM Watsonx.ai Provider Implementation"""
    
    def __init__(self):
        self._client = None
        self._model_id = os.getenv("WATSONX_MODEL", "ibm/granite-13b-chat-v2")
        self._project_id = os.getenv("WATSONX_PROJECT_ID")
        
    async def _lazy_init(self):
        """Lazy initialization of client"""
        if self._client is None:
            credentials = Credentials(
                api_key=os.getenv("WATSONX_API_KEY"),
                url=os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
            )
            self._client = WatsonxAI(
                credentials=credentials,
                project_id=self._project_id
            )
    
    async def invoke(
        self, 
        prompt: str, 
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None
    ) -> LLMResponse:
        
        await self._lazy_init()
        
        try:
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Watsonx invocation
            response = self._client.chat.create(
                model_id=self._model_id,
                messages=messages,
                temperature=0.1,  # Low temperature for consistent policy decisions
                max_tokens=1000,
                tools=tools if tools else None
            )
            
            # Extract tool calls if present
            tool_calls = []
            if hasattr(response, 'choices') and response.choices:
                choice = response.choices[0]
                if hasattr(choice, 'tool_calls') and choice.tool_calls:
                    for tc in choice.tool_calls:
                        tool_calls.append(ToolCall(
                            name=tc.function.name,
                            arguments=json.loads(tc.function.arguments)
                        ))
                
                content = choice.message.content if hasattr(choice.message, 'content') else ""
                
                return LLMResponse(
                    content=content,
                    tool_calls=tool_calls if tool_calls else None,
                    finish_reason=choice.finish_reason,
                    usage={
                        'prompt_tokens': response.usage.prompt_tokens,
                        'completion_tokens': response.usage.completion_tokens
                    } if hasattr(response, 'usage') else None
                )
                
        except Exception as e:
            raise Exception(f"Watsonx API error: {str(e)}")
    
    async def close(self):
        """Cleanup"""
        self._client = None

class LMStudioProvider(AbstractLLM):
    """LM Studio/OpenAI-compatible Provider"""
    
    def __init__(self):
        self._client = None
        self._base_url = os.getenv("LMSTUDIO_URL", "http://localhost:1234/v1")
        
    async def _lazy_init(self):
        """Lazy initialization"""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key="lm-studio",  # Dummy key for LM Studio
                base_url=self._base_url
            )
    
    async def invoke(
        self, 
        prompt: str, 
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None
    ) -> LLMResponse:
        
        await self._lazy_init()
        
        try:
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # OpenAI-compatible invocation
            response = await self._client.chat.completions.create(
                model="local-model",  # LM Studio uses this
                messages=messages,
                temperature=0.1,
                max_tokens=1000,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None
            )
            
            # Extract response
            choice = response.choices[0]
            message = choice.message
            
            # Extract tool calls
            tool_calls = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(ToolCall(
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments)
                    ))
            
            return LLMResponse(
                content=message.content or "",
                tool_calls=tool_calls if tool_calls else None,
                finish_reason=choice.finish_reason,
                usage={
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens
                }
            )
            
        except Exception as e:
            raise Exception(f"LM Studio API error: {str(e)}")
    
    async def close(self):
        """Cleanup"""
        if self._client:
            await self._client.close()

class LLMFactory:
    """Factory for creating LLM provider instances"""
    
    _providers = {}
    
    @staticmethod
    def get_provider(provider_name: str = None) -> AbstractLLM:
        """
        Get LLM provider instance with lazy loading
        Default provider: WATSONX if env set, else LMSTUDIO
        """
        # Determine default provider
        if not provider_name:
            provider_name = "WATSONX" if os.getenv("WATSONX_API_KEY") else "LMSTUDIO"
        
        provider_name = provider_name.upper()
        
        # Return cached instance
        if provider_name in LLMFactory._providers:
            return LLMFactory._providers[provider_name]
        
        # Create new instance
        if provider_name == "WATSONX":
            provider = WatsonxProvider()
        elif provider_name == "LMSTUDIO":
            provider = LMStudioProvider()
        else:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        # Cache and return
        LLMFactory._providers[provider_name] = provider
        return provider
    
    @staticmethod
    async def close_all():
        """Close all provider instances"""
        for provider in LLMFactory._providers.values():
            await provider.close()
        LLMFactory._providers.clear()