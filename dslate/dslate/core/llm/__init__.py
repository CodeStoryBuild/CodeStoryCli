"""LLM integration module for dslate."""

from .factory import ModelConfig, create_llm_model

__all__ = ["create_llm_model", "ModelConfig"]
