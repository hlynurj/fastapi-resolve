# fastapi-resolve

Extends FastAPI with two new return types for route handlers: **Deferred** and **Negotiated**.

**Deferred** lets a handler resolve a URL prefix — like a tenant slug or project identifier — and delegate the remaining path to a dedicated set of sub-handlers. The returned instance carries the resolved context as properties and declares its own routes as decorated methods.

**Negotiated** adds HTTP content negotiation, serving different response formats based on the client's `Accept` header.

## Installation

```
pip install fastapi-resolve
```

## Quick Start

```python
from fastapi import FastAPI
from fastapi_resolve import Router

app = FastAPI()
router = Router()

@router.get("/hello")
def hello():
    return {"message": "hello world"}

Router.use(app, router)
```

`Router.use` adds a catch-all route, so register any direct FastAPI routes (health checks, OpenAPI, etc.) **before** calling it.

## Route Patterns

Route patterns use `/`-separated sections. Each section is a literal, a typed parameter, or a wildcard.

### Parameter Types

| Pattern      | Matches                | Example              |
|-------------|------------------------|----------------------|
| `int:name`  | Integer                | `/users/42`          |
| `date:name` | Date (`yyyy-MM-dd`)    | `/log/2025-03-15`    |
| `uuid:name` | UUID                   | `/items/550e8400-...`|
| `slug:name` | Any string             | `/posts/hello-world` |

Parameters are extracted and injected into the handler by name:

```python
@router.get("/users/int:id")
def get_user(id: int):
    return {"id": id}
```

### Wildcards

A `*` at the end of a pattern matches any remaining path. This is mainly used with `Deferred` prefix handlers:

```python
@router.get("/slug:tenant/*")
def resolve_tenant(tenant: str) -> TenantEndpoints | None:
    ...
```

## Handler Parameters

Handlers can request any combination of these parameters by name:

```python
@router.get("/items/int:id")
async def get_item(request: Request, response: Response, id: int):
    ...
```

