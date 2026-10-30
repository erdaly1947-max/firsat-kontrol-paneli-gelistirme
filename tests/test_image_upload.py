from __future__ import annotations

import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from PIL import Image

import analysis_report


def image_bytes(image_format: str = "PNG") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (5, 4), (25, 60, 120)).save(output, format=image_format)
    return output.getvalue()


def _mock_http_response(payload, content_type: str = "application/json"):
    response = mock.MagicMock()
    response.__enter__.return_value = response
    response.status = 200
    response.headers = {"Content-Type": content_type}
    response.read.return_value = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    return response


def _mock_http_error(url: str, status: int, payload: str):
    return urllib.error.HTTPError(url, status, "mock error", {}, io.BytesIO(payload.encode("utf-8")))


class ImageRelayRoutingTests(unittest.TestCase):
    def test_manifest_and_image_upload_routes_use_production_relay(self) -> None:
        production_base = "https://firsat-kontrol-market-relay.onrender.com"
        config = {"upload_url": analysis_report.UPLOAD_URL, "upload_token": "test-token"}

        self.assertEqual(analysis_report.IMAGE_RELAY_BASE_URL, production_base)
        self.assertEqual(analysis_report.IMAGE_BASE_URL, production_base)
        for route in ("sign-upload", "stage", "commit", "abort"):
            with self.subTest(route=route):
                self.assertEqual(
                    analysis_report._image_upload_endpoint(config, route),
                    f"{production_base}/api/images/{route}",
                )
        with self.assertRaises(ValueError):
            analysis_report._image_upload_endpoint(config, "unknown")

        with mock.patch("analysis_report.urllib.request.urlopen", side_effect=[
            _mock_http_response({"ok": True, "service": "firsat-kontrol-market-relay", "version": 2}),
            _mock_http_response({"ok": True, "images": []}),
        ]) as urlopen:
            self.assertEqual(analysis_report.fetch_image_manifest(), [])
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(urlopen.call_args_list[0].args[0].full_url, f"{production_base}/healthz")
        self.assertEqual(urlopen.call_args_list[1].args[0].full_url, f"{production_base}/images/manifest")


