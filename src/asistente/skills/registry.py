"""Registro de skills: las mantiene, las expone al LLM como tools y las ejecuta."""

from __future__ import annotations

import logging
from typing import Any

from asistente.llm.base import ToolSpec
from asistente.skills.base import Skill

log = logging.getLogger(__name__)


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        self._disabled: set[str] = set()

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def toggle(self, name: str, enabled: bool) -> None:
        if name not in self._skills:
            raise KeyError(name)
        if enabled:
            self._disabled.discard(name)
        else:
            self._disabled.add(name)

    def is_enabled(self, name: str) -> bool:
        return name in self._skills and name not in self._disabled

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def enabled_skills(self) -> list[Skill]:
        return [s for n, s in self._skills.items() if n not in self._disabled]

    def all_names(self) -> list[str]:
        return list(self._skills)

    def tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(name=s.name, description=s.description, parameters=s.parameters)
            for s in self.enabled_skills()
        ]

    def run(self, name: str, args: dict[str, Any]) -> str:
        """Ejecuta una skill. Nunca lanza: los errores vuelven como texto para el LLM."""
        if name not in self._skills:
            return f"Error: la herramienta '{name}' no existe."
        if name in self._disabled:
            return f"Error: la herramienta '{name}' está desactivada."
        try:
            return self._skills[name].run(args)
        except Exception as exc:  # noqa: BLE001 - se lo contamos al LLM, no rompemos el bucle
            log.exception("fallo ejecutando skill %s", name)
            return f"Error ejecutando '{name}': {exc}"
