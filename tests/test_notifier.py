import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "scraper"))

import notifier


def test_publish_calls_sns(monkeypatch):
    mock_sns = MagicMock()
    monkeypatch.setattr(notifier, "_sns", mock_sns)

    notifier.publish("arn:aws:sns:us-east-1:123:test", "hello", "Subject")

    mock_sns.publish.assert_called_once_with(
        TopicArn="arn:aws:sns:us-east-1:123:test",
        Message="hello",
        Subject="Subject",
    )


def test_publish_truncates_long_subject(monkeypatch):
    mock_sns = MagicMock()
    monkeypatch.setattr(notifier, "_sns", mock_sns)

    notifier.publish("arn:aws:sns:us-east-1:123:test", "msg", "A" * 200)

    call_kwargs = mock_sns.publish.call_args.kwargs
    assert len(call_kwargs["Subject"]) == 100


def test_publish_uses_default_subject(monkeypatch):
    mock_sns = MagicMock()
    monkeypatch.setattr(notifier, "_sns", mock_sns)

    notifier.publish("arn:aws:sns:us-east-1:123:test", "msg")

    call_kwargs = mock_sns.publish.call_args.kwargs
    assert call_kwargs["Subject"] == "News Alert"
