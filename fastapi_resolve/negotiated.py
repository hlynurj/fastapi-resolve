from typing import Callable

from fastapi import HTTPException, Request
from starlette.responses import Response


class Negotiated(Response):
    @staticmethod
    def split_content_type(content_type: str) -> tuple[str, str]:
        r = content_type.split("/")
        if len(r) != 2:
            raise AttributeError("Content type must be in the format of 'mediatype/subtype'")
        return (r[0], r[1])
        
    def __init__(self, handlers: dict[str, Callable]) -> None:
        super().__init__()
        self.handlers: list[tuple[tuple[str, str], Callable]] = [(self.split_content_type(k), v) for k, v in handlers.items()]
        
    class Directive:
        def __init__(self, s: str) -> None:
            if not s.strip():
                raise ValueError
            split = s.strip().split(";")
            if not split[0].strip():
                raise ValueError
            types = split[0].strip().split("/")
            if len(types) != 2:
                raise ValueError
            self.media_type: str = types[0]
            self.sub_type: str = types[1]
            self.qualifier: float = 1
            q = next((p[2:] for p in split[1:] if p.strip().startswith("q=")), None)
            if q is not None:
                try:
                    self.qualifier: float = float(q)
                except ValueError:
                    pass
            if self.qualifier < 0 or self.qualifier > 1:
                raise ValueError
        
        def matches(self, content_type: tuple[str, str]) -> bool:
            if self.media_type == "*":
                return True
            (media_type, sub_type) = content_type
            if self.media_type != media_type:
                return False
            return self.sub_type == "*" or self.sub_type == sub_type
    
    def resolve(self, request: Request):
        accept = request.headers.get("accept", "").split(",")
        directives: list[Negotiated.Directive] = []
        for s in accept:
            try:
                directives.append(Negotiated.Directive(s))
            except ValueError:
                pass
        if len(directives) == 0:
            directives.append(self.Directive("*/*"))
            
        directives.sort(key=lambda d: d.qualifier, reverse=True)
        
        for directive in directives:
            for (key, handler) in self.handlers:
                if directive.matches(key):
                    return handler()
        
        raise HTTPException(status_code=406)