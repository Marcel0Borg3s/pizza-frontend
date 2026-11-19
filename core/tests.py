"""Tests for the API client used by every integration."""

from __future__ import annotations

import httpx
from django.test import SimpleTestCase, override_settings

from core.api import ApiError
from core.api.client import ApiClient, recent_calls


def _response(status_code: int, payload: object = None) -> httpx.Response:
    request = httpx.Request("GET", "http://127.0.0.1:8000/clients/")
    return httpx.Response(status_code, json=payload, request=request)


@override_settings(PIZZA_API_BASE_URL="http://api.test", PIZZA_API_TIMEOUT=2)
class ApiClientTests(SimpleTestCase):
    """The client must translate HTTP results into typed outcomes."""

    def setUp(self) -> None:
        self.client = ApiClient()

    def test_get_returns_json_payload(self) -> None:
        with self.subTest("success"):
            from unittest.mock import patch

            with patch("core.api.client.httpx.request", return_value=_response(200, {"id": "abc"})):
                self.assertEqual(self.client.get("clients/"), {"id": "abc"})

    def test_builds_url_from_base_and_path(self) -> None:
        from unittest.mock import patch

        with patch("core.api.client.httpx.request", return_value=_response(200, [])) as request:
            self.client.get("/clients/")
        self.assertEqual(request.call_args.args[1], "http://api.test/clients/")

    def test_validation_error_exposes_field_errors(self) -> None:
        from unittest.mock import patch

        payload = {"nickname": ["client with this nickname already exists."]}
        with patch("core.api.client.httpx.request", return_value=_response(400, payload)):
            with self.assertRaises(ApiError) as context:
                self.client.post("clients/", json={"nickname": "joana"})
        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("nickname", context.exception.field_errors)
        self.assertFalse(context.exception.is_offline)

    def test_timeout_is_reported_as_offline(self) -> None:
        from unittest.mock import patch

        with patch("core.api.client.httpx.request", side_effect=httpx.TimeoutException("boom")):
            with self.assertRaises(ApiError) as context:
                self.client.get("clients/")
        self.assertIsNone(context.exception.status_code)
        self.assertTrue(context.exception.is_offline)

    def test_connection_error_is_reported_as_offline(self) -> None:
        from unittest.mock import patch

        with patch("core.api.client.httpx.request", side_effect=httpx.ConnectError("refused")):
            with self.assertRaises(ApiError) as context:
                self.client.get("clients/")
        self.assertTrue(context.exception.is_offline)

    def test_calls_are_recorded_without_bodies(self) -> None:
        from unittest.mock import patch

        with patch("core.api.client.httpx.request", return_value=_response(200, [])):
            self.client.get("clients/")
        last_call = recent_calls()[0]
        self.assertEqual(last_call["method"], "GET")
        self.assertEqual(last_call["path"], "clients/")
        self.assertEqual(last_call["status_code"], 200)
        self.assertNotIn("json", last_call)
