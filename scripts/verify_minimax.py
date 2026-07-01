"""Verify MiniMax-M3 model connectivity and capabilities.

Usage:
    set MINIMAX_API_KEY=your_key
    python scripts/verify_minimax.py

Tests:
    1. Simple text completion (no thinking)
    2. Structured JSON output with json_schema response_format
    3. Multimodal image recognition
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on sys.path so we can import webwright.
_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from webwright.models import get_model
from webwright.models.base import image_part_from_path, text_part


def _load_model() -> object:
    config = {
        "model_class": "minimax",
        "model_name": "MiniMax-M3",
        "minimax_endpoint": "https://api.minimaxi.com/v1/chat/completions",
    }
    return get_model(config)


def test_text_completion(model: object) -> None:
    """Test 1: Simple text completion — verify connectivity and thinking disabled."""
    print("=" * 60)
    print("Test 1: Simple text completion")
    print("=" * 60)

    messages = [
        {"role": "user", "content": "Reply with exactly: Hello from MiniMax-M3!"},
    ]
    result = model(messages, max_output_tokens=100)
    print(f"Response: {result}")
    print()


def test_structured_json(model: object) -> None:
    """Test 2: Structured JSON output with json_schema response_format."""
    print("=" * 60)
    print("Test 2: Structured JSON output")
    print("=" * 60)

    messages = [
        {
            "role": "user",
            "content": (
                "Generate a JSON object with these fields:\n"
                "- name: your name\n"
                "- version: version number\n"
                "- features: list of 3 features"
            ),
        },
    ]
    result = model.query(messages)
    raw = result.get("extra", {}).get("raw_response", {})
    print(f"Parsed JSON: {raw}")
    print()


def test_image_recognition(model: object) -> None:
    """Test 3: Multimodal image recognition."""
    print("=" * 60)
    print("Test 3: Image recognition (multimodal)")
    print("=" * 60)

    # Use a test image from assets if available.
    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    test_images = list(assets_dir.rglob("*.png"))
    if not test_images:
        print("No test images found in assets/. Skipping image test.")
        return

    image_path = test_images[0]
    print(f"Using image: {image_path}")

    messages = [
        {
            "role": "user",
            "content": [
                text_part("Describe this image in one sentence."),
                image_part_from_path(image_path),
            ],
        },
    ]
    result = model(messages, max_output_tokens=200)
    print(f"Response: {result}")
    print()


def main() -> None:
    print("MiniMax-M3 Verification Script")
    print()

    model = _load_model()
    print(f"Model loaded: {model.config.model_name}")
    print(f"Endpoint: {model.config.minimax_endpoint}")
    print()

    try:
        test_text_completion(model)
    except Exception as exc:
        print(f"[FAIL] Text completion failed: {exc}")

    try:
        test_structured_json(model)
    except Exception as exc:
        print(f"[FAIL] Structured JSON failed: {exc}")

    try:
        test_image_recognition(model)
    except Exception as exc:
        print(f"[FAIL] Image recognition failed: {exc}")

    print("=" * 60)
    print("Verification complete.")


if __name__ == "__main__":
    main()
