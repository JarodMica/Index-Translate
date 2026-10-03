import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location("glm_example", Path(__file__).resolve().parents[1] / "glm_api_example.py")
glm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(glm)


def stream(events, done=True):
    body = b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events)
    return io.BytesIO(body + (b"data: [DONE]\n\n" if done else b""))


class GlmExampleTest(unittest.TestCase):
    def call(self, response):
        with patch.object(glm, "urlopen", return_value=response):
            return glm.translate({"case_id": "example", "messages": []},
                                 "example-test-key", {"model": "glm-5.3-flash"}, 5)

    def test_translation_deltas_and_usage(self):
        result = self.call(stream([
            {"id": "response-id", "model": "glm-5.3-flash", "choices": [
                {"delta": {"reasoning_content": "Do not score this"}}]},
            {"choices": [{"delta": {"content": "  Hello\n"}}]},
            {"choices": [{"delta": {"content": "world. "}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 8}}]))
        self.assertEqual(result["mt"], "  Hello\nworld. ")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["input_tokens"], 12)
        self.assertEqual(result["output_tokens"], 8)
        self.assertFalse(result["cap_hit"])
        self.assertIsNone(result["model_revision"])

    def test_length_output_remains_scorable(self):
        result = self.call(stream([{"choices": [
            {"delta": {"content": "Partial translation"}, "finish_reason": "length"}]}]))
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["cap_hit"])

    def test_missing_done_or_filter_is_not_success(self):
        for finish, done, status in [("stop", False, "api_error"),
                                     ("sensitive", True, "content_filter")]:
            with self.subTest(finish=finish):
                result = self.call(stream([{"choices": [
                    {"delta": {"content": "Partial text"}, "finish_reason": finish}]}], done))
                self.assertEqual(result["status"], status)
                self.assertEqual(result["mt"], "Partial text")

    def test_http_filter_redacts_credential(self):
        error = HTTPError(glm.ENDPOINT, 400, "error", {},
                          io.BytesIO(b'{"error":{"code":"1301","message":"example-test-key"}}'))
        with patch.object(glm, "urlopen", side_effect=error) as request:
            result = glm.translate({"case_id": "example", "messages": []},
                                   "example-test-key", {"model": "glm-5.3-flash"}, 5)
        self.assertEqual(result["status"], "content_filter")
        self.assertNotIn("example-test-key", json.dumps(result))
        self.assertEqual(request.call_count, 1)

    def test_selected_frozen_request_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            rows = [{"case_id": cid, "messages": [{"role": "user", "content": "Source\u2028text"}]}
                    for cid in ("first", "second")]
            (path / "requests.jsonl").write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
            result = {"case_id": "second", "status": "ok", "finish_reason": "stop",
                      "input_tokens": 3, "output_tokens": 2, "mt": "Translation"}
            with patch("sys.argv", ["example", "--requests", str(path / "requests.jsonl"),
                                     "--case-id", "second", "--output", str(path / "out.jsonl")]), \
                    patch.dict("os.environ", {"BIGMODEL_API_KEY": "example-test-key"}), \
                    patch.object(glm, "translate", return_value=result) as call, \
                    patch("builtins.print"):
                self.assertEqual(glm.main(), 0)
            self.assertEqual(call.call_count, 1)
            self.assertEqual(call.call_args.args[0], rows[1])
            self.assertEqual(glm.read_rows(path / "out.jsonl"), [result])


if __name__ == "__main__":
    unittest.main()
