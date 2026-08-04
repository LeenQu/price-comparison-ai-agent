from crawlers.noon.crawler import NoonCrawler

crawler = NoonCrawler()

results = crawler.search("iphone")

for product in results:
    print(product)