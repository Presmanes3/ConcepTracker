from sqlmodel import SQLModel, create_engine
import os
from dotenv import load_dotenv

# Ensure all database models are loaded so SQLModel knows them
from shared.schemas.models.archipelago import Archipelago
from shared.schemas.models.note import Note
from shared.schemas.models.link import Link
from shared.schemas.models.inference_log import InferenceLog

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def reset_db():
    print("Dropping tables...")
    SQLModel.metadata.drop_all(engine)
    print("Creating tables with 1024 dimensions...")
    SQLModel.metadata.create_all(engine)
    print("Database reset successfully.")

if __name__ == "__main__":
    reset_db()
