import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db
from app.core.firebase import verify_firebase_token
from app.modules.admin import service
from app.modules.admin.schemas import (
    DireccionCreate,
    DireccionUpdate,
    PersonaCreate,
    PersonaUpdate,
    UsuarioCreate,
)

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="templates")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_web_user(request: Request, db: AsyncSession):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = verify_firebase_token(token)
        uid = payload.get("uid")
    except Exception:
        return None
    return await service.get_usuario_by_firebase_uid(db, uid)


def _redirect_login():
    return RedirectResponse("/login", status_code=302)


def _ctx(request: Request, user, **kwargs) -> dict:
    return {"request": request, "user": user, **kwargs}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "firebase_api_key": settings.FIREBASE_WEB_API_KEY,
        "firebase_auth_domain": settings.FIREBASE_AUTH_DOMAIN,
    })


@router.post("/web/auth/token")
async def set_token(request: Request):
    body = await request.json()
    token = body.get("token", "")
    try:
        verify_firebase_token(token)
    except Exception:
        return JSONResponse({"error": "Token inválido"}, status_code=401)
    response = JSONResponse({"ok": True})
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    return response


@router.post("/web/auth/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/")
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    personas = await service.listar_personas(db)
    return templates.TemplateResponse("index.html", _ctx(request, user, total_personas=len(personas)))


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------

