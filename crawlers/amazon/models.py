from dataclasses import dataclass

@dataclass
class AmazonProduct:
    asin: str = ""
    title: str = ""
    brand: str = ""
    model: str = ""
    color: str = ""
    storage: str = ""
    price: float = 0.0
    currency: str = "SAR"
    rating: float = 0.0
    reviews: int = 0
    availability: str = ""
    prime: bool = False
    image_url: str = ""
    product_url: str = ""