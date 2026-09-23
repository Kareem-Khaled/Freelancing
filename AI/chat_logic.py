#!/usr/bin/env python3
"""
AI Chat Assistant - Business Logic Layer
Connects to Atomic Chat's OpenAI-compatible API
"""

from openai import OpenAI
import re

# Configuration
API_BASE = "http://localhost:18790/v1"
API_KEY = "not-needed"
MODEL = "qwen-3.5-35b"

# ============================================
# EDIT THIS SYSTEM MESSAGE BELOW
# ============================================
SYSTEM_MESSAGE = """
You are a sports expert assistant. Your ONLY focus is sports-related topics.

You can answer questions about:
- Sports news, scores, and statistics
- Athletes, teams, and leagues
- Game analysis and tactics
- Sports history and records
- Equipment, training, and fitness
- Betting odds and predictions (entertainment only)

If asked about non-sports topics, politely decline and redirect:
"I specialize in sports questions. For topics outside of sports, I'd recommend asking a more general assistant."

Always be knowledgeable, accurate, and passionate about sports.
"""
# ============================================

# Initialize client
client = OpenAI(base_url=API_BASE, api_key=API_KEY)

# Tags emitted by reasoning models that should never reach the user
THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"


class AIError(RuntimeError):
    """Raised when the backend cannot be reached or returns an error."""


class AIClient:
    """Business logic for AI chat interactions."""
    
    def __init__(self, system_message: str):
        self.system_message = system_message
        self.conversation_history = [{"role": "system", "content": system_message}]
    
    def update_system_message(self, new_message: str):
        """Update the system message and conversation history."""
        self.system_message = new_message
        if self.conversation_history and self.conversation_history[0]['role'] == 'system':
            self.conversation_history[0]['content'] = new_message
        else:
            self.conversation_history.insert(0, {"role": "system", "content": new_message})
    
    def clear_conversation(self):
        """Clear conversation history, keeping only system message."""
        self.conversation_history = [{"role": "system", "content": self.system_message}]
    
    def chat(self, user_message: str, stream: bool = False) -> str:
        """Send a message and get the full AI response as a string.

        If ``stream`` is True the response is streamed internally and the
        accumulated text is returned once the stream completes.
        """
        if stream:
            return "".join(self.chat_stream(user_message))

        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=self.conversation_history,
                stream=False,
            )
            content = response.choices[0].message.content or ""
        except Exception as exc:
            # Don't leave a dangling user turn in the history on failure
            self.conversation_history.pop()
            raise AIError(f"Could not reach the model at {API_BASE}: {exc}") from exc

        content = self._remove_thinking_tags(content)

        # Add assistant response to history
        self.conversation_history.append({"role": "assistant", "content": content})

        return content
    
    def chat_stream(self, user_message: str):
        """Stream the AI response chunk by chunk, with think-tags filtered out."""
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=self.conversation_history,
                stream=True,
            )
        except Exception as exc:
            self.conversation_history.pop()
            raise AIError(f"Could not reach the model at {API_BASE}: {exc}") from exc

        def raw_chunks():
            try:
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            except Exception as exc:
                raise AIError(f"Stream failed: {exc}") from exc

        content = ""
        try:
            for text in self._filter_think_stream(raw_chunks()):
                content += text
                yield text
        except AIError:
            self.conversation_history.pop()
            raise

        # Add assistant response to history
        self.conversation_history.append({"role": "assistant", "content": content})
    
    def _filter_think_stream(self, chunks):
        """Strip ``<think>...</think>`` spans from a stream of text chunks.

        Tags are handled even when they are split across chunk boundaries by
        holding back any trailing text that could be the start of a tag.
        """
        buffer = ""
        in_think = False

        for chunk in chunks:
            buffer += chunk
            while True:
                if in_think:
                    idx = buffer.find(THINK_CLOSE)
                    if idx == -1:
                        # Discard thinking text, but keep a possible partial tag
                        keep = self._partial_tail_len(buffer, THINK_CLOSE)
                        buffer = buffer[len(buffer) - keep:] if keep else ""
                        break
                    buffer = buffer[idx + len(THINK_CLOSE):]
                    in_think = False
                else:
                    idx = buffer.find(THINK_OPEN)
                    if idx == -1:
                        keep = self._partial_tail_len(buffer, THINK_OPEN)
                        safe = buffer[:len(buffer) - keep] if keep else buffer
                        buffer = buffer[len(buffer) - keep:] if keep else ""
                        if safe:
                            yield safe
                        break
                    if idx:
                        yield buffer[:idx]
                    buffer = buffer[idx + len(THINK_OPEN):]
                    in_think = True

        # Flush whatever is left (an unterminated <think> block is dropped)
        if not in_think and buffer:
            yield buffer
    
    @staticmethod
    def _partial_tail_len(text: str, tag: str) -> int:
        """Length of the trailing substring of ``text`` that prefixes ``tag``."""
        for n in range(min(len(tag) - 1, len(text)), 0, -1):
            if text.endswith(tag[:n]):
                return n
        return 0
    
    def _remove_thinking_tags(self, text: str) -> str:
        """Remove <think>...</think> spans (and stray tags) from text."""
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = re.sub(r'</?think>', '', text)
        return text.strip()
