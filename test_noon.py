from crawlers.noon.crawler import NoonCrawler

SEARCH_QUERIES = [
    "iphone",
]

crawler = NoonCrawler()

all_products = []

for query in SEARCH_QUERIES:

    print(f"\nSearching: {query}")

    products = crawler.search(query)

    all_products.extend(products)

print(f"\nCollected {len(all_products)} products.")