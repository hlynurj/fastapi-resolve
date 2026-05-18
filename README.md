# fastapi-resolve
Extends FastAPI route handlers with Deferred and Negotiated return types. Deferred lets a handler resolve a URL prefix (like a tenant or project) and delegate the remaining path to a dedicated set of sub-handlers. Negotiated adds HTTP content negotiation, serving different response formats based on the Accept header.
