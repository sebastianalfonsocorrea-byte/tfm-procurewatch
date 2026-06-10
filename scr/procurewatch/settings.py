from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    project_name: str = "ProcureWatch Analytics"
    environment: str = "local"
    data_dir: Path = Path("data")
    raw_data_dir: Path = Path("data/raw")
    processed_data_dir: Path = Path("data/processed")
    synthetic_data_dir: Path = Path("data/synthetic")
    models_dir: Path = Path("models")
    postgres_dsn: str | None = None
    neo4j_uri: str | None = None
    neo4j_user: str | None = None
    neo4j_password: str | None = None
    qdrant_url: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str = "qwen3:8b"

    @classmethod
    def from_env(cls) -> Settings:
        data_dir = Path(os.getenv("PROCUREWATCH_DATA_DIR", "data"))
        return cls(
            environment=os.getenv("PROCUREWATCH_ENV", "local"),
            data_dir=data_dir,
            raw_data_dir=Path(
                os.getenv("PROCUREWATCH_RAW_DATA_DIR", str(data_dir / "raw"))
            ),
            processed_data_dir=Path(
                os.getenv("PROCUREWATCH_PROCESSED_DATA_DIR", str(data_dir / "processed"))
            ),
            synthetic_data_dir=Path(
                os.getenv("PROCUREWATCH_SYNTHETIC_DATA_DIR", str(data_dir / "synthetic"))
            ),
            models_dir=Path(os.getenv("PROCUREWATCH_MODELS_DIR", "models")),
            postgres_dsn=os.getenv("PROCUREWATCH_POSTGRES_DSN"),
            neo4j_uri=os.getenv("PROCUREWATCH_NEO4J_URI"),
            neo4j_user=os.getenv("PROCUREWATCH_NEO4J_USER"),
            neo4j_password=os.getenv("PROCUREWATCH_NEO4J_PASSWORD"),
            qdrant_url=os.getenv("PROCUREWATCH_QDRANT_URL"),
            ollama_base_url=os.getenv("PROCUREWATCH_OLLAMA_BASE_URL"),
            ollama_model=os.getenv("PROCUREWATCH_OLLAMA_MODEL", "qwen3:8b"),
        )

    def required_local_directories(self) -> tuple[Path, ...]:
        return (
            self.raw_data_dir,
            self.processed_data_dir,
            self.synthetic_data_dir,
            self.models_dir,
        )

    def optional_service_status(self) -> dict[str, bool]:
        return {
            "PostgreSQL DSN": self.postgres_dsn is not None,
            "Neo4j URI": self.neo4j_uri is not None,
            "Qdrant URL": self.qdrant_url is not None,
            "Ollama URL": self.ollama_base_url is not None,
        }
