from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Float


class Base(DeclarativeBase):
    pass


class Product(Base):

    __tablename__ = "products"

    id = Column(Integer, primary_key=True)

    website = Column(String)

    name = Column(String)

    price = Column(Float)

    rating = Column(Float)

    reviews = Column(Integer)

    image = Column(String)

    product_url = Column(String)