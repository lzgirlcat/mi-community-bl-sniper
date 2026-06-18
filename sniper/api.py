# /usr/bin/python
from requests import Session
from enum import IntEnum
from typing import TypedDict, Optional
from secrets import token_urlsafe
from hashlib import sha1
from time import perf_counter
from email.utils import parsedate_to_datetime
from datetime import datetime
from pytz import timezone

UTC = timezone("UTC")


class ButtonState(IntEnum):
    POSSIBLE = 1
    RATELIMITED = 2
    ACCOUNT_TOO_YOUNG = 3


class UnlockState(IntEnum):
    GRANTED = 1
    NOT_GRANTED = 4


class ApplyResult(IntEnum):
    GRANTED = 1
    TOO_LATE = 3
    RATELIMITED = 4
    MAYBE_SUCCESS = 6


class StateCheckResponse(TypedDict):
    code: int
    ts: int
    is_pass: UnlockState
    button_state: ButtonState
    deadline: int
    deadline_format: Optional[str]  # "mm/dd hh:mm"


class ApplyResponse(TypedDict):
    code: int
    ts: int
    apply_result: ApplyResult
    deadline: int
    deadline_format: str  # "mm/dd hh:mm"


class Client:
    def __init__(
        self,
        token: str | None = None,
        proxy: str | None = None,
        version: tuple[str, str] = ("500432", "5.4.32"),
    ) -> None:
        self.session = Session()
        self.token = token
        self.version_code, self.version_name = version
        if proxy:
            self.session.proxies = {"https": proxy, "http": proxy}
        self.device_id = sha1(token_urlsafe(16).encode("utf-8")).hexdigest().upper()
        self.headers = {
            "User-Agent": "okhttp/4.12.0",
            "Connection": "keep-alive",
            "Accept-Encoding": "gzip, deflate, br",
        }

    @property
    def auth_headers(self):
        if not self.token:
            raise ValueError("token not provided!")
        return {
            **self.headers,
            "Cookie": ";".join(
                [
                    f"new_bbs_serviceToken={self.token}",
                    f"versionCode={self.version_code}",
                    f"versionName={self.version_name}",
                    f"deviceId={self.device_id}",
                ]
            ),
        }

    def check_status(self) -> StateCheckResponse:
        res = self.session.get(
            "https://sgp-api.buy.mi.com/bbs/api/global/user/bl-switch/state",
            headers=self.auth_headers,
        )
        res.raise_for_status()
        resp = res.json()
        return {**resp["data"], "code": resp["code"], "ts": resp.get("ts")}  # type: ignore

    def try_apply(self) -> ApplyResponse:
        res = self.session.post(
            "https://sgp-api.buy.mi.com/bbs/api/global/apply/bl-auth",
            headers=self.auth_headers,
            json={"is-retry": "true"},
        )
        res.raise_for_status()
        resp = res.json()
        return {**resp["data"], "code": resp["code"], "ts": resp.get("ts")}  # type: ignore

    def measure_offsets(self, probes=3) -> tuple[float, float, float]:
        start = perf_counter()
        res = self.session.head("https://sgp-api.buy.mi.com", headers=self.headers)
        duration = perf_counter() - start
        delays = []
        http_offsets = []
        for _ in range(probes):
            start_dt = datetime.now(tz=UTC)
            start = perf_counter()
            res = self.session.post(
                "https://sgp-api.buy.mi.com/bbs/api/global/apply/bl-auth",
                headers=self.headers
            )
            delays.append(perf_counter() - start)
            if date := res.headers.get("date"):
                dt = parsedate_to_datetime(date)
                http_offsets.append(
                    (dt - start_dt.replace(microsecond=0)).total_seconds()
                )

        return (
            duration / 2,
            sum(http_offsets) / len(http_offsets),
            sum([i / 2 for i in delays]) / len(delays),
        )
