import os
import boto3
from dotenv import load_dotenv

load_dotenv()

profile = os.getenv("AWS_PROFILE")
region = os.getenv("AWS_REGION", "us-east-1")

print(f"Testing AWS Profile: {profile} in region: {region}")

try:
    session = boto3.Session(profile_name=profile, region_name=region)
    bedrock = session.client("bedrock")
    models = bedrock.list_foundation_models()
    
    # Filter for Chat/Text models
    chat_models = [m['modelId'] for m in models['modelSummaries'] 
                   if 'nova' in m['modelId'].lower() or 'claude' in m['modelId'].lower()]
    print(f"Chat Models Available in {region}: {chat_models}")
    
    # Check for inference profiles
    try:
        profiles = bedrock.list_inference_profiles()
        print(f"Inference Profiles: {[p['inferenceProfileName'] for p in profiles['inferenceProfileSummaries']]}")
        print(f"Inference Profile IDs: {[p['inferenceProfileId'] for p in profiles['inferenceProfileSummaries']]}")
    except:
        print("Inference profiles listing failed or not supported.")

except Exception as e:
    print(f"❌ Diagnostic failed: {e}")
except Exception as e:
    print(f"❌ Connection failed: {e}")
