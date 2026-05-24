from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from .route_context import RouteContext


class Route:
    """
    Represents an HTTP route with pattern matching and parameter extraction.
    Routes are typically created via @router.get decorators etc.
    """

    def __init__(self, path: str, handler: Callable, methods: list[str] = []) -> None:
        self.sections: list[str] = path.strip("/").split("/")
        self.handler: Callable = handler
        self.methods: list[str] = methods

    def is_last_section(self, index: int) -> bool:
        return index == len(self.sections) - 1

    def matches_method(self, method: str) -> bool:
        return len(self.methods) == 0 or method in self.methods

    def matches(
        self,
        section: str,
        method: str,
        index: int,
        is_last_section: bool,
        context: RouteContext,
    ) -> bool:
        if index >= len(self.sections):
            return False
        if not self.matches_method(method):
            return False
        pattern: str = self.sections[index]
        if ":" in pattern:
            type_name, param_name = pattern.split(":", 1)
            try:
                if type_name == "int":
                    context.params[param_name] = int(section)
                elif type_name == "date":
                    context.params[param_name] = datetime.strptime(
                        section, "%Y-%m-%d"
                    ).date()
                elif type_name == "uuid":
                    context.params[param_name] = UUID(section)
                elif type_name == "slug":
                    context.params[param_name] = section
                else:
                    raise AttributeError(
                        f'Type "{type_name}" not supported in route pattern'
                    )
            except ValueError:
                return False
            return True
        elif pattern == "*" and is_last_section:
            context.is_wildcard = True
            return True
        elif pattern == section:
            return True
        return False
