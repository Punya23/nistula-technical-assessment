"""
Application configuration loaded from environment variables.

Uses Pydantic BaseSettings for type-safe config with .env file support.
All sensitive values (API keys) come from .env — never hardcoded.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # Claude API
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key for Claude access",
    )
    claude_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model identifier",
    )

    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")

    # Claude API settings
    claude_api_url: str = Field(
        default="https://api.anthropic.com/v1/messages",
        description="Claude API endpoint",
    )
    claude_timeout: int = Field(
        default=30,
        description="Claude API timeout in seconds",
    )
    claude_max_tokens: int = Field(
        default=1024,
        description="Max tokens for Claude response",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Singleton settings instance
settings = Settings()