- **`request`** — the FastAPI/Starlette `Request` object
- **`response`** — the FastAPI/Starlette `Response` object
- **`self`** — the `Deferred` instance, when the handler is a method on a `Deferred` subclass
- **`deferred`** — the context provided by the resolved `Deferred` instance (see [Splitting Routes Across Files](#splitting-routes-across-files)). By default this is the `Deferred` instance itself, but subclasses can override `context()` to return a domain object instead
- **`payload`** — the parsed JSON body, for POST/PUT/PATCH/DELETE requests. If the parameter has a Pydantic model annotation, the payload is validated and converted automatically
- **Route parameters** — matched by name from the pattern (e.g. `id` from `int:id`)

All parameters are optional — declare only the ones you need.

## HTTP Methods

```python
@router.get("/path")
@router.post("/path")
@router.put("/path")
@router.patch("/path")
@router.delete("/path")
@router.head("/path")
@router.route("/path", methods=["GET", "POST"])
```

`@router.get("/path")` will also automatically register with a `HEAD` method. Any body will be stripped for `HEAD` requests. you can check `request.method` to skip expensive work for `HEAD` requests.

## Deferred Routing

A handler can return a `Deferred` subclass to delegate routing to a nested scope. The subclass carries context as instance properties and declares its own routes via a class-level `Router`:

```python
from fastapi_resolve import Deferred, Router

class TenantEndpoints(Deferred):
    router = Router()

    def __init__(self, tenant):
        super().__init__()
        self.tenant = tenant

    @router.get("")
    def home(self, request):
        return templates.TemplateResponse(
            "home.html", 
            {"request": request, "tenant": self.tenant}
        )

    @router.get("dashboard")
    def dashboard(self, request):
        return templates.TemplateResponse(
            "dashboard.html", 
            {"request": request, "tenant": self.tenant}
        )

    @router.get("users/int:id")
    def get_user(self, id: int):
        return {"tenant": self.tenant, "user_id": id}
```

The top-level route resolves the prefix and returns the instance:

```python
router = Router()

@router.get("/slug:tenant/*")
def resolve_tenant(tenant: str) -> TenantEndpoints | None:
    if tenant == "acme":
        return TenantEndpoints("acme")
    # Returning None falls through to try other routes
```

This handles:

| Request               | Remaining path | Handler called |
|-----------------------|---------------|----------------|
| `GET /acme`           | `""`          | `home`         |
| `GET /acme/dashboard` | `dashboard`   | `dashboard`    |
| `GET /acme/users/42`  | `users/42`    | `get_user`     |
| `GET /acme/unknown`   | `unknown`     | 404            |
| `GET /nonexistent`    | —             | Falls through  |

### Dynamic Routing

A deferred handler can set up routers dynamically in `__init__`:

```python
from contents.normal_project import router as normal_project_router
from contents.extended_project import router as extended_project_router

class ProjectBranch(Deferred):
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        if project.type == "EXTENDED":
            self.routers.append(extended_project_router)
        else:
            self.routers.append(normal_project_router)
    
    def context(self):
        return self.project
```

### Nested Deferred

A deferred handler can itself return another `Deferred`, creating nested scopes. Here a tenant branch resolves a project within its scope and returns a `ProjectBranch` whose `context()` exposes the `Project` domain object:

```python
class ProjectBranch(Deferred):
    router = Router()

    def __init__(self, project: Project):
        super().__init__()
        self.project = project

    def context(self):
        return self.project

    @router.get("")
    def overview(self, request):
        return templates.TemplateResponse(
            "project.html",
            {"request": request, "project": self.project}
        )
```

```python
class TenantBranch(Deferred):
    router = Router()

    def __init__(self, tenant):
        super().__init__()
        self.tenant = tenant

    @router.get("")
    def overview(self, request):
        return templates.TemplateResponse(
            "overview.html", 
            {"request": request, "tenant": self.tenant}
        )

    @router.get("slug:project/*")
    def resolve_project(self, project: str) -> ProjectBranch | None:
        project = Project.get_by_slug(self.tenant, project)
        if project:
            return ProjectBranch(project)
```

This matches paths like `/acme/website/` — the first `Deferred` resolves the tenant, the second resolves the project within that tenant.

### Fallthrough

When a handler returns `None`, the router continues trying other matching routes. Once a handler returns a `Deferred` instance (non-`None`), the router is committed to that branch — if no deferred handler matches the remaining path, the result is 404.

### Splitting Routes Across Files

Routes don't have to be methods on the `Deferred` subclass. You can define routers in separate modules and attach them as class attributes — the `Deferred` base class picks up any `Router` instances on the class automatically.

External handlers receive the value returned by `context()` as the `deferred` parameter. By overriding `context()` to return a domain object, external routers can import that domain type directly — no coupling to the routing layer and no circular imports.

```python
# articles.py
from objects.project import Project
from fastapi_resolve import Router

router = Router()

@router.get("articles")
def list_articles(deferred: Project, request):
    return templates.TemplateResponse(
        "articles.html",
        {"request": request, "project": deferred}
    )

@router.get("articles/int:id")
def get_article(deferred: Project, request, id: int):
    article = Article.get(deferred, id)
    return templates.TemplateResponse(
        "article.html",
        {"request": request, "project": deferred, "article": article}
    )
```

```python
# project_branch.py
from objects.project import Project
from fastapi_resolve import Deferred, Router
from articles import router as article_router

class ProjectBranch(Deferred):
    router = Router()
    articles = article_router

    def __init__(self, project: Project):
        super().__init__()
        self.project = project

    def context(self):
        return self.project

    @router.get("")
    def home(self, request):
        return templates.TemplateResponse(
            "project.html", 
            {"request": request, "project": self.project}
        )
```

`articles.py` imports `Project` from the domain layer and gets full type safety on the `deferred` parameter. It has no dependency on `ProjectBranch` or any routing code.

A `Deferred` subclass can have any number of `Router` attributes — they're all collected and their routes are tried in order.

## Content Negotiation

Return a `Negotiated` instance to serve different formats based on the `Accept` header:

```python
from fastapi_resolve import Negotiated

@router.get("/article/int:id")
def get_article(request, id: int) -> Negotiated:
    article = Article.get(id)
    return Negotiated({
        "text/html": lambda: templates.TemplateResponse(
            "article.html", 
            {"request": request, "article": article}
        ),
        "application/json": lambda: article.to_dict(),
    })
```

The resolution follows standard HTTP content negotiation: quality factors are respected (`text/html;q=0.9`), wildcards work (`*/*`, `text/*`), and a 406 is returned if nothing matches. When no `Accept` header is present, `*/*` is assumed.

`Negotiated` works both at the top level and inside deferred handlers.

## Wiring It Up

```python
from fastapi import FastAPI
from fastapi_resolve import Router

app = FastAPI()
router = Router()

# ... register routes on router ...

Router.use(app, router)
```

You can pass multiple routers to `Router.use` — they're tried in order:

```python
Router.use(app, tenant_router, api_router, fallback_router)
```

## Logging

fastapi-resolve uses Python's `logging` module under the `fastapi_resolve` namespace. Set the `FASTAPI_RESOLVE_LOG_LEVEL` environment variable to enable debug output:

```bash
export FASTAPI_RESOLVE_LOG_LEVEL=DEBUG
```

This traces the full resolution chain — route matching, Deferred branching, fallthrough, and content negotiation:

```
DEBUG:fastapi_resolve.routing: Resolving GET 'acme/dashboard' against 4 route(s)
DEBUG:fastapi_resolve.routing: Matched 'slug:project/*' → getProject with params {'project': 'acme'}
DEBUG:fastapi_resolve.routing: Deferred to Project with 'dashboard' as remaining path
DEBUG:fastapi_resolve.routing: Resolving GET 'dashboard' against 3 route(s)
DEBUG:fastapi_resolve.routing: Matched 'dashboard' → Project.getDashboard with params {}
```

## License

MIT