from database.database import SessionLocal
from database.models import ProductDB


def save_products(products):
    """
    Save products from any crawler
    (Amazon Product objects or Noon dictionaries)
    into PostgreSQL.
    """

    db = SessionLocal()

    try:

        saved = 0

        for product in products:

            # Amazon returns Product objects
            if not isinstance(product, dict):
                website = product.website
                title = product.title
                price = product.price
                rating = product.rating
                reviews = product.reviews
                image = product.image
                url = product.url
                asin = getattr(product, "asin", None)

            # Noon returns dictionaries
            else:
                website = product["website"]
                title = product["title"]
                price = product["price"]
                rating = product["rating"]
                reviews = product["reviews"]
                image = product["image"]
                url = product["url"]
                asin = product.get("asin")

            if not url:
                continue

            # Prevent duplicates using URL
            exists = (
                db.query(ProductDB)
                .filter(ProductDB.product_url == url)
                .first()
            )

            if exists:
                continue

            new_product = ProductDB(
                website=website,
                name=title,
                price=price,
                rating=rating,
                reviews=reviews,
                image=image,
                product_url=url,
                asin=asin,
            )

            db.add(new_product)
            saved += 1

        db.commit()

        print(f"\n✅ Saved {saved} new products to PostgreSQL.")

    except Exception as e:

        db.rollback()
        print(f"\n❌ Database Error: {e}")

    finally:

        db.close()