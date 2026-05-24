from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class Deferred:
    def __init__(self) -> None:
        from .router import Router

        self.routers = [v for v in vars(type(self)).values() if isinstance(v, Router)]

    def context(self) -> Any:
        return self
