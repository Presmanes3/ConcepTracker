import ast

with open("src/cli/tag_selector.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update render method to add padding
old_render = """    def render(self) -> RenderableType:
        panels = [
            p.render(
                focused    = (i == self.panel_focus),
                cursor     = self.tag_focus if i == self.panel_focus else -1,
                selected   = self.selected,
                input_mode = self.input_mode,
                input_text = self.input_text,
            )
            for i, p in enumerate(self.panels)
        ]
        hint = Text(
            "\\n\\u2191\\u2193 Navigate   Space / Enter  Toggle   q  Confirm   Esc  Cancel",
            style="dim", justify="center",
        )
        selector = Group(*panels, self._preview(), hint)
        if self.dashboard:
            return Group(self.dashboard, selector)
        return selector"""

new_render = """    def render(self) -> RenderableType:
        # Calculate max possible height to prevent UI jumping
        max_height = 0
        current_height = 0
        for p in self.panels:
            p_max = max(len(p.tags) + 2, 3)
            max_height += p_max
            if p.expanded:
                current_height += p_max
            else:
                current_height += 3
                
        # Preview panel height: 3, Hint height: 2
        max_height += 5
        current_height += 5
        
        padding_lines = max_height - current_height
        padding = Text("\\n" * padding_lines) if padding_lines > 0 else Text("")

        panels = [
            p.render(
                focused    = (i == self.panel_focus),
                cursor     = self.tag_focus if i == self.panel_focus else -1,
                selected   = self.selected,
                input_mode = self.input_mode,
                input_text = self.input_text,
            )
            for i, p in enumerate(self.panels)
        ]
        hint = Text(
            "\\n\\u2191\\u2193 Navigate   Space / Enter  Toggle   q  Confirm   Esc  Cancel",
            style="dim", justify="center",
        )
        selector = Group(*panels, self._preview(), hint, padding)
        if self.dashboard:
            return Group(self.dashboard, selector)
        return selector"""

content = content.replace(old_render, new_render)

# 2. Remove screen=True
old_live = """    # screen=True — alternate buffer, no ghost lines when panels expand/collapse
    with Live(ui.render(), auto_refresh=False, screen=True) as live:"""

new_live = """    # Fixed height padding prevents ghost lines, so we can render inline
    with Live(ui.render(), auto_refresh=False) as live:"""

content = content.replace(old_live, new_live)

with open("src/cli/tag_selector.py", "w", encoding="utf-8") as f:
    f.write(content)

print("tag_selector.py updated")
