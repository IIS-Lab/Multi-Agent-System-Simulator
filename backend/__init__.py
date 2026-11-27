"""MASS (Multi Agent System Simulator) backend.

Loads a local .env file (development) before any module reads environment
variables. In production, real environment variables take precedence.
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
