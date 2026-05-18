# fastapi-resolve

## Statement of Intent

fastapi-resolve extends FastAPI with two new return types for route handlers: **Deferred** and **Negotiated**, processed by a custom **ResolvingRoute** class.

### Problem

FastAPI route handlers return data directly — dicts, Pydantic models, or Response objects. There is no built-in mechanism for a handler to resolve a URL prefix (such as a tenant or project slug) and delegate the remaining path to a dedicated set of sub-handlers, nor for serving multiple response formats based on the client's Accept header.

### Solution

Three public classes and one internal class:

**Deferred** — Abstract base class for branch endpoints. A top-level FastAPI route handler resolves a prefix (loading a tenant from the database, checking permissions) and returns a Deferred subclass instance. The instance carries the resolved context as properties and declares its own route handlers as decorated methods. The base class provides `resolve()` which matches the remaining URL path against those handlers and invokes the match.

**Negotiated** — Content negotiation. A handler returns a Negotiated instance mapping content types to response factories. Resolution picks the best match against the request's Accept header.

**ResolvingRoute(APIRoute)** — The FastAPI integration point. Overrides `get_route_handler()` to insert an unwrap loop: if a handler returns a Deferred instance, it calls `resolve()` and repeats until reaching a concrete response or a Negotiated instance. This is applied per-router via `route_class=ResolvingRoute`.

**Route** — Internal. Holds a path pattern, allowed HTTP methods, and a reference to the handler function. Built automatically from decorators on Deferred subclasses and collected into a class-level route list via `__init_subclass__`. Used by `Deferred.resolve()` for path matching and parameter extraction.

### Usage Pattern

```python
from fastapi import APIRouter, Request
from fastapi_resolve import Deferred, Negotiated, ResolvingRoute

router = APIRouter(route_class=ResolvingRoute)

class TenantEndpoints(Deferred):
    def __init__(self, tenant):
        self.tenant = tenant

    @Deferred.get("dashboard")
    async def dashboard(self, request: Request):
        ...

    @Deferred.get("users/int:id")
    async def get_user(self, request: Request, id: int):
        ...

@router.get("/{tenant}/{path:path}")
async def resolve_tenant(request: Request, tenant: str, path: str):
    tenant_obj = await load_tenant(tenant)
    if tenant_obj is None:
        return None
    return TenantEndpoints(tenant_obj)
```

### Design Decisions

- Route handlers on Deferred subclasses are decorated with `@Deferred.get`, `@Deferred.post`, etc. Decorators run at class definition time and attach Route instances to a class-level list via `__init_subclass__`.
- Deferred handlers can themselves return Deferred or Negotiated instances. The ResolvingRoute unwrap loop handles arbitrary nesting.
- Path parameter injection into handler arguments reuses patterns from existing filter framework code.
- No middleware system — that is FastAPI's domain. Per-handler decorators (like `@require_credentials`) operate at invocation time with access to the bound Deferred instance.
- Route is internal and not exported from the package's `__init__.py`.