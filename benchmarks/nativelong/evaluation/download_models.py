#!/usr/bin/env python3
"""Download the pinned evaluation models into the standard HF cache."""
import json
import subprocess
from pathlib import Path

if __name__ == "__main__":
    models = json.loads(Path(__file__).with_name("models.json").read_text())
    for spec in models.values():
        subprocess.run(["hf", "download", spec["repo_id"], *spec["files"],
                        "--revision", spec["revision"]], check=True)