@router.get("/personas")
async def personas_lista(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    personas = await service.listar_personas(db)
    return templates.TemplateResponse(
        "personas/lista.html",
        _ctx(request, user, personas=personas, error=request.query_params.get("error")),
    )


@router.get("/personas/nueva")
async def persona_nueva_form(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    return templates.TemplateResponse("personas/form.html", _ctx(request, user, persona=None, error=None))


@router.post("/personas/nueva")
async def persona_nueva_post(
    request: Request,
    nombre_completo: str = Form(...),
    documento_identidad: str = Form(...),
    telefono: str = Form(""),
    fecha_nacimiento: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    if await service.get_persona_by_documento(db, documento_identidad):
        return templates.TemplateResponse(
            "personas/form.html",
            _ctx(request, user, persona=None, error="Ya existe una persona con ese documento"),
            status_code=409,
        )
    await service.crear_persona(db, PersonaCreate(
        nombre_completo=nombre_completo,
        documento_identidad=documento_identidad,
        telefono=telefono or None,
        fecha_nacimiento=fecha_nacimiento or None,
    ))
    return RedirectResponse("/personas", status_code=302)


@router.get("/personas/{persona_id}/editar")
async def persona_editar_form(
    persona_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    persona = await service.get_persona_by_id(db, persona_id)
    if not persona:
        return RedirectResponse("/personas", status_code=302)
    return templates.TemplateResponse("personas/form.html", _ctx(request, user, persona=persona, error=None))


@router.post("/personas/{persona_id}/editar")
async def persona_editar_post(
    persona_id: uuid.UUID,
    request: Request,
    nombre_completo: str = Form(""),
    telefono: str = Form(""),
    fecha_nacimiento: str = Form(""),
    estado: str = Form("activo"),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    persona = await service.get_persona_by_id(db, persona_id)
    if persona:
        await service.actualizar_persona(db, persona, PersonaUpdate(
            nombre_completo=nombre_completo or None,
            telefono=telefono or None,
            fecha_nacimiento=fecha_nacimiento or None,
            estado=estado,
        ))
    return RedirectResponse("/personas", status_code=302)


@router.post("/personas/{persona_id}/eliminar")
async def persona_eliminar(
    persona_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    persona = await service.get_persona_by_id(db, persona_id)
    if persona:
        await service.eliminar_persona(db, persona)
    return RedirectResponse("/personas", status_code=302)


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

@router.get("/personas/{persona_id}/usuarios")
async def usuarios_lista(
    persona_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    persona = await service.get_persona_by_id(db, persona_id)
    if not persona:
        return RedirectResponse("/personas", status_code=302)
    usuarios = await service.listar_usuarios_de_persona(db, persona_id)
    return templates.TemplateResponse(
        "usuarios/lista.html",
        _ctx(request, user, persona=persona, usuarios=usuarios, error=request.query_params.get("error")),
    )


@router.post("/personas/{persona_id}/usuarios/nuevo")
async def usuario_nuevo_post(
    persona_id: uuid.UUID,
    request: Request,
    email: str = Form(...),
    firebase_uid: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    persona = await service.get_persona_by_id(db, persona_id)
    if not persona:
        return RedirectResponse("/personas", status_code=302)

    error = None
    if await service.get_usuario_by_email(db, email):
        error = "El email ya está registrado"
    elif await service.get_usuario_by_firebase_uid(db, firebase_uid):
        error = "El Firebase UID ya está registrado"

    if error:
        usuarios = await service.listar_usuarios_de_persona(db, persona_id)
        return templates.TemplateResponse(
            "usuarios/lista.html",
            _ctx(request, user, persona=persona, usuarios=usuarios, error=error),
            status_code=409,
        )

    await service.crear_usuario(db, persona_id, UsuarioCreate(email=email, firebase_uid=firebase_uid))
    return RedirectResponse(f"/personas/{persona_id}/usuarios", status_code=302)


@router.post("/usuarios/{usuario_id}/eliminar")
async def usuario_eliminar(
    usuario_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    usuario = await service.get_usuario_by_id(db, usuario_id)
    persona_id = usuario.persona_id if usuario else None
    if usuario:
        await service.eliminar_usuario(db, usuario)
    return RedirectResponse(f"/personas/{persona_id}/usuarios", status_code=302)


# ---------------------------------------------------------------------------
# Direcciones
# ---------------------------------------------------------------------------

@router.get("/personas/{persona_id}/direcciones")
async def direcciones_lista(
    persona_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    persona = await service.get_persona_by_id(db, persona_id)
    if not persona:
        return RedirectResponse("/personas", status_code=302)
    direcciones = await service.listar_direcciones_de_persona(db, persona_id)
    return templates.TemplateResponse(
        "direcciones/lista.html",
        _ctx(request, user, persona=persona, direcciones=direcciones),
    )


@router.post("/personas/{persona_id}/direcciones/nueva")
async def direccion_nueva_post(
    persona_id: uuid.UUID,
    request: Request,
    calle: str = Form(...),
    numero: str = Form(...),
    ciudad: str = Form(...),
    provincia: str = Form(...),
    descripcion: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    persona = await service.get_persona_by_id(db, persona_id)
    if persona:
        await service.crear_direccion(db, persona_id, DireccionCreate(
            calle=calle, numero=numero, ciudad=ciudad,
            provincia=provincia, descripcion=descripcion or None,
        ))
    return RedirectResponse(f"/personas/{persona_id}/direcciones", status_code=302)


@router.get("/direcciones/{direccion_id}/editar")
async def direccion_editar_form(
    direccion_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    direccion = await service.get_direccion_by_id(db, direccion_id)
    if not direccion:
        return RedirectResponse("/personas", status_code=302)
    return templates.TemplateResponse(
        "direcciones/form.html", _ctx(request, user, direccion=direccion)
    )


@router.post("/direcciones/{direccion_id}/editar")
async def direccion_editar_post(
    direccion_id: uuid.UUID,
    request: Request,
    calle: str = Form(""),
    numero: str = Form(""),
    ciudad: str = Form(""),
    provincia: str = Form(""),
    descripcion: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    direccion = await service.get_direccion_by_id(db, direccion_id)
    if not direccion:
        return RedirectResponse("/personas", status_code=302)
    persona_id = direccion.persona_id
    await service.actualizar_direccion(db, direccion, DireccionUpdate(
        calle=calle or None, numero=numero or None,
        ciudad=ciudad or None, provincia=provincia or None,
        descripcion=descripcion or None,
    ))
    return RedirectResponse(f"/personas/{persona_id}/direcciones", status_code=302)


@router.post("/direcciones/{direccion_id}/eliminar")
async def direccion_eliminar(
    direccion_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    direccion = await service.get_direccion_by_id(db, direccion_id)
    persona_id = direccion.persona_id if direccion else None
    if direccion:
        await service.eliminar_direccion(db, direccion)
    return RedirectResponse(f"/personas/{persona_id}/direcciones", status_code=302)
