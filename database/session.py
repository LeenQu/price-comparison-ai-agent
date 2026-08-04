from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.database import DATABASE_URL

# engine = create_engine(DATABASE_URL)

# SessionLocal = sessionmaker(
#     autoflush=False,
#     autocommit=False,
#     bind=engine
# )