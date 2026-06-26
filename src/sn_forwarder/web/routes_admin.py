from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    from .auth import require_admin
    user = require_admin(request, request.app.state.user_store)
    return HTMLResponse(f"<p>Admin: {user.username}</p>")
