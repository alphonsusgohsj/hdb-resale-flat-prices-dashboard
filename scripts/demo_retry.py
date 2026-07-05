"""Fault-injection demo for the ingest layer's retry/backoff.

Runs entirely offline with a fake HTTP session, so it is deterministic and does
not touch the real API. It injects failures into ``ingest._fetch_page`` and
shows the two behaviours that matter:

  1. Transient failure that recovers — the first two attempts raise a connection
     error, the third succeeds. Proves the loop retries and then carries on.
  2. Permanent failure — every attempt fails. Proves it backs off across all
     MAX_RETRIES attempts and finally raises IngestionError rather than
     returning bad/partial data.

Backoff is dialled down (0.2s base) so the demo is quick while still visibly
waiting between attempts.

Run from the repo root:  ./.venv/bin/python -m scripts.demo_retry
"""
from __future__ import annotations

import time

import requests

import config
from src import ingest


class FakeResponse:
    """Minimal stand-in for a requests.Response holding a good CKAN page."""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


_GOOD_PAYLOAD = {
    "success": True,
    "result": {"records": [{"_id": 1}], "total": 1},
}


class FlakySession:
    """Raises ConnectionError ``fail_times`` times, then returns a good page."""

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise requests.ConnectionError(f"simulated network drop (call {self.calls})")
        return FakeResponse(_GOOD_PAYLOAD)


def scenario(title: str, session: FlakySession) -> None:
    print("=" * 64)
    print(title)
    print("=" * 64)
    start = time.time()
    try:
        result = ingest._fetch_page(session, offset=0, limit=config.PAGE_SIZE)
        print(
            f"RESULT: succeeded after {session.calls} call(s); "
            f"got {len(result['records'])} record(s)"
        )
    except ingest.IngestionError as exc:
        print(f"RESULT: raised IngestionError after {session.calls} call(s)")
        print(f"        {exc}")
    print(f"elapsed: {time.time() - start:.2f}s\n")


if __name__ == "__main__":
    # Dial backoff down so the demo is quick but still visibly waits between tries.
    config.BACKOFF_BASE_SECONDS = 0.2
    config.MAX_RETRIES = 5

    scenario(
        "Scenario 1 - transient failure, recovers on attempt 3",
        FlakySession(fail_times=2),
    )
    scenario(
        "Scenario 2 - permanent failure, exhausts all 5 retries then raises",
        FlakySession(fail_times=999),
    )
