from fastapi import FastAPI
from database.connection import SessionLocal
from database.models import Product
from crawlers.amazon.crawler import AmazonCrawler
from crawlers.noon.crawler import NoonCrawler
from services.product_service import save_products

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
        products = db.query(Product).all()

        return [
            {
                "id": p.id,
                "website": p.website,
                "name": p.name,
                "price": p.price
            }
            for p in products
        ]

    finally:
        db.close()


@app.get("/search")
def search(query: str):

    amazon = AmazonCrawler().search(query)
    noon = NoonCrawler().search(query)

    save_products(amazon)
    save_products(noon)

    return {
        "amazon": amazon,
        "noon": noon
    }