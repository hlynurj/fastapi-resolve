from fastapi import FastAPI, APIRouter
from fastapi.responses import JSONResponse

from fastapi_resolve import Negotiated, ResolvingRoute

# FastAPI app to test classes from the fastapi-resolve package
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
router = APIRouter(route_class=ResolvingRoute)

@router.get("/negotiated")
def testNegotiatied() -> Negotiated:
    return Negotiated({
        "text/html": lambda: JSONResponse({"test": "html"}),
        "application/json": lambda: JSONResponse({"test": "json"})
    })
    
app.include_router(router)