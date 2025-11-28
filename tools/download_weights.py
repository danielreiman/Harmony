from huggingface_hub import hf_hub_download
from pathlib import Path

repo_id = "microsoft/OmniParser-v2.0"

files = [
    "icon_detect/train_args.yaml",
    "icon_detect/model.pt",
    "icon_detect/model.yaml"
]

local_dir = Path("../models/weights")
local_dir.mkdir(parents=True, exist_ok=True)

for f in files:
    print(f"Downloading {f}...")
    hf_hub_download(
        repo_id=repo_id,
        filename=f,
        local_dir=local_dir,
        local_dir_use_symlinks=False
    )

print("All files downloaded.")
