import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# OpenAI
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# Database
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/shouldercoach.db")

# CORS
ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

# NBA API rate limiting
NBA_API_SLEEP_SECONDS: float = 0.6
NBA_API_MAX_RETRIES: int = 3
NBA_API_BACKOFF_BASE: float = 2.0  # seconds; doubles each retry

# Seasons to seed (2019-20 through 2023-24)
NBA_SEASONS: list[str] = [
    "2019-20",
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
]

# Confidence thresholds
LOW_SAMPLE_THRESHOLD: int = 30
INSUFFICIENT_DATA_THRESHOLD: int = 5
