import os
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# pool_pre_ping=True makes SQLAlchemy test each pooled connection with a
# lightweight "SELECT 1" before handing it to a request handler.  This
# transparently recovers from stale connections after a DB restart or
# network hiccup, so workers never see a silent broken socket.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    hide_parameters=True,  # Keep credentials/auth-token payloads out of DB error logs.
    connect_args={"connect_timeout": 5},  # fail fast on unreachable host
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Re-export so callers can catch DB errors without importing SQLAlchemy directly.
DatabaseOperationalError = OperationalError
