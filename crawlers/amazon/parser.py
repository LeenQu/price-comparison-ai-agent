from bs4 import BeautifulSoup
from models.product import Product

def parse_noon_product(html):

    soup = BeautifulSoup(html, "html.parser")

    card = soup.find("a")

    if not card:
        return None

    title = card.find(
        "h2",
        attrs={"data-qa":"plp-product-box-name"}
    ).get_text(strip=True)

    url = "https://www.noon.com" + card["href"]

    image = card.find(
        "img",
        class_="_productImage_1yztz_82"
    )["src"]

    price = float(
        card.find(
            "strong",
            class_="_amount_1o2w0_59"
        ).text.replace(",", "")
    )

    rating = float(
        card.find(
            "div",
            class_="_textCtr_1r83y_16"
        ).text
    )

    review_text = card.find(
        "div",
        class_="_countCtr_1r83y_47"
    ).find("span").text

    if "K" in review_text:
        reviews = int(float(review_text.replace("K",""))*1000)
    else:
        reviews = int(review_text.replace(",",""))

    return Product(
        website="Noon",
        title=title,
        price=price,
        rating=rating,
        reviews=reviews,
        image=image,
        url=url
    )