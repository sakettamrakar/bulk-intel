# T-203 — Expand `KNOWN_BRANDS` to 200+ Indian brands; add normalisation

| Field | Value |
|---|---|
| Phase | 2 (P1) |
| Effort | 4 hours |
| Depends on | — |
| Blocks | — |
| Status | Not started |

---

## Context

`KNOWN_BRANDS` today is ~30 entries — a brand-recognition fig-leaf for the
Indian market. Real liquidation manifests carry hundreds of relevant brands
(Lloyd, Voltas, Whirlpool, Wonderchef, Haier, Realme, Mi, Fastrack, Titan,
Wakefit, Mamaearth, MyGlamm, Plum, Bata, …). Brands not in the list silently
default to a 60-point brand bonus instead of 90, costing them ~5 sellability
points and biasing the engine against the long tail.

A separate but related issue: brand strings are not normalised. "Amazon Brand
- Solimo", "Solimo", "AmazonBasics", "amazon_basics" are all the same brand
in reality but treated as distinct strings by the cleaner.

## Files to modify

- `config/settings.py` — expanded `KNOWN_BRANDS` (200+) and a new `BRAND_ALIASES` map.
- `processing/cleaner.py` — apply alias normalisation in `_fill_brand`.
- `tests/test_cleaner.py` — alias-resolution tests.
- `README.md` — note the expanded brand list and alias mechanism.

## Specification

### `KNOWN_BRANDS` (expanded list)

Maintain a curated list of recognised Indian + global brands the engine
should treat as known-quantity. Group by category for readability and
maintainability:

```python
# Curated list of brands that move noticeably faster on Indian marketplaces.
# Add liberally; downside of a false positive is small (5-pt sellability bonus),
# downside of a false negative is real (long-tail brands miss the bonus).
KNOWN_BRANDS: frozenset[str] = frozenset({
    # ---------- Electronics & mobile ----------
    "samsung", "apple", "sony", "lg", "boat", "philips", "realme", "xiaomi",
    "mi", "redmi", "oneplus", "oppo", "vivo", "lenovo", "dell", "hp",
    "asus", "acer", "jbl", "noise", "boult", "nothing", "fastrack", "fire-boltt",
    # ---------- Home appliances & kitchen ----------
    "prestige", "bajaj", "havells", "milton", "cello", "pigeon", "bergner",
    "butterfly", "lifelong", "solimo", "amazon_basics", "amazonbasics",
    "crystal", "tosaa", "blowhot", "longway", "surya", "stovekraft",
    "wonderchef", "voltas", "whirlpool", "lloyd", "haier", "godrej",
    "samsung", "lg", "panasonic", "hitachi", "blue_star", "carrier",
    "kent", "aquaguard", "preethi", "morphy_richards", "kenstar",
    "usha", "crompton", "orient", "v-guard", "vguard", "ifb",
    # ---------- Apparel & footwear ----------
    "nike", "adidas", "puma", "levis", "hm", "zara", "uniqlo", "decathlon",
    "fastrack", "titan", "fossil", "casio", "skagen", "tommy_hilfiger",
    "us_polo", "uspolo", "allen_solly", "louis_philippe", "van_heusen",
    "peter_england", "raymond", "bata", "woodland", "skechers", "reebok",
    "asics", "fila", "campus", "metro_shoes", "liberty",
    # ---------- Beauty & personal care ----------
    "lakme", "loreal", "maybelline", "nivea", "dove", "ponds", "olay",
    "neutrogena", "the_body_shop", "mamaearth", "myglamm", "plum",
    "biotique", "himalaya", "wow", "minimalist", "the_derma_co",
    "garnier", "cetaphil", "pantene", "tresemme", "head_shoulders",
    # ---------- Home & lifestyle ----------
    "wakefit", "the_sleep_company", "duroflex", "sleepyhead", "centuary",
    "ikea", "urban_ladder", "pepperfry", "home_centre", "fab_india",
    # ---------- Toys & kids ----------
    "lego", "hamleys", "fisher_price", "mattel", "hasbro", "funskool",
    # ---------- Books & stationery ----------
    "penguin", "harpercollins", "scholastic", "classmate", "navneet",
    "camel", "faber_castell", "pilot", "uni_ball",
})
```

(Final list to be at least 200 entries; the above is illustrative — extend
during the task.)

### `BRAND_ALIASES`

```python
# Source brand string (lowercased, alpha-num + underscore) → canonical brand.
# Apply *after* lowercasing, before known-brand lookup.
BRAND_ALIASES: Mapping[str, str] = {
    "amazon_brand_solimo":  "solimo",
    "amazon_basics":        "amazonbasics",
    "amazon_brand":         "amazonbasics",
    "amazonbasics_in":      "amazonbasics",
    "stovekraft_pigeon":    "pigeon",
    "pigeon_by_stovekraft": "pigeon",
    "tommy":                "tommy_hilfiger",
    "us_polo_assn":         "us_polo",
    "uspolo_assn":          "us_polo",
    "h_and_m":              "hm",
    "h_m":                  "hm",
    # ... add more as you encounter them in the wild.
}
```

### `processing/cleaner.py` change

In `_fill_brand`, after lowercasing:

```python
def _normalise_brand(self, raw: str) -> str:
    """Lowercase + alias-resolve a raw brand string."""
    s = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    return self.settings.brand_aliases.get(s, s)
```

Use this everywhere a raw brand becomes the comparison key (both for the
inferred brand and for `KNOWN_BRANDS` membership).

### Settings dataclass

```python
brand_aliases: Mapping[str, str] = field(default_factory=lambda: dict(BRAND_ALIASES))
```

## Acceptance criteria

- [ ] `KNOWN_BRANDS` contains **at least 200** distinct lowercased brand tokens.
- [ ] `BRAND_ALIASES` contains at least 15 real-world aliases observed in liquidation manifests.
- [ ] Cleaner applies alias normalisation before brand lookup.
- [ ] On the real manifest, more rows hit the "known brand" 90-point bonus (record before/after counts in PR).
- [ ] `test_cleaner.py` passes existing tests + new alias-specific tests.

## Test requirements (`tests/test_cleaner.py`)

1. `test_brand_alias_amazon_brand_solimo_to_solimo` — input `"Amazon Brand - Solimo"` → cleaner emits `brand` such that `brand.lower() in known_brands` (i.e. resolves to `solimo`).
2. `test_brand_alias_pigeon_by_stovekraft_to_pigeon`.
3. `test_unknown_brand_passthrough` — a brand not in any list passes through unchanged (lowercased, snake-cased).
4. `test_known_brand_count_grows_after_t203` — assert `len(KNOWN_BRANDS) >= 200`.

## Documentation requirements

- [ ] `README.md` § 5: note that `KNOWN_BRANDS` is curated and aliases are resolved before lookup.
- [ ] `README.md` § 6 (extension points): "How to add a brand alias".
- [ ] `config/settings.py` inline comment on the alias table explaining the canonicalisation rules.

## Out of scope

- Per-category brand strength (some brands strong in one category, weak in
  another). Future enhancement.
- Fuzzy brand matching (Levenshtein). The alias table is exact-match only.

## Risks & considerations

- The 200+ list will need quarterly refresh as new D2C brands emerge. Add a
  comment with last-curated date.
- Aliases must be validated against the actual manifest the engine sees;
  collect a spreadsheet of "raw brand string" → "intended canonical" while
  observing real lots and feed back.
