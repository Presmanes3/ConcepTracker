import os
from dotenv import load_dotenv
from pprint import pprint
from src.workflows.ingest_workflow import ingest_graph
from shared.schemas.workflow.ingest import IngestState

# Load environment variables
load_dotenv()

def main():
    """
    Direct entry point to test the Ingestion Workflow without CLI.
    """
    print("🚀 ConcepTracker - Starting Standalone Ingestion Test")
    
    test_input = IngestState(
        content="La arquitectura RAG con GraphRAG mejora el contexto global mediante grafos de conocimiento.",
        tags="AI"
    )
    
    print(f"📦 Input: {test_input.content}")
    
    # Invoking the compiled LangGraph from our workflow module
    result = ingest_graph.invoke(test_input)
    
    print("\n✅ Ingestion Result:")
    pprint({
        "note_id": result.get("note_id"),
        "summary": result.get("summary"),
        "num_links": len(result.get("links", []))
    })

if __name__ == "__main__":
    main()
