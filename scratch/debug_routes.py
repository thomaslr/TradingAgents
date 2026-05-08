from api.main import app
from starlette.routing import Match

scope = {
    "type": "http",
    "method": "POST",
    "path": "/api/runs/batch-delete",
    "headers": [],
    "query_string": b"",
}

for route in app.routes:
    match, child_scope = route.matches(scope)
    if match != Match.NONE:
        print(f"Matched {route.path}: {match}")
