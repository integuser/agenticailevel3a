import anthropic
from typing import List, Optional, Dict, Any


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    MAX_TOOL_ROUNDS = 2
    FALLBACK_TEXT = (
        "I wasn't able to produce an answer. Please try rephrasing your question."
    )

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Tools:
- `search_course_content`: use **only** for questions about specific course content or detailed educational materials
- `get_course_outline`: use for outline-related queries (e.g. "what's in course X", "list the lessons", "course structure"). Always return the course title, the course link, and the number and title of every lesson in the course
- **Up to 2 sequential tool calls per query.** Make a second call only for dependent lookups (e.g. get a course outline, then search content using what it revealed) or when the first result is insufficient. Make calls one at a time, never repeat a call that succeeded, and after the last call answer directly
- Synthesize search results into accurate, fact-based responses
- If search yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first (up to 2 calls), then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages = [{"role": "user", "content": query}]
        base = {**self.base_params, "system": system_content}
        tool_kwargs = {"tools": tools, "tool_choice": {"type": "auto"}} if tools else {}

        response = self.client.messages.create(
            **base, messages=list(messages), **tool_kwargs
        )

        rounds = 0
        while (
            tool_manager
            and rounds < self.MAX_TOOL_ROUNDS
            and response.stop_reason == "tool_use"
            and any(b.type == "tool_use" for b in response.content)
        ):
            rounds += 1
            failed = False
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                try:
                    out = tool_manager.execute_tool(block.name, **block.input)
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": out}
                    )
                except Exception as e:
                    failed = True
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Error executing {block.name}: {e}",
                            "is_error": True,
                        }
                    )
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": results})

            keep_tools = tool_kwargs and not failed and rounds < self.MAX_TOOL_ROUNDS
            response = self.client.messages.create(
                **base, messages=list(messages), **(tool_kwargs if keep_tools else {})
            )
            if failed:
                break

        return self._extract_text(response)

    def _extract_text(self, response) -> str:
        """Join all text blocks; fall back if none or if a tool_use is left unresolved."""
        blocks = response.content or []
        if any(b.type == "tool_use" for b in blocks):
            return self.FALLBACK_TEXT
        text = "".join(b.text for b in blocks if b.type == "text")
        return text or self.FALLBACK_TEXT
