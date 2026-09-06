"""Contrato de una skill.

Una skill es una capacidad que el LLM puede invocar como *tool*. Debe declarar su
nombre, una descripción para el modelo y el JSON Schema de sus argumentos.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Skill(Protocol):
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema del objeto de argumentos

    def run(self, args: dict[str, Any]) -> str:
        """Ejecuta la skill y devuelve un texto de resultado para el LLM."""
        ...
