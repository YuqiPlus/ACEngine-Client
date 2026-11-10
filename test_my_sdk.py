"""Explicit invocation example; not an automatic test or load generator."""

import argparse
import json
import os
import sys

from ace_engine import AceClient, AceError


def main():
    parser = argparse.ArgumentParser(
        description="Call ACE with credentials from environment variables"
    )
    parser.add_argument("image_path")
    parser.add_argument(
        "--model", choices=["mnet", "icaa17k", "noise", "exposure", "iqa"], default="mnet"
    )
    parser.add_argument(
        "--idempotency-key", help="Reuse the persisted key only for the same logical request"
    )
    parser.add_argument("--selections", nargs="+", default=["exposure"])
    args = parser.parse_args()
    token = os.getenv("ACE_ENGINE_TOKEN")
    credentials = (
        {"token": token}
        if token
        else {
            "access_key_id": os.getenv("ACE_ENGINE_ACCESS_KEY_ID"),
            "access_key_secret": os.getenv("ACE_ENGINE_ACCESS_KEY_SECRET")
            or os.getenv("ACE_ENGINE_SIGN"),
        }
    )
    try:
        with AceClient(
            base_url=os.getenv("ACE_ENGINE_BASE_URL", "https://ace-aesthetics.cn"),
            api_prefix=os.getenv("ACE_ENGINE_API_PREFIX", "/ibt"),
            raise_for_errors=True,
            **credentials,
        ) as client:
            if args.model == "iqa":
                result = client.iqa(
                    args.image_path,
                    selections=args.selections,
                    idempotency_key=args.idempotency_key,
                )
            elif args.model in ("mnet", "icaa17k"):
                result = getattr(client, args.model)(
                    args.image_path, idempotency_key=args.idempotency_key
                )
            else:
                result = getattr(client, args.model)(args.image_path)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except AceError as error:
        print(json.dumps(error.response, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
