"""Central configuration for the HDB resale pipeline.

Everything that might change — the dataset, the API page size, where the
warehouse lives — is defined here so it is never hard-coded across modules.
"""
from pathlib import Path

# --- Source API -------------------------------------------------------------
API_BASE_URL = "https://data.gov.sg/api/action/datastore_search"
# Resale flat prices based on registration date, Jan 2017 onwards.
RESOURCE_ID = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"

# The API rejects pages whose *payload* is too large; 10,000 rows is comfortably
# under that ceiling (20,000 fails with "Size of row data too large"). Kept
# configurable in case the row width ever grows.
PAGE_SIZE = 10_000

# --- Ingestion robustness ---------------------------------------------------
MAX_RETRIES = 5              # attempts per page before giving up
BACKOFF_BASE_SECONDS = 1.0   # exponential backoff delay = base * 2**attempt
REQUEST_TIMEOUT_SECONDS = 30

# --- Storage ----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "warehouse.duckdb"
EXPORTS_DIR = PROJECT_ROOT / "exports"
