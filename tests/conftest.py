"""Puts each skill's scripts/ directory on sys.path so tests can import
them as plain modules (config_loader, validate_data, preprocess,
analyze), the same way the scripts import each other when run directly."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
for scripts_dir in ["skills/analysis/scripts", "skills/dashboard/scripts", "skills/feedback/scripts"]:
    path = str(REPO_ROOT / scripts_dir)
    if path not in sys.path:
        sys.path.insert(0, path)
