import base64
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from fleetai.agent import (
    _clean_patch,
    _image_content,
    apply_patch,
    collect_codebase,
    generate_patch,
)


class FleetAIAgentTests(unittest.TestCase):
    def test_collect_codebase_only_includes_safe_tracked_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "app.py").write_text("print('hello')\n", encoding="utf-8")
            (root / ".env").write_text("API_KEY=secret\n", encoding="utf-8")
            (root / "photo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")
            subprocess.run(["git", "add", "."], cwd=root, check=True)

            context = collect_codebase(root)

        self.assertIn("app.py", context)
        self.assertIn("print('hello')", context)
        self.assertNotIn("API_KEY", context)
        self.assertNotIn("photo.png", context)

    def test_image_is_encoded_as_data_uri(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "ticket.png"
            image.write_bytes(b"image bytes")

            result = _image_content(image)

        self.assertEqual(result["type"], "image_url")
        self.assertEqual(
            result["image_url"]["url"],
            "data:image/png;base64," + base64.b64encode(b"image bytes").decode(),
        )

    def test_image_rejects_non_image_files(self):
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "ticket.txt"
            file_path.write_text("not an image", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unsupported image type"):
                _image_content(file_path)

    def test_image_rejects_files_over_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "ticket.png"
            file_path.write_bytes(b"image bytes")

            with patch("fleetai.agent.MAX_IMAGE_BYTES", 1):
                with self.assertRaisesRegex(ValueError, "10 MiB limit"):
                    _image_content(file_path)

    def test_generate_patch_sends_ticket_context_and_image(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(
                    {"choices": [{"message": {"content": "```diff\n--- a/app.py\n+++ b/app.py\n@@\n-old\n+new\n```"}}]}
                ).encode()

        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "ticket.png"
            image.write_bytes(b"image")
            with patch("fleetai.agent.urlopen", return_value=Response()) as mock_urlopen:
                patch_text = generate_patch(
                    "change it",
                    "Python app",
                    "### app.py\nold",
                    [image],
                    "test-key",
                    "test-model",
                    "https://example.test/v1/chat/completions",
                )

        request = mock_urlopen.call_args.args[0]
        sent = json.loads(request.data)
        user_content = sent["messages"][1]["content"]
        self.assertEqual(request.get_header("Authorization"), "Bearer " + "test-key")
        self.assertIn("change it", user_content[0]["text"])
        self.assertIn("Python app", user_content[0]["text"])
        self.assertIn("app.py", user_content[0]["text"])
        self.assertEqual(user_content[1]["type"], "image_url")
        self.assertIn("+new", patch_text)
        self.assertTrue(patch_text.endswith("\n"))

    def test_apply_patch_checks_then_applies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "app.py").write_text("old\n", encoding="utf-8")
            subprocess.run(["git", "add", "app.py"], cwd=root, check=True)
            patch_text = (
                "diff --git a/app.py b/app.py\n"
                "--- a/app.py\n"
                "+++ b/app.py\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+new\n"
            )

            apply_patch(root, patch_text)

            self.assertEqual((root / "app.py").read_text(encoding="utf-8"), "new\n")

    def test_clean_patch_rejects_empty_response(self):
        with self.assertRaisesRegex(ValueError, "empty patch"):
            _clean_patch("  ")


if __name__ == "__main__":
    unittest.main()
