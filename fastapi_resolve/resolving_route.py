
from typing import Callable

from fastapi import Request
from fastapi.routing import APIRoute

from .negotiated import Negotiated


class ResolvingRoute(APIRoute):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def get_route_handler(self) -> Callable:
        print("get_router_handler override")
        original = super().get_route_handler()

        async def wrapper(request: Request):
            response = await original(request)
            if isinstance(response, Negotiated):
                response = response.resolve(request)
            return response

        return wrapper
