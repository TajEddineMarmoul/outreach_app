import sys
import sqlite3
import os
from pathlib import Path
from src.scheduler import send_next_approved
from src.models import AppConfig

db_path = "data/outreach.db"
config_path = "config.yaml"

if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    sys.exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

import yaml
with open(config_path, "r") as f:
    raw = yaml.safe_load(f)
config = AppConfig.model_validate(raw)

print(f"Config loaded. delay_minutes: {config.sending.delay_minutes}, end_time: {config.sending.end_time}")

try:
    print("Calling send_next_approved...")
    result = send_next_approved(conn, config, campaign_id=40)
    print("Result:", result)
except Exception as e:
    import traceback
    traceback.print_exc()

conn.close()
