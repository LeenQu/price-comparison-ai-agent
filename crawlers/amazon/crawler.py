from playwright.sync_api import sync_playwright
from models.products import Product
import re
import random


class AmazonCrawler:
    BASE_URL = "https://www.amazon.sa"
    MAX_PRODUCTS = 200
    MAX_PAGES = 20  # safety cap so we never loop forever

    # Words that signal an accessory rather than an actual phone.
    # Checked case-insensitively against the product title.
    ACCESSORY_KEYWORDS = [
        "case", "cover", "screen protector", "protector", "tempered glass",
        "glass", "charger", "cable", "adapter", "holder", "stand", "mount",
        "skin", "sticker", "lens protector", "camera protector", "strap",
        "pouch", "sleeve", "bumper", "kickstand", "wallet", "power bank",
        "powerbank", "earphone", "headphone", "airpods", "wireless charger",
        "car mount", "ring holder", "popsocket", "grip",
    ]

    def _is_accessory(self, title):
        if not title:
            return True  # no title at all — can't confirm it's a real phone, drop it

        title_lower = title.lower()

        # Strong signal: accessory titles almost always say "for iPhone X",
        # while real phone listings just say "iPhone X".
        if "for iphone" in title_lower or "for apple iphone" in title_lower:
            return True

        return any(keyword in title_lower for keyword in self.ACCESSORY_KEYWORDS)

    def safe_text(self, locator):
        try:
            if locator.count() > 0:
                return locator.first.inner_text().strip()
        except:
            pass
        return None

    def safe_attr(self, locator, attr):
        try:
            if locator.count() > 0:
                return locator.first.get_attribute(attr)
        except:
            pass
        return None

    def _parse_card(self, card):
        """Extract a single Product from one search-result card, or None."""

        asin = card.get_attribute("data-asin")

        if not asin:
            return None

        title = self.safe_text(card.locator("h2 span"))

        # ---------------- Price ----------------
        price = None
        price_text = self.safe_text(card.locator(".a-price .a-offscreen"))
        if price_text:
            match = re.search(r"([\d,]+\.\d+)", price_text)
            if match:
                price = float(match.group(1).replace(",", ""))

        # ---------------- Rating ----------------
        rating = None
        rating_text = self.safe_text(card.locator(".a-icon-alt"))
        if rating_text:
            match = re.search(r"(\d+(\.\d+)?)", rating_text)
            if match:
                rating = float(match.group(1))

        # ---------------- Reviews ----------------
        reviews = None
        review_text = self.safe_text(
            card.locator('a[href*="#customerReviews"] span')
        )
        if review_text:
            match = re.search(r"(\d[\d,]*)", review_text)
            if match:
                reviews = int(match.group(1).replace(",", ""))

        # ---------------- Image ----------------
        image = self.safe_attr(card.locator("img.s-image"), "src")

        # ---------------- Product URL ----------------
        product_url = None
        try:
            links = card.locator("a[href*='/dp/']")
            if links.count() > 0:
                href = links.first.get_attribute("href")
                if href:
                    product_url = self.BASE_URL + href if href.startswith("/") else href
        except:
            pass

        # Skip cards where we couldn't get a title or url — they're not
        # usable products (often ads/placeholders/sponsored widgets)
        if not title or not product_url:
            return None

        return Product(
            website="Amazon",
            title=title,
            price=price,
            rating=rating,
            reviews=reviews,
            image=image,
            url=product_url,
            asin=asin,
        )

    def search(self, query):

        results = []
        seen_asins = set()
        skipped_accessories = 0
        consecutive_empty_pages = 0

        with sync_playwright() as p:

            browser = p.chromium.launch(headless=False)
            page = browser.new_page()

            for page_num in range(1, self.MAX_PAGES + 1):

                if len(results) >= self.MAX_PRODUCTS:
                    break

                url = f"{self.BASE_URL}/s?k={query}&page={page_num}"
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(random.randint(2000, 4000))

                cards = page.locator('[data-component-type="s-search-result"]')
                total = cards.count()

                print(f"\nPage {page_num}: found {total} cards")

                if total == 0:
                    # No more results — stop paginating
                    break

                new_on_this_page = 0

                for i in range(total):

                    if len(results) >= self.MAX_PRODUCTS:
                        break

                    card = cards.nth(i)
                    product = self._parse_card(card)

                    if not product:
                        continue

                    if self._is_accessory(product.title):
                        skipped_accessories += 1
                        continue

                    if product.asin in seen_asins:
                        continue

                    seen_asins.add(product.asin)
                    results.append(product)
                    new_on_this_page += 1

                    print(f"  [{len(results)}] {product.title[:60]}")

                # A single page with zero new products just means it was
                # accessory-heavy — that's fine, keep going. But if TWO
                # pages in a row add nothing, Amazon is likely looping the
                # same results, so bail out to avoid an endless crawl.
                if new_on_this_page == 0:
                    consecutive_empty_pages += 1
                    if consecutive_empty_pages >= 2:
                        print("Two empty pages in a row, stopping.")
                        break
                else:
                    consecutive_empty_pages = 0

            browser.close()

        print(f"\nTotal unique products collected: {len(results)}")
        print(f"Skipped as accessories: {skipped_accessories}")

        return results