class ImageRelayColdStartTests(unittest.TestCase):
    def test_manifest_retries_transient_connection_failure(self) -> None:
        with (
            mock.patch("analysis_report.urllib.request.urlopen", side_effect=[
                urllib.error.URLError("cold start connection refused"),
                _mock_http_response({"ok": True, "service": "firsat-kontrol-market-relay", "version": 2}),
                _mock_http_response({"ok": True, "images": []}),
            ]) as urlopen,
            mock.patch("analysis_report.time.sleep") as sleep,
        ):
            self.assertEqual(analysis_report.fetch_image_manifest(), [])
        self.assertEqual(urlopen.call_count, 3)
        sleep.assert_called_once_with(analysis_report.IMAGE_RELAY_RETRY_DELAYS[0])

    def test_manifest_retries_transient_gateway_error(self) -> None:
        route = analysis_report.IMAGE_BASE_URL + "/images/manifest"
        with (
            mock.patch("analysis_report.urllib.request.urlopen", side_effect=[
                _mock_http_response({"ok": True, "version": 2}),
                _mock_http_error(route, 502, "temporary gateway startup"),
                _mock_http_response({"ok": True, "images": []}),
            ]) as urlopen,
            mock.patch("analysis_report.time.sleep") as sleep,
        ):
            self.assertEqual(analysis_report.fetch_image_manifest(), [])
        self.assertEqual(urlopen.call_count, 3)
        sleep.assert_called_once_with(analysis_report.IMAGE_RELAY_RETRY_DELAYS[0])

    def test_manifest_404_is_not_hidden_or_retried(self) -> None:
        route = analysis_report.IMAGE_BASE_URL + "/images/manifest"
        with (
            mock.patch("analysis_report.urllib.request.urlopen", side_effect=[
                _mock_http_response({"ok": True, "version": 2}),
                _mock_http_error(route, 404, '{"error":"Endpoint izin listesinde değil."}'),
            ]) as urlopen,
            mock.patch("analysis_report.time.sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "HTTP 404.*Endpoint izin listesinde değil"):
                analysis_report.fetch_image_manifest()
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_not_called()

    def test_missing_cloudinary_configuration_is_reported_without_retries(self) -> None:
        route = analysis_report.IMAGE_BASE_URL + "/images/manifest"
        with (
            mock.patch("analysis_report.urllib.request.urlopen", side_effect=[
                _mock_http_response({"ok": True, "version": 2}),
                _mock_http_error(route, 503, '{"ok":false,"error":"Cloudinary bağlantısı ayarlanmadı."}'),
            ]) as urlopen,
            mock.patch("analysis_report.time.sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "Cloudinary bağlantısı ayarlanmadı"):
                analysis_report.fetch_image_manifest()
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_not_called()

    def test_repeated_network_failure_reports_attempt_count_and_last_error(self) -> None:
        with (
            mock.patch("analysis_report.urllib.request.urlopen", side_effect=urllib.error.URLError("DNS failure")) as urlopen,
            mock.patch("analysis_report.time.sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "4 denemede alınamadı.*DNS failure"):
                analysis_report.fetch_image_manifest()
        self.assertEqual(urlopen.call_count, 4)
        self.assertEqual(sleep.call_count, 3)


class ImageValidationTests(unittest.TestCase):
    def test_selection_count_is_limited_to_one_through_three(self) -> None:
        for count in (1, 2, 3):
            self.assertEqual(analysis_report.validate_image_selection_count(count), count)
        for count in (0, 4):
            with self.subTest(count=count), self.assertRaises(ValueError):
                analysis_report.validate_image_selection_count(count)

    def test_valid_png_jpg_and_jpeg_are_accepted(self) -> None:
        for filename, format_name, mime in (
            ("chart.png", "PNG", "image/png"),
            ("chart.jpg", "JPEG", "image/jpeg"),
            ("chart.jpeg", "JPEG", "image/jpeg"),
        ):
            with self.subTest(filename=filename):
                result = analysis_report.validate_image_bytes(image_bytes(format_name), filename)
                self.assertEqual(result["format"], format_name)
                self.assertEqual(result["content_type"], mime)
                self.assertGreater(result["size_bytes"], 0)

    def test_extension_signature_and_actual_decode_must_match(self) -> None:
        png = image_bytes("PNG")
        jpeg = image_bytes("JPEG")
        with self.assertRaisesRegex(ValueError, "imzası"):
            analysis_report.validate_image_bytes(png, "chart.jpg")
        with self.assertRaisesRegex(ValueError, "imzası"):
            analysis_report.validate_image_bytes(jpeg, "chart.png")
        with self.assertRaisesRegex(ValueError, "bozuk|açılamıyor"):
            analysis_report.validate_image_bytes(b"\x89PNG\r\n\x1a\nnot-an-image", "broken.png")
        with self.assertRaisesRegex(ValueError, "yalnızca|Yalnızca"):
            analysis_report.validate_image_bytes(png, "chart.gif")

    def test_missing_pillow_reports_dependency_problem_not_corrupt_image(self) -> None:
        real_import = __import__

        def import_without_pillow(name, *args, **kwargs):
            if name == "PIL" or name.startswith("PIL."):
                raise ModuleNotFoundError("No module named 'PIL'", name="PIL")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=import_without_pillow):
            with self.assertRaisesRegex(ValueError, "Pillow kurulu değil"):
                analysis_report.validate_image_bytes(image_bytes("PNG"), "chart.png")

    def test_per_image_size_limit_is_checked_before_decode(self) -> None:
        too_large = b"\x89PNG\r\n\x1a\n" + b"x" * analysis_report.MAX_IMAGE_BYTES
        with self.assertRaisesRegex(ValueError, "15 MiB"):
            analysis_report.validate_image_bytes(too_large, "large.png")

    def test_local_file_validation_and_preview_do_not_change_the_source(self) -> None:
        raw = image_bytes("PNG")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "screen.png"
            path.write_bytes(raw)
            metadata = analysis_report.validate_image_file(path)
            thumbnail = analysis_report.make_image_thumbnail(raw)
            self.assertEqual(metadata["size_bytes"], len(raw))
            self.assertTrue(thumbnail.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(path.read_bytes(), raw)

    def test_replacement_plan_keeps_newest_current_images(self) -> None:
        images = [
            {"id": "old", "uploaded_at": "2026-10-01T10:00:00+00:00"},
            {"id": "middle", "uploaded_at": "2026-10-02T10:00:00+00:00"},
            {"id": "newest", "uploaded_at": "2026-10-03T10:00:00+00:00"},
        ]
        one = analysis_report.build_image_replacement_plan(images, 1)
        self.assertEqual([item["id"] for item in one["keep"]], ["newest", "middle"])
        self.assertEqual([item["id"] for item in one["replace"]], ["old"])

        two = analysis_report.build_image_replacement_plan(images, 2)
        self.assertEqual([item["id"] for item in two["keep"]], ["newest"])
        self.assertEqual({item["id"] for item in two["replace"]}, {"old", "middle"})

        three = analysis_report.build_image_replacement_plan(images, 3)
        self.assertEqual(three["keep"], [])
        self.assertEqual({item["id"] for item in three["replace"]}, {"old", "middle", "newest"})

    def test_under_capacity_keeps_all_current_images(self) -> None:
        current = [{"id": "only", "uploaded_at": "2026-10-01T10:00:00+00:00"}]
        plan = analysis_report.build_image_replacement_plan(current, 1)
        self.assertEqual(plan["keep"], current)
        self.assertEqual(plan["replace"], [])


class ImageBatchUploadTests(unittest.TestCase):
    def _temporary_png(self, directory: str, name: str) -> Path:
        path = Path(directory) / name
        path.write_bytes(image_bytes("PNG"))
        return path

    def test_each_image_is_staged_separately_then_committed_once(self) -> None:
        first_id = "11111111-1111-4111-8111-111111111111"
        second_id = "22222222-2222-4222-8222-222222222222"
        with tempfile.TemporaryDirectory() as directory:
            paths = [
                self._temporary_png(directory, "first.png"),
                self._temporary_png(directory, "second.png"),
            ]
            with (
                mock.patch("analysis_report.upload_image_stage", side_effect=[
                    {"staged_id": first_id}, {"staged_id": second_id},
                ]) as stage,
                mock.patch("analysis_report.commit_image_uploads", return_value={
                    "ok": True, "images": [{"id": first_id}, {"id": second_id}],
                }) as commit,
                mock.patch("analysis_report.abort_image_uploads") as abort,
            ):
                result = analysis_report.upload_image_batch({"upload_url": analysis_report.UPLOAD_URL, "upload_token": "test"}, paths)
        self.assertTrue(result["ok"])
        self.assertEqual(stage.call_count, 2)
        self.assertEqual(commit.call_args.args[1], [first_id, second_id])
        abort.assert_not_called()

    def test_a_failed_stage_aborts_previously_staged_images_and_skips_commit(self) -> None:
        first_id = "11111111-1111-4111-8111-111111111111"
        with tempfile.TemporaryDirectory() as directory:
            paths = [
                self._temporary_png(directory, "first.png"),
                self._temporary_png(directory, "second.png"),
            ]
            with (
                mock.patch("analysis_report.upload_image_stage", side_effect=[
                    {"staged_id": first_id}, RuntimeError("stage failed"),
                ]),
                mock.patch("analysis_report.commit_image_uploads") as commit,
                mock.patch("analysis_report.abort_image_uploads") as abort,
            ):
                with self.assertRaisesRegex(RuntimeError, "stage failed"):
                    analysis_report.upload_image_batch({"upload_url": analysis_report.UPLOAD_URL, "upload_token": "test"}, paths)
        commit.assert_not_called()
        abort.assert_called_once_with(
            {"upload_url": analysis_report.UPLOAD_URL, "upload_token": "test"}, [first_id]
        )


if __name__ == "__main__":
    unittest.main()
