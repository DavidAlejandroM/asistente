"""El "cerebro": convierte texto del usuario en texto de respuesta.

Orquesta el bucle LLM ↔ tools y mantiene el historial de la conversación. No sabe
nada de audio; es la pieza pura y fácil de testear.
"""

from __future__ import annotations

import logging

from asistente.llm.base import Message
from asistente.skills.registry import SkillRegistry

log = logging.getLogger(__name__)

_FALLBACK = "Lo siento, no he podido completar la petición."


class Brain:
    def __init__(
        self,
        llm,
        skills: SkillRegistry,
        system_prompt: str,
        max_tool_iterations: int = 5,
        max_history: int = 40,
    ) -> None:
        self._llm = llm
        self._skills = skills
        self._max_tool_iterations = max_tool_iterations
        self._max_history = max_history
        self._system = Message(role="system", content=system_prompt)
        self.history: list[Message] = []

    @property
    def skills(self) -> SkillRegistry:
        return self._skills

    def reset(self) -> None:
        self.history.clear()

    def process(self, user_text: str) -> str:
        self.history.append(Message(role="user", content=user_text))
        response = None

        for _ in range(self._max_tool_iterations):
            messages = [self._system, *self.history]
            response = self._llm.chat(messages, self._skills.tool_specs())

            if not response.tool_calls:
                self.history.append(Message(role="assistant", content=response.text))
                self._trim()
                return response.text

            self.history.append(
                Message(role="assistant", content=response.text, tool_calls=response.tool_calls)
            )
            for call in response.tool_calls:
                result = self._skills.run(call.name, call.arguments)
                self.history.append(
                    Message(role="tool", content=result, tool_call_id=call.id)
                )

        log.warning("bucle de tools agotado tras %d iteraciones", self._max_tool_iterations)
        text = (response.text if response else "") or _FALLBACK
        self.history.append(Message(role="assistant", content=text))
        self._trim()
        return text

    def _trim(self) -> None:
        if len(self.history) > self._max_history:
            self.history = self.history[-self._max_history :]
