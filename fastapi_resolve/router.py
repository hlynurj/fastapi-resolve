from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, get_args, get_origin

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ValidationError

from ._logging import get_logger
from .deferred import Deferred
from .negotiated import Negotiated
from .route import Route
from .route_context import RouteContext

logger = get_logger("routing")

PAYLOAD_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class Router:
    """
    URL routing that supports Deferred and Negotiated return types and fall through.
    """

    def __init__(self) -> None:
        """Initialize an empty filter with no routes."""
        self._routes: list[Route] = []

    def add_route(self, path: str, handler: Callable, methods: list[str] = []):
        """
        Add a route pattern to this router.

        Args:
            path: Path pattern to match (e.g. "items/int:id")
            handler: Function to call on match
            methods: HTTP Methods to accept (defaults to empty list for all methods)
        """
        self._routes.append(Route(path, handler, methods))

    def route(self, path: str, methods: list[str] = []):
        """
        Decorator to register a handler for a path pattern.

        Args:
            path: Path pattern to match
            methods: HTTP Methods to accept (defaults to empty list for all methods)
        """

        def decorator(func):
            self.add_route(path, func, methods=methods)
            return func

        return decorator

    def get(self, path: str):
        """Decorator to register a GET and HEAD handler for a path pattern."""
        return self.route(path, methods=["GET", "HEAD"])

    def head(self, path: str):
        """Decorator to register a HEAD handler for a path pattern."""
        return self.route(path, methods=["HEAD"])

    def put(self, path: str):
        """Decorator to register a PUT handler for a path pattern."""
        return self.route(path, methods=["PUT"])

    def post(self, path: str):
        """Decorator to register a POST handler for a path pattern."""
        return self.route(path, methods=["POST"])

    def patch(self, path: str):
        """Decorator to register a PATCH handler for a path pattern."""
        return self.route(path, methods=["PATCH"])

    def delete(self, path: str):
        """Decorator to register a DELETE handler for a path pattern."""
        return self.route(path, methods=["DELETE"])

    @staticmethod
    def _process_segment(
        section: str, index: int, contexts: list[RouteContext], method: str
    ) -> bool:
        match_found: bool = False
        for context in contexts:
            if context.is_full_match and context.is_wildcard:
                match_found = True
            elif context.is_full_match:
                context.is_mismatch = True
            elif not context.is_mismatch:
                if context.route.matches(
                    section,
                    method,
                    index,
                    context.route.is_last_section(index),
                    context,
                ):
                    match_found = True
                    context.is_full_match = (
                        context.is_wildcard or context.route.is_last_section(index)
                    )
                else:
                    context.is_mismatch = True
        return match_found

    @staticmethod
    def _process_is_wildcard_next(
        index: int, contexts: list[RouteContext], method: str
    ):
        for context in contexts:
            if not (context.is_full_match or context.is_mismatch):
                if (
                    context.route.matches_method(method)
                    and len(context.route.sections) == index + 1
                    and context.route.sections[index] == "*"
                ):
                    context.is_full_match = True
                    context.is_wildcard = True

    @staticmethod
    def _find_all_routes(
        method: str, path: str, routes: list[Route]
    ) -> list[RouteContext]:
        contexts: list[RouteContext] = [RouteContext(route) for route in routes]
        p: str = path.strip("/") if path else ""
        sections: list[str] = [""] if p == "" else p.split("/")

        for i, section in enumerate(sections):
            if not Router._process_segment(section, i, contexts, method):
                return []
        Router._process_is_wildcard_next(len(sections), contexts, method)
        return [c for c in contexts if c.is_full_match and not c.is_mismatch]

    @staticmethod
    async def _get_payload(param, request: Request):
        """Extract and validate JSON payload based on parameter type annotation."""
        payload_data = await request.json()
        # Check if the parameter has a type annotation and try to construct it
        if param.annotation != param.empty:
            try:
                # Handle list[Model] types
                if get_origin(param.annotation) is list:
                    item_type = get_args(param.annotation)[0]
                    if issubclass(item_type, BaseModel):
                        # Convert list of dicts to list of Pydantic models
                        return [item_type(**item) for item in payload_data]
                # Handle direct Pydantic model types
                elif issubclass(param.annotation, BaseModel):
                    return param.annotation(**payload_data)
            except ValidationError as e:
                raise HTTPException(status_code=422, detail=e.errors())
            except Exception:  # noqa: BLE001
                raise HTTPException(status_code=400, detail="Invalid JSON payload")
        else:
            return payload_data

    @staticmethod
    async def _invoke_handler(
        context: RouteContext,
        request: Request,
        response: Response,
        deferred: Deferred | None = None,
    ):
        handler = context.route.handler
        sig = inspect.signature(handler)
        kwargs = {}

        for param_name, param in sig.parameters.items():
            if param_name == "request":
                kwargs["request"] = request
            elif param_name == "response":
                kwargs["response"] = response
            elif param_name == "deferred" and deferred is not None:
                kwargs["deferred"] = deferred.context()
            elif param_name == "self" and deferred is not None:
                kwargs["self"] = deferred
            elif param_name == "payload" and request.method in PAYLOAD_METHODS:
                kwargs["payload"] = await Router._get_payload(param, request)
            elif param_name in context.params:
                kwargs[param_name] = context.params[param_name]
            else:
                kwargs[param_name] = None

        if inspect.iscoroutinefunction(handler):
            return await handler(**kwargs)
        else:
            return handler(**kwargs)

    @staticmethod
    async def _dispatch_handler(
        context: RouteContext,
        path: str,
        request: Request,
        response: Response,
        deferred: Deferred | None = None,
    ) -> tuple[bool, Any]:
        committed = False
        logger.debug(
            "Matched '%s' → %s with params %s",
            "/".join(context.route.sections),
            context.route.handler.__qualname__,
            context.params or {},
        )
        returned = await Router._invoke_handler(context, request, response, deferred)
        if isinstance(returned, Deferred):
            committed = True
            prefix_length = len(context.route.sections)
            if context.route.sections[-1] == "*":
                prefix_length -= 1
            sections = path.split("/")
            remaining = "/".join(sections[prefix_length:])
            logger.debug(
                "Deferred to %s with '%s' as remaining path",
                type(returned).__name__,
                remaining,
            )
            returned = await Router._dispatch_request(
                remaining, request, response, returned.routers, returned
            )
        if isinstance(returned, Negotiated):
            logger.debug(
                "Negotiated returned with %d types, resolving against Accept header",
                len(returned.handlers),
            )
            returned = returned.resolve(request)
        if returned is None and not committed:
            logger.debug("Returning None and falling through to next handler")
        return (committed, returned)

    @staticmethod
    async def _dispatch_request(
        path: str,
        request: Request,
        response: Response,
        routers: list[Router],
        deferred: Deferred | None = None,
    ):
        logger.debug(
            "Resolving %s '%s' against %d route(s)",
            request.method,
            path,
            sum(len(r._routes) for r in routers),
        )
        contexts = Router._find_all_routes(
            request.method,
            path,
            [route for router in routers for route in router._routes],
        )
        for context in contexts:
            (committed, response) = await Router._dispatch_handler(
                context, path, request, response, deferred
            )
            if committed or response:
                return response
        logger.debug("No route matched, raising 404 status")
        raise HTTPException(status_code=404, detail="Not found")

    @staticmethod
    def use(app: FastAPI, *routers: Router) -> None:
        """
        Registers router with a FastAPI application.

        Note: This adds a catch-all route handler. Register any direct
        FastAPI routes (health checks, metrics, etc) BEFORE calling this method.

        Args:
            app: FastAPI application instance
            *routers: Router instances in order of precedence
        """

        logger.info(
            "Registered %d router(s) with %d route(s)",
            len(routers),
            sum(len(r._routes) for r in routers),
        )

        async def handler(path: str, request: Request, response: Response):
            return await Router._dispatch_request(
                path, request, response, list(routers)
            )

        app.add_api_route(
            "/{path:path}",
            handler,
            methods=["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH"],
        )
