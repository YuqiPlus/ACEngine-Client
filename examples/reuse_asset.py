"""Run explicitly: this example starts two potentially billable model calls."""

import os
import sys
from ace_engine import AceClient

if len(sys.argv) != 2:
    raise SystemExit("Usage: python examples/reuse_asset.py <image_path>")

with AceClient(
    access_key_id=os.environ["ACE_ENGINE_ACCESS_KEY_ID"],
    access_key_secret=os.environ["ACE_ENGINE_ACCESS_KEY_SECRET"],
    raise_for_errors=True,
) as client:
    asset = client.upload_asset(sys.argv[1])["data"]["assetId"]
    for model in ("mnet", "icaa17k"):
        # In a real application persist key + asset + model before sending.
        key = client.new_idempotency_key()
        response = client.infer(model, asset, idempotency_key=key)
        print(model, response["data"], response["meta"])
