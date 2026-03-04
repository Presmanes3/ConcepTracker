import os
import threading
import boto3
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class TranscribeService:
    """
    Singleton service to interact with AWS Transcribe.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TranscribeService, cls).__new__(cls)
                cls._instance._init_service()
        return cls._instance

    def _init_service(self):
        """Initialize the Transcribe client."""
        ak = os.getenv("AWS_ACCESS_KEY_ID")
        sk = os.getenv("AWS_SECRET_ACCESS_KEY")
        region = os.getenv("AWS_REGION", "eu-west-1")
        profile = os.getenv("AWS_PROFILE")

        session_kwargs = {}
        if profile:
            session_kwargs["profile_name"] = profile
        if ak and sk:
            session_kwargs["aws_access_key_id"] = ak
            session_kwargs["aws_secret_access_key"] = sk
        if region:
            session_kwargs["region_name"] = region

        session = boto3.Session(**session_kwargs)
        self.client = session.client("transcribe")

    def health_check(self) -> dict:
        """Check if the Transcribe service is accessible."""
        try:
            # A simple call to list transcription jobs to verify connectivity and permissions
            self.client.list_transcription_jobs(MaxResults=1)
            return {"status": "healthy"}
        except Exception as e:
            error_msg = str(e)
            if "MissingRegionError" in error_msg:
                hint = "AWS_REGION is missing."
            elif "NoCredentialsError" in error_msg:
                hint = "AWS credentials not found."
            elif "InvalidClientTokenId" in error_msg:
                hint = "Invalid AWS Access Key."
            elif "SignatureDoesNotMatch" in error_msg:
                hint = "Invalid AWS Secret Key."
            else:
                hint = error_msg
            return {"status": "unhealthy", "message": hint}

# Export a singleton instance
transcribe_service = TranscribeService()
