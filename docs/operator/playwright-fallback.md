# Playwright SERP Fallback

The Playwright fallback is an operator-assisted triage tool for runs where
SerpAPI is unavailable or quota is exhausted. It is capped, slow, and headed
by default. It is not a production scraper.

## One-time setup

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Enable it explicitly:

```bash
export BULK_INTEL_PLAYWRIGHT_FALLBACK=1
export BULK_INTEL_PLAYWRIGHT_HEADLESS=0
```

The browser profile lives under `.cache/playwright/profile`. On the first
headed run, sign in to Google manually if needed. The pipeline never types or
stores Google credentials; it only reuses the persistent browser profile.

## CAPTCHA flow

If Google shows a CAPTCHA or unusual-traffic page, the run pauses in headed
mode and waits for you to solve it in the visible browser window. In headless
mode, the client raises immediately and writes a screenshot under
`.cache/playwright/captcha_<timestamp>.png`.

Abort the run if CAPTCHA repeats after manual solve, if the page asks for
unexpected account recovery, or if you need more than the configured preview
budget. For larger runs, use SerpAPI quota rather than raising the cap.

## Recommended cap

Keep `PLAYWRIGHT_MAX_QUERIES_PER_RUN` at 10 for normal preview work. Do not
raise it above 25 without reviewing the compliance posture. The fallback is
for deciding whether a lot deserves deeper paid enrichment, not for bulk SERP
harvesting.

## Maintenance

Google selector drift is expected. Refresh the HTML fixtures quarterly or
when the parser starts returning empty results for normal pages.

To purge browser state manually:

```bash
rm -rf .cache/playwright
```
