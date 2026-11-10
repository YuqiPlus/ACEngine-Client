"""Exercise actual requests/multipart/redirect handling against an isolated HTTP API."""

import base64
import email.parser
import email.policy
import json
import tempfile
import threading
import time
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import requests

from ace_engine import AceClient, AceError, BinaryResult, Client, __version__

ASSET = "11111111-1111-4111-8111-111111111111"
REQUEST = "22222222-2222-4222-8222-222222222222"
TASK = "33333333-3333-4333-8333-333333333333"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/5RkAAAAASUVORK5CYII="
)
KEY, SECRET = "fixture-key-id", "fixture-only-secret"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def handle_request(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        record = {
            "method": self.command,
            "path": self.path,
            "headers": dict(self.headers),
            "raw": body,
        }
        if self.headers.get("Content-Type", "").startswith("multipart/form-data"):
            msg = email.parser.BytesParser(policy=email.policy.default).parsebytes(
                (
                    "Content-Type: "
                    + self.headers["Content-Type"]
                    + "\r\nMIME-Version: 1.0\r\n\r\n"
                ).encode()
                + body
            )
            record["parts"] = [
                (
                    part.get_param("name", header="content-disposition"),
                    part.get_filename(),
                    part.get_content_type(),
                    part.get_payload(decode=True),
                )
                for part in msg.iter_parts()
            ]
        elif body:
            record["body"] = json.loads(body)
        self.server.records.append(record)
        replies = self.server.overrides.get((self.command, self.path), [])
        if replies:
            status, reply, headers, delay = replies.pop(0)
            if delay:
                time.sleep(delay)
        else:
            status, reply, headers = self.default(record)
        if isinstance(reply, dict) or isinstance(reply, list):
            reply = json.dumps(reply).encode()
            headers = {"Content-Type": "application/json", **headers}
        try:
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def default(self, r):
        path = self.path
        data = {}
        if path == "/ibt/v1/assets":
            data = {
                "assetId": ASSET,
                "sha256": "fixture-hash",
                "sizeBytes": len(PNG),
                "mediaType": "image/png",
            }
        elif path == "/ibt/v1/assets/import":
            data = {"assetId": ASSET}
        elif path.startswith("/ibt/v1/assets/"):
            data = {"assetId": ASSET}
        elif path.startswith("/ibt/v1/inferences/") and self.command == "POST":
            key = self.headers["Idempotency-Key"]
            fingerprint = (path, r["body"]["assetId"])
            replayed = key in self.server.invocations
            if replayed and self.server.invocations[key] != fingerprint:
                return 409, {"code": "409", "success": False, "message": "Idempotency conflict"}, {}
            self.server.invocations[key] = fingerprint
            if not replayed:
                self.server.charges += 1
            return (
                200,
                {
                    "code": "200",
                    "success": True,
                    "data": {"score": 8.5},
                    "meta": {
                        "requestId": REQUEST,
                        "assetId": ASSET,
                        "costCents": 1,
                        "durationMs": 100,
                        "replayed": replayed,
                    },
                },
                {"X-Request-Id": REQUEST},
            )
        elif path.startswith("/ibt/v1/inferences/"):
            data = {"requestId": REQUEST, "status": "SUCCEEDED", "costCents": 1}
        elif path == "/ibt/v1/iqa/assets":
            data = {"assetId": ASSET, "kind": "image"}
        elif path == "/ibt/v1/iqa/tasks" and self.command == "POST":
            self.server.jobs += 1
            return (
                202,
                {"code": "200", "success": True, "data": {"taskId": TASK, "status": "QUEUED"}},
                {},
            )
        elif path == "/ibt/v1/iqa/tasks":
            data = [{"taskId": TASK, "status": "SUCCEEDED"}]
        elif path.endswith("/cancel"):
            data = {"taskId": TASK, "status": "CANCEL_REQUESTED"}
        elif path.startswith("/ibt/v1/iqa/tasks/"):
            status = self.server.task_states[0]
            if len(self.server.task_states) > 1:
                self.server.task_states.pop(0)
            data = {
                "taskId": TASK,
                "status": status,
                "result": {"items": [{"metrics": {"brightness": 8}}]},
            }
        elif path == "/ibt/v1/iqa/health":
            data = {"ok": True, "device": "cuda:0"}
        elif path == "/ibt/v1/iqa/config":
            data = r.get("body", {"holistic_weight": {}})
        elif path == "/ibt/api/file/creative-crop" or path == "/ibt/api/file/acellm":
            return 200, b"\xff\xd8\xfffixture-image", {"Content-Type": "image/jpeg"}
        elif path == "/ibt/api/file/highlight":
            return 200, b"fixture-video", {"Content-Type": "video/mp4"}
        elif path.startswith("/ibt/api/file/"):
            data = {"metric": path.rsplit("/", 1)[1], "value": 0.8}
        return 200, {"code": "200", "success": True, "data": data}, {}

    do_GET = handle_request
    do_POST = handle_request
    do_PUT = handle_request


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.records, self.server.overrides = [], {}
        self.server.invocations, self.server.charges, self.server.jobs = {}, 0, 0
        self.server.task_states = ["QUEUED", "RUNNING", "SUCCEEDED"]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.temp = tempfile.TemporaryDirectory()
        self.image = Path(self.temp.name) / "image.png"
        self.image.write_bytes(PNG)
        self.url = "http://127.0.0.1:" + str(self.server.server_port)
        self.client = AceClient(self.url, KEY, SECRET, timeout=2)
        self.client.session.trust_env = False

    def tearDown(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def override(self, method, path, reply, status=200, headers=None, delay=0):
        self.server.overrides.setdefault((method, "/ibt" + path), []).append(
            (status, reply, headers or {}, delay)
        )

    def test_original_constructor_alias_and_api_prefix_do_not_duplicate(self):
        self.assertIs(Client, AceClient)
        self.assertEqual(__version__, "0.2.0")
        with AceClient(self.url + "/ibt/", access_key_id=KEY, access_key_secret=SECRET) as c:
            c.session.trust_env = False
            self.assertEqual(c.api_url, self.url + "/ibt")
            self.assertEqual(c.mnet(self.image)["code"], "200")
        self.assertTrue(all("/ibt/ibt/" not in r["path"] for r in self.server.records))
        for kwargs in [
            dict(base_url="https://user:pass@example.org"),
            dict(base_url="https://example.org/?secret=x"),
            dict(access_key_id=KEY, sign=SECRET, token="jwt"),
            dict(access_key_id=KEY, sign=SECRET, access_key_secret="different"),
            dict(access_key_id=KEY, sign=SECRET, timeout=0),
            dict(access_key_id=KEY, sign=SECRET, api_prefix="/../bad"),
        ]:
            with self.subTest(kwargs=list(kwargs)):
                with self.assertRaises(ValueError):
                    AceClient(**kwargs)

    def test_reusable_asset_then_two_models_and_identical_key_replay_charges_once(self):
        uploaded = self.client.upload_asset(self.image)
        self.assertEqual(uploaded["data"]["assetId"], ASSET)
        part = self.server.records[0]["parts"][0]
        self.assertEqual(part[2], "image/png")
        self.assertEqual(part[3], PNG)
        self.assertEqual(self.server.records[0]["headers"]["X-API-Key-Secret"], SECRET)
        first = self.client.mnet(asset_id=ASSET, idempotency_key="stable-key")
        again = self.client.infer("mnet", ASSET, idempotency_key="stable-key")
        self.assertFalse(first["meta"]["replayed"])
        self.assertTrue(again["meta"]["replayed"])
        self.assertEqual(self.server.charges, 1)
        self.assertEqual(again["meta"]["idempotencyKey"], "stable-key")
        self.assertEqual(again["meta"]["costCents"], 1)
        self.client.icaa17k(asset_id=ASSET, idempotency_key="another-key")
        self.assertEqual(self.server.charges, 2)
        self.assertEqual(sum(r["path"] == "/ibt/v1/assets" for r in self.server.records), 1)
        conflict = self.client.infer("icaa17k", ASSET, idempotency_key="stable-key")
        self.assertEqual(conflict["httpStatus"], 409)
        self.assertEqual(self.server.charges, 2)
        self.assertEqual(self.client.get_inference(REQUEST)["data"]["status"], "SUCCEEDED")

    def test_file_convenience_uses_new_flow_and_legacy_mode_is_explicit(self):
        result = self.client.icaa17k(self.image)
        self.assertEqual(result["code"], "200")
        self.assertEqual(
            [r["path"] for r in self.server.records],
            ["/ibt/v1/assets", "/ibt/v1/inferences/icaa17k"],
        )
        self.client.mnet(self.image, legacy=True, idempotency_key="legacy-key")
        last = self.server.records[-1]
        self.assertEqual(last["path"], "/ibt/api/file/mnet")
        self.assertEqual(last["headers"]["Idempotency-Key"], "legacy-key")
        parts = {part[0]: part[3] for part in last["parts"]}
        self.assertEqual(parts["accessKeyId"].decode(), KEY)
        self.assertEqual(parts["sign"].decode(), SECRET)

    def test_existing_quality_methods_and_new_exposure_match_actual_endpoints(self):
        methods = [
            "sharpness",
            "color",
            "contrast",
            "evaluate_all",
            "noise",
            "roc4mllm",
            "physique",
            "human",
            "exposure",
            "holistic",
            "overall_iqa",
            "paa",
        ]
        for method in methods:
            with self.subTest(method=method):
                reply = getattr(self.client, method)(self.image)
                self.assertEqual(reply["data"]["metric"], method)
                self.assertNotIn("X-API-Key-Secret", self.server.records[-1]["headers"])

    def test_http_business_errors_and_request_ids_are_preserved_but_credentials_are_redacted(self):
        self.override(
            "POST",
            "/v1/inferences/mnet",
            {
                "code": "402",
                "success": False,
                "message": "quota: " + SECRET,
                "data": {"echo": SECRET},
            },
            402,
            {"X-Request-Id": REQUEST},
        )
        result = self.client.infer("mnet", ASSET, idempotency_key="recover-key")
        self.assertEqual(result["code"], "402")
        self.assertEqual(result["httpStatus"], 402)
        self.assertEqual(result["meta"]["requestId"], REQUEST)
        self.assertNotIn(SECRET, json.dumps(result))
        self.override(
            "POST", "/api/file/noise", {"code": "503", "success": False, "message": "GPU busy"}
        )
        self.assertEqual(self.client.noise(self.image)["code"], "503")

    def test_strict_mode_exposes_structured_recovery_details(self):
        self.client.raise_for_errors = True
        self.override(
            "POST",
            "/v1/inferences/mnet",
            {"code": "503", "success": False, "message": "busy " + SECRET, "retryable": True},
            503,
            {"X-Request-Id": REQUEST},
        )
        with self.assertRaises(AceError) as caught:
            self.client.mnet(asset_id=ASSET, idempotency_key="same")
        self.assertEqual(caught.exception.idempotency_key, "same")
        self.assertEqual(caught.exception.request_id, REQUEST)
        self.assertNotIn(SECRET, str(caught.exception))
        self.assertEqual(caught.exception.http_status, 503)

    def test_timeouts_never_retry_or_fall_back_and_keep_the_same_logical_request_key(self):
        with patch.object(
            self.client.session, "request", side_effect=requests.ReadTimeout("echo " + SECRET)
        ) as call:
            result = self.client.mnet(asset_id=ASSET, idempotency_key="keep-me")
            self.assertEqual(call.call_count, 1)
            self.assertTrue(result["outcomeUnknown"])
            self.assertEqual(result["meta"]["idempotencyKey"], "keep-me")
            self.assertEqual(result["meta"]["assetId"], ASSET)
            self.assertNotIn(SECRET, str(result))
        with patch.object(
            self.client.session, "request", side_effect=requests.ReadTimeout()
        ) as call:
            result = self.client.noise(self.image)
            self.assertFalse(result["retryable"])
            self.assertEqual(call.call_count, 1)

    def test_redirects_html_and_invalid_json_cannot_become_successes_or_forward_secrets(self):
        self.override(
            "POST",
            "/v1/inferences/mnet",
            b"redirect",
            302,
            {"Location": self.url + "/steal", "Content-Type": "text/plain"},
        )
        self.assertFalse(self.client.mnet(asset_id=ASSET)["success"])
        self.assertEqual(len(self.server.records), 1)
        self.override(
            "POST",
            "/v1/inferences/mnet",
            b"<html>" + SECRET.encode() + b"</html>",
            500,
            {"Content-Type": "text/html"},
        )
        result = self.client.mnet(asset_id=ASSET)
        self.assertEqual(result["httpStatus"], 500)
        self.assertNotIn(SECRET, str(result))
        self.override("POST", "/v1/inferences/mnet", [])
        self.assertEqual(self.client.mnet(asset_id=ASSET)["errorType"], "protocol")

    def test_user_tokens_are_sent_only_on_managed_apis_and_never_fallback_to_file_credentials(self):
        with AceClient(self.url, token="fixture-user-token") as c:
            c.session.trust_env = False
            self.assertEqual(c.upload_asset(self.image)["code"], "200")
            self.assertEqual(
                self.server.records[-1]["headers"]["Authorization"], "Bearer fixture-user-token"
            )
            self.assertNotIn("X-API-Key-Id", self.server.records[-1]["headers"])
            count = len(self.server.records)
            self.assertEqual(c.noise(self.image)["code"], "400")
            self.assertEqual(len(self.server.records), count)

    def test_local_input_failures_and_path_injection_make_no_requests(self):
        for result in [
            self.client.mnet(),
            self.client.mnet(self.image, asset_id=ASSET),
            self.client.mnet(self.temp.name),
            self.client.mnet(Path(self.temp.name) / "missing"),
            self.client.infer("bad", ASSET),
            self.client.get_inference("../../secret"),
            self.client.mnet(asset_id=ASSET, idempotency_key="bad\nkey"),
        ]:
            self.assertFalse(result["success"])
        large = Path(self.temp.name) / "large.png"
        with large.open("wb") as stream:
            stream.truncate(21 * 1024 * 1024)
        self.assertEqual(self.client.upload_asset(large)["code"], "413")
        self.assertEqual(self.server.records, [])

    def test_iqa_task_creation_polling_preserves_kind_selections_and_recovery_metadata(self):
        result = self.client.iqa(
            self.image, selections=["exposure"], idempotency_key="iqa-key", poll_interval=0.001
        )
        self.assertEqual(result["data"]["status"], "SUCCEEDED")
        self.assertEqual(result["meta"]["idempotencyKey"], "iqa-key")
        self.assertEqual(result["meta"]["taskId"], TASK)
        creation = next(
            r
            for r in self.server.records
            if r["method"] == "POST" and r["path"] == "/ibt/v1/iqa/tasks"
        )
        self.assertEqual(
            creation["body"], {"assetIds": [ASSET], "selections": ["exposure"], "kind": "image"}
        )
        self.assertEqual(creation["headers"]["Idempotency-Key"], "iqa-key")
        self.assertEqual(self.server.jobs, 1)
        self.assertEqual(self.client.list_iqa_tasks()["data"][0]["taskId"], TASK)
        self.assertEqual(self.client.cancel_iqa_task(TASK)["data"]["status"], "CANCEL_REQUESTED")

    def test_iqa_wait_timeout_does_not_resubmit_or_cancel_the_running_job(self):
        self.server.task_states = ["RUNNING"]
        result = self.client.iqa(
            self.image, selections=["exposure"], wait_timeout=0.02, poll_interval=0.005
        )
        self.assertEqual(result["code"], "408")
        self.assertEqual(result["meta"]["taskId"], TASK)
        self.assertIn("idempotencyKey", result["meta"])
        self.assertEqual(self.server.jobs, 1)
        self.assertFalse(any(r["path"].endswith("/cancel") for r in self.server.records))
        self.server.task_states = ["SUCCEEDED"]
        self.assertEqual(self.client.get_iqa_task(TASK)["data"]["status"], "SUCCEEDED")

    def test_iqa_partial_failed_and_cancelled_statuses_are_distinguished(self):
        self.server.task_states = ["PARTIAL"]
        self.assertEqual(self.client.wait_iqa_task(TASK)["data"]["status"], "PARTIAL")
        for status in ["FAILED", "CANCELLED", "UNKNOWN"]:
            self.server.task_states = [status]
            reply = self.client.wait_iqa_task(TASK)
            self.assertFalse(reply["success"])
            self.assertEqual(reply["meta"]["taskId"], TASK)
        self.server.task_states = ["RUNNING"]
        self.client.raise_for_errors = True
        with self.assertRaises(AceError) as caught:
            self.client.iqa(
                self.image, selections=["noise"], wait_timeout=0.01, poll_interval=0.005
            )
        self.assertEqual(caught.exception.task_id, TASK)
        self.assertIsNotNone(caught.exception.idempotency_key)

    def test_iqa_rejects_bad_selections_duplicate_assets_missing_files_before_submission(self):
        for selections in [["fake"], ["exposure", "exposure"], ["holistic"], "noise"]:
            self.assertFalse(self.client.iqa(self.image, selections=selections)["success"])
        self.assertFalse(self.client.iqa([self.image, Path(self.temp.name) / "missing"])["success"])
        self.assertFalse(self.client.create_iqa_task([ASSET, ASSET])["success"])
        self.assertFalse(
            self.client.create_iqa_task([ASSET], kind="video", selections=["overall_iqa"])[
                "success"
            ]
        )
        self.assertFalse(self.client.iqa(self.image, idempotency_key="bad key")["success"])
        self.assertEqual(self.server.records, [])

    def test_binary_outputs_keep_content_types_and_explicit_save_protects_existing_files(self):
        result = self.client.creative_crop(self.image)
        self.assertIsInstance(result, BinaryResult)
        self.assertEqual(result.content_type, "image/jpeg")
        output = Path(self.temp.name) / "result.jpg"
        result.save(output)
        with self.assertRaises(FileExistsError):
            result.save(output)
        result.save(output, overwrite=True)
        self.assertEqual(output.read_bytes(), result.content)
        reply = self.client.acellm(self.image, selections=["exposure", "sharpness"])
        self.assertIsInstance(reply, BinaryResult)
        parts = self.server.records[-1]["parts"]
        self.assertEqual(
            [p[3].decode() for p in parts if p[0] == "selections"], ["exposure", "sharpness"]
        )
        self.assertIsInstance(self.client.highlight(self.image, query="goal"), BinaryResult)
        self.override(
            "POST",
            "/api/file/creative-crop",
            {"code": "503", "success": False, "message": "Unavailable"},
            503,
        )
        self.assertEqual(self.client.creative_crop(self.image)["code"], "503")

    def test_context_manager_and_close_are_idempotent_and_do_not_make_requests(self):
        self.client.close()
        self.client.close()
        self.assertEqual(self.client.get_asset(ASSET)["message"], "Client is closed")
        self.assertEqual(self.server.records, [])


if __name__ == "__main__":
    unittest.main()
