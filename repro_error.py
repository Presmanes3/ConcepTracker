import os
import yaml
from langchain_aws import ChatBedrock
from shared.schemas.workflow.ingest import IngestState
from shared.schemas.agents.normalizer import LLMNormalizerOutput
from shared.prompts.normalizer_agent import NORMALIZER_PROMPT
from src.repository.config_repository import config_repository
from dotenv import load_dotenv

load_dotenv()

def test_repro():
    model_id = "eu.amazon.nova-micro-v1:0"
    llm = ChatBedrock(
        model_id=model_id,
        region_name=os.getenv("AWS_REGION", "eu-west-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        model_kwargs={"temperature": 0.1}
    )
    
    content = "En Python, los decoradores son funciones que envuelven a otras funciones para extender su comportamiento."
    
    messages = NORMALIZER_PROMPT.format_messages(
        source_type="manual",
        source_url="N/A",
        raw_title="Not provided",
        raw_tags="Dev",
        raw_message=content
    )
    
    print("--- PROMPT ---")
    for m in messages:
        print(f"[{m.type}]: {m.content}")
    
    print("\n--- INVOKING ---")
    chain = llm.with_structured_output(LLMNormalizerOutput, include_raw=True)
    try:
        response_bundle = chain.invoke(messages)
        print("\n--- RAW RESPONSE ---")
        print(response_bundle["raw"])
        print("\n--- PARSED ---")
        print(response_bundle["parsed"])
        if response_bundle.get("parsing_error"):
            print("\n--- PARSING ERROR ---")
            print(response_bundle["parsing_error"])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_repro()
