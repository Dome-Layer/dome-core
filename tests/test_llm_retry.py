import pytest

from dome_core.llm.retry import is_retryable


def test_is_retryable_without_anthropic():
    assert is_retryable(ValueError("test")) is False


def test_is_retryable_generic_exception():
    assert is_retryable(RuntimeError("test")) is False


@pytest.fixture
def mock_api_status_error():
    try:
        import anthropic
    except ImportError:
        pytest.skip("anthropic not installed")

    class FakeResponse:
        status_code = 529
        headers = {}

    class FakeError(anthropic.APIStatusError):
        def __init__(self, status_code):
            self.status_code = status_code
            self.response = FakeResponse()
            self.message = "test"

    return FakeError


def test_is_retryable_529(mock_api_status_error):
    assert is_retryable(mock_api_status_error(529)) is True


def test_is_retryable_500(mock_api_status_error):
    assert is_retryable(mock_api_status_error(500)) is True


def test_is_retryable_400(mock_api_status_error):
    assert is_retryable(mock_api_status_error(400)) is False
