"""Compatibilidade: validações canônicas vivem em :mod:`domain.validation`."""

from ..domain.validation.outputs import summarize_cli, validate_prn

__all__ = ["summarize_cli", "validate_prn"]
