"""Invalidate structured SERP cache rows."""
from __future__ import annotations

import argparse
import time

from config.settings import get_settings
from enrichment.serp_cache import SerpCache


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Invalidate SERP cache entries.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--by-signature", help="Delete rows whose cached search_signature contains this text.")
    group.add_argument("--by-brand", help="Delete rows whose cached brand contains this text.")
    group.add_argument("--older-than-hours", type=float, help="Delete rows older than this many hours.")
    group.add_argument("--all", action="store_true", help="Delete every SERP cache row after stdin confirmation.")
    args = parser.parse_args(argv)

    settings = get_settings()
    cache = SerpCache(settings.serp_cache_path, ttl_hours=settings.serp_cache_ttl_hours)
    if args.by_signature:
        deleted = cache.invalidate_by_payload_field("search_signature", args.by_signature)
    elif args.by_brand:
        deleted = cache.invalidate_by_payload_field("brand", args.by_brand)
    elif args.older_than_hours is not None:
        cutoff = int(time.time() - (args.older_than_hours * 3600))
        deleted = cache.purge(older_than=cutoff)
    else:
        response = input("Delete all SERP cache rows? Type DELETE to continue: ")
        if response != "DELETE":
            print("Aborted.")
            return 1
        deleted = cache.clear()

    print(f"Deleted {deleted} SERP cache row(s).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
