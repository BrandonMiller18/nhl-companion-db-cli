import os
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import time

from dotenv import load_dotenv

# Load .env from DB CLI service root directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

RECORDS_BASE = "https://records.nhl.com/site/api"
NHL_WEB_BASE = "https://api-web.nhle.com/v1"


def get_env(name: str, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


# Polling configuration for watch-live
# Poll every 5 seconds when there are live games
LIVE_GAMES_POLL_SECONDS = 5

# Poll every 5 minutes (300 seconds) when there are no live games
NO_GAMES_POLL_SECONDS = 300


