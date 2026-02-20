import boto3
import os
from typing import List, Optional
from botocore.exceptions import ClientError

class BedrockService:
    """
    Service for interacting with AWS Bedrock to validate models.
    """
    def __init__(self, region: str = None):
        self.region = region or os.getenv("AWS_REGION", "eu-west-1")
        self.client = boto3.client("bedrock", region_name=self.region)

    def validate_model_id(self, model_id: str) -> bool:
        """
        Checks if the provided model ID or Inference Profile ID is accessible.
        """
        try:
            # 1. Check foundation models
            response = self.client.list_foundation_models(byInferenceType="ON_DEMAND")
            model_ids = [m['modelId'] for m in response.get('modelSummaries', [])]
            if model_id in model_ids:
                return True
            
            # 2. Check inference profiles (for regional IDs like eu.amazon...)
            # Note: list_inference_profiles is in bedrock client too
            profiles = self.client.list_inference_profiles()
            profile_ids = [p['inferenceProfileId'] for p in profiles.get('inferenceProfileSummaries', [])]
            if model_id in profile_ids:
                return True

            return False
        except (ClientError, Exception) as e:
            # If we can't connect, we can't validate. 
            # In a real app we might want to log this.
            return False
            
bedrock_service = BedrockService()
