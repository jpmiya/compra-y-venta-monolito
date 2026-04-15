
# Especificación Funcional: Sistema Monolítico de Compra y Venta de Productos

## 1. Objetivo y Alcance
**Objetivo:** Desarrollar una aplicación backend que permita comprar, vender y distribuir productos en línea, garantizando seguridad, rapidez y facilidad de uso.
**Alcance:** En esta primera etapa, el sistema contará con un único rol de usuario (`admin/admin`) con capacidad para realizar todas las acciones. Las funcionalidades se dividen en módulos.

---

## 2. Requisitos No Funcionales, Seguridad y Configuración
*   **Autenticación Delegada:** Gestión de identidades, contraseñas, recuperación de cuenta y verificación de email manejadas exclusivamente por **Firebase Authentication** (soporta email/password, Google, etc.).
*   **Seguridad Backend:** No se almacenan contraseñas localmente. El backend valida el token JWT provisto por Firebase en cada solicitud. 
*   **Protección de Datos:** Encriptación de datos sensibles en la base de datos local y **registro de actividades importantes (logs)**. (En etapas futuras se implementará protección por roles).
*   **Archivo de Propiedades:** Sistema configurable mediante parámetros: Conexión a BD, seguridad (intentos de login, tiempo de sesión), billetera (límites, moneda), búsqueda (cantidad máxima de resultados), notificaciones y configuración de Firebase (project ID, API keys).

---

## 3. Módulo de Administración del Sistema
*   **Roles:** Actualmente solo existe el administrador que puede visualizar y operar todo. En el futuro se dividirán en público, vendedor, comprador y entregador.
*   **Entidad Persona:** Individuo real. Datos obligatorios: Nombre completo, Documento de identidad (único), Teléfono, Fecha de registro, Fecha de nacimiento y Estado (activo/inactivo).
*   **Entidad Usuario:** Asociado a una Persona (relación 1:N, una persona puede tener varios usuarios). Datos: Email (id de Firebase), Identificador único de Firebase (UID), Fecha de último acceso y Estado.
*   **Bajas:** Pueden ser físicas o lógicas, **se sugiere de forma lógica**.

---

## 4. Módulo de Vendedor (Gestión de Productos)
*   **Direcciones del vendedor:** Una Persona puede registrar múltiples direcciones (domicilio, local, depósito) que operarán como puntos de venta.
*   **Alta de Productos:** Campos obligatorios: Nombre, Descripción detallada, Categoría (desde catálogo predefinido), Precio, Cantidad en stock, Usuario vendedor (automático) y Dirección del punto de venta (seleccionada de las creadas previamente).
*   **Puesta a la Venta:** Activar productos para hacerlos visibles, establecer condiciones (precio, disponibilidad) y definir la ubicación de despacho.

---

## 5. Módulo de Búsqueda y Visualización
*   **Catálogo:** Listar productos a la venta mostrando Nombre, Precio, Categoría, Imagen (si aplica) y Dirección del punto de venta.
*   **Búsqueda:** Por categoría o palabras clave (que apliquen sobre el nombre o la descripción del producto).
*   **Ordenamiento:** Por relevancia, precio o nombre.

---

## 6. Módulo de Billetera Virtual
*   **Funciones:** Visualizar saldo disponible, agregar saldo (simulación de carga de fondos) y ver historial de transacciones (cargas y compras).

---

## 7. Módulo de Carrito de Compras
*   **Gestión del Carrito:** Visualizar, agregar, modificar cantidades y eliminar productos. Es **persistente** (no tiene fecha de vencimiento).
*   **Flujo de Checkout (Orden estricto):**
    1. Validar stock disponible de cada producto.
    2. Verificar saldo suficiente en la billetera del comprador.
    3. Generar un `deliveryOrder` por cada ítem del carrito.
    4. Vaciar el carrito de compras.
    5. Actualizar/disminuir el stock en el catálogo de Productos.
    6. Descontar el importe total de la billetera del comprador.

---

## 8. Módulo de Delivery / Entregas
*   **Visualización:** El repartidor lista productos pendientes de entrega, detallando dirección del comprador, producto, cantidad y punto de venta (entre otros datos relevantes).
*   **Asignación:** Tomar productos para entregarlos (asignarse como responsable) y visualizar sus asignaciones pendientes.
*   **Gestión:** Marcar como entregados, registrar fecha/hora de la entrega y actualizar el estado de la orden (`deliveryOrder`).

---

## 9. Diagramas de Flujo de Procesos
Para guiar la lógica general del código, seguir estos flujos vitales:
*   **Proceso de Compra:** Usuario busca -> Agrega al carrito -> Revisa carrito -> Realiza checkout -> Sistema valida stock/saldo -> Genera `deliveryOrders` -> Vacía carrito -> Actualiza stock y billetera.
*   **Proceso de Entrega:** Sistema genera `deliveryOrder` -> Entregador visualiza pendientes -> Toma pedido -> Entrega producto -> Sistema actualiza estado.

---

## 10. Requisitos Técnicos, Entregables y Testing
*   **Documentación:** Modelo C4 (que incluya la integración con Firebase), directorio UML y `Readme.md` estructurado.
*   **Código e Infraestructura:** Subir código fuente e imagen Docker a un repositorio en Gitlab **nombrado "...-code"**. Incluir scripts de BD y archivo de propiedades. Requiere un Pipeline de integración.
*   **Testing:** Documentar la API RESTful (Swagger/OpenAPI) y proveer Colección Postman ejecutando los escenarios con el token de Firebase.
