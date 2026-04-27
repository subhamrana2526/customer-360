import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BACKEND_ROOT / "data"))
CACHE_DIR = Path(os.getenv("CACHE_DIR", DATA_DIR / "cache"))
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
STATIC_DIR = Path(os.getenv("FRONTEND_DIR", REPO_ROOT / "frontend"))

CUSTOMERS_FILE = DATA_DIR / "customers.json"
PRODUCT_CATALOG_FILE = DATA_DIR / "product_catalog.json"
MACRO_NEWS_FILE = DATA_DIR / "macro_news.json"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL_SYNTH = os.getenv("OPENAI_MODEL_SYNTH", "gpt-4o")
OPENAI_MODEL_SUMM = os.getenv("OPENAI_MODEL_SUMM", "gpt-4o-mini")

HUBSPOT_TOKEN = os.getenv("HUBSPOT_TOKEN", "")
HUBSPOT_WINDOW_DAYS = int(os.getenv("HUBSPOT_WINDOW_DAYS", "180"))

ELIXIR_BASE_URL = os.getenv("ELIXIR_BASE_URL", "https://api-v2.elchemy.com")
ELIXIR_TOKEN = os.getenv("ELIXIR_TOKEN", "")
ELIXIR_API_KEY = os.getenv("ELIXIR_API_KEY", "")

NEWS_CAP = int(os.getenv("NEWS_CAP", "15"))


def customer_cache_dir(customer_id: str) -> Path:
    return CACHE_DIR / customer_id


def raw_dir(customer_id: str) -> Path:
    return customer_cache_dir(customer_id) / "raw"


def stage1_dir(customer_id: str) -> Path:
    return customer_cache_dir(customer_id) / "stage1"


def brief_path(customer_id: str) -> Path:
    return customer_cache_dir(customer_id) / "brief.json"


def ensure_customer_dirs(customer_id: str) -> None:
    raw_dir(customer_id).mkdir(parents=True, exist_ok=True)
    stage1_dir(customer_id).mkdir(parents=True, exist_ok=True)
