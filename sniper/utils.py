from datetime import datetime, timedelta
from time import monotonic
from yt_dlp.cookies import extract_cookies_from_browser, YoutubeDLCookieJar


class TimeOffsetManager:
    def __init__(self, start_dt: datetime) -> None:
        self.start_monotonic = monotonic()
        self.start_dt = start_dt

    @property
    def time(self):
        return self.start_dt + timedelta(seconds=monotonic() - self.start_monotonic)


def get_cookies(browser: str = "firefox", profile: str | None = None):
    if browser == "thorium":
        if not profile:
            profile = ""
        browser, profile = "chromium", f"/home/lz/.config/thorium/{profile}"
    cookies: "YoutubeDLCookieJar" = extract_cookies_from_browser(
        browser, profile or None
    )
    return {
        cookie.name: cookie.value
        for cookie in cookies
        if (cookie.domain == "mi.com" or cookie.domain.endswith(".mi.com"))
        and cookie.value
    }