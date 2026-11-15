import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))        # llm.py
sys.path.insert(0, str(ROOT / "v2"))  # engine, intent, v2_core
