"""Fachada de infraestrutura para a implementação SELAFIN validada."""

from ...core.selafin_results import (
    LEVEL_NAMES, U_NAMES, V_NAMES, SelafinFile,
    generate_velocity_animation, plot_level_variation,
)

__all__ = [
    "LEVEL_NAMES", "U_NAMES", "V_NAMES", "SelafinFile",
    "generate_velocity_animation", "plot_level_variation",
]
