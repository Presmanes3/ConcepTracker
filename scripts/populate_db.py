"""
Pre-population script for ConcepTracker — PKM Theme.

Injects a curated set of notes about Personal Knowledge Management through the
full ingest pipeline. Archipelagos and Continents will emerge naturally as the
LLM detects clusters across the notes.

Usage:
    python -m scripts.populate_db
"""

import time
from rich.console import Console
from rich.table import Table
from rich.rule import Rule

from src.workflows.ingest_workflow import ingest_graph
from shared.schemas.workflow.ingest import IngestState
from src.repository.archipelago_repository import archipelago_repository

console = Console()

# ---------------------------------------------------------------------------
# PKM-themed notes — designed to form natural clusters
# ---------------------------------------------------------------------------
NOTES = [
    # --- Spaced Repetition cluster ---
    {
        "content": "Spaced repetition is a learning technique where information is reviewed at increasing intervals over time. Each successful recall pushes the next review further into the future, exploiting the psychological spacing effect.",
        "tag": "PKM,Learning"
    },
    {
        "content": "Anki is a flashcard application that implements the SuperMemo SM-2 spaced repetition algorithm. It schedules reviews based on self-reported recall quality (1-4 rating), adjusting intervals accordingly.",
        "tag": "PKM,Tools"
    },
    {
        "content": "The forgetting curve, described by Hermann Ebbinghaus in 1885, shows that memory decays exponentially after learning. Spaced repetition counteracts this by reviewing material just before it is forgotten.",
        "tag": "PKM,Learning"
    },
    {
        "content": "Active recall is the practice of retrieving information from memory without looking at the source. Studies show it is significantly more effective for long-term retention than passive re-reading or highlighting.",
        "tag": "PKM,Learning"
    },

    # --- Zettelkasten / Linking Ideas cluster ---
    {
        "content": "The Zettelkasten method, developed by sociologist Niklas Luhmann, consists of writing atomic notes (one idea per card) and linking them by reference. Luhmann credited it for his extraordinary academic output of over 70 books.",
        "tag": "PKM,Zettelkasten"
    },
    {
        "content": "In Zettelkasten, literature notes capture the ideas from a source in your own words. Permanent notes then distill those ideas into standalone, link-ready atoms. The distinction prevents passive reading from masquerading as learning.",
        "tag": "PKM,Zettelkasten"
    },
    {
        "content": "Linking ideas in a personal knowledge base creates emergent knowledge: connections you did not explicitly plan reveal patterns and new insights. The value of a network of notes grows super-linearly with the number of links.",
        "tag": "PKM,Zettelkasten"
    },
    {
        "content": "Obsidian is a note-taking application built around a local Markdown vault. Its graph view visualises connections between notes, making Zettelkasten-style linking visually explorable.",
        "tag": "PKM,Tools"
    },

    # --- Second Brain / Capture workflow cluster ---
    {
        "content": "Tiago Forte's 'Building a Second Brain' (BASB) proposes the CODE framework: Capture, Organize, Distil, Express. The goal is to offload knowledge from biological memory to a trusted external system.",
        "tag": "PKM,Frameworks"
    },
    {
        "content": "The PARA method (Projects, Areas, Resources, Archives) organises captured information by actionability rather than topic. A note belongs to a Project if it is directly relevant to a current active goal.",
        "tag": "PKM,Frameworks"
    },
    {
        "content": "Evergreen notes, as described by Andy Matuschak, are notes written and refined over time rather than discarded. They accumulate understanding across reading sessions and form the backbone of a personal knowledge graph.",
        "tag": "PKM,Zettelkasten"
    },
    {
        "content": "Information overload occurs when the volume of incoming information exceeds a person's capacity to process it. A PKM system mitigates overload by providing trusted capture, triage, and retrieval workflows.",
        "tag": "PKM,Concepts"
    },

    # --- Knowledge Graphs / AI integration cluster ---
    {
        "content": "A knowledge graph represents entities as nodes and relationships as directed, typed edges. Unlike flat note lists, knowledge graphs make implicit relationships explicit and queryable.",
        "tag": "PKM,KnowledgeGraphs"
    },
    {
        "content": "Retrieval-Augmented Generation (RAG) connects large language models to external knowledge bases, allowing the model to ground answers in up-to-date or private information rather than relying solely on training data.",
        "tag": "AI,KnowledgeGraphs"
    },
    {
        "content": "GraphRAG extends standard RAG by constructing a knowledge graph from the source corpus and then querying the graph for multi-hop reasoning. It enables answering questions that require synthesising information across several documents.",
        "tag": "AI,KnowledgeGraphs"
    },
]


