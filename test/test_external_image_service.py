from __future__ import annotations

import base64
import unittest
from unittest import mock

from services import external_image_service
from services.config import config


FAKE_SETTINGS = {
    "enabled": True,
    "base_url": "https://image.example.com",
    "api_key": "test-key",
    "timeout_sec": 180,
    "external_models": {"gpt-image-2.5": "gpt-image-2.5"},
}


class ExternalImageModelMapTests(unittest.TestCase):
    def test_model_map_empty_when_disabled(self):
        with mock.patch.object(
            config, "get_external_image_settings",
            return_value={**FAKE_SETTINGS, "enabled": False},
        ):
            self.assertEqual(external_image_service.external_model_map(), {})
            self.assertFalse(external_image_service.is_external_model("gpt-image-2.5"))

    def test_model_map_and_detection_when_enabled(self):
        with mock.patch.object(config, "get_external_image_settings", return_value=FAKE_SETTINGS):
            self.assertEqual(
                external_image_service.external_model_map(),
                {"gpt-image-2.5": "gpt-image-2.5"},
            )
            self.assertTrue(external_image_service.is_external_model("gpt-image-2.5"))
            self.assertFalse(external_image_service.is_external_model("gpt-image-2"))
            self.assertEqual(external_image_service.list_external_models(), ["gpt-image-2.5"])


class ExternalImageUrlConversionTests(unittest.TestCase):
    def test_url_response_is_downloaded_and_converted_to_b64(self):
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"fake-image-body"
        fake_response = mock.Mock()
        fake_response.json.return_value = {
            "created": 123,
            "data": [{"url": "https://image.example.com/a.png", "revised_prompt": "r"}],
        }
        with mock.patch.object(external_image_service, "_download_image", return_value=png_bytes) as download:
            items = external_image_service._to_b64_items(fake_response.json.return_value, 180)

        self.assertEqual(len(items), 1)
        self.assertEqual(base64.b64decode(items[0]["b64_json"]), png_bytes)
        self.assertEqual(items[0]["revised_prompt"], "r")
        download.assert_called_once()

    def test_b64_response_passes_through_without_download(self):
        with mock.patch.object(external_image_service, "_download_image") as download:
            items = external_image_service._to_b64_items(
                {"data": [{"b64_json": "YWJj", "revised_prompt": "p"}]}, 180,
            )
        self.assertEqual(items, [{"b64_json": "YWJj", "revised_prompt": "p"}])
        download.assert_not_called()

    def test_empty_data_raises(self):
        with self.assertRaises(external_image_service.ExternalImageError):
            external_image_service._to_b64_items({"data": []}, 180)


class ImageTypeDetectionTests(unittest.TestCase):
    def test_detect_png(self):
        self.assertEqual(
            external_image_service._detect_image_type(b"\x89PNG\r\n\x1a\n" + b"x"),
            ("png", "image/png"),
        )

    def test_detect_jpeg(self):
        self.assertEqual(
            external_image_service._detect_image_type(b"\xff\xd8\xff" + b"x"),
            ("jpg", "image/jpeg"),
        )

    def test_detect_webp(self):
        raw = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"x"
        self.assertEqual(external_image_service._detect_image_type(raw), ("webp", "image/webp"))

    def test_detect_unknown_falls_back_to_png(self):
        self.assertEqual(external_image_service._detect_image_type(b"zzzz"), ("png", "image/png"))


class ExternalImageRequestTests(unittest.TestCase):
    def test_generate_builds_url_format_payload(self):
        captured = {}

        def fake_post(path, payload, timeout):
            captured["path"] = path
            captured["payload"] = payload
            return {"data": [{"b64_json": "YWJj", "revised_prompt": "p"}]}

        with (
            mock.patch.object(config, "get_external_image_settings", return_value=FAKE_SETTINGS),
            mock.patch.object(external_image_service, "_post_json", side_effect=fake_post),
        ):
            items = external_image_service.generate("a cat", "gpt-image-2.5", n=2, size="1024x1024", quality="high")

        self.assertEqual(captured["path"], "/v1/images/generations")
        self.assertEqual(captured["payload"]["model"], "gpt-image-2.5")
        self.assertEqual(captured["payload"]["response_format"], "url")
        self.assertEqual(captured["payload"]["n"], 2)
        self.assertEqual(captured["payload"]["size"], "1024x1024")
        self.assertEqual(len(items), 1)

    def test_generate_rejects_unmapped_model(self):
        with mock.patch.object(config, "get_external_image_settings", return_value=FAKE_SETTINGS):
            with self.assertRaises(external_image_service.ExternalImageError):
                external_image_service.generate("a cat", "not-mapped")


if __name__ == "__main__":
    unittest.main()
