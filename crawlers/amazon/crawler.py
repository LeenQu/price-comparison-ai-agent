from playwright.sync_api import sync_playwright
import re


class AmazonCrawler:

    BASE_URL = "https://www.amazon.sa"

    def search(self, query):

        results = []

        with sync_playwright() as p:

            browser = p.chromium.launch(headless=False)

            page = browser.new_page()

            page.goto(
                f"{self.BASE_URL}/s?k={query}",
                wait_until="domcontentloaded"
            )

            page.wait_for_timeout(3000)

            product_cards = page.locator('[data-component-type="s-search-result"]')

            count = min(5, product_cards.count())

            print(f"Found {count} products\n")

            for i in range(count):

                card = product_cards.nth(i)

                # ---------------- Title ----------------
                try:
                    title = card.locator("h2 span").first.inner_text().strip()
                except Exception:
                    title = None

                # ---------------- Price ----------------
                try:
                    price = None

                    price_text = card.locator(".a-price").first.inner_text()

                    match = re.search(r"(\d[\d,]*\.\d{2})", price_text)

                    if match:
                        price = float(match.group(1).replace(",", ""))

                except Exception:
                    price = None

                # ---------------- Rating ----------------
                try:
                    rating = None

                    rating_text = card.locator("span.a-icon-alt").first.inner_text()

                    match = re.search(r"(\d+(\.\d+)?)", rating_text)

                    if match:
                        rating = float(match.group(1))

                except Exception:
                    rating = None

                # ---------------- Reviews ----------------
                try:
                    reviews = None

                    review_link = card.locator("a[aria-label*='ratings']").first

                    if review_link.count() > 0:

                        review_text = review_link.get_attribute("aria-label")

                        match = re.search(r"(\d[\d,]*)", review_text)

                        if match:
                            reviews = int(match.group(1).replace(",", ""))

                except Exception:
                    reviews = None

                # ---------------- Image ----------------
                try:
                    image = card.locator("img").first.get_attribute("src")
                except Exception:
                    image = None

                # ---------------- Product URL ----------------
                try:
                    links = card.locator("a")

                    print("Number of links:", links.count())

                    for j in range(min(5, links.count())):
                        print(
                            j,
                            links.nth(j).get_attribute("href")
                        )

                    product_url = None

                except Exception:
                    product_url = None

                product = {
                    "website": "Amazon",
                    "name": title,
                    "price": price,
                    "rating": rating,
                    "reviews": reviews,
                    "image": image,
                    "product_url": product_url
                }

                results.append(product)
                print(card.locator("a[aria-label*='ratings']").count())
                
            browser.close()

        return results