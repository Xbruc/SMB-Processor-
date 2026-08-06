"""Leitores e geradores de formatos externos."""

from .netcdf import NetCDFFile, generate_map_animation, generate_map_overlay
from .selafin import SelafinFile, generate_velocity_animation, plot_level_variation

__all__ = [
    "NetCDFFile", "SelafinFile", "generate_map_animation",
    "generate_map_overlay", "generate_velocity_animation", "plot_level_variation",
]
