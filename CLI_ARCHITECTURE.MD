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
  - Pure functions that return `Rich` renderables (Tables, Panels).
  - **Rules**: Stateless and data-driven.

- **`screens/` (The Interaction)**
  - Stateful TUI components built on **Textual**.
  - Handle keyboard input and navigation.
  - **Rules**: Use **Views** for rendering Rich content inside Textual widgets.

## Workflow
`Command` ➔ `Interactor` ➔ `Service` ➔ `Screen/View`
