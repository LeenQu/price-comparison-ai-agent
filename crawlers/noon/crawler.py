import re
from urllib.parse import urljoin, quote_plus

from playwright.sync_api import sync_playwright

from database.save_products import save_products
from models.products import Product

MAX_PAGES = 5
MAX_PRODUCTS = 200

BANNED_WORDS = [
    "case",
    "cover",
    "charger",
    "screen protector",
    "protector",
    "wallet",
    "airpods",
    "airtag",
    "watch",
    "tracker",
    "cable",
    "adapter",
    "power bank",
]


def parse_reviews_count(text):
    """
    Convert Noon's abbreviated review-count text into a plain integer
    so it fits the `reviews` INTEGER column.

    Examples: "1.4K" -> 1400, "29.0K" -> 29000, "3.6M" -> 3600000,
    "1,234" -> 1234, "842" -> 842
    """
    if not text:
        return None

    text = text.strip().upper().rstrip("+")

    match = re.match(r"^(\d+(?:\.\d+)?)([KM]?)$", text.replace(",", ""))
    if not match:
        return None

    number = float(match.group(1))
    suffix = match.group(2)

    if suffix == "K":
        number *= 1_000
    elif suffix == "M":
        number *= 1_000_000

    return int(round(number))


def parse_rating(text):
    """Convert a rating string like '4.6' into a float for the FLOAT column."""
    if not text:
        return None

    try:
        return float(text.strip())
    except ValueError:
        return None


def valid_product(title):
    if not title:
        return False

    title = title.lower()

    if "iphone" not in title:
        return False

    return not any(word in title for word in BANNED_WORDS)


class NoonCrawler:

    BASE_URL = "https://www.noon.com/saudi-en"

    def search(self, query):

        product_urls = set()

        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=False,
                slow_mo=50
            )

            try:

                context = browser.new_context(
                    viewport={"width": 1600, "height": 900},
                    user_agent="Mozilla/5.0"
                )

                page = context.new_page()

                # ---------------------------------------
                # STEP 1 - Collect product URLs
                # ---------------------------------------

                for page_num in range(1, MAX_PAGES + 1):

                    encoded_query = quote_plus(query)

                    url = (
                        f"{self.BASE_URL}/search"
                        f"?q={encoded_query}&page={page_num}"
                    )

                    print(f"\n===== PAGE {page_num} =====")

                    page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )

                    try:
                        page.wait_for_selector(
                            "div[data-qa='plp-product-box']",
                            timeout=15000
                        )
                    except Exception:
                        print("No product cards found.")
                        break

                    cards = page.locator(
                        "div[data-qa='plp-product-box']"
                    )

                    count = cards.count()

                    print("Cards found:", count)

                    if count == 0:
                        break

                    new_products = 0

                    for i in range(count):

                        try:

                            card = cards.nth(i)

                            href = card.locator("a").first.get_attribute("href")

                            if not href:
                                continue

                            href = urljoin(self.BASE_URL, href)

                            if href not in product_urls:
                                product_urls.add(href)
                                new_products += 1

                                if len(product_urls) >= MAX_PRODUCTS:
                                    break

                        except Exception:
                            continue

                    print("New unique products:", new_products)

                    if len(product_urls) >= MAX_PRODUCTS:
                        break

                print(f"\nCollected {len(product_urls)} unique URLs")

                # ---------------------------------------
                # STEP 2 - Visit product pages
                # ---------------------------------------

                results = []
                batch = []

                total = len(product_urls)

                for index, product_url in enumerate(product_urls, start=1):

                    print(f"[{index}/{total}]")

                    try:

                        page.goto(
                            product_url,
                            wait_until="domcontentloaded",
                            timeout=60000
                        )

                        page.wait_for_selector(
                            "h1",
                            timeout=10000
                        )

                        # ---------------- TITLE ----------------

                        try:
                            title = (
                                page.locator("h1")
                                .first
                                .inner_text()
                                .strip()
                            )
                        except Exception:
                            continue

                        if not valid_product(title):
                            continue

                        # ---------------- PRICE ----------------

                        price = None

                        try:

                            price_locator = page.locator(
                                "div[data-qa='product-price'] strong"
                            )

                            if price_locator.count() == 0:

                                price_locator = (
                                    page.locator("strong")
                                    .filter(
                                        has_text=re.compile(
                                            r"^\d[\d,]*$"
                                        )
                                    )
                                )

                            text = (
                                price_locator
                                .first
                                .inner_text()
                            )

                            match = re.search(
                                r"([\d,]+)",
                                text
                            )

                            if match:
                                price = float(
                                    match.group(1).replace(",", "")
                                )

                        except Exception:
                            pass

                        if price is None:
                            continue

                        # ---------------- RATING ----------------

                        rating = None

                        try:

                            rating = parse_rating(
                                page.locator("span")
                                .filter(
                                    has_text=re.compile(
                                        r"^[1-5]\.\d$"
                                    )
                                )
                                .first
                                .inner_text()
                                .strip()
                            )

                        except Exception:
                            pass

                        # ---------------- REVIEWS ----------------

                        reviews = None

                        try:

                            spans = page.locator("span")
                            span_count = spans.count()

                            for j in range(span_count):

                                text = (
                                    spans.nth(j)
                                    .inner_text()
                                    .strip()
                                )

                                if re.match(
                                    r"^\d+(\.\d+)?[KM]\+?$",
                                    text
                                ):
                                    reviews = parse_reviews_count(text)
                                    break

                        except Exception:
                            pass

                        # ---------------- IMAGE ----------------

                        image = None

                        try:

                            img = page.locator(
                                "img[src*='nooncdn']"
                            ).first

                            image = img.get_attribute("src")

                            if not image:
                                image = img.get_attribute(
                                    "data-src"
                                )

                        except Exception:
                            pass

                        product = Product(
                            website="Noon",
                            title=title,
                            price=price,
                            rating=rating,
                            reviews=reviews,
                            image=image,
                            url=product_url,
                        )

                        results.append(product)
                        batch.append(product)

                        if len(batch) == 20:
                            save_products(batch)
                            print(
                                f"Saved {len(batch)} products."
                            )
                            batch.clear()

                    except Exception as e:
                        print(
                            f"\nError processing:\n"
                            f"{product_url}\n{e}"
                        )

                if batch:
                    save_products(batch)
                    print(
                        f"Saved final {len(batch)} products."
                    )

                return results

            finally:
                browser.close()