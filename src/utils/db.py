import os
from sqlmodel import create_engine, Session, SQLModel, text
from dotenv import load_dotenv

# Ensure all database models are loaded for SQLModel metadata
from shared.schemas.models.archipelago import Archipelago
from shared.schemas.models.note import Note
from shared.schemas.models.link import Link
from shared.schemas.models.inference_log import InferenceLog
from shared.schemas.models.transcription import Transcription

load_dotenv()

class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance.engine = create_engine(os.getenv("DATABASE_URL"))
        return cls._instance

    def init_db(self):
        # Make sure pgvector extension exists
        with self.engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        return Session(self.engine)

    def health_check(self):
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print(f"DB Health Check Failed: {e}")
            return False

# Convenience global instance
db_manager = DatabaseManager()

def init_db():
    db_manager.init_db()

def get_session():
    return db_manager.get_session()

def health_check():
    return db_manager.health_check()

if __name__ == "__main__":
    init_db()
    if health_check():
        print("Database is healthy and tables are created.")
    else:
        print("Database connection failed.")
