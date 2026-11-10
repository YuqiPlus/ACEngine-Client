"""Public ACE APIs: private assets, billed inferences, IQA jobs and file APIs."""

import mimetypes
import re
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter

from .results import AceError, BinaryResult


class AceClient:
    """Synchronous client. Methods return server envelopes unless strict mode is enabled.

    Instances own a Session and should not be shared between concurrent threads.
    No request is automatically retried, and redirects never forward credentials.
    """

    MODELS = frozenset(("mnet", "icaa17k"))
    IQA_METRICS = frozenset(
        (
            "sharpness",
            "color_accuracy",
            "saturation",
            "exposure",
            "contrast",
            "noise",
            "holistic",
            "overall_iqa",
        )
    )
    DEFAULT_IQA_METRICS = ("sharpness", "exposure", "contrast", "noise")
    PENDING_TASKS = frozenset(("QUEUED", "RUNNING", "CANCEL_REQUESTED"))
    TERMINAL_TASKS = frozenset(("SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"))

    def __init__(
        self,
        base_url="https://ace-aesthetics.cn",
        access_key_id=None,
        sign=None,
        timeout=120,
        *,
        access_key_secret=None,
        token=None,
        api_prefix="/ibt",
        raise_for_errors=False,
    ):
        if not isinstance(base_url, str):
            raise ValueError("base_url must be an HTTP(S) URL")
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in ("https", "http")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or any(c.isspace() for c in base_url)
        ):
            raise ValueError("base_url must be HTTP(S), without credentials, query or fragment")
        if sign is not None and access_key_secret is not None and sign != access_key_secret:
            raise ValueError("sign and access_key_secret must match when both are supplied")
        secret = access_key_secret if access_key_secret is not None else sign
        if token is not None and (access_key_id is not None or secret is not None):
            raise ValueError("Use either API-Key credentials or a user token, not both")
        credentials = (token,) if token is not None else (access_key_id, secret)
        if any(
            not isinstance(value, str) or not value.strip() or "\r" in value or "\n" in value
            for value in credentials
        ):
            raise ValueError("Provide a complete API-Key pair or a user token")
        if not isinstance(api_prefix, str) or (
            api_prefix and not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+/?", api_prefix)
        ):
            raise ValueError("api_prefix must be empty or a root-relative path")
        if not self._positive(timeout):
            raise ValueError("timeout must be a positive number of seconds")
        self.base_url = base_url.rstrip("/")
        prefix = api_prefix.rstrip("/")
        self.api_url = (
            self.base_url
            if not prefix or self.base_url.endswith(prefix)
            else self.base_url + prefix
        )
        self.access_key_id, self.sign, self.token = access_key_id, secret, token
        self.timeout = timeout
        self.raise_for_errors = raise_for_errors
        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=0))
        self.session.mount("http://", HTTPAdapter(max_retries=0))
        self._closed = False

    @staticmethod
    def _positive(value):
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and 0 < value < float("inf")
        )

    @staticmethod
    def new_idempotency_key():
        return str(uuid.uuid4())

    @staticmethod
    def _ok(value):
        return (
            isinstance(value, dict)
            and str(value.get("code")) == "200"
            and value.get("success") is not False
        )

    def _redact(self, value):
        if isinstance(value, str):
            for credential in (self.sign, self.token, self.access_key_id):
                if credential:
                    value = value.replace(credential, "[REDACTED]")
            return value
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        if isinstance(value, dict):
            return {key: self._redact(item) for key, item in value.items()}
        return value

    def _finish(self, value):
        if self._ok(value):
            return value
        value = self._redact(value)
        if self.raise_for_errors:
            raise AceError(value)
        return value

    def _failure(self, code, message, *, context=None, error_type="client", **extra):
        value = {
            "code": str(code),
            "success": False,
            "message": message,
            "data": None,
            "errorType": error_type,
            **extra,
        }
        if context:
            value["meta"] = dict(context)
        return self._finish(value)

    def _key(self, value):
        key = self.new_idempotency_key() if value is None else value
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key):
            raise ValueError(
                "idempotency_key must contain 1-128 letters, digits, '.', '_', ':' or '-'"
            )
        return key

    @staticmethod
    def _identifier(value):
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError("Expected a canonical UUID")
        return value

    def _request(
        self,
        method,
        path,
        *,
        data=None,
        files=None,
        json=None,
        context=None,
        binary=None,
        legacy=False,
        timeout=None,
    ):
        if self._closed:
            return self._failure(400, "Client is closed", context=context)
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        elif not legacy:
            headers.update({"X-API-Key-Id": self.access_key_id, "X-API-Key-Secret": self.sign})
        if context and context.get("idempotencyKey"):
            headers["Idempotency-Key"] = context["idempotencyKey"]
        if binary:
            headers["Accept"] = binary + "/*, application/json"
        try:
            response = self.session.request(
                method,
                self.api_url + path,
                headers=headers,
                data=data,
                files=files,
                json=json,
                timeout=self.timeout if timeout is None else timeout,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            return self._failure(
                500,
                "Network request failed ({})".format(type(error).__name__),
                context=context,
                error_type="network",
                retryable=method == "GET" or bool(context and context.get("idempotencyKey")),
                outcomeUnknown=method != "GET",
                httpStatus=None,
            )
        try:
            status = response.status_code
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            request_id = response.headers.get("X-Request-Id")
            if (
                binary
                and 200 <= status < 300
                and (
                    content_type.startswith(binary + "/")
                    or content_type == "application/octet-stream"
                )
            ):
                return BinaryResult(response.content, content_type, request_id)
            try:
                value = response.json()
            except ValueError:
                return self._failure(
                    status if status >= 300 else 502,
                    "Unexpected non-JSON response (HTTP {})".format(status),
                    context=context,
                    error_type="protocol",
                    httpStatus=status,
                    retryable=status in (429, 502, 503, 504),
                    outcomeUnknown=method != "GET",
                )
            if not isinstance(value, dict):
                return self._failure(
                    502,
                    "Expected a JSON response object",
                    context=context,
                    error_type="protocol",
                    httpStatus=status,
                )
            value = dict(value)
            meta = value.get("meta")
            value["meta"] = {
                **(dict(context) if context else {}),
                **(meta if isinstance(meta, dict) else {}),
            }
            if request_id:
                value["meta"].setdefault("requestId", request_id)
            if not 200 <= status < 300:
                value.update({"success": False, "httpStatus": status})
                if str(value.get("code", "200")) == "200":
                    value["code"] = str(status)
                value.setdefault("message", "HTTP {}".format(status))
                value.setdefault("retryable", status in (429, 502, 503, 504))
                value.setdefault("errorType", "http")
            elif not self._ok(value):
                value.setdefault("code", "502")
                value["success"] = False
                value.setdefault("message", "Server did not confirm success")
                value.setdefault("errorType", "business")
                value["httpStatus"] = status
            elif binary:
                return self._failure(
                    502,
                    "Expected binary output but received JSON",
                    context=context,
                    error_type="protocol",
                    httpStatus=status,
                )
            return self._finish(value)
        finally:
            response.close()

    def _upload(
        self, path, file_path, *, fields=None, kind="image", context=None, legacy=False, binary=None
    ):
        try:
            file = Path(file_path)
            if not file.is_file():
                return self._failure(
                    404, "Input file does not exist", context=context, error_type="file"
                )
            size = file.stat().st_size
            limit = (100 if kind == "video" else 20) * 1024 * 1024
            if not 0 < size <= limit:
                return self._failure(
                    413 if size > limit else 400,
                    "Input file is empty or exceeds the size limit",
                    context=context,
                    error_type="file",
                )
            media = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            with file.open("rb") as source:
                return self._request(
                    "POST",
                    path,
                    files={"file": (file.name, source, media)},
                    data=fields,
                    legacy=legacy,
                    context=context,
                    binary=binary,
                )
        except (OSError, TypeError, ValueError):
            return self._failure(
                400, "Input file cannot be read", context=context, error_type="file"
            )

    def upload_asset(self, image_path):
        """Upload a private image, returning data.assetId. No inference is started."""
        return self._upload("/v1/assets", image_path)

    def import_asset(self, image_url):
        """Ask the backend to import an allowed URL; the SDK never downloads it."""
        if not isinstance(image_url, str) or not image_url.strip():
            return self._failure(400, "image_url is required")
        return self._request("POST", "/v1/assets/import", json={"imageUrl": image_url})

    def get_asset(self, asset_id):
        try:
            self._identifier(asset_id)
        except (ValueError, TypeError, AttributeError):
            return self._failure(400, "Invalid asset_id")
        return self._request("GET", "/v1/assets/" + asset_id)

    def infer(self, model, asset_id, *, idempotency_key=None):
        try:
            if model not in self.MODELS:
                raise ValueError("Supported models are mnet and icaa17k")
            self._identifier(asset_id)
            key = self._key(idempotency_key)
        except (ValueError, TypeError, AttributeError) as error:
            return self._failure(400, str(error))
        return self._request(
            "POST",
            "/v1/inferences/" + model,
            json={"assetId": asset_id},
            context={"assetId": asset_id, "idempotencyKey": key, "model": model},
        )

    def get_inference(self, request_id):
        try:
            self._identifier(request_id)
        except (ValueError, TypeError, AttributeError):
            return self._failure(400, "Invalid request_id")
        return self._request("GET", "/v1/inferences/" + request_id)

    def _model(self, model, image_path, asset_id, key, legacy):
        try:
            key = self._key(key)
        except ValueError as error:
            return self._failure(400, str(error))
        if (image_path is None) == (asset_id is None):
            return self._failure(400, "Provide exactly one of image_path or asset_id")
        if legacy:
            if asset_id is not None:
                return self._failure(400, "legacy=True requires an image file")
            return self._file(model, image_path, idempotency_key=key)
        if image_path is not None:
            reply = self._upload(
                "/v1/assets",
                image_path,
                context={"idempotencyKey": key, "model": model, "stage": "upload"},
            )
            if not self._ok(reply):
                return reply
            asset_id = (
                reply.get("data", {}).get("assetId")
                if isinstance(reply.get("data"), dict)
                else None
            )
            if not asset_id:
                return self._failure(
                    502,
                    "Upload response omitted assetId",
                    context={"idempotencyKey": key},
                    error_type="protocol",
                )
        return self.infer(model, asset_id, idempotency_key=key)

    def mnet(self, image_path=None, *, asset_id=None, idempotency_key=None, legacy=False):
        return self._model("mnet", image_path, asset_id, idempotency_key, legacy)

    def icaa17k(self, image_path=None, *, asset_id=None, idempotency_key=None, legacy=False):
        return self._model("icaa17k", image_path, asset_id, idempotency_key, legacy)

    def _file(
        self, endpoint, file_path, *, fields=None, kind="image", binary=None, idempotency_key=None
    ):
        if self.token:
            return self._failure(
                400,
                "File compatibility APIs require API-Key credentials; use asset/inference or IQA task APIs for user tokens",
            )
        payload = {"accessKeyId": self.access_key_id, "sign": self.sign}
        if fields:
            payload.update(fields)
        return self._upload(
            "/api/file/" + endpoint,
            file_path,
            fields=payload,
            kind=kind,
            binary=binary,
            legacy=True,
            context={"idempotencyKey": idempotency_key} if idempotency_key else None,
        )

    # Existing names and server response fields remain intact.
    def sharpness(self, image_path):
        return self._file("sharpness", image_path)

    def color(self, image_path):
        return self._file("color", image_path)

    def contrast(self, image_path):
        return self._file("contrast", image_path)

    def evaluate_all(self, image_path):
        return self._file("evaluate_all", image_path)

    def noise(self, image_path):
        return self._file("noise", image_path)

    def roc4mllm(self, image_path):
        return self._file("roc4mllm", image_path)

    def physique(self, image_path):
        return self._file("physique", image_path)

    def human(self, image_path):
        return self._file("human", image_path)

    def exposure(self, image_path):
        return self._file("exposure", image_path)

    def holistic(self, image_path):
        return self._file("holistic", image_path)

    def overall_iqa(self, image_path):
        return self._file("overall_iqa", image_path)

    def paa(self, image_path):
        return self._file("paa", image_path)

    def creative_crop(self, image_path):
        return self._file("creative-crop", image_path, binary="image")

    def highlight(self, video_path, *, query=""):
        return self._file(
            "highlight", video_path, fields={"query": query}, kind="video", binary="video"
        )

    def videomamba(self, video_path, *, query=""):
        return self._file("videomamba", video_path, fields={"query": query}, kind="video")

    def acellm(self, image_path, *, selections=("exposure",)):
        if (
            not isinstance(selections, (list, tuple))
            or not selections
            or any(not isinstance(item, str) for item in selections)
        ):
            return self._failure(400, "selections must be a non-empty list of metric names")
        return self._file(
            "acellm", image_path, fields={"selections": list(selections)}, binary="image"
        )

    def iqa_health(self):
        return self._request("GET", "/v1/iqa/health")

    def get_iqa_config(self):
        return self._request("GET", "/v1/iqa/config")

    def configure_iqa(self, config):
        if not isinstance(config, dict):
            return self._failure(400, "config must be an object")
        return self._request("PUT", "/v1/iqa/config", json=config)

    def upload_iqa_asset(self, file_path, *, kind="image"):
        if kind not in ("image", "video"):
            return self._failure(400, "kind must be image or video")
        return self._upload("/v1/iqa/assets", file_path, kind=kind, fields={"kind": kind})

    def create_iqa_task(
        self, asset_ids, *, selections=DEFAULT_IQA_METRICS, kind="image", idempotency_key=None
    ):
        try:
            if (
                kind not in ("image", "video")
                or not isinstance(asset_ids, (list, tuple))
                or not 1 <= len(asset_ids) <= (1 if kind == "video" else 50)
            ):
                raise ValueError("Provide 1-50 image asset IDs or one video asset ID")
            if len(set(asset_ids)) != len(asset_ids):
                raise ValueError("asset_ids must not contain duplicates")
            for asset_id in asset_ids:
                self._identifier(asset_id)
            if (
                not isinstance(selections, (list, tuple))
                or not selections
                or len(set(selections)) != len(selections)
                or not self.IQA_METRICS.issuperset(selections)
            ):
                raise ValueError("Invalid IQA selections")
            base = self.IQA_METRICS - {"holistic", "overall_iqa"}
            if "holistic" in selections and not base.intersection(selections):
                raise ValueError("holistic requires at least one base metric")
            if kind == "video" and "overall_iqa" in selections:
                raise ValueError("overall_iqa is not available for video tasks")
            key = self._key(idempotency_key)
        except (ValueError, TypeError, AttributeError) as error:
            return self._failure(400, str(error))
        return self._request(
            "POST",
            "/v1/iqa/tasks",
            json={"assetIds": list(asset_ids), "selections": list(selections), "kind": kind},
            context={"idempotencyKey": key, "assetIds": list(asset_ids)},
        )

    def list_iqa_tasks(self):
        return self._request("GET", "/v1/iqa/tasks")

    def _iqa_task(self, task_id, cancel=False, timeout=None):
        try:
            self._identifier(task_id)
        except (ValueError, TypeError, AttributeError):
            return self._failure(400, "Invalid task_id")
        return self._request(
            "POST" if cancel else "GET",
            "/v1/iqa/tasks/" + task_id + ("/cancel" if cancel else ""),
            context={"taskId": task_id},
            timeout=timeout,
        )

    def get_iqa_task(self, task_id):
        return self._iqa_task(task_id)

    def cancel_iqa_task(self, task_id):
        return self._iqa_task(task_id, cancel=True)

    def wait_iqa_task(self, task_id, *, wait_timeout=300, poll_interval=1):
        if not self._positive(wait_timeout) or not self._positive(poll_interval):
            return self._failure(400, "wait_timeout and poll_interval must be positive seconds")
        deadline = time.monotonic() + wait_timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return self._failure(
                    408,
                    "Stopped waiting; the server task has NOT been cancelled",
                    context={"taskId": task_id},
                    error_type="wait_timeout",
                    retryable=True,
                )
            reply = self._iqa_task(task_id, timeout=min(self.timeout, remaining))
            if not self._ok(reply):
                return reply
            task = reply.get("data")
            status = task.get("status") if isinstance(task, dict) else None
            if status in self.TERMINAL_TASKS:
                if status not in ("SUCCEEDED", "PARTIAL"):
                    return self._failure(
                        409 if status == "CANCELLED" else 500,
                        task.get("message") or "IQA task {}".format(status),
                        context={"taskId": task_id},
                        error_type="task",
                        task=task,
                    )
                return reply
            if status not in self.PENDING_TASKS:
                return self._failure(
                    502,
                    "Unknown IQA task status",
                    context={"taskId": task_id},
                    error_type="protocol",
                )
            time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))

    def iqa(
        self,
        file_paths,
        *,
        selections=DEFAULT_IQA_METRICS,
        kind="image",
        wait=True,
        idempotency_key=None,
        wait_timeout=300,
        poll_interval=1,
    ):
        paths = [file_paths] if isinstance(file_paths, (str, Path)) else file_paths
        if not isinstance(paths, (list, tuple)) or not 1 <= len(paths) <= (
            1 if kind == "video" else 50
        ):
            return self._failure(400, "Provide 1-50 image paths or one video path")
        # Validate before uploading: a bad selection or missing second file must
        # not leave avoidable partial uploads in the user's private storage.
        try:
            key = self._key(idempotency_key)
            if (
                kind not in ("image", "video")
                or not isinstance(selections, (list, tuple))
                or not selections
                or len(set(selections)) != len(selections)
                or not self.IQA_METRICS.issuperset(selections)
            ):
                raise ValueError("Invalid IQA selections or media kind")
            if "holistic" in selections and not (
                self.IQA_METRICS - {"holistic", "overall_iqa"}
            ).intersection(selections):
                raise ValueError("holistic requires at least one base metric")
            if kind == "video" and "overall_iqa" in selections:
                raise ValueError("overall_iqa is not available for video tasks")
            if wait and (not self._positive(wait_timeout) or not self._positive(poll_interval)):
                raise ValueError("wait_timeout and poll_interval must be positive seconds")
            for path in paths:
                file = Path(path)
                if (
                    not file.is_file()
                    or not 0 < file.stat().st_size <= (100 if kind == "video" else 20) * 1024 * 1024
                ):
                    raise ValueError("Input file is missing, empty or too large")
        except (ValueError, TypeError, OSError) as error:
            return self._failure(400, str(error))
        assets = []
        for path in paths:
            uploaded = self._upload(
                "/v1/iqa/assets",
                path,
                kind=kind,
                fields={"kind": kind},
                context={"idempotencyKey": key, "assetIds": list(assets), "stage": "upload"},
            )
            if not self._ok(uploaded):
                return uploaded
            asset_id = (
                uploaded.get("data", {}).get("assetId")
                if isinstance(uploaded.get("data"), dict)
                else None
            )
            if not asset_id:
                return self._failure(502, "Upload response omitted assetId", error_type="protocol")
            assets.append(asset_id)
        created = self.create_iqa_task(
            assets, selections=selections, kind=kind, idempotency_key=key
        )
        if not self._ok(created) or not wait:
            return created
        task_id = (
            created.get("data", {}).get("taskId") if isinstance(created.get("data"), dict) else None
        )
        if not task_id:
            return self._failure(
                502,
                "Task response omitted taskId",
                error_type="protocol",
                context=created.get("meta"),
            )
        try:
            result = self.wait_iqa_task(
                task_id, wait_timeout=wait_timeout, poll_interval=poll_interval
            )
        except AceError as error:
            error.response["meta"] = {**created.get("meta", {}), **error.response.get("meta", {})}
            raise AceError(error.response) from None
        result["meta"] = {**created.get("meta", {}), **result.get("meta", {})}
        return result

    def close(self):
        if not self._closed:
            self.session.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
