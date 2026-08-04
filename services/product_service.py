from database.connection import SessionLocal
from database.models import Product


def save_products(products):

    db = SessionLocal()

    try:
        for product in products:

            db_product = Product(
                website=product["website"],
                name=product["name"],
                price=product["price"],
                rating=product.get("rating"),
                reviews=product.get("reviews"),
                image=product.get("image"),
                product_url=product.get("product_url")
            )

            db.add(db_product)

        db.commit()

    finally:
        db.close()