"""Compatibilidade: o modelo canônico agora vive em :mod:`domain.models`."""

from ..domain.models.project import Project

__all__ = ["Project"]
