from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    from .auth import require_user
    user = require_user(request, request.app.state.user_store)
    templates = request.app.state.templates
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})
