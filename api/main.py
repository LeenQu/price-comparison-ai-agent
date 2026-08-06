from fastapi import FastAPI
from dataclasses import asdict

from database.database import SessionLocal
from database.models import ProductDB
from database.save_products import save_products
from crawlers.amazon.crawler import AmazonCrawler
from crawlers.noon.crawler import NoonCrawler

app = FastAPI(
    title="Price Comparison API",
    version="1.0"
)


@app.get("/")
def home():
    return {"message": "Price Comparison API is running"}


@app.get("/products")
def get_products():

    db = SessionLocal()

    try:
        products = db.query(ProductDB).all()

        return [
            {
                "id": p.id,
                "website": p.website,
                "name": p.name,
                "price": p.price,
                "rating": p.rating,
                "reviews": p.reviews,
                "image": p.image,
                "product_url": p.product_url,
            }
            for p in products
        ]

    finally:
        db.close()


@app.get("/search")
def search(query: str):

    # NOTE: this runs both crawlers live, headless=False, with pagination
    # up to 200 products for Amazon — this endpoint can take a while
    # (potentially minutes) per request. Fine for now while developing,
    # but worth revisiting (background jobs / caching) before this is
    # user-facing.

    amazon = AmazonCrawler().search(query)
    noon = NoonCrawler().search(query)

    save_products(amazon)
    save_products(noon)

    return {
        "amazon": [asdict(p) for p in amazon],
        "noon": [asdict(p) for p in noon],
    }