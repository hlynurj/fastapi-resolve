from datetime import date

from fastapi import FastAPI, Request, Response

from fastapi_resolve import Deferred, Negotiated, Router
from tests.project import Project

# FastAPI app to test classes from the fastapi-resolve package
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
router = Router()


@router.get("/slug:project/*")
def getProject(project: str) -> Project | None:
    if project == "acme":
        return Project("acme")


@router.get("/acme")
def testFallthrough():
    return {"test": "shouldn't happen"}


@router.get("/params/slug:slug/int:int/date:date")
def testParams(
    request: Request,
    response: Response,
    deferred: Deferred,
    slug: str,
    int: int,
    date: date,
):
    return {
        "request": request is not None,
        "response": response is not None,
        "deferred": deferred is not None,
        "slug": slug,
        "int": int,
        "date": date,
    }


@router.get("/negotiated")
def testNegotiatied() -> Negotiated:
    return Negotiated(
        {
            "text/html": lambda: {"test": "html"},
            "application/json": lambda: {"test": "json"},
        }
    )


Router.use(app, router)
