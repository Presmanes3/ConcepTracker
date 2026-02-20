"""
test_nova_fix.py
────────────────
Unit tests for BaseAgent's Nova Micro double-tool-call hardening.

We test the internal logic by building a minimal concrete subclass and
patching the underlying LangChain `with_structured_output` chain so no
real AWS call is made.

Scenarios covered:
  1. Two tool_use blocks → parsed output comes from the LAST block.
  2. One tool_use block with empty list fields → re-parsed from raw input.
  3. One tool_use block fully populated → parsed output unchanged.
  4. No tool_use blocks present → parsed output from `include_raw` unchanged.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel


# ── Minimal schema used as LLM output ────────────────────────────────────────

class SampleOutput(BaseModel):
    title: str = ""
    tags: List[str] = []


# ── Minimal concrete subclass of BaseAgent ───────────────────────────────────

def _make_agent():
    """Build a BaseAgent subclass without touching AWS at all."""
    # Patch the LLM init so no real Bedrock client is created
    with (
        patch("src.agents.base_agent.ChatBedrock"),
        patch("src.agents.base_agent.config_repository") as mock_cfg,
        patch("src.agents.base_agent.cost_service"),
    ):
        mock_cfg.get_active_model_id.return_value = "eu.amazon.nova-micro-v1:0"

        from src.agents.base_agent import BaseAgent

        class _ConcreteAgent(BaseAgent[BaseModel, SampleOutput]):
            def run(self, input_data: BaseModel) -> Dict[str, Any]:
                return {}

        agent = _ConcreteAgent()
    return agent


# ── Helpers to build fake LangChain response bundles ─────────────────────────

def _make_ai_message(tool_blocks: list[dict]) -> MagicMock:
    msg = MagicMock()
    msg.content = tool_blocks
    msg.usage_metadata = {"input_tokens": 10, "output_tokens": 10}
    return msg


def _bundle(ai_message: MagicMock, parsed: Any, parsing_error: Any = None) -> dict:
    return {"raw": ai_message, "parsed": parsed, "parsing_error": parsing_error}


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestNovaFix:

    def setup_method(self):
        self.agent = _make_agent()

    def _call_with_bundle(self, bundle: dict) -> SampleOutput:
        """Invoke _call_llm with a mocked chain that returns the given bundle."""
        with (
            patch("src.agents.base_agent.cost_service"),
            patch.object(self.agent.llm, "with_structured_output") as mock_wso,
        ):
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = bundle
            mock_wso.return_value = mock_chain

            from langchain_core.messages import HumanMessage
            messages = [HumanMessage(content="test")]
            return self.agent._call_llm(messages, output_schema=SampleOutput)

    # ── Scenario 1: two blocks → pick last ───────────────────────────────────

    def test_two_blocks_picks_last(self):
        """When Nova emits 2 tool_use blocks, the last one wins."""
        empty_block = {
            "type": "tool_use",
            "name": "SampleOutput",
            "input": {"title": "", "tags": []},
        }
        real_block = {
            "type": "tool_use",
            "name": "SampleOutput",
            "input": {"title": "Real Title", "tags": ["a", "b"]},
        }
        ai_msg = _make_ai_message([empty_block, real_block])
        # `parsed` from LangChain picks the first (wrong) block
        first_parsed = SampleOutput(title="", tags=[])
        bundle = _bundle(ai_msg, first_parsed)

        result = self._call_with_bundle(bundle)

        assert result.title == "Real Title"
        assert result.tags == ["a", "b"]

    # ── Scenario 2: single block with empty list fields, raw has data ─────────

    def test_single_block_empty_list_reparsed(self):
        """
        Single block where `with_structured_output` returns empty list for a
        field that has data in the raw JSON → should be re-parsed.
        """
        raw_block = {
            "type": "tool_use",
            "name": "SampleOutput",
            "input": {"title": "Good Title", "tags": ["x", "y", "z"]},
        }
        ai_msg = _make_ai_message([raw_block])
        # LangChain parsed tags as [] despite raw having data
        bad_parsed = SampleOutput(title="Good Title", tags=[])
        bundle = _bundle(ai_msg, bad_parsed)

        result = self._call_with_bundle(bundle)

        assert result.tags == ["x", "y", "z"]

    # ── Scenario 3: single fully-populated block → unchanged ─────────────────

    def test_single_block_fully_populated_unchanged(self):
        """No fix needed when a single block is already correct."""
        raw_block = {
            "type": "tool_use",
            "name": "SampleOutput",
            "input": {"title": "OK", "tags": ["t1"]},
        }
        ai_msg = _make_ai_message([raw_block])
        good_parsed = SampleOutput(title="OK", tags=["t1"])
        bundle = _bundle(ai_msg, good_parsed)

        result = self._call_with_bundle(bundle)

        assert result.title == "OK"
        assert result.tags == ["t1"]

    # ── Scenario 4: no tool_use blocks → parsed unchanged ────────────────────

    def test_no_tool_blocks_returns_original_parsed(self):
        """If there are no tool_use blocks the fix is a no-op."""
        ai_msg = _make_ai_message([{"type": "text", "text": "hello"}])
        original = SampleOutput(title="Original", tags=["orig"])
        bundle = _bundle(ai_msg, original)

        result = self._call_with_bundle(bundle)

        assert result.title == "Original"
        assert result.tags == ["orig"]

    # ── Scenario 5: parsing error raises ValueError ───────────────────────────

    def test_parsing_error_raises(self):
        """A parsing_error in the bundle should surface as a ValueError."""
        ai_msg = _make_ai_message([])
        bundle = _bundle(ai_msg, None, parsing_error="JSON decode error")

        with pytest.raises(ValueError, match="Structured Output mismatch"):
            self._call_with_bundle(bundle)
