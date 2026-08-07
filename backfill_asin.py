"""
One-time backfill script. Does NOT delete or re-crawl anything.

For existing rows where website = 'Amazon' and asin IS NULL, this
extracts the ASIN directly from the already-saved product_url
(Amazon URLs always contain /dp/ASIN/) and updates just that column.

Noon rows are never touched - they don't have ASINs.

Run it like:

    python backfill_asin.py

It will show you a preview of what it's about to change and ask
for confirmation before writing anything.
"""

import re
from database.database import SessionLocal
from database.models import ProductDB

ASIN_PATTERN = re.compile(r"/dp/([A-Z0-9]{10})")

db = SessionLocal()

try:
    rows = (
        db.query(ProductDB)
        .filter(ProductDB.website == "Amazon", ProductDB.asin.is_(None))
        .all()
    )

    print(f"Found {len(rows)} Amazon rows with missing asin.\n")

    if not rows:
        print("Nothing to backfill. Done.")
    else:
        to_update = []
        no_match = []

        for r in rows:
            match = ASIN_PATTERN.search(r.product_url or "")
            if match:
                to_update.append((r, match.group(1)))
            else:
                no_match.append(r)

        print(f"Can extract ASIN for: {len(to_update)} rows")
        print(f"Could NOT extract ASIN for: {len(no_match)} rows (url format unexpected)")

        print("\nPreview (first 5):")
        for r, asin in to_update[:5]:
            print(f"  id={r.id}  name={r.name[:50]!r}  ->  asin={asin}")

        if no_match:
            print("\nRows that couldn't be matched (left untouched):")
            for r in no_match[:5]:
                print(f"  id={r.id}  url={r.product_url}")

        answer = input(f"\nUpdate {len(to_update)} rows now? [y/N]: ").strip().lower()

        if answer == "y":
            for r, asin in to_update:
                # Guard against collision with an existing asin (unique column)
                clash = (
                    db.query(ProductDB)
                    .filter(ProductDB.asin == asin, ProductDB.id != r.id)
                    .first()
                )
                if clash:
                    print(f"  Skipping id={r.id}: asin {asin} already used by id={clash.id}")
                    continue
                r.asin = asin

            db.commit()
            print(f"\n✅ Updated {len(to_update)} rows.")
        else:
            print("\nCancelled. No changes made.")

finally:
    db.close()