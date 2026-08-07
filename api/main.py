from fastapi import FastAPI, BackgroundTasks, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from database.database import SessionLocal
from database.models import ProductDB
from database.save_products import save_products
from crawlers.amazon.crawler import AmazonCrawler
from crawlers.noon.crawler import NoonCrawler
from services.claude_service import (
    ask_about_products,
    compare_prices_across_sites,
    recommend_product,
)
from services.ollama_service import ask_about_products_ollama

app = FastAPI(
    title="Price Comparison API",
    version="1.0"
)

# Allows the frontend (a locally-opened HTML file, or served from a
# different port) to call this API from the browser. Open to all
# origins for local development - if this is ever deployed publicly,
# this should be restricted to your actual frontend's domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _serialize(p: ProductDB) -> dict:
    return {
        "id": p.id,
        "website": p.website,
        "name": p.name,
        "price": p.price,
        "rating": p.rating,
        "reviews": p.reviews,
        "image": p.image,
        "product_url": p.product_url,
        "asin": p.asin,
    }


@app.get("/")
def home():
    return {"message": "Price Comparison API is running"}


@app.get("/products")
def get_products(
    website: Optional[str] = None,
    limit: int = Query(100, le=500),
):
    """
    Lists products already saved in the database.
    Optional filters: website (e.g. "Amazon" or "Noon"), limit.
    """

    db = SessionLocal()

    try:
        q = db.query(ProductDB)

        if website:
            q = q.filter(ProductDB.website.ilike(website))

        products = q.limit(limit).all()

        return [_serialize(p) for p in products]

    finally:
        db.close()


@app.get("/ask")
def ask(
    query: str,
    question: str,
    limit: int = Query(50, le=100),
):
    """
    Answers a natural-language question about products already saved
    in the database (e.g. query="iphone",
    question="which is the cheapest one with good reviews?").

    `query` narrows down which saved products to hand to Claude
    (same matching as /search). `question` is what you actually want
    to know. Does NOT trigger a live crawl - search/crawl first if
    the database doesn't have what you need yet.
    """

    db = SessionLocal()

    try:
        products = (
            db.query(ProductDB)
            .filter(ProductDB.name.ilike(f"%{query}%"))
            .limit(limit)
            .all()
        )

        try:
            structured_answer = ask_about_products(question, products)
        except RuntimeError as e:
            # e.g. CLAUDE_API_KEY missing
            raise HTTPException(status_code=503, detail=str(e))

        return {
            "query": query,
            "question": question,
            "based_on_products": len(products),
            **structured_answer,
        }

    finally:
        db.close()


@app.get("/recommend")
def recommend(
    category: str = "iphone",
    budget_max: Optional[float] = None,
    min_rating: Optional[float] = None,
    storage: Optional[str] = None,
    website: Optional[str] = None,
    limit: int = Query(60, le=150),
):
    """
    Recommends the best product matching structured filters.

    Filters are applied in SQL first (hard constraints - guaranteed
    correct), and Claude only picks/explains the best candidate among
    what's already been filtered. This means Claude can never recommend
    something outside your stated budget or rating, for example.

    - category: keyword to search for, e.g. "iphone" (default), "iphone 15"
    - budget_max: maximum price in SAR
    - min_rating: minimum rating (0-5)
    - storage: substring match against the name, e.g. "128GB", "256GB"
    - website: "Amazon" or "Noon" to restrict to one site
    """

    db = SessionLocal()

    try:
        q = db.query(ProductDB).filter(ProductDB.name.ilike(f"%{category}%"))

        if budget_max is not None:
            q = q.filter(ProductDB.price <= budget_max)

        if min_rating is not None:
            q = q.filter(ProductDB.rating >= min_rating)

        if storage:
            q = q.filter(ProductDB.name.ilike(f"%{storage}%"))

        if website:
            q = q.filter(ProductDB.website.ilike(website))

        candidates = (
            q.order_by(ProductDB.rating.desc().nullslast(), ProductDB.price.asc())
            .limit(limit)
            .all()
        )

        preferences_parts = [f"category: {category}"]
        if budget_max is not None:
            preferences_parts.append(f"budget <= {budget_max} SAR")
        if min_rating is not None:
            preferences_parts.append(f"min rating {min_rating}")
        if storage:
            preferences_parts.append(f"storage: {storage}")
        if website:
            preferences_parts.append(f"website: {website}")
        preferences_description = ", ".join(preferences_parts)

        try:
            recommendation = recommend_product(preferences_description, candidates)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))

        return {
            "filters": {
                "category": category,
                "budget_max": budget_max,
                "min_rating": min_rating,
                "storage": storage,
                "website": website,
            },
            "candidates_found": len(candidates),
            **recommendation,
        }

    finally:
        db.close()


