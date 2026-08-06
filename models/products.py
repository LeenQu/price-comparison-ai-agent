from dataclasses import dataclass
from typing import Optional


@dataclass
class Product:
    website: str
    title: str
    price: Optional[float]
    rating: Optional[float]
    reviews: Optional[int]
    image: Optional[str]
    url: Optional[str]
    asin: Optional[str] = None  # Amazon-specific unique ID, None for other sites