def run():
    console.print(Rule("[bold cyan]ConcepTracker — PKM Pre-population[/bold cyan]"))
    console.print(f"[dim]Ingesting {len(NOTES)} notes through the full pipeline...[/dim]\n")

    results = []

    for i, note_data in enumerate(NOTES, 1):
        console.print(f"[cyan]({i}/{len(NOTES)})[/cyan] {note_data['content'][:80]}...")

        state = IngestState(content=note_data["content"], tags=note_data["tag"])

        try:
            with console.status("  [dim]Processing...[/dim]"):
                result = ingest_graph.invoke(state)

            action = result.get("action", "CREATE")
            note_id = result.get("note_id")
            arch_action = result.get("archipelago_action", "NONE")
            arch_name = result.get("archipelago_name")

            geo_str = "[dim]~island~[/dim]"
            if arch_action == "JOIN" and arch_name:
                geo_str = f"[cyan]joined '{arch_name}'[/cyan]"
            elif arch_action == "CREATE_ARCHIPELAGO" and arch_name:
                geo_str = f"[bold cyan]NEW archipelago '{arch_name}'[/bold cyan]"
            elif arch_action == "CREATE_CONTINENT" and arch_name:
                geo_str = f"[bold magenta]NEW continent '{arch_name}'[/bold magenta]"

            status_color = {"CREATE": "green", "MERGE": "blue", "SKIP": "yellow"}.get(action, "white")
            console.print(f"  [{status_color}]{action}[/{status_color}] ID:{note_id}  {geo_str}")

            results.append({
                "id": note_id,
                "action": action,
                "arch_action": arch_action,
                "arch_name": arch_name,
                "content": note_data["content"][:60] + "...",
            })

        except Exception as e:
            console.print(f"  [red]ERROR:[/red] {e}")
            results.append({"id": None, "action": "ERROR", "arch_action": "NONE", "arch_name": None, "content": note_data["content"][:60]})

        # Brief pause between calls to avoid rate limiting
        time.sleep(1.5)

    # --- Final summary ---
    console.print(Rule("[bold]Summary[/bold]"))

    table = Table(border_style="blue", box=None)
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Action", style="white")
    table.add_column("Geography", style="yellow")
    table.add_column("Note (truncated)", style="dim")

    for r in results:
        geo = r["arch_name"] or r["arch_action"]
        table.add_row(str(r["id"] or "-"), r["action"], geo, r["content"])

    console.print(table)

    # Show emerged archipelagos
    console.print(Rule("[bold]Emerged Archipelagos & Continents[/bold]"))
    all_archs = archipelago_repository.get_all_archipelagos()
    if not all_archs:
        console.print("[dim]No archipelagos formed yet.[/dim]")
    else:
        arch_table = Table(border_style="cyan", box=None)
        arch_table.add_column("ID", style="cyan", justify="right")
        arch_table.add_column("Type", style="magenta")
        arch_table.add_column("Name", style="bold")
        arch_table.add_column("Islands", justify="right")
        arch_table.add_column("Summary", style="dim")

        for arch in all_archs:
            count = archipelago_repository.count_notes_in_archipelago(arch.id)
            icon = "🌍" if arch.type == "continent" else "🗺️"
            arch_table.add_row(
                str(arch.id),
                f"{icon} {arch.type}",
                arch.name,
                str(count),
                arch.summary[:80] + ("..." if len(arch.summary) > 80 else "")
            )
        console.print(arch_table)


if __name__ == "__main__":
    run()
