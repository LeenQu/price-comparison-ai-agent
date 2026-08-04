from crawlers.amazon.crawler import AmazonCrawler

crawler = AmazonCrawler()

products = crawler.search("iphone")

for product in products:
    print(product)