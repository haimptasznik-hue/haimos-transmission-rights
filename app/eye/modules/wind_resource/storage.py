"""
Storage — save outputs to EYE project folder + HaimOS vault with backup logic.
"""
import os
import shutil
from datetime import datetime


def safe_save(df, path, label=""):
    """Save DataFrame to CSV. If file exists, backup first."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = path.replace(".csv", f"_backup_{ts}.csv")
        shutil.copy2(path, bak)
    df.to_csv(path)
    if label:
        print(f"  Saved [{label}]: {path}")


def safe_write(text, path, label=""):
    """Write text file with backup."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = path.replace(".md", f"_backup_{ts}.md").replace(".yaml", f"_backup_{ts}.yaml")
        shutil.copy2(path, bak)
    with open(path, "w") as f:
        f.write(text)
    if label:
        print(f"  Saved [{label}]: {path}")
