"""Offline validation of IBM watsonx response parsing."""

import pytest

from app.integrations.watsonx import WatsonxProviderError, _extract_answer


def test_extracts_chat_message_text() -> None:
    answer = _extract_answer(
        {
            "choices": [
                {
                    "message": {
                        "content": "A response grounded in the supplied data."
                    }
                }
            ]
        }
    )

    assert answer == "A response grounded in the supplied data."


def test_extracts_text_blocks_from_chat_response() -> None:
    answer = _extract_answer(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "First verified point."},
                            {"type": "image", "image_url": "not-used"},
                            {"type": "text", "text": "Second verified point."},
                        ]
                    }
                }
            ]
        }
    )

    assert answer == "First verified point.\nSecond verified point."


def test_rejects_empty_chat_response() -> None:
    with pytest.raises(WatsonxProviderError, match="empty answer"):
        _extract_answer({"choices": [{"message": {"content": ""}}]})