@app.get("/ask-local")
def ask_local(
    query: str,
    question: str,
    limit: int = Query(50, le=100),
):
    """
    Same as /ask, but answers using a local Ollama model instead of
    the Claude API - free, no API key needed, but requires Ollama
    running locally and is generally lower quality/slower than Claude
    on the same task.
    """

    db = SessionLocal()

    try:
        products = (
            db.query(ProductDB)
            .filter(ProductDB.name.ilike(f"%{query}%"))
            .limit(limit)
            .all()
        )

        try:
            structured_answer = ask_about_products_ollama(question, products)
        except RuntimeError as e:
            # e.g. Ollama not running
            raise HTTPException(status_code=503, detail=str(e))

        return {
            "query": query,
            "question": question,
            "based_on_products": len(products),
            "backend": "ollama",
            **structured_answer,
        }

    finally:
        db.close()


@app.get("/compare")
def compare(
    query: str,
    limit_per_website: int = Query(30, le=100),
):
    """
    Finds the same phone model listed on both Amazon and Noon (for
    products already saved in the database) and returns a price
    comparison for each match. Does NOT trigger a live crawl -
    search/crawl first if the database doesn't have what you need yet.

    limit_per_website applies separately to each site, so a low limit
    can't let one site's results crowd out the other's.
    """

    db = SessionLocal()

    try:
        amazon_products = (
            db.query(ProductDB)
            .filter(
                ProductDB.website == "Amazon",
                ProductDB.name.ilike(f"%{query}%"),
            )
            .limit(limit_per_website)
            .all()
        )

        noon_products = (
            db.query(ProductDB)
            .filter(
                ProductDB.website == "Noon",
                ProductDB.name.ilike(f"%{query}%"),
            )
            .limit(limit_per_website)
            .all()
        )

        products = amazon_products + noon_products

        try:
            comparison = compare_prices_across_sites(query, products)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))

        return {
            "query": query,
            "based_on_products": len(products),
            "amazon_matches_found": len(amazon_products),
            "noon_matches_found": len(noon_products),
            **comparison,
        }

    finally:
        db.close()


@app.get("/search")
def search(
    query: str,
    website: Optional[str] = None,
    limit: int = Query(50, le=200),
):
    """
    Fast search over products already saved in the database.
    Does NOT trigger a live crawl - use POST /crawl for that.

    website filter is applied in SQL before the limit, so it can't
    be crowded out by results from the other site.
    """

    db = SessionLocal()

    try:
        q = db.query(ProductDB).filter(ProductDB.name.ilike(f"%{query}%"))

        if website:
            q = q.filter(ProductDB.website.ilike(website))

        products = q.limit(limit).all()

        return {
            "query": query,
            "count": len(products),
            "results": [_serialize(p) for p in products],
        }

    finally:
        db.close()


def _run_crawl(query: str):
    """
    Runs both crawlers for a query and saves results.
    Each crawler is wrapped separately so a failure in one
    (e.g. a site changing its layout) doesn't prevent the
    other from saving its results.
    """

    try:
        amazon_results = AmazonCrawler().search(query)
        save_products(amazon_results)
    except Exception as e:
        print(f"\n\u274c Amazon crawl failed for '{query}': {e}")

    try:
        noon_results = NoonCrawler().search(query)
        save_products(noon_results)
    except Exception as e:
        print(f"\n\u274c Noon crawl failed for '{query}': {e}")


@app.post("/crawl")
def trigger_crawl(query: str, background_tasks: BackgroundTasks):
    """
    Triggers a live crawl of Amazon and Noon for the given query.
    Runs in the background (can take a few minutes) so this request
    returns immediately. Check /search or /products afterward.
    """

    background_tasks.add_task(_run_crawl, query)

    return {
        "status": "started",
        "query": query,
        "message": "Crawl running in background. Check /search or /products shortly for results.",
    }