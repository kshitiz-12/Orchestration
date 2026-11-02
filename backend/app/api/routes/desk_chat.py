"""Chat for the admin desk: questions from records, and Excel dropped into the same thread."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import SessionDep, TenantDep, UserDep
from app.services.desk_chat import answer_question, import_workbook

router = APIRouter(prefix="/desk", tags=["desk"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class ChatIn(BaseModel):
    message: str = ""
    history: list[dict] = Field(default_factory=list)


@router.post("/chat")
def desk_chat(body: ChatIn, session: SessionDep, tenant_id: TenantDep, _: UserDep):
    return {"reply": answer_question(session, tenant_id, body.message, body.history), "synced": False}


@router.post("/chat/file")
async def desk_chat_file(
    session: SessionDep,
    tenant_id: TenantDep,
    _: UserDep,
    file: UploadFile = File(...),
    note: str = Form(""),
):
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB)")
    if not content:
        raise HTTPException(status_code=422, detail="The file is empty")
    return import_workbook(session, tenant_id, file.filename or "", content, note)
