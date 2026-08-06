from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)

    page = browser.new_page()

    page.goto(
        "https://www.amazon.sa/s?k=iphone",
        wait_until="domcontentloaded"
    )

    page.wait_for_timeout(5000)

    card = page.locator('[data-component-type="s-search-result"]').first

    print(card.inner_html())

    input("Press Enter...")

    browser.close()