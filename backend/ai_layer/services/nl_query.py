"""
NLQueryService — natural language -> ERP data using Claude tool-use.

Flow:
  1. User sends a plain-English question from the in-app ERP chat.
  2. We call Claude (Anthropic Messages API) with the shared ERP tool registry.
  3. Claude decides which tool(s) to call and with what arguments.
  4. We execute each tool against the real database (scoped to the user's retail).
  5. Claude synthesises a final narrative response from the results.
  6. We return the response + metadata.

The tools are the SAME functions exposed over MCP (see ai_layer/erp_tools.py),
so the chat and the MCP server never drift apart.
"""

import datetime
import json

from django.conf import settings

from anthropic import Anthropic

from ai_layer.erp_tools import ANTHROPIC_TOOLS, dispatch

_client = None

# Safety cap on tool-use round-trips per query (prevents runaway loops).
_MAX_TURNS = 6
_MAX_TOKENS = 1024


def _get_client():
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def _text_from(message) -> str:
    """Concatenate all text blocks from a Claude message."""
    return "".join(
        block.text for block in message.content if block.type == "text"
    ).strip()


def run_nl_query(retail, user, query_text: str) -> dict:
    """
    Execute a natural-language ERP query with Claude.
    Returns: {response, tool_calls, tokens_used}
    """
    client = _get_client()
    today = str(datetime.date.today())
    retail_name = getattr(retail, "retail_name", str(retail))

    system_prompt = (
        f"You are an AI assistant for {retail_name}, a jewellery business using "
        f"Jewel India ERP. Today's date is {today}. "
        "You have tools that query real-time business data. "
        "Always call the relevant tool(s) BEFORE answering — never guess figures. "
        "Use Indian number formatting where appropriate (e.g. Rs 2,50,000 = 2.5 lakh). "
        "Be concise and professional. "
        "If a date range is needed and the user didn't specify one, use the current "
        f"financial year (April 1 to {today}). "
        "If a tool returns an error, briefly explain what data you couldn't retrieve "
        "rather than inventing numbers."
    )

    messages = [{"role": "user", "content": query_text}]
    tool_calls_log = []
    tokens_used = 0

    for _turn in range(_MAX_TURNS):
        response = client.messages.create(
            model=settings.AI_CHAT_MODEL,
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            tools=ANTHROPIC_TOOLS,
            messages=messages,
        )
        if response.usage:
            tokens_used += response.usage.input_tokens + response.usage.output_tokens

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return {
                "response": _text_from(response)
                or "I couldn't find any relevant data for that query.",
                "tool_calls": tool_calls_log,
                "tokens_used": tokens_used,
            }

        # Execute every tool_use block Claude requested this turn.
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            tool_calls_log.append({"tool": block.name, "args": block.input})
            result = dispatch(block.name, block.input, retail)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })

        messages.append({"role": "user", "content": tool_results})

    # Ran out of turns — return whatever text we have.
    return {
        "response": "I wasn't able to fully resolve that within the allowed steps. "
        "Please try narrowing the question.",
        "tool_calls": tool_calls_log,
        "tokens_used": tokens_used,
    }
