"""Test script to verify multi-LLM configuration."""

import os
import sys

# Add the vibe module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "vibe"))

from vibe.core.llm import ModelConfig, create_llm_model
from vibe.core.config import VibeConfig, load_config, save_config


def test_model_creation():
    """Test creating different LLM models."""
    print("Testing LLM Model Creation...")
    print("=" * 60)

    # Test 1: Gemini (default)
    print("\n1. Testing Gemini model creation...")
    try:
        config = ModelConfig(
            provider="gemini",
            model_name="gemini-2.0-flash-exp",
            api_key=os.getenv("GOOGLE_API_KEY"),
        )
        model = create_llm_model(config)
        print(f"✓ Successfully created Gemini model: {type(model).__name__}")
    except Exception as e:
        print(f"✗ Failed to create Gemini model: {e}")

    # Test 2: OpenAI (if API key available)
    print("\n2. Testing OpenAI model creation...")
    if os.getenv("OPENAI_API_KEY"):
        try:
            config = ModelConfig(
                provider="openai",
                model_name="gpt-4",
                api_key=os.getenv("OPENAI_API_KEY"),
            )
            model = create_llm_model(config)
            print(
                f"✓ Successfully created OpenAI model: {type(model).__name__}"
            )
        except Exception as e:
            print(f"✗ Failed to create OpenAI model: {e}")
    else:
        print("⊘ Skipped (OPENAI_API_KEY not set)")

    # Test 3: Anthropic (if API key available)
    print("\n3. Testing Anthropic model creation...")
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            config = ModelConfig(
                provider="anthropic",
                model_name="claude-3-5-sonnet-20241022",
                api_key=os.getenv("ANTHROPIC_API_KEY"),
            )
            model = create_llm_model(config)
            print(
                f"✓ Successfully created Anthropic model: {type(model).__name__}"
            )
        except Exception as e:
            print(f"✗ Failed to create Anthropic model: {e}")
    else:
        print("⊘ Skipped (ANTHROPIC_API_KEY not set)")

    print("\n" + "=" * 60)


def test_config_file():
    """Test .vibeconfig file operations."""
    print("\nTesting .vibeconfig File Operations...")
    print("=" * 60)

    # Test creating a config
    print("\n1. Creating sample .vibeconfig...")
    test_config = VibeConfig(
        model_provider="gemini",
        model_name="gemini-2.0-flash-exp",
        temperature=0.7,
    )

    test_file = ".vibeconfig"
    if save_config(test_config, test_file):
        print(f"✓ Successfully saved {test_file}")
    else:
        print("✗ Failed to save config file")

    # Test loading a config
    print(f"\n2. Loading {test_file}...")
    loaded_config = load_config(".")
    if loaded_config:
        print(f"✓ Successfully loaded config:")
        print(f"  Provider: {loaded_config.model_provider}")
        print(f"  Model: {loaded_config.model_name}")
        print(f"  Temperature: {loaded_config.temperature}")
    else:
        print("✗ Failed to load config file")

    # Cleanup
    try:
        if os.path.exists(test_file):
            os.remove(test_file)
            print("\n✓ Cleaned up test file")
    except:
        pass

    print("\n" + "=" * 60)


def test_model_inference():
    """Test parsing model from command-line format."""
    print("\nTesting Model Inference...")
    print("=" * 60)

    test_cases = [
        ("openai:gpt-4", "openai", "gpt-4"),
        ("gemini:gemini-2.0-flash-exp", "gemini", "gemini-2.0-flash-exp"),
        (
            "anthropic:claude-3-5-sonnet-20241022",
            "anthropic",
            "claude-3-5-sonnet-20241022",
        ),
    ]

    for model_str, expected_provider, expected_model in test_cases:
        parts = model_str.split(":", 1)
        provider = parts[0]
        model_name = parts[1] if len(parts) > 1 else None

        if provider == expected_provider and model_name == expected_model:
            print(f"✓ '{model_str}' -> provider={provider}, model={model_name}")
        else:
            print(f"✗ '{model_str}' parsing failed")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("VIBE MULTI-LLM CONFIGURATION TEST")
    print("=" * 60)

    test_model_creation()
    test_config_file()
    test_model_inference()

    print("\n" + "=" * 60)
    print("TESTS COMPLETED")
    print("=" * 60)
    print("\nTo use vibe with different models:")
    print("  vibe --model openai:gpt-4 commit")
    print("  vibe --model gemini:gemini-2.0-flash-exp expand abc123")
    print("  vibe --model anthropic:claude-3-5-sonnet-20241022 commit")
    print("\nSee LLM_SETUP.md for full documentation.")
    print()
