"""Load and validate JSON catalogs."""
import json
import logging
from datetime import datetime, date
from pathlib import Path

logger = logging.getLogger(__name__)

def load_catalog(path: str | Path) -> list[dict]:
    """Load and validate a catalog JSON.

    Validates schema_version, rates_as_of (warn if older than 90 days),
    and that each item has at minimum {product_name, amazon_price}.
    Coerces missing wholesale_price to None.
    """
    path = Path(path)
    if not path.exists():
        logger.warning(f"Catalog not found at {path}, returning empty list.")
        return []
        
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    version = data.get("schema_version")
    if not version:
        raise ValueError("Missing schema_version in catalog.")
        
    rates_as_of = data.get("rates_as_of")
    if rates_as_of:
        try:
            rates_date = datetime.strptime(rates_as_of, "%Y-%m-%d").date()
            if (date.today() - rates_date).days > 90:
                logger.warning(f"Catalog rates_as_of ({rates_as_of}) is older than 90 days.")
        except ValueError:
            pass
            
    items = data.get("items", [])
    valid_items = []
    
    for i, item in enumerate(items):
        if "product_name" not in item:
            raise ValueError(f"Item at index {i} missing product_name")
        if "amazon_price" not in item:
            raise ValueError(f"Item at index {i} missing amazon_price")
            
        item["wholesale_price"] = item.get("wholesale_price", None)
        valid_items.append(item)
        
    logger.info("Loaded %d catalog items from %s", len(valid_items), path.name)
    return valid_items
