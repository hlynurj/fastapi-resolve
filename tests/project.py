from __future__ import annotations

from fastapi import HTTPException

from fastapi_resolve import Deferred, Router


class Project(Deferred):
    router = Router()

    def __init__(self, project: str):
        self.project = project

    @router.get("dashboard")
    def getDashboard(self):
        return {"project": self.project}

    @router.get("")
    def getProject(self):
        return {"test": "project's main page", "project": self.project}

    @router.get("slug:subproject/*")
    def getSecondProject(self, subproject: str) -> Project | None:
        if subproject == "sub-project":
            return Project("sub-project")

    @router.get("400")
    def test400():
        raise HTTPException(400)
