import os
import sys
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "scraper"))

import state


def test_get_last_hash_returns_value(monkeypatch):
    mock_ssm = MagicMock()
    mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "abc123"}}
    monkeypatch.setattr(state, "_ssm", mock_ssm)

    result = state.get_last_hash("/test/key")

    assert result == "abc123"
    mock_ssm.get_parameter.assert_called_once_with(Name="/test/key")


def test_get_last_hash_returns_none_when_not_found(monkeypatch):
    mock_ssm = MagicMock()
    error = ClientError({"Error": {"Code": "ParameterNotFound", "Message": "x"}}, "GetParameter")
    mock_ssm.get_parameter.side_effect = error
    monkeypatch.setattr(state, "_ssm", mock_ssm)

    result = state.get_last_hash("/test/missing")

    assert result is None


def test_get_last_hash_reraises_other_errors(monkeypatch):
    mock_ssm = MagicMock()
    error = ClientError({"Error": {"Code": "AccessDenied", "Message": "x"}}, "GetParameter")
    mock_ssm.get_parameter.side_effect = error
    monkeypatch.setattr(state, "_ssm", mock_ssm)

    with pytest.raises(ClientError):
        state.get_last_hash("/test/key")


def test_put_last_hash_calls_ssm_correctly(monkeypatch):
    mock_ssm = MagicMock()
    monkeypatch.setattr(state, "_ssm", mock_ssm)

    state.put_last_hash("/test/key", "newHash")

    mock_ssm.put_parameter.assert_called_once_with(
        Name="/test/key",
        Value="newHash",
        Type="String",
        Overwrite=True,
    )
