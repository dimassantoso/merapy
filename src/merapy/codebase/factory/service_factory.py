from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from merapy.codebase.factory.app_factory import AppServerFactory
from merapy.codebase.factory.module_factory import ModuleFactory

if TYPE_CHECKING:
    from merapy.codebase.factory.dependency import Dependency
    from merapy.config.config import Config


@runtime_checkable
class ServiceFactory(Protocol):
    """Wire of modules + apps + dependency container.

    Mirrors candi's ``factory.ServiceFactory``. The generated service in
    ``internal/service.py`` is the concrete implementation.
    """

    @property
    def name(self) -> str: ...

    def config(self) -> "Config": ...
    def dependency(self) -> "Dependency": ...
    def modules(self) -> list[ModuleFactory]: ...
    def applications(self) -> list[AppServerFactory]: ...
