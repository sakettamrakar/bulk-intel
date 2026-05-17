"""Operator-assisted Playwright fallback for Google SERP.

Google's ToS prohibits automated scraping of Search. This client is bounded
as a triage fallback: explicit opt-in, headed browser by default, persistent
profile, human CAPTCHA resolution, hard per-run query cap, slow rate limit,
no login automation, no proxy rotation, and no fingerprint spoofing. It is
not a production bulk enrichment path; operators should buy structured SERP
API quota for high-volume runs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus

from config.settings import Settings
from enrichment.serp_price_provider import parse_price

logger = logging.getLogger(__name__)


class BudgetExhausted(RuntimeError):
    """Raised when the configured Playwright query cap is reached."""


class CaptchaEncountered(RuntimeError):
    """Raised when CAPTCHA cannot be resolved within the configured window."""

    def __init__(self, message: str, screenshot_path: str | None = None) -> None:
        super().__init__(message)
        self.screenshot_path = screenshot_path


@dataclass(frozen=True)
class PlaywrightSerpClient:
    """SerpClient implementation backed by a persistent Chromium context."""

    settings: Settings
    queries_used: int = 0
    page_factory: Callable[[], Any] | None = None
    time_fn: Callable[[], float] = time.monotonic
    sleep_fn: Callable[[float], None] = time.sleep
    random_fn: Callable[[float, float], float] = random.uniform
    backend_name: str = "playwright"
    _page: Any = field(default=None, init=False, compare=False)
    _context: Any = field(default=None, init=False, compare=False)
    _playwright: Any = field(default=None, init=False, compare=False)
    _last_search_at: float | None = field(default=None, init=False, compare=False)
    _captchas_encountered: int = field(default=0, init=False, compare=False)

    @property
    def captchas_encountered(self) -> int:
        return int(self._captchas_encountered)

    def search(self, query: str) -> list[dict[str, Any]]:
        """Return organic SERP candidates in the shared SerpClient shape."""
        if self.queries_used >= self.settings.playwright_max_queries_per_run:
            raise BudgetExhausted("PLAYWRIGHT_MAX_QUERIES_PER_RUN reached")
        self._rate_limit()
        page = self._ensure_session()
        if hasattr(page, "goto"):
            page.goto(
                "https://www.google.com/search?q=" + quote_plus(query),
                timeout=int(self.settings.playwright_page_timeout_s * 1000),
            )
        if detect_captcha(page):
            object.__setattr__(self, "_captchas_encountered", self.captchas_encountered + 1)
            self._handle_captcha(page)
        results = parse_results(page)
        object.__setattr__(self, "queries_used", self.queries_used + 1)
        object.__setattr__(self, "_last_search_at", self.time_fn())
        return results

    def close(self) -> None:
        for obj in (self._context, self._playwright):
            if obj is not None and hasattr(obj, "close"):
                obj.close()
            elif obj is not None and hasattr(obj, "stop"):
                obj.stop()
        object.__setattr__(self, "_page", None)
        object.__setattr__(self, "_context", None)
        object.__setattr__(self, "_playwright", None)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _ensure_session(self):
        if self._page is not None:
            return self._page
        Path(self.settings.playwright_profile_path).mkdir(parents=True, exist_ok=True)
        if self.page_factory is not None:
            page = self.page_factory()
            object.__setattr__(self, "_page", page)
            return page

        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        context = playwright.chromium.launch_persistent_context(
            self.settings.playwright_profile_path,
            headless=self.settings.playwright_headless,
        )
        page = context.pages[0] if context.pages else context.new_page()
        object.__setattr__(self, "_playwright", playwright)
        object.__setattr__(self, "_context", context)
        object.__setattr__(self, "_page", page)
        return page

    def _rate_limit(self) -> None:
        if self._last_search_at is None:
            return
        jitter = self.random_fn(
            -self.settings.playwright_rate_limit_jitter_seconds,
            self.settings.playwright_rate_limit_jitter_seconds,
        )
        target = max(0.0, self.settings.playwright_rate_limit_seconds + jitter)
        elapsed = self.time_fn() - self._last_search_at
        if elapsed < target:
            self.sleep_fn(target - elapsed)

    def _handle_captcha(self, page) -> None:
        screenshot_path = _captcha_screenshot_path(self.settings)
        if hasattr(page, "screenshot"):
            page.screenshot(path=screenshot_path)
        if self.settings.playwright_headless:
            raise CaptchaEncountered(f"CAPTCHA encountered at {_page_url(page)}", screenshot_path)
        logger.warning("CAPTCHA encountered; waiting for operator resolution in headed browser")
        try:
            if hasattr(page, "wait_for_selector"):
                page.wait_for_selector(
                    "div.g, div[data-snc], #search",
                    timeout=int(self.settings.playwright_captcha_timeout_s * 1000),
                )
        except Exception as exc:
            raise CaptchaEncountered(
                f"CAPTCHA not resolved before timeout at {_page_url(page)}",
                screenshot_path,
            ) from exc
        if detect_captcha(page):
            raise CaptchaEncountered(f"CAPTCHA still present at {_page_url(page)}", screenshot_path)


def detect_captcha(page) -> bool:
    """Return True when the page appears to be a CAPTCHA/interstitial."""
    url = _page_url(page).lower()
    body = _page_text(page).lower()
    if "/sorry/" in url or "/signin" in url:
        return True
    if "unusual traffic" in body or "recaptcha" in body:
        return True
    return False


def parse_results(page) -> list[dict[str, Any]]:
    """Parse organic results using layered, best-effort selectors."""
    html = _page_html(page)
    json_ld = _parse_json_ld(html)
    if json_ld:
        return json_ld
    cards = _parse_result_cards(html)
    if cards:
        return cards
    links = _parse_links(html)
    if links:
        return links
    logger.warning("Playwright SERP parser found no recognizable results")
    return []


def _parse_json_ld(html: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.I | re.S,
    ):
        try:
            payload = json.loads(_strip_tags(match.group(1)).strip())
        except json.JSONDecodeError:
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("name") or item.get("headline") or "").strip()
            url = str(item.get("url") or "").strip()
            if title and url:
                out.append(_result(title, url, str(item.get("description") or ""), item.get("offers", {}).get("price") if isinstance(item.get("offers"), dict) else None))
    return out


def _parse_result_cards(html: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    blocks = re.split(r'<div[^>]+(?:class=["\'][^"\']*\bg\b[^"\']*["\']|data-snc=["\'][^"\']*["\'])[^>]*>', html, flags=re.I)
    for block in blocks[1:]:
        if re.search(r"\bSponsored\b|Ad\W", _strip_tags(block), re.I):
            continue
        href = _first_href(block)
        title = _first_title(block)
        if href and title:
            snippet = _strip_tags(block)
            out.append(_result(title, href, snippet, parse_price(snippet)))
    return out


def _parse_links(html: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for href, label in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S):
        title = _strip_tags(label).strip()
        if "sponsored" in title.lower():
            continue
        if title and href.startswith("http") and "google." not in href:
            out.append(_result(title, href, title, None))
    return out


def _result(title: str, url: str, snippet: str, price: object) -> dict[str, Any]:
    parsed_price = price if isinstance(price, (int, float)) else parse_price(price if price is not None else snippet)
    return {
        "title": title,
        "price": float(parsed_price) if parsed_price is not None else None,
        "rating": None,
        "url": url,
        "snippet": snippet,
    }


def _first_href(html: str) -> str:
    match = re.search(r'<a[^>]+href=["\']([^"\']+)["\']', html, flags=re.I)
    return match.group(1) if match else ""


def _first_title(html: str) -> str:
    match = re.search(r"<h3[^>]*>(.*?)</h3>", html, flags=re.I | re.S)
    return _strip_tags(match.group(1)).strip() if match else ""


def _page_url(page) -> str:
    value = getattr(page, "url", "")
    return value() if callable(value) else str(value)


def _page_text(page) -> str:
    if hasattr(page, "inner_text"):
        try:
            return str(page.inner_text("body"))
        except TypeError:
            return str(page.inner_text())
        except Exception:
            return ""
    return _strip_tags(_page_html(page))


def _page_html(page) -> str:
    if hasattr(page, "content"):
        return str(page.content())
    return str(getattr(page, "html", ""))


def _strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def _captcha_screenshot_path(settings: Settings) -> str:
    path = Path(settings.playwright_profile_path).parent
    path.mkdir(parents=True, exist_ok=True)
    return str(path / f"captcha_{int(time.time())}.png")
