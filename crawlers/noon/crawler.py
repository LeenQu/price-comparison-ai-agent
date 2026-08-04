import re
from playwright.sync_api import sync_playwright


class NoonCrawler:

    BASE_URL = "https://www.noon.com/saudi-en"

    def search(self, query):

        results = []

        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=False,
                slow_mo=300
            )

            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
            )

            page = context.new_page()

            page.goto(
                f"{self.BASE_URL}/search?q={query}",
                wait_until="networkidle"
            )

            page.wait_for_timeout(5000)

            print("Title:", page.title())
            print("URL:", page.url)

            page.screenshot(path="noon_page.png", full_page=True)

            links = page.locator("a[href*='/p/']")

            print("Found product links:", links.count())

            count = min(5, links.count())

            for i in range(count):

                try:
                    product = links.nth(i)

                    text = product.inner_text().strip()

                    lines = [line.strip() for line in text.split("\n") if line.strip()]

                    if not lines:
                        continue

                    title = lines[0]

                    price = None

                    for line in lines:
                        match = re.search(r"(\d{1,3}(?:,\d{3})*)", line)

                        if match:
                            value = match.group(1).replace(",", "")

                            if int(value) > 500:
                                price = float(value)
                                break

                    results.append({
                    "website": "Noon",
                    "name": title,
                    "price": price,
                    "rating": None,
                    "reviews": None,
                    "image": None,
                    "product_url": None
                  })

                except Exception as e:
                    print(e)

            browser.close()

        return results