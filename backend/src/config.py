from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    max_attempts: int = 3
    command_timeout: int = 60
    clone_timeout: int = 120
    install_timeout: int = 300

    sandbox_memory: str = "256m"
    sandbox_cpus: float = 1.0
    sandbox_pids: int = 128

    docker_dns_1: str = "1.1.1.1"
    docker_dns_2: str = "8.8.8.8"

    sandbox_root: Path = Path.home() / ".phantom" / "sandboxes"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
