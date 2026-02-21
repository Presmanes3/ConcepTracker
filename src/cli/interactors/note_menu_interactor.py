"""
NoteMenuInteractor — testable class replacing the closure-heavy show_note_action_menu().

Responsibilities:
  - Owns a ColumnMenu and drives its lifecycle
  - Fetches data (repos, embedding, agents) via injected dependencies
  - Builds view renderables via src.cli.views (no inline Rich rendering)
  - Each action is an isolated method, fully unit-testable

Usage::

    from src.cli.interactors.note_menu_interactor import NoteMenuInteractor
    NoteMenuInteractor(note_id=42).run()
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

import questionary
from rich.console import Console
from rich.panel import Panel

from src.cli.column_menu import ColumnMenu
from src.cli.views.note_views import note_detail_view
from src.cli.views.arch_views import archipelago_badge
from src.registry import repos

if TYPE_CHECKING:
    from shared.schemas.models.note import Note

console = Console()


class NoteMenuInteractor:
    """
    Interactive action menu for a single note.

    Inject dependencies for easier testing::

        interactor = NoteMenuInteractor(
            note_id=42,
            note_repo=mock_note_repo,
            link_repo=mock_link_repo,
        )
        interactor.run()
    """

    def __init__(
        self,
        note_id: int,
        note_repo=None,
        link_repo=None,
        arch_repo=None,
        embedding_service=None,
    ):
        self._note_id = note_id
        self._note_repo = note_repo or repos.notes
        self._link_repo = link_repo or repos.links
        self._arch_repo = arch_repo or repos.archipelagos
        self._embedding_service = embedding_service  # lazy, loaded on first use

        self._note: Optional["Note"] = None
        self._menu: Optional[ColumnMenu] = None

    # ── Public entry point ─────────────────────────────────────────────────

    def run(self) -> None:
        """Open the note action menu. Blocks until the user quits."""
        self._note = self._note_repo.get_note_by_id(self._note_id)
        if not self._note:
            console.print(f"[red]Note {self._note_id} not found.[/red]")
            return

        self._menu = ColumnMenu("Choose an action")
        self._refresh_header()

        self._menu.add_action("🔍 Explore (Find similar, Trace)", self._handle_explore, needs_suspend=True)
        self._menu.add_action("🚀 Jump to Note", self._handle_jump, needs_suspend=True)
        self._menu.add_action("✏️  Edit Note (Content, Summary)", self._handle_edit, needs_suspend=True)
        self._menu.add_action("🏷️  Manage Tags", self._handle_tags, needs_suspend=False)
        self._menu.add_action("🔗 Manage Links", self._handle_links, needs_suspend=True)
        self._menu.add_action("🗑️  Delete Note", self._handle_delete, needs_suspend=True)
        self._menu.add_action("🔙 Back to list", lambda: "exit")

        self._menu.run()

    # ── Internal helpers ───────────────────────────────────────────────────

    def _refresh(self) -> None:
        """Reload note from DB and update menu header."""
        self._note = self._note_repo.get_note_by_id(self._note_id)
        self._refresh_header()

    def _refresh_header(self) -> None:
        badge = self._resolve_badge()
        
        # Fetch links for the connections panel
        out_links = self._link_repo.get_links_by_source(self._note_id)
        in_links = self._link_repo.get_links_by_target(self._note_id)
        
        # Fetch summaries for the linked notes
        linked_ids = {l.target_id for l in out_links} | {l.source_id for l in in_links}
        linked_notes = self._note_repo.get_notes_by_ids(list(linked_ids))
        summaries = {n.id: n.summary for n in linked_notes}
        
        self._menu.header_renderable = note_detail_view(
            self._note, 
            arch_badge=badge,
            out_links=out_links,
            in_links=in_links,
            note_summaries=summaries
        )

    def _resolve_badge(self) -> str:
        arch_id = self._note.archipelago_id if self._note else None
        if not arch_id:
            return "[dim]~island~[/dim]"
        arch = self._arch_repo.get_archipelago_by_id(arch_id)
        return archipelago_badge(arch.name if arch else None, arch.type if arch else None)

    def _get_embedding_service(self):
        if self._embedding_service is None:
            from src.services.embedding_service import embedding_service
            self._embedding_service = embedding_service
        return self._embedding_service

    @staticmethod
    def _ok(msg: str) -> Panel:
        return Panel(f"[green]{msg}[/green]", border_style="green")

    # ── Action handlers ────────────────────────────────────────────────────

    def _handle_explore(self):
        from rich.table import Table
        from rich.text import Text
        from src.cli.views.arch_views import archipelago_badge as badge_fn

        sub_action = questionary.select(
            "Explore Options:",
            choices=[
                questionary.Choice("Find similar concepts", "find"),
                questionary.Choice("Trace chronological evolution", "trace"),
                questionary.Choice("Back", "back"),
            ],
        ).ask()

        if sub_action == "find":
            with console.status("[cyan]Searching for similar concepts...[/cyan]"):
                svc = self._get_embedding_service()
                vector = svc.get_embedding(self._note.summary)
                results = self._note_repo.semantic_search(vector, limit=5)

            if not results:
                console.print(Panel("[yellow]No similar concepts found.[/yellow]", border_style="yellow"))
            else:
                table = Table(box=None, show_header=True, header_style="bold magenta")
                table.add_column("Match", justify="right", style="green")
                table.add_column("ID", justify="right", style="cyan")
                table.add_column("Archipelago")
                table.add_column("Summary")
                for res_note, distance in results:
                    if res_note.id == self._note.id:
                        continue
                    pct = max(0, min(100, int((1 - distance) * 100)))
                    color = "green" if pct > 70 else "yellow"
                    arch = self._arch_repo.get_archipelago_by_id(res_note.archipelago_id)
                    b = badge_fn(arch.name if arch else None, arch.type if arch else None)
                    s = res_note.summary[:60] + "…" if len(res_note.summary) > 60 else res_note.summary
                    table.add_row(f"[{color}]{pct}%[/{color}]", str(res_note.id), b, s)
                console.print(Panel(table, title="[bold cyan]Similar Concepts[/bold cyan]", border_style="cyan"))
            questionary.press_any_key_to_continue().ask()

        elif sub_action == "trace":
            with console.status("[cyan]Tracing evolution...[/cyan]"):
                svc = self._get_embedding_service()
                vector = svc.get_embedding(self._note.summary)
                results = self._note_repo.get_similar_notes(
                    current_id=None, embedding=vector, limit=5, threshold=0.8
                )
            if not results:
                console.print(Panel("[yellow]No related concepts found for tracing.[/yellow]", border_style="yellow"))
            else:
                results.sort(key=lambda x: x["id"])
                trace_text = Text()
                for i, res in enumerate(results):
                    is_current = res["id"] == self._note.id
                    prefix = "👉 " if is_current else "   "
                    style = "bold green" if is_current else "white"
                    s = res["summary"][:60] + "…" if len(res["summary"]) > 60 else res["summary"]
                    trace_text.append(f"{prefix}[ID {res['id']}] ", style="cyan")
                    trace_text.append(f"{s}\n", style=style)
                    if i < len(results) - 1:
                        trace_text.append("   │\n", style="dim")
                console.print(Panel(trace_text, title="[bold magenta]Chronological Trace[/bold magenta]", border_style="magenta"))
            questionary.press_any_key_to_continue().ask()

    def _handle_jump(self):
        target_id_str = questionary.text("Enter Note ID to jump to:").ask()
        if target_id_str and target_id_str.isdigit():
            target_id = int(target_id_str)
            target_note = self._note_repo.get_note_by_id(target_id)
            if target_note:
                # Re-seat this interactor on the new note and refresh
                self._note_id = target_id
                self._note = target_note
                self._refresh_header()
                console.print(f"[green]Jumped to Note {target_id}.[/green]")
                questionary.press_any_key_to_continue().ask()
            else:
                console.print(f"[red]Note {target_id} not found.[/red]")
                questionary.press_any_key_to_continue().ask()

    def _handle_edit(self):
        sub_action = questionary.select(
            "What to edit?",
            choices=[
                questionary.Choice("Edit Content", "content"),
                questionary.Choice("Edit Summary", "summary"),
                questionary.Choice("Back", "back"),
            ],
        ).ask()

        if sub_action == "content":
            console.print("[dim]Multiline editor — press Esc then Enter to save.[/dim]")
            new_content = questionary.text("New Content:", default=self._note.content, multiline=True).ask()
            if new_content and new_content != self._note.content:
                self._note_repo.update_note(self._note_id, content=new_content)
                self._refresh()
                return self._ok("Content updated successfully.")

        elif sub_action == "summary":
            console.print("[dim]Multiline editor — press Esc then Enter to save.[/dim]")
            new_summary = questionary.text("New Summary:", default=self._note.summary, multiline=True).ask()
            if new_summary and new_summary != self._note.summary:
                self._note_repo.update_note(self._note_id, summary=new_summary)
                self._refresh()
                return self._ok("Summary updated successfully.")

    def _handle_tags(self):
        from src.agents.tag_recommender_agent import TagRecommenderAgent
        from collections import Counter
        from src.cli.tag_selector import build_tag_selector_ui

        current_tags = [t.strip() for t in self._note.tags.split(",")] if self._note.tags else []

        ai_tags = TagRecommenderAgent().run(
            {"content": self._note.content, "summary": self._note.summary}
        ).get("tags", [])

        svc = self._get_embedding_service()
        vector = svc.get_embedding(self._note.summary)
        similar = self._note_repo.semantic_search(vector, limit=15)
        tag_counts: Counter = Counter()
        for similar_note, _ in similar:
            if similar_note.id == self._note.id:
                continue
            if similar_note.tags:
                for t in similar_note.tags.split(","):
                    tag = t.strip()
                    if tag and tag not in current_tags:
                        tag_counts[tag] += 1

        db_tags = [{"name": tag, "count": count} for tag, count in tag_counts.most_common(10)]

        def on_tags_done(selected_tags):
            final_tags_str = ",".join(selected_tags)
            if final_tags_str != self._note.tags:
                self._note_repo.update_note(self._note_id, tags=final_tags_str)
                self._refresh()

        return build_tag_selector_ui(current_tags, ai_tags, db_tags, on_done=on_tags_done)

    def _handle_links(self):
        from shared.schemas.models.link import Link

        sub_action = questionary.select(
            "Manage Links:",
            choices=[
                questionary.Choice("Add Link (This → Other)", "add"),
                questionary.Choice("Remove Link", "remove"),
                questionary.Choice("Back", "back"),
            ],
        ).ask()

        if sub_action == "add":
            target_id_str = questionary.text("Enter Target Note ID:").ask()
            if target_id_str and target_id_str.isdigit():
                target_id = int(target_id_str)
                target_note = self._note_repo.get_note_by_id(target_id)
                if not target_note:
                    console.print(f"[red]Note {target_id} not found.[/red]")
                    questionary.press_any_key_to_continue().ask()
                else:
                    relation = questionary.text(
                        "Relation type (e.g. 'supports', 'contradicts', 'expands'):",
                        default="relates_to",
                    ).ask()
                    reason = questionary.text("Reason for link:").ask()
                    if relation:
                        new_link = Link(
                            source_id=self._note_id,
                            target_id=target_id,
                            relation_type=relation,
                            reason=reason or "Manual link",
                        )
                        self._link_repo.save_link(new_link)
                        self._refresh()
                        return self._ok("Link added successfully.")

        elif sub_action == "remove":
            out_links = self._link_repo.get_links_by_source(self._note_id)
            in_links = self._link_repo.get_links_by_target(self._note_id)
            all_links = out_links + in_links
            if not all_links:
                console.print("[yellow]No links to remove.[/yellow]")
                questionary.press_any_key_to_continue().ask()
            else:
                choices = []
                for lnk in out_links:
                    choices.append(questionary.Choice(f"[{lnk.id}] Out: {lnk.relation_type} → {lnk.target_id}", lnk.id))
                for lnk in in_links:
                    choices.append(questionary.Choice(f"[{lnk.id}] In: {lnk.relation_type} ← {lnk.source_id}", lnk.id))
                link_id = questionary.select("Select link to remove:", choices=choices).ask()
                if link_id:
                    self._link_repo.delete_link(link_id)
                    self._refresh()
                    return self._ok("Link removed successfully.")

    def _handle_delete(self):
        confirm = questionary.confirm(f"Delete note {self._note_id}?").ask()
        if confirm:
            self._note_repo.delete_note(self._note_id)
            console.print(f"[green]Note {self._note_id} deleted.[/green]")
            questionary.press_any_key_to_continue().ask()
            return "exit"


# ── Backward-compat wrapper ────────────────────────────────────────────────────

def show_note_action_menu(note) -> None:
    """
    Thin wrapper kept for backward compatibility with ls.py / find.py.
    Delegates to NoteMenuInteractor.
    """
    NoteMenuInteractor(note_id=note.id).run()
