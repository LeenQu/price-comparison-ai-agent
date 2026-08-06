from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, Float


class Base(DeclarativeBase):
    pass


class ProductDB(Base):

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)

    website = Column(String, nullable=False)

    name = Column(String, nullable=False)

    price = Column(Float)

    rating = Column(Float)

    reviews = Column(Integer)

    image = Column(String)

    product_url = Column(String, unique=True, nullable=False)