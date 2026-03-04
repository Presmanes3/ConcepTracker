"""Config interactor — view and update application model/pricing settings."""
from __future__ import annotations

from typing import Optional

from rich.console import Console

from shared.schemas.api.config import ConfigUpdateRequest, ModelPricingSchema
from src.cli.client.http_client import ConcepTrackerClient
from src.cli.views import render_config_list, render_config_summary, render_model_activated

console = Console()


class ConfigInteractor:
    """Orchestrate the config command flow against the REST API."""

    def __init__(
        self,
        model: Optional[str] = None,
        input_price: float = 0.0,
        output_price: float = 0.0,
        active: bool = False,
        list_all: bool = False,
    ) -> None:
        self._model = model
        self._input_price = input_price
        self._output_price = output_price
        self._active = active
        self._list_all = list_all

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        """Execute the config flow and print results."""
        with ConcepTrackerClient() as client:
            config = client.get_config()

            if self._list_all:
                console.print(render_config_list(config, config.active_model_id))
                return

            if self._model:
                self._update(client, config)
            else:
                pricing = config.pricing.get(config.active_model_id)
                console.print(render_config_summary(config.active_model_id, pricing))

    # ── Private helpers ────────────────────────────────────────────────────────

    def _update(self, client: ConcepTrackerClient, current_config) -> None:
        body = ConfigUpdateRequest()

        if self._input_price > 0 or self._output_price > 0:
            body.model_pricing = {
                self._model: ModelPricingSchema(
                    input=self._input_price,
                    output=self._output_price,
                )
            }

        if self._active:
            body.active_model_id = self._model

        if body.active_model_id is None and body.model_pricing is None:
            # Nothing to change — just show summary
            pricing = current_config.pricing.get(self._model)
            console.print(render_config_summary(self._model, pricing))
            return

        updated = client.update_config(body)

        if self._input_price > 0 or self._output_price > 0:
            console.print(f"[green]✔[/green] Pricing for '[bold]{self._model}[/bold]' updated.")

        if self._active:
            console.print(render_model_activated(self._model))
        elif self._input_price > 0 or self._output_price > 0:
            console.print("[green]✔[/green] Settings saved.")
