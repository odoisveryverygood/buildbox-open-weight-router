"""Per-run, thread-safe reservations and bounded, read-only replay calls."""

import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from decimal import Decimal

from pydantic import Field, model_validator

from .records import Record, ResearchFailure, SourceCapture, Status, failure
from .sources import RecordedSources, as_search_port


class Limits(Record):
    max_calls: int = Field(default=32, ge=0, le=128)
    max_tokens: int = Field(default=0, ge=0, le=100_000)
    max_usd: Decimal = Field(default=Decimal("0"), ge=0, allow_inf_nan=False)
    call_usd_reservation: Decimal = Field(default=Decimal("0"), ge=0, allow_inf_nan=False)
    timeout_seconds: float = Field(default=2.0, gt=0, le=30, allow_inf_nan=False)
    deadline_seconds: float = Field(default=15.0, gt=0, le=60, allow_inf_nan=False)
    max_retries: int = Field(default=1, ge=0, le=2)
    retry_delay_seconds: float = Field(default=0.02, ge=0, le=1, allow_inf_nan=False)
    max_response_bytes: int = Field(default=262_144, ge=1, le=1_048_576)
    max_search_results: int = Field(default=12, ge=1, le=12)

    @model_validator(mode="after")
    def reserve_within_total(self) -> "Limits":
        if self.call_usd_reservation > self.max_usd:
            raise ValueError("A single reservation exceeds the global cap")
        return self


class BudgetLedger:
    """One ledger shared by all three jobs in this process/run.

    Reservations are consumed conservatively, even on timeout. These numbers are
    caps, not asserted provider charges. Cross-process accounting is a requested
    integration responsibility; the current adapter cannot make billable calls.
    """

    def __init__(self, limits: Limits) -> None:
        self.limits = limits
        self._lock = threading.Lock()
        self._calls = 0
        self._tokens = 0
        self._reserved = Decimal("0")

    def reserve(self, *, tokens: int = 0, usd: Decimal | None = None) -> None:
        cost = self.limits.call_usd_reservation if usd is None else usd
        if tokens < 0 or not cost.is_finite() or cost < 0:
            raise ValueError("Invalid reservation")
        with self._lock:
            if self._calls + 1 > self.limits.max_calls:
                raise failure(Status.BUDGET, "Global call cap exhausted")
            if (
                self._tokens + tokens > self.limits.max_tokens
                or self._reserved + cost > self.limits.max_usd
            ):
                raise failure(Status.BUDGET, "Global token/spending reservation cap exhausted")
            self._calls += 1
            self._tokens += tokens
            self._reserved += cost

    @property
    def usage(self) -> tuple[int, int, Decimal]:
        with self._lock:
            return self._calls, self._tokens, self._reserved


class BoundedReader:
    def __init__(
        self, sources: RecordedSources, budget: BudgetLedger, cancelled: threading.Event
    ) -> None:
        self.sources = sources
        self.port = as_search_port(sources)
        self.budget = budget
        self.cancelled = cancelled
        self.deadline = time.monotonic() + budget.limits.deadline_seconds
        self._pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="public-replay")

    def check(self) -> None:
        if self.cancelled.is_set():
            raise failure(Status.CANCELLED, "Research cancelled; no snapshot published")
        if time.monotonic() >= self.deadline:
            raise failure(Status.TIMEOUT, "Research deadline reached; no snapshot published")

    def call[T](self, function: Callable[[], T]) -> T:
        for attempt in range(self.budget.limits.max_retries + 1):
            self.check()
            self.budget.reserve()
            future = self._pool.submit(function)
            end = min(self.deadline, time.monotonic() + self.budget.limits.timeout_seconds)
            try:
                while True:
                    self.check()
                    remaining = end - time.monotonic()
                    if remaining <= 0:
                        raise failure(
                            Status.TIMEOUT, "Read deadline exceeded; reservation retained"
                        )
                    try:
                        result = future.result(timeout=min(remaining, 0.02))
                        self.check()
                        return result
                    except TimeoutError:
                        if future.done():
                            raise failure(Status.TIMEOUT, "Source timed out") from None
            except ResearchFailure as exc:
                future.cancel()
                # Never retry timed-out work that may still be running. Sources have no writes.
                if (
                    exc.issue.status != Status.RATE_LIMIT
                    or attempt == self.budget.limits.max_retries
                ):
                    raise
                if self.cancelled.wait(self.budget.limits.retry_delay_seconds):
                    self.check()
            except Exception:
                future.cancel()
                raise failure(
                    Status.INVALID, "Public source adapter failed; details omitted"
                ) from None
        raise AssertionError("Retry loop exhausted without a result")

    def read(self, url: str) -> SourceCapture:
        # Validate the exact recorded destination before dispatch, never follow content links.
        capture = self.sources.capture(url)
        if len(capture.body.encode()) > self.budget.limits.max_response_bytes:
            raise failure(Status.SEARCH_LIMIT, "Recorded response exceeds configured byte cap")
        body = self.call(lambda: self.port.extract(url=url))
        if len(body.encode()) > self.budget.limits.max_response_bytes:
            raise failure(Status.SEARCH_LIMIT, "Source response exceeds configured byte cap")
        if body != capture.body:
            raise failure(Status.CONFLICT, "Captured bytes changed during replay")
        return capture

    def search(self, query: str, limit: int) -> tuple[str, ...]:
        if limit < 1 or limit > self.budget.limits.max_search_results:
            raise failure(Status.SEARCH_LIMIT, "Requested results exceed search cap")
        results = self.call(lambda: self.port.search(query=query, limit=limit))
        if len(results) > limit:
            raise failure(Status.SEARCH_LIMIT, "Adapter exceeded search result limit")
        for url in results:
            self.sources.capture(url)
        return results

    def close(self) -> None:
        # Running replay calls are pure reads; late results cannot publish or retry.
        self._pool.shutdown(wait=False, cancel_futures=True)
