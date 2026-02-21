import ast

with open("src/cli/interactors/note_menu.py", "r", encoding="utf-8") as f:
    content = f.read()

old_menu = """        action = questionary.select(
            "What do you want to do?",
            choices=[
                questionary.Choice("🔍 Explore (Find similar, Trace)", "explore"),
                questionary.Choice("🚀 Jump to Note", "jump"),
                questionary.Choice("✏️  Edit Note (Content, Summary)", "edit"),
                questionary.Choice("🏷️  Manage Tags", "tags"),
                questionary.Choice("🔗 Manage Links", "links"),
                questionary.Choice("🗑️  Delete Note", "delete"),
                questionary.Separator(),
                questionary.Choice("🔙 Back to list", "back"),
            ]
        ).ask()"""

new_menu = """        console.print(Panel("[bold cyan]Choose an action:[/bold cyan]", style="blue", width=40))

        custom_style = questionary.Style([
            ('qmark', 'fg:#673ab7 bold'),
            ('question', 'bold'),
            ('answer', 'fg:#f44336 bold'),
            ('pointer', 'fg:#673ab7 bold'),
            ('highlighted', 'fg:#673ab7 bold'),
            ('selected', 'fg:#cc5454'),
            ('separator', 'fg:#cc5454'),
            ('instruction', ''),
        ])

        action = questionary.select(
            " ",
            choices=[
                questionary.Choice("  🔍 Explore (Find similar, Trace)", "explore"),
                questionary.Choice("  🚀 Jump to Note", "jump"),
                questionary.Choice("  ✏️  Edit Note (Content, Summary)", "edit"),
                questionary.Choice("  🏷️  Manage Tags", "tags"),
                questionary.Choice("  🔗 Manage Links", "links"),
                questionary.Choice("  🗑️  Delete Note", "delete"),
                questionary.Separator(),
                questionary.Choice("  🔙 Back to list", "back"),
            ],
            style=custom_style,
            qmark="",
            pointer="●",
            instruction=" "
        ).ask()"""

content = content.replace(old_menu, new_menu)

old_explore = """            sub_action = questionary.select(
                "Explore Options:",
                choices=[
                    questionary.Choice("Find similar concepts", "find"),
                    questionary.Choice("Trace chronological evolution", "trace"),
                    questionary.Choice("Back", "back")
                ]
            ).ask()"""

new_explore = """            console.print(Panel("[bold cyan]Explore Options:[/bold cyan]", style="blue", width=40))
            sub_action = questionary.select(
                " ",
                choices=[
                    questionary.Choice("  Find similar concepts", "find"),
                    questionary.Choice("  Trace chronological evolution", "trace"),
                    questionary.Choice("  Back", "back")
                ],
                style=custom_style,
                qmark="",
                pointer="●",
                instruction=" "
            ).ask()"""

content = content.replace(old_explore, new_explore)

old_edit = """            sub_action = questionary.select(
                "What to edit?",
                choices=[
                    questionary.Choice("Edit Content", "content"),
                    questionary.Choice("Edit Summary", "summary"),
                    questionary.Choice("Back", "back")
                ]
            ).ask()"""

new_edit = """            console.print(Panel("[bold cyan]What to edit?[/bold cyan]", style="blue", width=40))
            sub_action = questionary.select(
                " ",
                choices=[
                    questionary.Choice("  Edit Content", "content"),
                    questionary.Choice("  Edit Summary", "summary"),
                    questionary.Choice("  Back", "back")
                ],
                style=custom_style,
                qmark="",
                pointer="●",
                instruction=" "
            ).ask()"""

content = content.replace(old_edit, new_edit)

old_links = """            sub_action = questionary.select(
                "Manage Links:",
                choices=[
                    questionary.Choice("Add Link (This -> Other)", "add"),
                    questionary.Choice("Remove Link", "remove"),"""

new_links = """            console.print(Panel("[bold cyan]Manage Links:[/bold cyan]", style="blue", width=40))
            sub_action = questionary.select(
                " ",
                choices=[
                    questionary.Choice("  Add Link (This -> Other)", "add"),
                    questionary.Choice("  Remove Link", "remove"),"""

content = content.replace(old_links, new_links)

# Also need to fix the rest of the links menu
old_links_rest = """                    questionary.Choice("Remove Link", "remove"),
                    questionary.Choice("Back", "back")
                ]
            ).ask()"""

new_links_rest = """                    questionary.Choice("  Remove Link", "remove"),
                    questionary.Choice("  Back", "back")
                ],
                style=custom_style,
                qmark="",
                pointer="●",
                instruction=" "
            ).ask()"""

content = content.replace(old_links_rest, new_links_rest)

with open("src/cli/interactors/note_menu.py", "w", encoding="utf-8") as f:
    f.write(content)

print("note_menu.py updated")
