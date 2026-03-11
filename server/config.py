from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    render_host: str = "0.0.0.0"
    render_port: int = 8443
    render_workers: int = 1
    render_binary: str = "./build/live2d-render"
    render_output_dir: str = "./renders"
    render_output_ttl: int = 3600  # seconds
    registry_path: str = "./assets/models/registry.json"

    tls_cert: str = "certs/server.crt"
    tls_key: str = "certs/server.key"

    api_key: str = ""  # empty = auth disabled

    @property
    def output_dir(self) -> Path:
        return Path(self.render_output_dir)

    @property
    def binary_path(self) -> Path:
        return Path(self.render_binary)


settings = Settings()
