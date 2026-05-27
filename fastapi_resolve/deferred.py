from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from router import Router


class Deferred:
    def routers(self) -> list["Router"]:
        from .router import Router

        return [v for v in vars(type(self)).values() if isinstance(v, Router)]

    def context(self) -> Any:
        return self
