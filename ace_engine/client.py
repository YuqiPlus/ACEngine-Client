import os

import requests


class AceClient:
    def __init__(self, base_url, access_key_id, sign, timeout=30):
        """
        Initialize an AceEngine API client.

        :param base_url: Base API URL, for example https://ace-aesthetics.cn
        :param access_key_id: Access credential ID
        :param sign: API signature key
        :param timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.access_key_id = access_key_id
        self.sign = sign
        self.timeout = timeout
        self.session = requests.Session()

    def _make_response(self, code="500", success=False, message="Unknown Error", data=None):
        """Return a consistent response shape for local client errors."""
        return {"code": str(code), "success": success, "message": message, "data": data}

    def _request_template(self, endpoint, image_path):
        """
        Upload an image to an AceEngine algorithm endpoint.

        :param endpoint: Algorithm endpoint suffix
        :param image_path: Local image path
        """
        url = f"{self.base_url}/ibt/api/file/{endpoint}"

        if not os.path.exists(image_path):
            return self._make_response(code="404", message=f"File does not exist: {image_path}")

        try:
            with open(image_path, "rb") as image_file:
                file_name = os.path.basename(image_path)
                files = {"file": (file_name, image_file, "image/jpeg")}
                payload = {"accessKeyId": self.access_key_id, "sign": self.sign}

                response = self.session.post(url, files=files, data=payload, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
        except requests.exceptions.RequestException as exc:
            return self._make_response(message=f"Network request failed: {exc}")
        except Exception as exc:
            return self._make_response(message=f"Client error: {exc}")

    def mnet(self, image_path):
        """Run MNet aesthetic scoring."""
        return self._request_template("mnet", image_path)

    def sharpness(self, image_path):
        """Run sharpness detection."""
        return self._request_template("sharpness", image_path)

    def icaa17k(self, image_path):
        """Run ICAA17K comprehensive scoring."""
        return self._request_template("icaa17k", image_path)

    def color(self, image_path):
        """Run color quality evaluation."""
        return self._request_template("color", image_path)

    def contrast(self, image_path):
        """Run contrast evaluation."""
        return self._request_template("contrast", image_path)

    def evaluate_all(self, image_path):
        """Run holistic image quality evaluation."""
        return self._request_template("evaluate_all", image_path)

    def noise(self, image_path):
        """Run noise detection."""
        return self._request_template("noise", image_path)

    def roc4mllm(self, image_path):
        """Run multimodal-model related evaluation."""
        return self._request_template("roc4mllm", image_path)

    def physique(self, image_path):
        """Run body/composition evaluation."""
        return self._request_template("physique", image_path)

    def human(self, image_path):
        """Run portrait quality evaluation."""
        return self._request_template("human", image_path)

    def close(self):
        """Close the underlying HTTP session."""
        self.session.close()