import os
import sys

from ace_engine import AceClient


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python test_my_sdk.py <image_path>")

    client = AceClient(
        base_url=os.getenv("ACE_ENGINE_BASE_URL", "https://ace-aesthetics.cn/"),
        access_key_id=os.environ["ACE_ENGINE_ACCESS_KEY_ID"],
        sign=os.environ["ACE_ENGINE_SIGN"],
    )

    try:
        result = client.evaluate_all(sys.argv[1])
        print(result)
    finally:
        client.close()


if __name__ == "__main__":
    main()