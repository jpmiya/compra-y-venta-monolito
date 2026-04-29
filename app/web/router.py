import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
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
from app.modules.productos import service as productos_service
from app.modules.productos.schemas import ProductoCreate, ProductoUpdate
from app.modules.billetera import service as billetera_service
from app.modules.carrito import service as carrito_service
from app.modules.delivery import service as delivery_service

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="templates")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_firebase_uid(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None, None
    try:
        payload = verify_firebase_token(token)
        return payload.get("uid"), token
    except Exception:
        return None, None


async def _get_web_user(request: Request, db: AsyncSession):
    uid, _ = await _get_firebase_uid(request)
    if not uid:
        return None
    return await service.get_usuario_by_firebase_uid(db, uid)


def _redirect_login():
    return RedirectResponse("/login", status_code=302)


def _redirect_registro():
    return RedirectResponse("/web/registro", status_code=302)


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


@router.get("/ui/personas/nueva")
async def persona_nueva_form(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    return templates.TemplateResponse("personas/form.html", _ctx(request, user, persona=None, error=None))


@router.post("/ui/personas/nueva")
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
    return RedirectResponse("/ui/personas", status_code=302)


@router.get("/ui/personas/{persona_id}/editar")
async def persona_editar_form(
    persona_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    persona = await service.get_persona_by_id(db, persona_id)
    if not persona:
        return RedirectResponse("/ui/personas", status_code=302)
    return templates.TemplateResponse("personas/form.html", _ctx(request, user, persona=persona, error=None))


@router.post("/ui/personas/{persona_id}/editar")
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
    return RedirectResponse("/ui/personas", status_code=302)


@router.post("/ui/personas/{persona_id}/eliminar")
async def persona_eliminar(
    persona_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    persona = await service.get_persona_by_id(db, persona_id)
    if persona:
        await service.eliminar_persona(db, persona)
    return RedirectResponse("/ui/personas", status_code=302)


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

@router.post("/ui/personas/{persona_id}/usuarios/nuevo")
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
        return RedirectResponse("/ui/personas", status_code=302)

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
    return RedirectResponse(f"/ui/personas/{persona_id}/usuarios", status_code=302)


@router.post("/ui/usuarios/{usuario_id}/eliminar")
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
    return RedirectResponse(f"/ui/personas/{persona_id}/usuarios", status_code=302)


# ---------------------------------------------------------------------------
# Direcciones
# ---------------------------------------------------------------------------

@router.post("/ui/personas/{persona_id}/direcciones/nueva")
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
    return RedirectResponse(f"/ui/personas/{persona_id}/direcciones", status_code=302)


@router.get("/ui/direcciones/{direccion_id}/editar")
async def direccion_editar_form(
    direccion_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    direccion = await service.get_direccion_by_id(db, direccion_id)
    if not direccion:
        return RedirectResponse("/ui/personas", status_code=302)
    return templates.TemplateResponse(
        "direcciones/form.html", _ctx(request, user, direccion=direccion)
    )


@router.post("/ui/direcciones/{direccion_id}/editar")
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
        return RedirectResponse("/ui/personas", status_code=302)
    persona_id = direccion.persona_id
    await service.actualizar_direccion(db, direccion, DireccionUpdate(
        calle=calle or None, numero=numero or None,
        ciudad=ciudad or None, provincia=provincia or None,
        descripcion=descripcion or None,
    ))
    return RedirectResponse(f"/ui/personas/{persona_id}/direcciones", status_code=302)


@router.post("/ui/direcciones/{direccion_id}/eliminar")
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
    return RedirectResponse(f"/ui/personas/{persona_id}/direcciones", status_code=302)


# ---------------------------------------------------------------------------
# Registro de primer acceso
# ---------------------------------------------------------------------------

@router.get("/web/registro")
async def registro_form(request: Request, db: AsyncSession = Depends(get_db)):
    uid, _ = await _get_firebase_uid(request)
    if not uid:
        return _redirect_login()
    return templates.TemplateResponse("registro.html", {"request": request, "error": None})


@router.post("/web/registro")
async def registro_post(
    request: Request,
    nombre_completo: str = Form(...),
    documento_identidad: str = Form(...),
    fecha_nacimiento: str = Form(...),
    telefono: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    uid, _ = await _get_firebase_uid(request)
    if not uid:
        return _redirect_login()

    # Obtener email del token
    from app.core.firebase import get_firebase_user
    try:
        fb_user = get_firebase_user(uid)
        email = fb_user.email or f"{uid}@unknown.com"
    except Exception:
        email = f"{uid}@unknown.com"

    if await service.get_persona_by_documento(db, documento_identidad):
        return templates.TemplateResponse("registro.html", {
            "request": request,
            "error": "Ya existe una persona con ese documento",
        }, status_code=409)

    from app.modules.admin.schemas import PersonaCreate, UsuarioCreate
    persona = await service.crear_persona(db, PersonaCreate(
        nombre_completo=nombre_completo,
        documento_identidad=documento_identidad,
        fecha_nacimiento=fecha_nacimiento or None,
        telefono=telefono or None,
    ))
    await service.crear_usuario(db, persona.id, UsuarioCreate(
        email=email,
        firebase_uid=uid,
    ))
    return RedirectResponse("/", status_code=302)


# ---------------------------------------------------------------------------
# Dashboard (actualizado con más stats)
# ---------------------------------------------------------------------------

@router.get("/")
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    uid, _ = await _get_firebase_uid(request)
    if not uid:
        return _redirect_login()
    user = await service.get_usuario_by_firebase_uid(db, uid)
    if not user:
        return _redirect_registro()
    personas = await service.listar_personas(db)
    resultado = await productos_service.listar_productos(db, page=1, page_size=1)
    pendientes = await delivery_service.listar_pendientes(db)
    billetera = await billetera_service.get_or_create_billetera(db, user.id)
    return templates.TemplateResponse("index.html", _ctx(
        request, user,
        total_personas=len(personas),
        total_productos=resultado["total"],
        total_deliveries=len(pendientes),
        saldo="%.2f" % billetera.saldo,
    ))


# ---------------------------------------------------------------------------
# Personas (web aliases — la API vive en /personas sin prefijo)
# ---------------------------------------------------------------------------

@router.get("/ui/personas")
async def ui_personas_lista(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    personas = await service.listar_personas(db)
    return templates.TemplateResponse(
        "personas/lista.html",
        _ctx(request, user, personas=personas, error=request.query_params.get("error")),
    )


@router.get("/ui/personas/{persona_id}/usuarios")
async def ui_usuarios_lista(
    persona_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    persona = await service.get_persona_by_id(db, persona_id)
    if not persona:
        return RedirectResponse("/ui/personas", status_code=302)
    usuarios = await service.listar_usuarios_de_persona(db, persona_id)
    return templates.TemplateResponse(
        "usuarios/lista.html",
        _ctx(request, user, persona=persona, usuarios=usuarios, error=request.query_params.get("error")),
    )


@router.get("/ui/personas/{persona_id}/direcciones")
async def ui_direcciones_lista(
    persona_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    persona = await service.get_persona_by_id(db, persona_id)
    if not persona:
        return RedirectResponse("/ui/personas", status_code=302)
    direcciones = await service.listar_direcciones_de_persona(db, persona_id)
    return templates.TemplateResponse(
        "direcciones/lista.html",
        _ctx(request, user, persona=persona, direcciones=direcciones),
    )


# ---------------------------------------------------------------------------
# Productos
# ---------------------------------------------------------------------------

@router.get("/ui/productos")
async def ui_productos_lista(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    resultado = await productos_service.listar_productos(db, page=1, page_size=200)
    return templates.TemplateResponse(
        "productos/lista.html",
        _ctx(request, user, productos=resultado["items"], error=request.query_params.get("error")),
    )


@router.get("/ui/productos/nuevo")
async def ui_producto_nuevo_form(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    categorias = await productos_service.listar_categorias(db)
    persona = await service.get_persona_by_id(db, user.persona_id)
    direcciones = await service.listar_direcciones_de_persona(db, user.persona_id) if persona else []
    return templates.TemplateResponse(
        "productos/form.html",
        _ctx(request, user, producto=None, categorias=categorias, direcciones=direcciones, error=None),
    )


@router.post("/ui/productos/nuevo")
async def ui_producto_nuevo_post(
    request: Request,
    nombre: str = Form(...),
    descripcion: str = Form(...),
    precio: float = Form(...),
    stock: int = Form(...),
    sku: str = Form(...),
    categoria_id: uuid.UUID = Form(...),
    direccion_punto_venta_id: uuid.UUID = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    try:
        await productos_service.crear_producto(db, ProductoCreate(
            nombre=nombre, descripcion=descripcion, precio=precio, stock=stock,
            sku=sku, categoria_id=categoria_id,
            direccion_punto_venta_id=direccion_punto_venta_id, imagenes=[],
        ), user)
        return RedirectResponse("/ui/productos", status_code=302)
    except Exception as e:
        categorias = await productos_service.listar_categorias(db)
        direcciones = await service.listar_direcciones_de_persona(db, user.persona_id)
        return templates.TemplateResponse(
            "productos/form.html",
            _ctx(request, user, producto=None, categorias=categorias,
                 direcciones=direcciones, error=str(e)),
            status_code=400,
        )


@router.get("/ui/productos/{producto_id}/editar")
async def ui_producto_editar_form(
    producto_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    producto = await productos_service.get_producto_by_id(db, producto_id)
    if not producto:
        return RedirectResponse("/ui/productos", status_code=302)
    categorias = await productos_service.listar_categorias(db)
    direcciones = await service.listar_direcciones_de_persona(db, user.persona_id)
    return templates.TemplateResponse(
        "productos/form.html",
        _ctx(request, user, producto=producto, categorias=categorias,
             direcciones=direcciones, error=None),
    )


@router.post("/ui/productos/{producto_id}/editar")
async def ui_producto_editar_post(
    producto_id: uuid.UUID,
    request: Request,
    nombre: str = Form(""),
    descripcion: str = Form(""),
    precio: float = Form(None),
    stock: int = Form(None),
    categoria_id: uuid.UUID = Form(None),
    direccion_punto_venta_id: uuid.UUID = Form(None),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    producto = await productos_service.get_producto_by_id(db, producto_id)
    if producto:
        await productos_service.actualizar_producto(db, producto, ProductoUpdate(
            nombre=nombre or None, descripcion=descripcion or None,
            precio=precio, stock=stock,
            categoria_id=categoria_id,
            direccion_punto_venta_id=direccion_punto_venta_id,
        ))
    return RedirectResponse("/ui/productos", status_code=302)


@router.post("/ui/productos/{producto_id}/eliminar")
async def ui_producto_eliminar(
    producto_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    producto = await productos_service.get_producto_by_id(db, producto_id)
    if producto:
        await productos_service.eliminar_producto(db, producto)
    return RedirectResponse("/ui/productos", status_code=302)


# ---------------------------------------------------------------------------
# Búsqueda
# ---------------------------------------------------------------------------

@router.get("/ui/busqueda")
async def ui_busqueda(
    request: Request,
    q: Optional[str] = Query(None),
    categoria_id: Optional[str] = Query(None),
    orden: str = Query("fecha_creacion"),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    categorias = await productos_service.listar_categorias(db)
    cat_uuid = uuid.UUID(categoria_id) if categoria_id else None
    resultado = await productos_service.listar_productos(
        db, page=1, page_size=50, busqueda=q, categoria_id=cat_uuid, orden=orden
    )
    mensaje = request.query_params.get("mensaje")
    return templates.TemplateResponse("busqueda/index.html", _ctx(
        request, user,
        productos=resultado["items"],
        total=resultado["total"],
        categorias=categorias,
        q=q, categoria_id=categoria_id, orden=orden,
        mensaje=mensaje, error=None,
    ))


# ---------------------------------------------------------------------------
# Billetera
# ---------------------------------------------------------------------------

@router.get("/ui/billetera")
async def ui_billetera(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    billetera = await billetera_service.get_or_create_billetera(db, user.id)
    transacciones = await billetera_service.listar_transacciones(db, billetera.id)
    mensaje = request.query_params.get("mensaje")
    return templates.TemplateResponse("billetera/index.html", _ctx(
        request, user, billetera=billetera, transacciones=transacciones,
        mensaje=mensaje, error=None,
    ))


@router.post("/ui/billetera/cargar")
async def ui_billetera_cargar(
    request: Request,
    monto: float = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    billetera = await billetera_service.get_or_create_billetera(db, user.id)
    try:
        await billetera_service.cargar_saldo(db, billetera, monto)
        return RedirectResponse("/ui/billetera?mensaje=Saldo+cargado+correctamente", status_code=302)
    except ValueError as e:
        transacciones = await billetera_service.listar_transacciones(db, billetera.id)
        return templates.TemplateResponse("billetera/index.html", _ctx(
            request, user, billetera=billetera, transacciones=transacciones,
            error=str(e), mensaje=None,
        ), status_code=400)


# ---------------------------------------------------------------------------
# Carrito
# ---------------------------------------------------------------------------

@router.get("/ui/carrito")
async def ui_carrito(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    carrito = await carrito_service.get_or_create_carrito(db, user.id)
    carrito_data = carrito_service.calcular_totales(carrito)
    mensaje = request.query_params.get("mensaje")
    return templates.TemplateResponse("carrito/index.html", _ctx(
        request, user, carrito=carrito_data, mensaje=mensaje, error=None,
    ))


@router.post("/ui/carrito/agregar")
async def ui_carrito_agregar(
    request: Request,
    producto_id: uuid.UUID = Form(...),
    cantidad: int = Form(1),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    try:
        await carrito_service.agregar_item(db, user.id, producto_id, cantidad)
        return RedirectResponse("/ui/busqueda?mensaje=Producto+agregado+al+carrito", status_code=302)
    except ValueError as e:
        return RedirectResponse(f"/ui/busqueda?error={str(e)}", status_code=302)


@router.post("/ui/carrito/items/{producto_id}/eliminar")
async def ui_carrito_eliminar_item(
    producto_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    try:
        await carrito_service.eliminar_item(db, user.id, producto_id)
    except ValueError:
        pass
    return RedirectResponse("/ui/carrito", status_code=302)


@router.post("/ui/carrito/vaciar")
async def ui_carrito_vaciar(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    await carrito_service.vaciar_carrito(db, user.id)
    return RedirectResponse("/ui/carrito", status_code=302)


@router.post("/ui/carrito/checkout")
async def ui_carrito_checkout(
    request: Request,
    direccion_entrega: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    try:
        await carrito_service.checkout(db, user.id, direccion_entrega)
        return RedirectResponse("/ui/deliveries?mensaje=Compra+realizada+con+exito", status_code=302)
    except ValueError as e:
        carrito = await carrito_service.get_or_create_carrito(db, user.id)
        carrito_data = carrito_service.calcular_totales(carrito)
        return templates.TemplateResponse("carrito/index.html", _ctx(
            request, user, carrito=carrito_data, error=str(e), mensaje=None,
        ), status_code=400)


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

@router.get("/ui/deliveries")
async def ui_deliveries(
    request: Request,
    tab: str = Query("pendientes"),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    pendientes = await delivery_service.listar_pendientes(db)
    asignados = await delivery_service.listar_asignados(db, user.id)
    mensaje = request.query_params.get("mensaje")
    return templates.TemplateResponse("deliveries/index.html", _ctx(
        request, user,
        pendientes=pendientes, asignados=asignados,
        tab=tab, mensaje=mensaje, error=None,
    ))


@router.post("/ui/deliveries/{delivery_id}/tomar")
async def ui_delivery_tomar(
    delivery_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    delivery = await delivery_service.get_delivery_by_id(db, delivery_id)
    if delivery:
        try:
            await delivery_service.tomar_delivery(db, delivery, user.id)
        except ValueError:
            pass
    return RedirectResponse("/ui/deliveries?tab=asignados", status_code=302)


@router.post("/ui/deliveries/{delivery_id}/entregar")
async def ui_delivery_entregar(
    delivery_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await _get_web_user(request, db)
    if not user:
        return _redirect_login()
    delivery = await delivery_service.get_delivery_by_id(db, delivery_id)
    if delivery:
        try:
            await delivery_service.entregar(db, delivery, user.id)
        except ValueError:
            pass
    return RedirectResponse("/ui/deliveries?tab=asignados&mensaje=Delivery+marcado+como+entregado", status_code=302)
