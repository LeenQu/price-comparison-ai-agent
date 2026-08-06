import re
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


def valid_product(title):
    if not title:
        return False

    title = title.lower()

    if "iphone" not in title:
        return False

    for word in BANNED_WORDS:
        if word in title:
            return False

    return True


class NoonCrawler:

    BASE_URL = "https://www.noon.com/saudi-en"

    def search(self, query):

        product_urls = {}

        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=False,
                slow_mo=50
            )

            context = browser.new_context(
                viewport={"width": 1600, "height": 900},
                user_agent="Mozilla/5.0"
            )

            page = context.new_page()

            # ---------------------------------------
            # STEP 1 - Collect product URLs
            # ---------------------------------------
            for page_num in range(1, MAX_PAGES + 1):

                url = f"{self.BASE_URL}/search?q={query}&page={page_num}"

                print(f"\n===== PAGE {page_num} =====")

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                page.wait_for_timeout(3000)

                links = page.locator("a[href*='/p/']")
                count = links.count()

                print("Links found:", count)

                if count == 0:
                    break

                new_products = 0

                for i in range(count):

                    try:

                        href = links.nth(i).get_attribute("href")

                        if not href:
                            continue

                        if href.startswith("/"):
                            href = "https://www.noon.com" + href

                        if href not in product_urls:
                            product_urls[href] = True
                            new_products += 1

                            if len(product_urls) >= MAX_PRODUCTS:
                                break

                    except:
                        continue

                print("New unique products:", new_products)

                if len(product_urls) >= MAX_PRODUCTS:
                    break

            print(f"\nCollected {len(product_urls)} unique URLs")

            # ---------------------------------------
            # STEP 2 - Visit product pages
            # ---------------------------------------
            results = []

            total = len(product_urls)

            for index, product_url in enumerate(product_urls.keys(), start=1):

                print(f"[{index}/{total}]")

                try:

                    page.goto(
                        product_url,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )

                    page.wait_for_timeout(1500)

                    # TITLE
                    title = None
                    try:
                        title = page.locator("h1").first.inner_text().strip()
                    except:
                        pass

                    if not valid_product(title):
                        continue

                    # PRICE
                    price = None
                    try:
                        text = page.locator("strong").first.inner_text()
                        match = re.search(r"([\d,]+)", text)
                        if match:
                            price = float(match.group(1).replace(",", ""))
                    except:
                        pass

                    if price is None:
                        continue

                    # RATING
                    rating = None
                    try:
                        rating = page.locator("span:has-text('.')").first.inner_text().strip()
                    except:
                        pass

                    # REVIEWS
                    reviews = None
                    try:
                        reviews = page.locator("text=Ratings").first.inner_text().strip()
                    except:
                        pass

                    # IMAGE
                    image = None
                    try:
                        img = page.locator("img[src*='nooncdn']").first

                        image = img.get_attribute("src")

                        if not image:
                            image = img.get_attribute("data-src")

                    except:
                        pass

                    # product = {
                    #     "website": "Noon",
                    #     "title": title,
                    #     "price": price,
                    #     "rating": rating,
                    #     "reviews": reviews,
                    #     "image": image,
                    #     "url": product_url
                    # }

                    # results.append(product)
                    
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

                    # Save every 20 products
                    if len(results) % 20 == 0:
                        save_products(results[-20:])
                        print(f"Saved {len(results)} products to database...")

                except Exception as e:
                    print(e)

            # Save remaining products
            remaining = len(results) % 20

            if remaining:
                save_products(results[-remaining:])
                print(f"Saved final {remaining} products.")

            browser.close()

            return results