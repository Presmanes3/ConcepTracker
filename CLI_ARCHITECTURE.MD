# CLI Architecture

Structure and responsibilities for the `src/cli` layer.

## Layers

- **`commands/` (The Entry Point)**
  - Parse CLI arguments and flags.
  - Instantiate and call the appropriate **Interactor**.
  - **Rules**: No business logic, no complex formatting.

- **`interactors/` (The Orchestrator)**
  - Manage the flow of a use case.
  - Call **Services** (`src/services`) for data/logic.
  - Transition between **Screens** or pass data to **Views**.
  - **Rules**: No direct SQL, no direct `print()`.

- **`views/` (The Presentation)**
  - Pure functions that return `Rich` renderables (Tables, Panels, Markdown).
  - **Rules**: Stateless and data-driven. They don't know about Textual; they only care about how data looks.

- **`screens/` (The Orchestration)**
  - Stateful TUI components built on **Textual**.
  - Responsibilities:
    1. **Layout**: Define the `ComposeResult` (the widget tree).
    2. **Wiring**: Map `Static` widgets to `View` functions.
    3. **Events**: Handle keyboard input, focus, and screen transitions.
  - **Rules**: Screens should be "thin". They delegate data fetching to Interactors and visual formatting to Views.

## The "Static Bridge" Pattern
Since Textual handles the TUI and Rich handles the formatting, we use `Static` widgets as bridges:
1. `Screen` identifies a region (e.g., `#status-bar`).
2. `Screen` calls a `View` (e.g., `render_status(data)`).
3. `Screen` updates the widget: `self.query_one("#status-bar", Static).update(view_output)`.
