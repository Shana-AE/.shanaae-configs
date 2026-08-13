import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.vision_describe import (
    BRIDGE_PROFILES,
    build_payload,
    describe,
    main,
    parse_analysis,
    parse_models_verbose,
    resolve_route,
    validate_base_url,
)


MODELS_VERBOSE = """qiniu/moonshotai/kimi-k3
{
  "capabilities": {
    "attachment": true,
    "input": {"image": true}
  }
}
qiniu/deepseek/deepseek-v4-flash
{
  "capabilities": {
    "attachment": false,
    "input": {"image": false}
  }
}
qiniu/qwen/qwen3.5-plus
{
  "capabilities": {
    "attachment": true,
    "input": {"image": false}
  }
}
"""


class ParseModelsVerboseTests(unittest.TestCase):
    def test_parses_model_records_with_nested_json(self):
        records = parse_models_verbose(MODELS_VERBOSE)

        self.assertEqual(3, len(records))
        self.assertTrue(records["qiniu/moonshotai/kimi-k3"]["capabilities"]["input"]["image"])


class ResolveRouteTests(unittest.TestCase):
    def setUp(self):
        self.records = parse_models_verbose(MODELS_VERBOSE)

    def test_uses_native_vision_only_when_transport_and_image_input_are_enabled(self):
        self.assertEqual("native", resolve_route("qiniu/moonshotai/kimi-k3", self.records))

    def test_routes_text_only_models_through_the_bridge(self):
        self.assertEqual("bridge", resolve_route("qiniu/deepseek/deepseek-v4-flash", self.records))

    def test_routes_incomplete_capability_metadata_through_the_bridge(self):
        self.assertEqual("bridge", resolve_route("qiniu/qwen/qwen3.5-plus", self.records))

    def test_routes_unknown_models_through_the_bridge(self):
        self.assertEqual("bridge", resolve_route("unknown/model", self.records))


class BridgeProfileTests(unittest.TestCase):
    def test_balanced_profile_prefers_qwen_and_never_uses_kimi_k3(self):
        self.assertEqual(
            ["qwen/qwen3.5-plus", "gemini-2.5-flash-lite"],
            BRIDGE_PROFILES["balanced"],
        )
        self.assertNotIn("moonshotai/kimi-k3", BRIDGE_PROFILES["balanced"])

    def test_economy_profile_prefers_doubao_mini(self):
        self.assertEqual("doubao-seed-2.0-mini", BRIDGE_PROFILES["economy"][0])


class BuildPayloadTests(unittest.TestCase):
    def test_builds_a_bounded_structured_visual_analysis_request(self):
        payload = build_payload(
            model="qwen/qwen3.5-plus",
            images=[("actual", b"png-bytes", "image/png")],
            prompt="Compare this rendered modal with the expected design.",
        )

        self.assertEqual("qwen/qwen3.5-plus", payload["model"])
        self.assertEqual(800, payload["max_tokens"])
        self.assertIn("data:image/png;base64,", payload["messages"][1]["content"][2]["image_url"]["url"])
        self.assertIn("JSON", payload["messages"][0]["content"])

    def test_labels_reference_and_actual_images_in_one_request(self):
        payload = build_payload(
            model="qwen/qwen3.5-plus",
            images=[
                ("reference", b"reference-bytes", "image/png"),
                ("actual", b"actual-bytes", "image/png"),
            ],
            prompt="Compare these interfaces.",
        )

        content = payload["messages"][1]["content"]
        self.assertEqual("Reference image:", content[1]["text"])
        self.assertIn("data:image/png;base64,", content[2]["image_url"]["url"])
        self.assertEqual("Actual image:", content[3]["text"])
        self.assertIn("data:image/png;base64,", content[4]["image_url"]["url"])


class DescribeTests(unittest.TestCase):
    def test_falls_back_when_primary_model_returns_malformed_json(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "actual.png"
            image.write_bytes(b"png-bytes")

            with patch(
                "scripts.vision_describe.request_description",
                side_effect=[
                    "not-json",
                    '{"summary":"usable","layout_issues":[],"style_issues":[],"responsive_issues":[],"uncertainties":[],"confidence":0.8}',
                ],
            ):
                result = describe(image, None, "Compare this UI.", "balanced")

        self.assertEqual("gemini-2.5-flash-lite", result["model"])
        self.assertEqual("usable", result["analysis"]["summary"])

    def test_rejects_analysis_without_a_summary(self):
        with self.assertRaises(ValueError):
            parse_analysis('{"confidence":0.8}')

    def test_normalizes_missing_lists_and_common_confidence_formats(self):
        high = parse_analysis('{"summary":"usable","confidence":"High: clear visual evidence"}')
        scaled = parse_analysis('{"summary":"usable","confidence":5}')

        self.assertEqual([], high["layout_issues"])
        self.assertEqual(0.8, high["confidence"])
        self.assertEqual(0.5, scaled["confidence"])

    def test_extracts_json_object_from_surrounding_text(self):
        analysis = parse_analysis(
            'Here is the result:\n{"summary":"usable","confidence":0.7}\nEnd of response.'
        )

        self.assertEqual("usable", analysis["summary"])
        self.assertEqual(0.7, analysis["confidence"])


class BaseUrlTests(unittest.TestCase):
    def test_accepts_qiniu_https_endpoints(self):
        self.assertEqual("https://api.qnaigc.com/v1", validate_base_url("https://api.qnaigc.com/v1/"))
        self.assertEqual("https://api.modelink.ai/v1", validate_base_url("https://api.modelink.ai/v1"))

    def test_rejects_non_qiniu_or_insecure_endpoints(self):
        with self.assertRaises(ValueError):
            validate_base_url("https://example.com/v1")
        with self.assertRaises(ValueError):
            validate_base_url("http://api.qnaigc.com/v1")


class CliTests(unittest.TestCase):
    def test_route_reports_missing_opencode_without_a_traceback(self):
        stderr = StringIO()
        with patch("scripts.vision_describe.load_runtime_models", side_effect=FileNotFoundError("opencode")):
            with patch("sys.stderr", stderr):
                exit_code = main(["route", "--model", "qiniu/z-ai/glm-5.2"])

        self.assertEqual(1, exit_code)
        self.assertIn("opencode", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
