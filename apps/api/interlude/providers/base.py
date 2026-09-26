import time
from collections.abc import Callable
from typing import TypeVar
import httpx

T = TypeVar("T")


class ProviderError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def retry(operation: Callable[[], T], name: str, retries: int, sleep=time.sleep) -> T:
    for attempt in range(retries + 1):
        retryable = True
        try:
            return operation()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            code = f"{name}_http_{status}"
            retryable = status in (408, 429) or status >= 500
        except httpx.TimeoutException:
            code = f"{name}_timeout"
        except httpx.HTTPError:
            code = f"{name}_connection_failed"
        except (ValueError, KeyError, TypeError, IndexError):
            code = f"{name}_invalid_response"
        if attempt >= retries or not retryable:
            raise ProviderError(code) from None
        sleep(min(2 ** attempt, 8))
    raise AssertionError("unreachable")
