from crawlers.amazon.crawler import AmazonCrawler
from database.save_products import save_products

crawler = AmazonCrawler()

products = crawler.search("iphone")

save_products(products)

print(f"\nCollected {len(products)} products\n")

for product in products:
    print(product)