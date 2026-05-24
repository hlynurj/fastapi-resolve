from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from route import Route


class RouteContext:
    def __init__(self, route: "Route"):
        self.route: "Route" = route
        self.params: dict[str, Any] = {}
        self.is_mismatch: bool = False
        self.is_full_match: bool = False
        self.is_wildcard: bool = False
