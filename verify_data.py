"""
Diagnostic-only script. Does not modify any data.
Run it like:

    python verify_data.py

Checks:
  1. Row counts per website
  2. Sample rows (so you can eyeball real values)
  3. Nulls in important columns
  4. Duplicate product_urls (should be none - it's a unique column)
  5. Price sanity (zero/negative/absurdly high prices)
  6. Rating out of 0-5 range
  7. Reviews that are negative (would indicate the K/M parsing bug is back)
"""

from database.database import SessionLocal
from database.models import ProductDB
from sqlalchemy import func

db = SessionLocal()

try:
    print("=" * 60)
    print("1. ROW COUNTS PER WEBSITE")
    print("=" * 60)
    counts = (
        db.query(ProductDB.website, func.count(ProductDB.id))
        .group_by(ProductDB.website)
        .all()
    )
    total = 0
    for website, count in counts:
        print(f"  {website}: {count}")
        total += count
    print(f"  TOTAL: {total}")

    print("\n" + "=" * 60)
    print("2. SAMPLE ROWS (5 per website)")
    print("=" * 60)
    for website, _ in counts:
        print(f"\n--- {website} ---")
        rows = (
            db.query(ProductDB)
            .filter(ProductDB.website == website)
            .limit(5)
            .all()
        )
        for r in rows:
            print(
                f"  id={r.id} | name={r.name[:50]!r} | price={r.price} | "
                f"rating={r.rating} | reviews={r.reviews} | asin={r.asin}"
            )
            print(f"     url={r.product_url}")
            print(f"     image={r.image}")

    print("\n" + "=" * 60)
    print("3. NULL / MISSING VALUES")
    print("=" * 60)
    for col_name, col in [
        ("name", ProductDB.name),
        ("price", ProductDB.price),
        ("product_url", ProductDB.product_url),
        ("image", ProductDB.image),
        ("rating", ProductDB.rating),
        ("reviews", ProductDB.reviews),
    ]:
        null_count = db.query(ProductDB).filter(col.is_(None)).count()
        flag = "  <-- check this" if null_count > 0 and col_name in ("name", "price", "product_url") else ""
        print(f"  {col_name}: {null_count} nulls{flag}")

    print("\n" + "=" * 60)
    print("4. DUPLICATE product_url (should be 0 - column is unique)")
    print("=" * 60)
    dupes = (
        db.query(ProductDB.product_url, func.count(ProductDB.id))
        .group_by(ProductDB.product_url)
        .having(func.count(ProductDB.id) > 1)
        .all()
    )
    print(f"  Duplicate URLs found: {len(dupes)}")
    for url, cnt in dupes[:5]:
        print(f"    {cnt}x  {url}")

    print("\n" + "=" * 60)
    print("5. PRICE SANITY")
    print("=" * 60)
    zero_or_negative = db.query(ProductDB).filter(ProductDB.price <= 0).count()
    absurd_high = db.query(ProductDB).filter(ProductDB.price > 50000).count()
    print(f"  Zero or negative prices: {zero_or_negative}")
    print(f"  Prices over 50,000 SAR (suspicious for a phone): {absurd_high}")
    if absurd_high > 0:
        rows = db.query(ProductDB).filter(ProductDB.price > 50000).limit(5).all()
        for r in rows:
            print(f"    id={r.id} price={r.price} name={r.name[:50]!r}")

    print("\n" + "=" * 60)
    print("6. RATING OUT OF RANGE (should be 0-5)")
    print("=" * 60)
    bad_rating = (
        db.query(ProductDB)
        .filter((ProductDB.rating < 0) | (ProductDB.rating > 5))
        .count()
    )
    print(f"  Ratings outside 0-5: {bad_rating}")

    print("\n" + "=" * 60)
    print("7. NEGATIVE REVIEW COUNTS (would indicate parsing bug)")
    print("=" * 60)
    bad_reviews = db.query(ProductDB).filter(ProductDB.reviews < 0).count()
    print(f"  Negative review counts: {bad_reviews}")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)

finally:
    db.close()