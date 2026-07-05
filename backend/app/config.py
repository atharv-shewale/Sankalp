import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the root directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = str(BASE_DIR / "backend" / "sankalp.db")

# LLM APIs config
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Fallback mode flag
MOCK_LLM_MODE = not (ANTHROPIC_API_KEY or GEMINI_API_KEY)

# Port & Host configurations
HOST = "0.0.0.0"
PORT = 8000
WS_URL = f"ws://localhost:{PORT}/ws"
