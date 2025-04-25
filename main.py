
import flet as ft
import requests
import json
from datetime import datetime
import asyncio
import httpx
import traceback
import logging
import sys
from icons import Icons
from colors import Colors

# Configuración de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("distriapp_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DistriApp")

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Configuración de la API - Ajusta esta URL según tu servidor
API_URL = "http://localhost:5000/api"

# Decorador para funciones seguras de botones
def safe_button_handler(func):
    def wrapper(e, *args, **kwargs):  
        try:
            logger.info(f"Botón presionado: {func.__name__}")
            return func(e, *args, **kwargs)
        except Exception as ex:
            error_msg = f"Error en {func.__name__}: {str(ex)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            try:
                if hasattr(e, 'page') and e.page:
                    e.page.dialog = ft.AlertDialog(
                        title=ft.Text("Error"),
                        content=ft.Text(error_msg),
                        actions=[
                            ft.TextButton("OK", on_click=lambda _: setattr(e.page.dialog, 'open', False) or e.page.update())
                        ]
                    )
                    e.page.dialog.open = True
                    e.page.update()
            except:
                pass
    return wrapper

class DistriApp:


    def __init__(self, page: ft.Page):
        self.page = page
        self.BASE_URL = API_URL
        logger.info("Iniciando DistriApp...")

        # Intentar conectar con la API
        try:
            logger.info(f"Verificando conexión con API: {self.BASE_URL}/ping")
            response = requests.get(f"{self.BASE_URL}/ping", timeout=3)
            if response.status_code != 200:
                logger.error(f"Error de conexión. Status code: {response.status_code}")
                self.mostrar_error_conexion()
                return
            logger.info("Conexión a API exitosa")
        except Exception as e:
            logger.error(f"❌ Excepción al pinguear la API: {e}")
            self.mostrar_error_conexion()
            return
        
        # Variables de estado
        self.productos_temporal = []
        self.zonas_disponibles = ["Bernal", "Avellaneda #1", "Avellaneda #2", "Quilmes Centro", "Solano"]
        
        # Comprobar la conexión con la API
        try:
            response = requests.get(f"{API_URL}/ping", timeout=3)
            if response.status_code != 200:
                self.mostrar_error_conexion()
                return
        except:
            self.mostrar_error_conexion()
            return
            
        # Construir la interfaz
        self.construir_interfaz()
    
    def mostrar_error_conexion(self):
        logger.error("Mostrando error de conexión")
        self.page.add(
            ft.Column([
                ft.Text("Error de conexión con el servidor", size=20, color=Colors.RED, weight="bold"),
                ft.Text(f"No se pudo conectar a {API_URL}. Verifica que el servidor esté en ejecución."),
                ft.ElevatedButton("Reintentar", on_click=self.reintentar_conexion)
            ], alignment=ft.MainAxisAlignment.CENTER)
        )
        self.page.update()  # Asegurarse de actualizar la UI
    
    @safe_button_handler
    def reintentar_conexion(self, e):
        logger.info("Reintentando conexión...")
        self.page.clean()
        self.page.update()  # Actualizar antes de reiniciar
        self.__init__(self.page)
        
    def construir_interfaz(self):
        # Determinar si es móvil o escritorio
        is_mobile = self.page.width < 600 if self.page.width else True
        logger.info(f"Construyendo interfaz para {'móvil' if is_mobile else 'escritorio'}")
        
        if is_mobile:
            self.construir_interfaz_movil()
        else:
            self.construir_interfaz_escritorio()
            
    ## Conectar con la API y obtener los datos ##
    
    async def buscar_clientes(self, busqueda: str):
        url = f"{self.BASE_URL}/clientes?buscar={busqueda}"
        try:
            logger.debug(f"Buscando clientes con: {busqueda}")
            async with httpx.AsyncClient(timeout=10.0) as client:  # Aumentado a 10 segundos
                response = await client.get(url)
                return response.json()
        except Exception as e:
            logger.error(f"Error buscando clientes: {str(e)}")
            return []

    async def obtener_costo_producto(self, nombre_producto: str) -> float:
        url = f"{self.BASE_URL}/productos/costo/{nombre_producto}"
        try:
            logger.debug(f"Obteniendo costo de: {nombre_producto}")
            async with httpx.AsyncClient(timeout=10.0) as client:  # Timeout aumentado
                response = await client.get(url)
                data = response.json()
                return data.get("costo", 0)
        except Exception as e:
            logger.error(f"Error obteniendo costo del producto: {str(e)}")
            # También podrías actualizar la UI aquí mostrando un error
            return 0
            
    async def buscar_productos(self, busqueda: str):
        url = f"{self.BASE_URL}/productos?buscar={busqueda}"
        logger.debug(f"Intentando conectar a: {url}")  # Mensaje de diagnóstico
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                logger.debug("Cliente HTTP creado, enviando petición...")  # Mensaje de diagnóstico
                response = await client.get(url)
                logger.debug(f"Respuesta recibida con código: {response.status_code}")  # Mensaje de diagnóstico
                return response.json()
        except httpx.ConnectError as e:
            logger.error(f"Error de conexión al intentar conectar con {url}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error inesperado: {str(e)}")
            return []
        
    def on_buscar_cliente_change(self, e):
        logger.debug(f"Buscando cliente con: {e.control.value}")
        asyncio.create_task(self.actualizar_sugerencias_clientes(e.control.value))
    
    # Versiones seguras de los métodos de eventos de botones usando el decorador
    
    @safe_button_handler
    def actualizar_info_productos_seguro(self, e=None):
        return self.actualizar_info_productos(e)
        
    @safe_button_handler
    def sugerir_clientes_seguro(self, e):
        return self.sugerir_clientes(e)
        
    @safe_button_handler
    def sugerir_productos_seguro(self, e):
        return self.sugerir_productos(e)
        
    @safe_button_handler
    def registrar_pedido_seguro(self, e):
        return self.registrar_pedido(e)
    
    @safe_button_handler
    def editar_orden_actual_seguro(self, e):
        return self.editar_orden_actual(e)
        
    @safe_button_handler
    def vaciar_orden_actual_seguro(self, e):
        return self.vaciar_orden_actual(e)
        
    @safe_button_handler
    def guardar_pedido_completo_seguro(self, e):
        return self.guardar_pedido_completo(e)
        
    @safe_button_handler
    def mostrar_file_chooser_seguro(self, e):
        return self.mostrar_file_chooser(e)
        
    @safe_button_handler
    def mostrar_clientes_para_editar_seguro(self, e):
        return self.mostrar_clientes_para_editar(e)
        
    @safe_button_handler
    def mostrar_estadisticas_seguro(self, e):
        return self.mostrar_estadisticas(e)
        
    @safe_button_handler
    def generar_productos_por_dia_seguro(self, e):
        return self.generar_productos_por_dia(e)
        
    @safe_button_handler
    def ver_pedidos_dia_seguro(self, e):
        return self.ver_pedidos_dia(e)
    
    def construir_interfaz_movil(self):
        # Header
        header = ft.Container(
            content=ft.Row([
                ft.Icon(Icons.SHOPPING_CART, size=30, color=Colors.BLUE),
                ft.Text("DistriApp", size=24, weight="bold", color=Colors.BLUE)
            ], alignment=ft.MainAxisAlignment.CENTER),
            padding=10,
            bgcolor=Colors.WHITE,
            border_radius=10,
            border=ft.border.all(1, Colors.BLUE),
            margin=ft.margin.only(bottom=10)
        )
        
        # Panel de formulario
        self.cliente_tf = ft.TextField(
            label="Cliente ✍️",
            border=ft.InputBorder.OUTLINE,
            expand=True,
            on_change=self.sugerir_clientes_seguro,
            prefix_icon=Icons.PERSON
        )
        
        self.producto_tf = ft.TextField(
            label="Producto 🔍",
            border=ft.InputBorder.OUTLINE,
            expand=True,
            on_change=self.sugerir_productos_seguro,
            prefix_icon=Icons.SHOP
        )
        
        # Row para cantidad y costo
        self.cantidad_tf = ft.TextField(
            label="Cantidad 🔢",
            border=ft.InputBorder.OUTLINE,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
            prefix_icon=Icons.PHONE
        )
        
        self.costo_tf = ft.TextField(
            label="Costo 💲",
            border=ft.InputBorder.OUTLINE,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
            prefix_icon=Icons.MONEY
        )
        
        cantidad_costo_row = ft.Row(
            controls=[
                self.cantidad_tf,
                self.costo_tf
            ],
            spacing=10
        )
        
        # Dropdown para zonas
        self.zona_dd = ft.Dropdown(
            label="📍 Zona",
            options=[ft.dropdown.Option(zona) for zona in self.zonas_disponibles],
            width=400,
            expand=True,
            prefix_icon=Icons.FLAG
        )
        
        # Botones principales - Aplicando safe_button_handler
        self.boton_registrar = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.CHECK_CIRCLE),
                ft.Text("Registrar", weight="bold")
            ]),
            on_click=self.registrar_pedido_seguro,  # Usamos la versión segura
            style=ft.ButtonStyle(
                color=Colors.WHITE,
                bgcolor=Colors.GREEN
            ),
            expand=True
        )
        
        self.boton_pedidos_hoy = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.FILTER),
                ft.Text("Pedidos Hoy", weight="bold")
            ]),
            on_click=self.ver_pedidos_dia_seguro,  # Usamos la versión segura
            expand=True
        )
        
        buttons_row1 = ft.Row(
            controls=[
                self.boton_registrar,
                self.boton_pedidos_hoy
            ],
            spacing=10
        )
        
        # Segunda fila de botones - Aplicando safe_button_handler
        self.boton_modificar = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.EDIT),
                ft.Text("Modificar", weight="bold")
            ]),
            on_click=self.mostrar_clientes_para_editar_seguro,  # Usamos la versión segura
            expand=True
        )
        
        self.boton_csv = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.FILE),
                ft.Text("Subir CSV", weight="bold")
            ]),
            on_click=self.mostrar_file_chooser_seguro,  # Usamos la versión segura
            expand=True
        )
        
        buttons_row2 = ft.Row(
            controls=[
                self.boton_modificar,
                self.boton_csv
            ],
            spacing=10
        )
        
        # Tercera fila de botones - Aplicando safe_button_handler
        self.boton_estadisticas = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.FOLDER),
                ft.Text("Estadísticas", weight="bold")
            ]),
            on_click=self.mostrar_estadisticas_seguro,  # Usamos la versión segura
            expand=True
        )
        
        self.boton_productos_dia = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.SHOP),
                ft.Text("PRODUCTOS", weight="bold")
            ]),
            on_click=self.generar_productos_por_dia_seguro,  # Usamos la versión segura
            style=ft.ButtonStyle(
                bgcolor=Colors.RED,
                color=Colors.WHITE
            ),
            expand=True
        )
        
        buttons_row3 = ft.Row(
            controls=[
                self.boton_estadisticas,
                self.boton_productos_dia
            ],
            spacing=10
        )
        
        # Panel de formulario
        form_panel = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    self.cliente_tf,
                    self.producto_tf,
                    cantidad_costo_row,
                    self.zona_dd,
                    buttons_row1,
                    buttons_row2,
                    buttons_row3
                ], spacing=15),
                padding=20
            ),
            elevation=5,
            margin=ft.margin.only(bottom=10),
            expand=1
        )
        
        # Lista de productos
        self.lista_productos = ft.ListView(
            spacing=10,
            padding=10,
            auto_scroll=True,
            expand=True
        )
        
        # Título de la lista
        titulo_lista = ft.Container(
            content=ft.Text(
                value="Productos en pedido actual",
                size=18,
                weight="bold",
                text_align=ft.TextAlign.CENTER
            ),
            padding=10,
            bgcolor=Colors.BLUE,
            border_radius=ft.border_radius.only(
                top_left=10, top_right=10
            )
        )
        
        # Contador de productos e info de total
        self.info_productos = ft.Container(
            content=ft.Row([
                ft.Text("Total: 0 productos", weight="bold"),
                ft.Text("$0.00", weight="bold")
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=10,
            bgcolor=Colors.BLUE,
            border_radius=ft.border_radius.only(
                bottom_left=10, bottom_right=10
            ),
            visible=False
        )
        
        # Botones de control para la orden - Aplicando safe_button_handler
        self.boton_editar = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.EDIT),
                ft.Text("Editar", weight="bold")
            ]),
            on_click=self.editar_orden_actual_seguro,  # Usamos la versión segura
            expand=True
        )
        
        self.boton_vaciar = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.DELETE),
                ft.Text("Vaciar", weight="bold")
            ]),
            on_click=self.vaciar_orden_actual_seguro,  # Usamos la versión segura
            style=ft.ButtonStyle(
                bgcolor=Colors.RED,
                color=Colors.WHITE
            ),
            expand=True
        )
        
        self.boton_enviar = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.MESSAGE),
                ft.Text("Enviar", weight="bold")
            ]),
            on_click=self.guardar_pedido_completo_seguro,  # Usamos la versión segura
            style=ft.ButtonStyle(
                bgcolor=Colors.BLUE,
                color=Colors.WHITE
            ),
            expand=True
        )
        
        control_buttons = ft.Row(
            controls=[
                self.boton_editar,
                self.boton_vaciar,
                self.boton_enviar
            ],
            spacing=10
        )
        
        # Panel de lista
        list_panel = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    titulo_lista,
                    self.lista_productos,
                    self.info_productos,
                    control_buttons
                ], spacing=5),
                padding=ft.padding.only(bottom=20, left=10, right=10)
            ),
            elevation=5,
            expand=1
        )
        
        # Contenedor principal con pestañas
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="Formulario",
                    icon=Icons.BOOKMARK,
                    content=form_panel
                ),
                ft.Tab(
                    text="Productos",
                    icon=Icons.SHOPPING_CART,
                    content=list_panel,
                    on_select=self.actualizar_info_productos_seguro  # Usamos la versión segura
                )
            ],
            expand=True
        )
        
        # Asignar el contenido principal
        self.page.add(header, tabs)
        self.page.update()  # Aseguramos que la interfaz se actualice
        logger.info("Interfaz móvil construida completamente")
        
    def construir_interfaz_escritorio(self):
        # Header
        header = ft.Container(
            content=ft.Row([
                ft.Icon(Icons.SHOPPING_CART, size=30, color=Colors.BLUE),
                ft.Text("DistriApp", size=24, weight="bold", color=Colors.BLUE),
                ft.Container(
                    expand=True
                ),
                ft.Container(
                    content=ft.Row([
                        ft.Text("Fecha: ", weight="bold"),
                        ft.Text(datetime.now().strftime("%d/%m/%Y"))
                    ]),
                    padding=10,
                    bgcolor=Colors.BLUE,
                    border_radius=5
                )
            ]),
            padding=10,
            bgcolor=Colors.WHITE,
            border_radius=10,
            border=ft.border.all(1, Colors.BLUE),
            margin=ft.margin.only(bottom=10)
        )
        
        # Panel izquierdo - Formulario
        self.cliente_tf = ft.TextField(
            label="Cliente ✍️",
            border=ft.InputBorder.OUTLINE,
            width=400,
            on_change=self.sugerir_clientes_seguro,  # Usamos la versión segura
            prefix_icon=Icons.PERSON
        )
        
        self.producto_tf = ft.TextField(
            label="Producto 🔍",
            border=ft.InputBorder.OUTLINE,
            width=400,
            on_change=self.sugerir_productos_seguro,  # Usamos la versión segura
            prefix_icon=Icons.SHOP
        )
        
        self.cantidad_tf = ft.TextField(
            label="Cantidad 🔢",
            border=ft.InputBorder.OUTLINE,
            keyboard_type=ft.KeyboardType.NUMBER,
            width=400,
            prefix_icon=Icons.PHONE
        )
        
        self.costo_tf = ft.TextField(
            label="Costo 💲",
            border=ft.InputBorder.OUTLINE,
            keyboard_type=ft.KeyboardType.NUMBER,
            width=400,
            prefix_icon=Icons.MONEY
        )
        
        # Dropdown para zonas
        self.zona_dd = ft.Dropdown(
            label="📍 Zona",
            options=[ft.dropdown.Option(zona) for zona in self.zonas_disponibles],
            width=400,
            prefix_icon=Icons.FLAG
        )
        
        # Botones principales - Aplicando safe_button_handler
        self.boton_registrar = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.CHECK_CIRCLE),
                ft.Text("Registrar", weight="bold")
            ]),
            on_click=self.registrar_pedido_seguro,  # Usamos la versión segura
            style=ft.ButtonStyle(
                color=Colors.WHITE,
                bgcolor=Colors.GREEN
            ),
            width=195
        )
        
        self.boton_pedidos_hoy = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.FILTER),
                ft.Text("Pedidos Hoy", weight="bold")
            ]),
            on_click=self.ver_pedidos_dia_seguro,  # Usamos la versión segura
            width=195
        )
        
        buttons_row1 = ft.Row([self.boton_registrar, self.boton_pedidos_hoy], spacing=10)
        
        # Segunda fila de botones - Aplicando safe_button_handler
        self.boton_modificar = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.EDIT),
                ft.Text("Modificar", weight="bold")
            ]),
            on_click=self.mostrar_clientes_para_editar_seguro,  # Usamos la versión segura
            width=195
        )
        
        self.boton_csv = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.FILE),
                ft.Text("Subir CSV", weight="bold")
            ]),
            on_click=self.mostrar_file_chooser_seguro,  # Usamos la versión segura
            width=195
        )
        
        buttons_row2 = ft.Row([self.boton_modificar, self.boton_csv], spacing=10)
        
        # Tercera fila de botones - Aplicando safe_button_handler
        self.boton_estadisticas = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.FOLDER),
                ft.Text("Estadísticas", weight="bold")
            ]),
            on_click=self.mostrar_estadisticas_seguro,  # Usamos la versión segura
            width=195
        )
        
        self.boton_productos_dia = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.SHOP),
                ft.Text("PRODUCTOS", weight="bold")
            ]),
            on_click=self.generar_productos_por_dia_seguro,  # Usamos la versión segura
            style=ft.ButtonStyle(
                bgcolor=Colors.RED,
                color=Colors.WHITE
            ),
            width=195
        )
        
        buttons_row3 = ft.Row([self.boton_estadisticas, self.boton_productos_dia], spacing=10)
        
        # Panel izquierdo completo
        left_panel = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    self.cliente_tf,
                    self.producto_tf,
                    self.cantidad_tf,
                    self.costo_tf,
                    self.zona_dd,
                    buttons_row1,
                    buttons_row2,
                    buttons_row3
                ], spacing=15),
                padding=20
            ),
            elevation=5,
            width=440
        )
        
        # Panel derecho - Lista de productos
        # Título de la lista
        titulo_lista = ft.Container(
            content=ft.Text(
                value="Productos en pedido actual",
                size=18,
                weight="bold",
                text_align=ft.TextAlign.CENTER
            ),
            padding=10,
            bgcolor=Colors.BLUE,
            border_radius=ft.border_radius.only(
                top_left=10, top_right=10
            )
        )
        
        self.lista_productos = ft.ListView(
            spacing=10,
            padding=10,
            auto_scroll=True,
            expand=True
        )
        
        # Contador de productos e info de total
        self.info_productos = ft.Container(
            content=ft.Row([
                ft.Text("Total: 0 productos", weight="bold"),
                ft.Text("$0.00", weight="bold")
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=10,
            bgcolor=Colors.BLUE,
            border_radius=ft.border_radius.only(
                bottom_left=10, bottom_right=10
            ),
            visible=False
        )
        
        # Botones de control - Aplicando safe_button_handler
        self.boton_editar = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.EDIT),
                ft.Text("Editar", weight="bold")
            ]),
            on_click=self.editar_orden_actual_seguro,  # Usamos la versión segura
            expand=True
        )
        
        self.boton_vaciar = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.DELETE),
                ft.Text("Vaciar", weight="bold")
            ]),
            on_click=self.vaciar_orden_actual_seguro,  # Usamos la versión segura
            style=ft.ButtonStyle(
                bgcolor=Colors.RED,
                color=Colors.WHITE
            ),
            expand=True
        )
        
        self.boton_enviar = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.MESSAGE),
                ft.Text("Enviar", weight="bold")
            ]),
            on_click=self.guardar_pedido_completo_seguro,  # Usamos la versión segura
            style=ft.ButtonStyle(
                bgcolor=Colors.BLUE,
                color=Colors.WHITE
            ),
            expand=True
        )
        
        control_buttons = ft.Row(
            controls=[
                self.boton_editar,
                self.boton_vaciar,
                self.boton_enviar
            ],
            spacing=10
        )
        
        # Panel derecho completo
        right_panel = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    titulo_lista,
                    self.lista_productos,
                    self.info_productos,
                    control_buttons
                ], spacing=5),
                padding=ft.padding.only(bottom=20, left=10, right=10)
            ),
            elevation=5,
            expand=True
        )
        
        # Organizar en layout principal
        main_row = ft.Row(
            controls=[
                left_panel,
                right_panel
            ],
            spacing=20,
            expand=True
        )
        
        # Añadir a la página
        self.page.add(header, main_row)
        self.page.update()  # Aseguramos que la interfaz se actualice
        logger.info("Interfaz escritorio construida completamente")
    
    # Los métodos originales se mantienen igual
    def actualizar_info_productos(self, e=None):
        """Actualiza la información de resumen de productos"""
        logger.debug("Actualizando info de productos")
        num_productos = len(self.productos_temporal)
        total = sum(p['cantidad'] * p['costo'] for p in self.productos_temporal)
        
        # Actualizar texto
        self.info_productos.content.controls[0].value = f"Total: {num_productos} producto{'s' if num_productos != 1 else ''}"
        self.info_productos.content.controls[1].value = f"${total:.2f}"
        
        # Mostrar u ocultar según haya productos
        self.info_productos.visible = num_productos > 0
        
        # Actualizar la interfaz
        self.info_productos.update()
    
    # --- Funciones para manejar eventos ---
    def sugerir_clientes(self, e):
        logger.debug(f"Sugiriendo clientes para: {e.control.value if e.control.value else 'vacío'}")
        if e.control.value and len(e.control.value) >= 2:
            try:
                logger.debug(f"Consultando API para sugerencias de clientes: {e.control.value}")
                response = requests.get(f"{API_URL}/clientes?buscar={e.control.value}")
                if response.status_code == 200:
                    sugerencias = response.json()
                    logger.debug(f"Sugerencias de clientes recibidas: {len(sugerencias)}")
                    if sugerencias:
                        self.mostrar_sugerencias(sugerencias, self.cliente_tf)
                else:
                    logger.warning(f"Error al buscar clientes: código {response.status_code}")
            except Exception as ex:
                logger.error(f"Error al buscar clientes: {str(ex)}")
                logger.error(traceback.format_exc())
    
    def sugerir_productos(self, e):
        logger.debug(f"Sugiriendo productos para: {e.control.value if e.control.value else 'vacío'}")
        if e.control.value and len(e.control.value) >= 2:
            try:
                logger.debug(f"Consultando API para sugerencias de productos: {e.control.value}")
                response = requests.get(f"{API_URL}/productos?buscar={e.control.value}")
                if response.status_code == 200:
                    sugerencias = response.json()
                    logger.debug(f"Sugerencias de productos recibidas: {len(sugerencias)}")
                    if sugerencias:
                        self.mostrar_sugerencias(sugerencias, self.producto_tf)
                else:
                    logger.warning(f"Error al buscar productos: código {response.status_code}")
            except Exception as ex:
                logger.error(f"Error al buscar productos: {str(ex)}")
                logger.error(traceback.format_exc())
                
    def mostrar_sugerencias(self, sugerencias, campo):
        logger.debug(f"Mostrando {len(sugerencias)} sugerencias para {campo.label}")
        # Contenido del diálogo con mejor estilo
        dlg_content = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Text(f"Seleccione {campo.label.split()[0].lower()}:", weight="bold"),
                    padding=ft.padding.only(bottom=10)
                )
            ] + [
                ft.Container(
                    content=ft.Text(s),
                    padding=10,
                    margin=ft.margin.only(bottom=5),
                    border_radius=5,
                    bgcolor=Colors.BLUE,
                    ink=True,
                    on_click=lambda e, s=s: self.seleccionar_sugerencia(s, campo),
                    data=s  # Almacenar el valor para usarlo en el evento on_click
                ) for s in sugerencias
            ],
            scroll="auto",
            height=min(400, len(sugerencias) * 50 + 60),
            width=300
        )
        
        dlg = ft.AlertDialog(
            content=dlg_content
        )
        
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
    
    def seleccionar_sugerencia(self, texto, campo):
        logger.debug(f"Sugerencia seleccionada: {texto} para campo {campo.label}")
        campo.value = texto
        # Si el campo es producto, llenar automáticamente el costo
        if campo == self.producto_tf:
            try:
                logger.debug(f"Obteniendo costo para producto: {texto}")
                response = requests.get(f"{API_URL}/productos/costo/{texto}")
                if response.status_code == 200:
                    data = response.json()
                    costo = data.get('costo', 0)
                    logger.debug(f"Costo obtenido: {costo}")
                    self.costo_tf.value = str(costo)
                    self.costo_tf.update()
                else:
                    logger.warning(f"Error al obtener costo: código {response.status_code}")
            except Exception as ex:
                logger.error(f"Error al obtener costo del producto: {str(ex)}")
                logger.error(traceback.format_exc())
        campo.update()
        self.cerrar_dialogo()
        
    def mostrar_notificacion(self, mensaje):
        """Muestra una notificación temporal"""
        logger.debug(f"Mostrando notificación: {mensaje}")
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(mensaje),
            action="OK"
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def mostrar_estadisticas(self, e):
        """Muestra estadísticas de ventas"""
        logger.info("Mostrando estadísticas")
        try:
            # Mostrar indicador de carga
            self.mostrar_cargando("Cargando estadísticas...")
            
            # Obtener estadísticas desde la API
            logger.debug("Consultando API para estadísticas")
            response = requests.get(f"{API_URL}/estadisticas")
            
            # Quitar indicador de carga
            self.cerrar_dialogo()
            
            if response.status_code == 200:
                datos = response.json()
                logger.debug("Estadísticas obtenidas correctamente")
                
                # Crear contenido del diálogo
                dlg_content = ft.Column(
                    scroll="auto",
                    height=500,
                    width=550,
                    spacing=15
                )
                
                # Sección - Total de ventas
                ventas_seccion = ft.Container(
                    content=ft.Column([
                        ft.Text("Ventas Totales", size=20, weight="bold"),
                        ft.Divider(),
                        ft.Row([
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("Hoy", weight="bold", text_align=ft.TextAlign.CENTER),
                                    ft.Text(
                                        f"${datos['ventas_hoy']:.2f}",
                                        size=24,
                                        color=Colors.BLUE,
                                        text_align=ft.TextAlign.CENTER
                                    )
                                ]),
                                padding=10,
                                border_radius=10,
                                bgcolor=Colors.BLUE,
                                expand=True
                            ),
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("Esta semana", weight="bold", text_align=ft.TextAlign.CENTER),
                                    ft.Text(
                                        f"${datos['ventas_semana']:.2f}",
                                        size=24,
                                        color=Colors.GREEN,
                                        text_align=ft.TextAlign.CENTER
                                    )
                                ]),
                                padding=10,
                                border_radius=10,
                                bgcolor=Colors.GREEN,
                                expand=True
                            ),
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("Este mes", weight="bold", text_align=ft.TextAlign.CENTER),
                                    ft.Text(
                                        f"${datos['ventas_mes']:.2f}",
                                        size=24,
                                        color=Colors.ORANGE,
                                        text_align=ft.TextAlign.CENTER
                                    )
                                ]),
                                padding=10,
                                border_radius=10,
                                bgcolor=Colors.ORANGE,
                                expand=True
                            )
                        ])
                    ]),
                    padding=15,
                    border_radius=10,
                    bgcolor=Colors.WHITE,
                    border=ft.border.all(1, Colors.BLUE)
                )
                dlg_content.controls.append(ventas_seccion)
                
                # Sección - Productos más vendidos
                productos_seccion = ft.Container(
                    content=ft.Column([
                        ft.Text("Productos Más Vendidos", size=20, weight="bold"),
                        ft.Divider()
                    ]),
                    padding=15,
                    border_radius=10,
                    bgcolor=Colors.WHITE,
                    border=ft.border.all(1, Colors.BLUE)
                )
                
                # Agregar los productos más vendidos
                for producto in datos['productos_top']:
                    producto_item = ft.Row([
                        ft.Icon(Icons.SHOP, color=Colors.BLUE),
                        ft.Text(producto['nombre'], expand=True),
                        ft.Text(f"{producto['cantidad']} uds.", weight="bold")
                    ])
                    productos_seccion.content.controls.append(producto_item)
                
                dlg_content.controls.append(productos_seccion)
                
                # Sección - Zonas más activas
                zonas_seccion = ft.Container(
                    content=ft.Column([
                        ft.Text("Zonas Más Activas", size=20, weight="bold"),
                        ft.Divider()
                    ]),
                    padding=15,
                    border_radius=10,
                    bgcolor=Colors.WHITE,
                    border=ft.border.all(1, Colors.BLUE)
                )
                
                # Agregar las zonas más activas
                for zona in datos['zonas_top']:
                    zona_item = ft.Row([
                        ft.Icon(Icons.LOCATION, color=Colors.RED),
                        ft.Text(zona['nombre'], expand=True),
                        ft.Text(f"${zona['ventas']:.2f}", weight="bold")
                    ])
                    zonas_seccion.content.controls.append(zona_item)
                
                dlg_content.controls.append(zonas_seccion)
                
                # Mostrar el diálogo
                dlg = ft.AlertDialog(
                    title=ft.Text("Estadísticas de Ventas"),
                    content=dlg_content,
                    actions=[
                        ft.TextButton("Cerrar", on_click=lambda _: self.cerrar_dialogo())
                    ],
                    actions_alignment=ft.MainAxisAlignment.END
                )
                
                self.page.dialog = dlg
                dlg.open = True
                self.page.update()
            else:
                logger.error(f"Error al obtener estadísticas: código {response.status_code}")
                self.mostrar_error("❌ Error al obtener estadísticas")
        except Exception as e:
            logger.error(f"Error en mostrar_estadisticas: {str(e)}")
            logger.error(traceback.format_exc())
            self.cerrar_dialogo()
            self.mostrar_error(f"❌ Error: {str(e)}")
    
    def generar_productos_por_dia(self, e):
        """Genera un listado de productos necesarios para el día"""
        logger.info("Generando productos por día")
        try:
            # Mostrar indicador de carga
            self.mostrar_cargando("Generando informe de productos...")
            
            # Obtener los productos desde la API
            logger.debug("Consultando API para productos del día")
            response = requests.get(f"{API_URL}/productos/dia")
            
            # Quitar indicador de carga
            self.cerrar_dialogo()
            
            if response.status_code == 200:
                productos = response.json()
                logger.debug(f"Se obtuvieron {len(productos)} productos para el día")
                
                if not productos:
                    self.mostrar_notificacion("ℹ️ No hay productos para preparar hoy")
                    return
                
                # Crear contenido del diálogo
                dlg_content = ft.Column(
                    scroll="auto",
                    height=500,
                    width=550,
                    spacing=15
                )
                
                # Título informativo con fecha
                fecha_hoy = datetime.now().strftime("%d/%m/%Y")
                dlg_content.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Productos a preparar", size=20, weight="bold", text_align=ft.TextAlign.CENTER),
                            ft.Text(f"Fecha: {fecha_hoy}", text_align=ft.TextAlign.CENTER)
                        ]),
                        padding=10,
                        bgcolor=Colors.RED,
                        border_radius=10
                    )
                )
                
                # Tabla de productos
                tabla = ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Producto", weight="bold")),
                        ft.DataColumn(ft.Text("Cantidad", weight="bold"), numeric=True),
                        ft.DataColumn(ft.Text("Unidad", weight="bold"))
                    ],
                    border=ft.border.all(1, Colors.GREY),
                    vertical_lines=ft.border.BorderSide(1, Colors.GREY),
                    horizontal_lines=ft.border.BorderSide(1, Colors.GREY),
                    heading_row_height=50,
                    data_row_height=50,
                    bgcolor=Colors.WHITE
                )
                
                # Agregar filas a la tabla
                for producto in productos:
                    tabla.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(producto['nombre'])),
                                ft.DataCell(ft.Text(str(producto['cantidad']))),
                                ft.DataCell(ft.Text(producto.get('unidad', 'uds.')))
                            ],
                            color=Colors.BLACK
                        )
                    )
                
                # Contenedor para la tabla con estilo
                tabla_container = ft.Container(
                    content=tabla,
                    border_radius=10,
                    bgcolor=Colors.WHITE,
                    padding=10,
                    border=ft.border.all(1, Colors.GREY)
                )
                
                dlg_content.controls.append(tabla_container)
                
                # Botones de acción
                botones = ft.Row([
                    ft.FilledButton(
                        content=ft.Row([
                            ft.Icon(Icons.SHARE),
                            ft.Text("Generar PDF", weight="bold")
                        ]),
                        style=ft.ButtonStyle(bgcolor=Colors.RED, color=Colors.WHITE),
                        on_click=lambda _: self.generar_pdf_productos_dia(),
                        expand=True
                    ),
                    ft.FilledButton(
                        content=ft.Row([
                            ft.Icon(Icons.PRINT),
                            ft.Text("Imprimir", weight="bold")
                        ]),
                        style=ft.ButtonStyle(bgcolor=Colors.BLUE, color=Colors.WHITE),
                        on_click=lambda _: self.imprimir_productos_dia(),
                        expand=True
                    )
                ], spacing=10)
                
                dlg_content.controls.append(botones)
                
                # Mostrar el diálogo
                dlg = ft.AlertDialog(
                    content=dlg_content,
                    actions=[
                        ft.TextButton("Cerrar", on_click=lambda _: self.cerrar_dialogo())
                    ],
                    actions_alignment=ft.MainAxisAlignment.END
                )
                
                self.page.dialog = dlg
                dlg.open = True
                self.page.update()
            else:
                logger.error(f"Error al obtener productos del día: código {response.status_code}")
                self.mostrar_error("❌ Error al obtener productos del día")
        except Exception as e:
            logger.error(f"Error en generar_productos_por_dia: {str(e)}")
            logger.error(traceback.format_exc())
            self.cerrar_dialogo()
            self.mostrar_error(f"❌ Error: {str(e)}")
    
    @safe_button_handler
    def generar_pdf_productos_dia(self):
        """Genera un PDF con los productos a preparar en el día"""
        logger.info("Generando PDF de productos por día")
        try:
            # Mostrar indicador de carga
            self.mostrar_cargando("Generando PDF...")
            
            # Abrir URL del PDF en una nueva pestaña del navegador
            url_pdf = f"{API_URL}/pdf/productos_dia"
            logger.debug(f"Abriendo URL para PDF de productos: {url_pdf}")
            self.page.launch_url(url_pdf)
            
            # Quitar indicador de carga
            self.cerrar_dialogo()
            
            # Mostrar mensaje
            self.mostrar_notificacion("✅ PDF generado y descargado")
        except Exception as e:
            logger.error(f"Error al generar PDF de productos: {str(e)}")
            logger.error(traceback.format_exc())
            self.cerrar_dialogo()
            self.mostrar_error(f"❌ Error al generar PDF: {str(e)}")
    
    @safe_button_handler
    def imprimir_productos_dia(self):
        """Envía la página a imprimir directamente"""
        logger.info("Enviando a impresión productos del día")
        try:
            # Abrir URL de impresión en una nueva pestaña del navegador
            url_imprimir = f"{API_URL}/imprimir/productos_dia"
            logger.debug(f"Abriendo URL para impresión: {url_imprimir}")
            self.page.launch_url(url_imprimir)
            
            # Mostrar mensaje
            self.mostrar_notificacion("✅ Enviado a impresión")
        except Exception as e:
            logger.error(f"Error al imprimir productos: {str(e)}")
            logger.error(traceback.format_exc())
            self.mostrar_error(f"❌ Error al imprimir: {str(e)}")

    def mostrar_file_chooser(self, e):
        """Mostrar diálogo para entrada de CSV"""
        try:
            logger.info("Abriendo selector de archivos CSV")
            
            # Crear un campo de texto simplificado para pegar el CSV
            texto_csv = ft.TextField(
                label="Pega tu contenido CSV aquí",
                multiline=True,
                min_lines=10,
                max_lines=20,
                border=ft.InputBorder.OUTLINE,
                expand=True
            )
            
            # Crear diálogo simplificado
            dlg = ft.AlertDialog(
                title=ft.Text("Importar CSV"),
                content=ft.Column([
                    ft.Text("Pega tu contenido CSV en el campo de abajo:"),
                    texto_csv
                ], width=400, height=300),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: self.cerrar_dialogo()),
                    ft.ElevatedButton("Procesar", on_click=lambda _: self.procesar_csv_texto(texto_csv.value))
                ]
            )
            
            # Mostrar el diálogo
            self.page.dialog = dlg
            dlg.open = True
            self.page.update()
        except Exception as e:
            logger.error(f"Error al mostrar diálogo CSV: {str(e)}")
            logger.error(traceback.format_exc())
            self.mostrar_error(f"Error al mostrar diálogo: {str(e)}")


        
    def procesar_csv_texto(self, texto_csv):
        if not texto_csv or texto_csv.strip() == "":
            self.mostrar_notificacion("No has ingresado ningún dato CSV")
            return
        
        # Cerrar diálogo
        self.cerrar_dialogo()
        
        # Mostrar indicador de carga
        self.mostrar_cargando("Procesando CSV...")
        
        # Enviar los datos a la API
        try:
            response = requests.post(
                f"{API_URL}/productos/csv", 
                json={"datos_csv": texto_csv}
            )
            
            # Cerrar el indicador de carga
            self.cerrar_dialogo()
            
            if response.status_code == 200:
                self.mostrar_notificacion("CSV procesado correctamente")
            else:
                self.mostrar_error(f"Error al procesar CSV: {response.json().get('error', 'Error desconocido')}")
        except Exception as e:
            self.cerrar_dialogo()
            self.mostrar_error(f"Error al procesar CSV: {str(e)}")
            # Función que maneja el procesamiento del CSV
            @safe_button_handler
            def procesar_csv(e):
                try:
                    # Obtener el texto del campo
                    datos_csv = texto_csv.value
                    
                    # Verificar que no esté vacío
                    if not datos_csv or datos_csv.strip() == "":
                        logger.warning("Intento de procesar CSV vacío")
                        self.mostrar_notificacion("⚠️ No has ingresado ningún dato CSV")
                        return
                    
                    logger.debug(f"Procesando CSV de {len(datos_csv.splitlines())} líneas")
                    
                    # Cerrar diálogo actual
                    self.cerrar_dialogo()
                    
                    # Mostrar diálogo de carga
                    self.mostrar_cargando("Procesando datos CSV...")
                    
                    # Enviar los datos a la API
                    logger.debug("Enviando datos CSV a la API")
                    response = requests.post(
                        f"{API_URL}/productos/csv", 
                        json={"datos_csv": datos_csv}
                    )
                    
                    # Cerrar diálogo de carga
                    self.cerrar_dialogo()
                    
                    # Verificar si la petición fue exitosa
                    if response.status_code == 200:
                        # Mostrar mensaje de éxito
                        logger.info("CSV procesado correctamente")
                        self.mostrar_exito("CSV procesado correctamente", 
                                       "Los productos han sido actualizados en el sistema.")
                    else:
                        # Intenta obtener el mensaje de error
                        try:
                            error_msg = response.json().get('error', 'Error desconocido')
                        except:
                            error_msg = f"Error de servidor (código {response.status_code})"
                        
                        logger.error(f"Error al procesar CSV: {error_msg}")
                        self.mostrar_error(f"Error al procesar CSV: {error_msg}")
                
                except Exception as ex:
                    self.cerrar_dialogo()  # Asegurarse de cerrar el diálogo de carga
                    logger.error(f"Excepción al procesar CSV: {str(ex)}")
                    logger.error(traceback.format_exc())
                    self.mostrar_error(f"Error al procesar CSV: {str(ex)}")
            
            # Crear diálogo
            dlg = ft.AlertDialog(
                title=ft.Text("Importar productos desde CSV"),
                content=ft.Column([
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Formato esperado:", weight="bold"),
                            ft.Text("nombre,costo,precio_venta,stock")
                        ]),
                        padding=10,
                        bgcolor=Colors.BLUE,
                        border_radius=5,
                        margin=ft.margin.only(bottom=10)
                    ),
                    ft.Row([
                        ft.Text("Ejemplo:", weight="bold"),
                        ft.TextButton(
                            "Cargar ejemplo",
                            on_click=lambda _: setattr(texto_csv, 'value', ejemplo_csv) or texto_csv.update()
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    texto_csv
                ], width=500),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: self.cerrar_dialogo()),
                    ft.FilledButton(
                        "Procesar CSV", 
                        icon=Icons.FILE,
                        on_click=procesar_csv
                    )
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )
            
            # Mostrar el diálogo
            self.page.dialog = dlg
            dlg.open = True
            self.page.update()
        except Exception as e:
            logger.error(f"Error al mostrar diálogo CSV: {str(e)}")
            logger.error(traceback.format_exc())
            self.mostrar_error(f"Error al mostrar diálogo: {str(e)}")
    
    def ver_pedidos_dia(self, e):
        """Muestra los pedidos del día actual"""
        logger.info("Obteniendo pedidos del día")
        try:
            # Mostrar indicador de carga
            self.mostrar_cargando("Cargando pedidos...")
            
            # Obtener los pedidos desde la API
            logger.debug("Consultando API para pedidos de hoy")
            response = requests.get(f"{API_URL}/pedidos/hoy")
            
            # Quitar indicador de carga
            self.cerrar_dialogo()
            
            if response.status_code == 200:
                clientes = response.json()
                logger.debug(f"Se obtuvieron {len(clientes)} clientes con pedidos hoy")
                
                if not clientes:
                    self.mostrar_notificacion("📄 No hay pedidos registrados hoy.")
                    return
                
                # Crear la ventana de diálogo con los clientes
                dlg_content = ft.Column(
                    scroll="auto",
                    height=400,
                    width=400,
                    spacing=10
                )
                
                # Título informativo
                dlg_content.controls.append(
                    ft.Container(
                        content=ft.Text("Seleccione un cliente para ver detalles:", weight="bold"),
                        padding=ft.padding.only(bottom=10)
                    )
                )
                
                # Lista de clientes
                for cliente in clientes:
                    btn = ft.Container(
                        content=ft.Row([
                            ft.Icon(Icons.PERSON, color=Colors.BLUE),
                            ft.Text(cliente, size=16)
                        ]),
                        padding=10,
                        border_radius=5,
                        bgcolor=Colors.BLUE,
                        ink=True,
                        on_click=lambda _, c=cliente: self.mostrar_detalle_cliente(c)
                    )
                    dlg_content.controls.append(btn)
                
                # Botón para descargar todos los PDFs
                dlg_content.controls.append(
                    ft.FilledButton(
                        content=ft.Row([
                            ft.Icon(Icons.SHARE),
                            ft.Text("Generar PDFs para todos", weight="bold")
                        ]),
                        width=400,
                        on_click=lambda _: self.generar_pdf_todos_clientes(clientes)
                    )
                )
                
                # Mostrar el diálogo
                dlg = ft.AlertDialog(
                    title=ft.Text("Pedidos del día"),
                    content=dlg_content,
                    actions=[
                        ft.TextButton("Cerrar", on_click=lambda _: self.cerrar_dialogo())
                    ],
                    actions_alignment=ft.MainAxisAlignment.END
                )
                
                self.page.dialog = dlg
                dlg.open = True
                self.page.update()
            else:
                logger.error(f"Error al obtener pedidos: código {response.status_code}")
                self.mostrar_error("❌ Error al obtener pedidos")
        except Exception as e:
            logger.error(f"Error en ver_pedidos_dia: {str(e)}")
            logger.error(traceback.format_exc())
            self.cerrar_dialogo()
            self.mostrar_error(f"❌ Error: {str(e)}")
    
    def cerrar_dialogo(self, e=None):
        """Cierra cualquier diálogo abierto"""
        logger.debug("Cerrando diálogo")
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()
    
    @safe_button_handler
    def mostrar_detalle_cliente(self, cliente):
        """Muestra los detalles de los pedidos de un cliente"""
        logger.info(f"Mostrando detalles del cliente: {cliente}")
        try:
            # Cerrar diálogo anterior
            self.cerrar_dialogo()
            
            # Mostrar indicador de carga
            self.mostrar_cargando(f"Cargando pedidos de {cliente}...")
            
            # Obtener los pedidos desde la API
            logger.debug(f"Consultando API para pedidos de cliente: {cliente}")
            response = requests.get(f"{API_URL}/pedidos/cliente/{cliente}")
            
            # Quitar indicador de carga
            self.cerrar_dialogo()
            
            if response.status_code == 200:
                pedidos = response.json()
                logger.debug(f"Se obtuvieron {len(pedidos)} pedidos para el cliente {cliente}")
                
                if not pedidos:
                    self.mostrar_notificacion(f"No hay pedidos para {cliente} en la fecha actual")
                    return
                
                # Crear contenido del diálogo
                dlg_content = ft.Column(
                    scroll="auto",
                    height=400,
                    width=500,
                    spacing=10
                )
                
                total_general = 0
                
                for pedido in pedidos:
                    producto = pedido['producto']
                    cantidad = pedido['cantidad']
                    costo = pedido['costo']
                    zona = pedido['zona']
                    
                    total = cantidad * costo
                    total_general += total
                    
                    item = ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Icon(Icons.SHOP, color=Colors.BLUE),
                                    ft.Text(producto, weight="bold", size=16, expand=True)
                                ]),
                                ft.Container(
                                    content=ft.Column([
                                        ft.Row([
                                            ft.Text("Cantidad:", weight="bold"),
                                            ft.Text(str(cantidad))
                                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                        ft.Row([
                                            ft.Text("Precio unitario:", weight="bold"),
                                            ft.Text(f"${costo:.2f}")
                                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                        ft.Row([
                                            ft.Text("Total:", weight="bold"),
                                            ft.Text(f"${total:.2f}")
                                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                        ft.Row([
                                            ft.Text("Zona:", weight="bold"),
                                            ft.Text(zona)
                                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                                    ]),
                                    margin=ft.margin.only(top=5),
                                    padding=10,
                                    bgcolor=Colors.BLUE,
                                    border_radius=5
                                )
                            ]),
                            padding=10
                        ),
                        elevation=3,
                        margin=ft.margin.only(bottom=5)
                    )
                    dlg_content.controls.append(item)
                
                # Agregar el total
                total_item = ft.Container(
                    content=ft.Row([
                        ft.Text("TOTAL GENERAL:", weight="bold", size=16),
                        ft.Text(f"${total_general:.2f}", weight="bold", size=16, color=Colors.RED)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=15,
                    bgcolor=Colors.BLUE,
                    border_radius=10
                )
                dlg_content.controls.append(total_item)
                
                # Mostrar el diálogo
                dlg = ft.AlertDialog(
                    title=ft.Text(f"Detalle de pedidos - {cliente}"),
                    content=dlg_content,
                    actions=[
                        ft.FilledButton(
                            "Generar PDF",
                            icon=Icons.SHARE,
                            on_click=lambda e, c=cliente: self.generar_pdf_cliente(c)
                        ),
                        ft.TextButton("Cerrar", on_click=lambda e: self.cerrar_dialogo())
                    ],
                    actions_alignment=ft.MainAxisAlignment.END
                )
                
                self.page.dialog = dlg
                dlg.open = True
                self.page.update()
            else:
                logger.error(f"Error al obtener detalles del cliente: código {response.status_code}")
                self.mostrar_error(f"❌ Error al obtener detalles del cliente: {response.json().get('error', 'Error desconocido')}")
        except Exception as e:
            logger.error(f"Error en mostrar_detalle_cliente: {str(e)}")
            logger.error(traceback.format_exc())
            self.cerrar_dialogo()
            self.mostrar_error(f"❌ Error: {str(e)}")
    
    def registrar_pedido(self, e):
        try:
            logger.info("Función registrar_pedido llamada")
            
            # Validar campos
            cliente = self.cliente_tf.value.strip() if self.cliente_tf.value else "Error cliente"
            producto = self.producto_tf.value.strip() if self.producto_tf.value else "Error en producto"
            cantidad_str = self.cantidad_tf.value.strip() if self.cantidad_tf.value else "Error en cantidad"
            costo_str = self.costo_tf.value.strip() if self.costo_tf.value else "Error en costo"
            zona = self.zona_dd.value if self.zona_dd.value else "Error en la zona"
            
            logger.debug(f"Datos para registrar: Cliente={cliente}, Producto={producto}, Cantidad={cantidad_str}, Costo={costo_str}, Zona={zona}")
            
            # Validar que todos los campos estén llenos
            if not all([cliente, producto, cantidad_str, costo_str, zona]):
                logger.warning("Campos incompletos al registrar pedido")
                self.mostrar_error("⚠️ Todos los campos son obligatorios.")
                return
            
            # Convertir valores a tipos apropiados con validación
            try:
                cantidad_int = int(cantidad_str)
                if cantidad_int <= 0:
                    logger.warning(f"Cantidad inválida: {cantidad_int}")
                    self.mostrar_error("⚠️ La cantidad debe ser mayor a cero.")
                    return
            except ValueError:
                logger.warning(f"Error al convertir cantidad: {cantidad_str}")
                self.mostrar_error("⚠️ La cantidad debe ser un número entero válido.")
                return
            
            try:
                costo_float = float(costo_str)
                if costo_float <= 0:
                    logger.warning(f"Costo inválido: {costo_float}")
                    self.mostrar_error("⚠️ El costo debe ser mayor a cero.")
                    return
            except ValueError:
                logger.warning(f"Error al convertir costo: {costo_str}")
                self.mostrar_error("⚠️ El costo debe ser un número válido.")
                return
            
            # Verificar stock disponible
            try:
                logger.debug(f"Verificando stock para producto: {producto}")
                response = requests.get(f"{API_URL}/productos/stock/{producto}")
                
                if response.status_code == 200:
                    data = response.json()
                    stock_actual = data.get('stock', 0)
                    logger.debug(f"Stock disponible: {stock_actual}")
                    if stock_actual < cantidad_int:
                        logger.warning(f"Stock insuficiente. Pedido: {cantidad_int}, Disponible: {stock_actual}")
                        self.mostrar_error(f"⚠️ Stock insuficiente. Disponible: {stock_actual}")
                        return
                else:
                    logger.error(f"Error al verificar stock. Código: {response.status_code}")
                    self.mostrar_error("❌ Error al verificar stock. Inténtelo nuevamente.")
                    return
            except Exception as ex:
                logger.error(f"Error al verificar stock: {str(ex)}")
                logger.error(traceback.format_exc())
                self.mostrar_error("❌ Error de conexión al verificar stock.")
                return
            
            # Agregar a lista temporal
            self.productos_temporal.append({
                'producto': producto,
                'cantidad': cantidad_int,
                'costo': costo_float,
                'zona': zona
            })
            logger.info(f"Producto agregado a la lista temporal. Total productos: {len(self.productos_temporal)}")
            
            # Actualizar la lista visual
            self.actualizar_lista_temporal()
            
            # Limpiar campos excepto cliente y zona
            self.producto_tf.value = ""
            self.cantidad_tf.value = ""
            self.costo_tf.value = ""
            self.producto_tf.update()
            self.cantidad_tf.update()
            self.costo_tf.update()
            
            # Actualizar información de resumen
            self.actualizar_info_productos()
            
            # Mostrar notificación
            self.mostrar_notificacion("✅ Producto agregado al pedido")
            
        except Exception as ex:
            logger.error(f"Error no controlado en registrar_pedido: {str(ex)}")
            logger.error(traceback.format_exc())
            self.mostrar_error(f"❌ Error: {str(ex)}")
    
    def mostrar_error(self, mensaje):
        """Muestra un mensaje de error al usuario"""
        logger.debug(f"Mostrando error: {mensaje}")
        dlg = ft.AlertDialog(
            title=ft.Text("Error"),
            content=ft.Text(mensaje),
            actions=[
                ft.TextButton("Aceptar", on_click=lambda e: self.cerrar_dialogo())
            ]
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
            
    def actualizar_lista_temporal(self):
        logger.debug(f"Actualizando lista temporal. Productos: {len(self.productos_temporal)}")
        # Limpiar lista actual
        self.lista_productos.controls.clear()
        
        # Añadir cada producto a la lista
        for producto in self.productos_temporal:
            total_item = producto['cantidad'] * producto['costo']
            
            item = ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(Icons.SHOP, color=Colors.BLUE),
                            ft.Text(
                                value=producto['producto'],
                                size=16,
                                weight="bold",
                                expand=True
                            ),
                            ft.IconButton(
                                icon=Icons.DELETE,
                                icon_color=Colors.RED,
                                tooltip="Eliminar",
                                on_click=lambda e, p=producto: self.eliminar_de_orden_actual(p)
                            )
                        ]),
                        ft.Container(
                            content=ft.Row([
                                ft.Text(f"Cantidad: {producto['cantidad']}", size=14),
                                ft.Text(f"Precio: ${producto['costo']:.2f}", size=14),
                                ft.Text(f"Total: ${total_item:.2f}", weight="bold", size=14)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            margin=ft.margin.only(top=5),
                            padding=10,
                            bgcolor=Colors.BLUE,
                            border_radius=5
                        )
                    ]),
                    padding=10
                ),
                elevation=3,
                margin=ft.margin.only(bottom=5)
            )
            self.lista_productos.controls.append(item)
        
        # Actualizar la interfaz
        self.lista_productos.update()
    
    def eliminar_de_orden_actual(self, producto, e=None):
        """Eliminar un producto de la orden actual con confirmación"""
        logger.debug(f"Solicitando eliminar producto: {producto['producto']}")
        
        @safe_button_handler
        def confirmar_eliminar(e):
            logger.info(f"Eliminando producto: {producto['producto']}")
            self.productos_temporal.remove(producto)
            self.actualizar_lista_temporal()
            self.actualizar_info_productos()
            self.cerrar_dialogo()
            self.mostrar_notificacion("✅ Producto eliminado de la orden")
        
        # Mostrar diálogo de confirmación
        dlg = ft.AlertDialog(
            title=ft.Text("Confirmar eliminación"),
            content=ft.Text(f"¿Está seguro de que desea eliminar '{producto['producto']}' de la orden?"),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: self.cerrar_dialogo()),
                ft.ElevatedButton(
                    "Eliminar",
                    style=ft.ButtonStyle(color=Colors.WHITE, bgcolor=Colors.RED),
                    on_click=confirmar_eliminar
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
    
    def guardar_pedido_completo(self, e):
        logger.info("Iniciando guardar_pedido_completo")
        try:
            if not self.productos_temporal:
                logger.warning("Intento de guardar orden sin productos")
                self.mostrar_error("⚠️ No hay productos en la orden")
                return
                
            cliente = self.cliente_tf.value.strip() if self.cliente_tf.value else ""
            zona = self.zona_dd.value if self.zona_dd.value else ""
            
            logger.debug(f"Datos para guardar pedido: Cliente={cliente}, Zona={zona}, Productos={len(self.productos_temporal)}")
            
            if not cliente:
                logger.warning("Intento de guardar orden sin cliente")
                self.mostrar_error("⚠️ Debe seleccionar un cliente")
                return
            
            if not zona:
                logger.warning("Intento de guardar orden sin zona")
                self.mostrar_error("⚠️ Debe seleccionar una zona")
                return
            
            # Mostrar diálogo de confirmación
            total_productos = len(self.productos_temporal)
            total_monto = sum(p['cantidad'] * p['costo'] for p in self.productos_temporal)
            
            dlg = ft.AlertDialog(
                title=ft.Text("Confirmar envío de pedido"),
                content=ft.Column([
                    ft.Text("¿Está seguro de que desea enviar este pedido?"),
                    ft.Container(
                        content=ft.Column([
                            ft.Text(f"Cliente: {cliente}", weight="bold"),
                            ft.Text(f"Zona: {zona}"),
                            ft.Text(f"Total productos: {total_productos}"),
                            ft.Text(f"Monto total: ${total_monto:.2f}", weight="bold")
                        ]),
                        margin=ft.margin.symmetric(vertical=10),
                        padding=10,
                        bgcolor=Colors.BLUE,
                        border_radius=5
                    )
                ]),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: self.cerrar_dialogo()),
                    ft.ElevatedButton(
                        "Confirmar y enviar",
                        style=ft.ButtonStyle(color=Colors.WHITE, bgcolor=Colors.GREEN),
                        on_click=lambda e: self.procesar_envio_pedido(cliente, zona)
                    )
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )
            
            self.page.dialog = dlg
            dlg.open = True
            self.page.update()
            
        except Exception as e:
            logger.error(f"Error en guardar_pedido_completo: {str(e)}")
            logger.error(traceback.format_exc())
            self.mostrar_error(f"❌ Error al preparar el pedido: {str(e)}")
    
    @safe_button_handler
    def procesar_envio_pedido(self, cliente, zona):
        """Procesa el envío del pedido a la API"""
        logger.info(f"Procesando envío de pedido para: {cliente}, zona: {zona}")
        self.cerrar_dialogo()
        self.mostrar_cargando("Enviando pedido al servidor...")
        
        try:
            exito = True
            errores = []
            
            for i, producto in enumerate(self.productos_temporal):
                # Enviar cada pedido a la API
                data = {
                    'cliente': cliente,
                    'producto': producto['producto'],
                    'cantidad': producto['cantidad'],
                    'costo': producto['costo'],
                    'zona': zona
                }
                
                logger.debug(f"Enviando producto {i+1}/{len(self.productos_temporal)}: {producto['producto']}")
                response = requests.post(f"{API_URL}/pedidos", json=data)
                if response.status_code != 200:
                    exito = False
                    error_msg = response.json().get('error', 'Error desconocido')
                    errores.append(f"Error con producto '{producto['producto']}': {error_msg}")
                    logger.error(f"Error al guardar producto {producto['producto']}: {error_msg}")
            
            self.cerrar_dialogo()
            
            if exito:
                # Mostrar mensaje de éxito con animación
                logger.info("Pedido guardado exitosamente")
                self.mostrar_exito("¡Pedido guardado exitosamente! 🎉", 
                                   f"Se han registrado {len(self.productos_temporal)} productos para {cliente}.")
                # Vaciar la orden actual
                self.productos_temporal.clear()
                self.actualizar_lista_temporal()
                self.actualizar_info_productos()
            else:
                # Mostrar errores
                error_texto = "\n• ".join(errores)
                logger.error(f"Errores al guardar pedido: {error_texto}")
                self.mostrar_error(f"❌ Errores al guardar el pedido:\n• {error_texto}")
                
        except Exception as e:
            logger.error(f"Error en procesar_envio_pedido: {str(e)}")
            logger.error(traceback.format_exc())
            self.cerrar_dialogo()
            self.mostrar_error(f"❌ Error al guardar: {str(e)}")
    
    def mostrar_cargando(self, mensaje="Cargando..."):
        """Muestra un indicador de carga con mensaje"""
        logger.debug(f"Mostrando indicador de carga: {mensaje}")
        dlg = ft.AlertDialog(
            content=ft.Column([
                ft.ProgressRing(),
                ft.Text(mensaje, text_align=ft.TextAlign.CENTER)
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
            modal=True
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
    
    def mostrar_exito(self, titulo, mensaje):
        """Muestra un mensaje de éxito con animación"""
        logger.debug(f"Mostrando mensaje de éxito: {titulo}")
        dlg = ft.AlertDialog(
            title=ft.Text(titulo),
            content=ft.Column([
                ft.Container(
                    content=ft.Icon(
                        Icons.CHECK_CIRCLE,
                        color=Colors.GREEN,
                        size=64
                    ),
                    alignment=ft.alignment.center
                ),
                ft.Text(mensaje, text_align=ft.TextAlign.CENTER)
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
            actions=[
                ft.TextButton("Aceptar", on_click=lambda e: self.cerrar_dialogo())
            ],
            actions_alignment=ft.MainAxisAlignment.CENTER
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
    
    def editar_orden_actual(self, e):
        logger.info("Iniciando edición de orden actual")
        if not self.productos_temporal:
            logger.warning("Intento de editar orden sin productos")
            self.mostrar_notificacion("⚠️ No hay productos en la orden actual")
            return
        
        # Crear contenido para el diálogo de edición
        dlg_content = ft.Column(
            scroll="auto",
            height=400,
            width=400,
            spacing=10
        )
        
        for i, producto in enumerate(self.productos_temporal):
            # Crear controles para editar el producto
            cantidad_tf = ft.TextField(
                label="Cantidad",
                value=str(producto['cantidad']),
                border=ft.InputBorder.OUTLINE,
                width=100,
                keyboard_type=ft.KeyboardType.NUMBER
            )
            
            costo_tf = ft.TextField(
                label="Costo",
                value=str(producto['costo']),
                border=ft.InputBorder.OUTLINE,
                width=100,
                keyboard_type=ft.KeyboardType.NUMBER
            )
            
            # Crear un card para el producto
            item = ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(Icons.SHOP, color=Colors.BLUE),
                            ft.Text(producto['producto'], weight="bold", size=16, expand=True)
                        ]),
                        ft.Row([
                            cantidad_tf,
                            costo_tf
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([
                            ft.OutlinedButton(
                                "Eliminar",
                                icon=Icons.DELETE,
                                on_click=lambda e, idx=i: self.eliminar_en_edicion(idx, dlg_content)
                            ),
                            ft.FilledButton(
                                "Actualizar",
                                icon=Icons.FLAG,
                                on_click=lambda e, idx=i, c=cantidad_tf, p=costo_tf: self.actualizar_en_edicion(idx, c, p, dlg_content)
                            )
                        ], alignment=ft.MainAxisAlignment.END)
                    ]),
                    padding=10
                ),
                elevation=3,
                margin=ft.margin.only(bottom=5)
            )
            
            dlg_content.controls.append(item)
        
        # Crear diálogo
        dlg = ft.AlertDialog(
            title=ft.Text("Editar productos en la orden"),
            content=dlg_content,
            actions=[
                ft.TextButton("Cerrar", on_click=lambda e: self.cerrar_dialogo())
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        # Mostrar diálogo
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
    
    @safe_button_handler
    def eliminar_en_edicion(self, indice, contenedor):
        """Elimina un producto desde el diálogo de edición"""
        logger.info(f"Eliminando producto en índice {indice} desde diálogo de edición")
        if 0 <= indice < len(self.productos_temporal):
            # Eliminar de la lista temporal
            producto = self.productos_temporal.pop(indice)
            
            # Eliminar de la interfaz visual
            if 0 <= indice < len(contenedor.controls):
                contenedor.controls.pop(indice)
                contenedor.update()
            
            # Actualizar la lista principal
            self.actualizar_lista_temporal()
            self.actualizar_info_productos()
            
            # Mostrar notificación
            self.mostrar_notificacion(f"Producto '{producto['producto']}' eliminado")
    
    @safe_button_handler
    def actualizar_en_edicion(self, indice, campo_cantidad, campo_costo, contenedor):
        """Actualiza un producto desde el diálogo de edición"""
        logger.info(f"Actualizando producto en índice {indice} desde diálogo de edición")
        if 0 <= indice < len(self.productos_temporal):
            try:
                # Obtener nuevos valores
                nueva_cantidad = int(campo_cantidad.value)
                nuevo_costo = float(campo_costo.value)
                
                # Validar valores
                if nueva_cantidad <= 0 or nuevo_costo <= 0:
                    logger.warning(f"Valores inválidos para actualización: cantidad={nueva_cantidad}, costo={nuevo_costo}")
                    self.mostrar_notificacion("⚠️ Los valores deben ser mayores a cero")
                    return
                
                # Actualizar producto
                producto_actual = self.productos_temporal[indice]['producto']
                logger.debug(f"Actualizando producto '{producto_actual}': cantidad={nueva_cantidad}, costo={nuevo_costo}")
                self.productos_temporal[indice]['cantidad'] = nueva_cantidad
                self.productos_temporal[indice]['costo'] = nuevo_costo
                
                # Actualizar la lista principal
                self.actualizar_lista_temporal()
                self.actualizar_info_productos()
                
                # Mostrar notificación
                self.mostrar_notificacion("✅ Producto actualizado correctamente")
                
            except ValueError:
                logger.warning(f"Error al convertir valores: cantidad={campo_cantidad.value}, costo={campo_costo.value}")
                self.mostrar_notificacion("⚠️ Valores inválidos. Verifique que sean números")
                
    @safe_button_handler
    def abrir_edicion_cliente(self, cliente):
            """Abre la ventana de edición de pedidos para un cliente específico"""
            logger.info(f"Abriendo edición para cliente: {cliente}")
            try:
                # Cerrar diálogo anterior
                self.cerrar_dialogo()
                
                # Mostrar indicador de carga
                self.mostrar_cargando(f"Cargando pedidos de {cliente}...")
                
                # Obtener los pedidos desde la API
                logger.debug(f"Consultando API para pedidos de cliente: {cliente}")
                response = requests.get(f"{API_URL}/pedidos/cliente/{cliente}")
                
                # Quitar indicador de carga
                self.cerrar_dialogo()
                
                if response.status_code == 200:
                    pedidos = response.json()
                    logger.debug(f"Se obtuvieron {len(pedidos)} pedidos para editar")
                    
                    if not pedidos:
                        self.mostrar_notificacion(f"No hay pedidos para {cliente} en la fecha actual")
                        return
                    
                    # Crear contenido del diálogo de edición
                    dlg_content = ft.Column(
                        scroll="auto",
                        height=500,
                        width=550,
                        spacing=15
                    )
                    
                    # Lista de controles de entrada para actualizar
                    self.edicion_pedidos = []
                    self.cliente_actual_edicion = cliente
                    
                    for pedido in pedidos:
                        id_pedido = pedido['id']
                        producto = pedido['producto']
                        cantidad = pedido['cantidad']
                        costo = pedido['costo']
                        zona = pedido['zona']
                        

                        cantidad_tf = ft.TextField(
                            label="Cantidad",
                            value=str(cantidad),
                            border=ft.InputBorder.OUTLINE,
                            width=100,
                            keyboard_type=ft.KeyboardType.NUMBER
                        )
                        
                        costo_tf = ft.TextField(
                            label="Costo",
                            value=str(costo),
                            border=ft.InputBorder.OUTLINE,
                            width=100,
                            keyboard_type=ft.KeyboardType.NUMBER
                        )
                        
                        zona_dd = ft.Dropdown(
                            label="Zona",
                            options=[ft.dropdown.Option(z) for z in self.zonas_disponibles],
                            value=zona,
                            width=200
                        )
                        
                        # Guardar referencia a los controles para actualización posterior
                        self.edicion_pedidos.append({
                            'id': id_pedido,
                            'producto': producto,
                            'cantidad_tf': cantidad_tf,
                            'costo_tf': costo_tf,
                            'zona_dd': zona_dd
                        })
                        
                        # Crear tarjeta para el pedido
                        item = ft.Card(
                            content=ft.Container(
                                content=ft.Column([
                                    ft.Row([
                                        ft.Icon(Icons.SHOP, color=Colors.BLUE),
                                        ft.Text(producto, weight="bold", size=16, expand=True),
                                        ft.IconButton(
                                            icon=Icons.DELETE,
                                            icon_color=Colors.RED,
                                            tooltip="Eliminar",
                                            on_click=lambda _, pid=id_pedido: self.eliminar_pedido(pid)
                                        )
                                    ]),
                                    ft.Row([
                                        cantidad_tf,
                                        costo_tf
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ft.Row([
                                        zona_dd
                                    ]),
                                    ft.FilledButton(
                                        "Actualizar",
                                        icon=Icons.VISIBILITY,
                                        on_click=lambda _, pid=id_pedido, idx=len(self.edicion_pedidos)-1: self.actualizar_pedido(pid, idx),
                                        width=200,
                                        style=ft.ButtonStyle(
                                            bgcolor=Colors.BLUE,
                                            color=Colors.WHITE
                                        )
                                    )
                                ]),
                                padding=15
                            ),
                            elevation=3,
                            margin=ft.margin.only(bottom=10)
                        )
                        dlg_content.controls.append(item)
                    
                    # Mostrar el diálogo de edición
                    dlg = ft.AlertDialog(
                        title=ft.Text(f"Editar pedidos - {cliente}"),
                        content=dlg_content,
                        actions=[
                            ft.TextButton("Cerrar", on_click=lambda _: self.cerrar_dialogo())
                        ],
                        actions_alignment=ft.MainAxisAlignment.END
                    )
                    
                    self.page.dialog = dlg
                    dlg.open = True
                    self.page.update()
                else:
                    logger.error(f"Error al obtener detalles del cliente: código {response.status_code}")
                    self.mostrar_error(f"❌ Error al obtener detalles del cliente: {response.json().get('error', 'Error desconocido')}")
            except Exception as e:
                logger.error(f"Error en abrir_edicion_cliente: {str(e)}")
                logger.error(traceback.format_exc())
                self.cerrar_dialogo()
                self.mostrar_error(f"❌ Error: {str(e)}")
        
    @safe_button_handler
    def actualizar_pedido(self, id_pedido, indice):
            """Actualiza un pedido específico"""
            logger.info(f"Actualizando pedido ID: {id_pedido}, índice: {indice}")
            try:
                # Obtener los datos de los controles
                pedido = self.edicion_pedidos[indice]
                
                # Validar los valores ingresados
                try:
                    cantidad = int(pedido['cantidad_tf'].value)
                    costo = float(pedido['costo_tf'].value)
                    zona = pedido['zona_dd'].value
                    
                    if cantidad <= 0 or costo <= 0:
                        logger.warning(f"Valores inválidos para actualización: cantidad={cantidad}, costo={costo}")
                        self.mostrar_notificacion("⚠️ La cantidad y el costo deben ser mayores a cero")
                        return
                    
                    if not zona:
                        logger.warning("Zona no seleccionada para actualización")
                        self.mostrar_notificacion("⚠️ Debe seleccionar una zona")
                        return
                    
                except ValueError:
                    logger.warning(f"Error al convertir valores de controles")
                    self.mostrar_notificacion("⚠️ Valores inválidos. Verifique que sean números")
                    return
                
                # Crear objeto de datos para la API
                datos = {
                    'cantidad': cantidad,
                    'costo': costo,
                    'zona': zona
                }
                
                # Mostrar indicador de carga
                self.mostrar_cargando("Actualizando pedido...")
                
                # Enviar a la API
                logger.debug(f"Enviando actualización a API: {datos}")
                response = requests.put(f"{API_URL}/pedidos/{id_pedido}", json=datos)
                
                # Quitar indicador de carga
                self.cerrar_dialogo()
                
                if response.status_code == 200:
                    logger.info("Pedido actualizado correctamente")
                    self.mostrar_notificacion("✅ Pedido actualizado correctamente")
                else:
                    logger.error(f"Error al actualizar pedido: código {response.status_code}")
                    self.mostrar_error(f"❌ Error al actualizar pedido: {response.json().get('error', 'Error desconocido')}")
                    
            except Exception as e:
                logger.error(f"Error en actualizar_pedido: {str(e)}")
                logger.error(traceback.format_exc())
                self.cerrar_dialogo()
                self.mostrar_error(f"❌ Error: {str(e)}")
        
    @safe_button_handler
    def eliminar_pedido(self, id_pedido):
            """Elimina un pedido con confirmación"""
            logger.info(f"Solicitando eliminar pedido ID: {id_pedido}")
            
            @safe_button_handler
            def confirmar_eliminar(e):
                try:
                    # Mostrar cargando
                    self.cerrar_dialogo()
                    self.mostrar_cargando("Eliminando pedido...")
                    
                    # Enviar petición a la API
                    logger.debug(f"Enviando solicitud de eliminación a API para pedido ID: {id_pedido}")
                    response = requests.delete(f"{API_URL}/pedidos/{id_pedido}")
                    
                    # Quitar cargando
                    self.cerrar_dialogo()
                    
                    if response.status_code == 200:
                        # Recargar la ventana de edición
                        logger.info("Pedido eliminado correctamente")
                        self.mostrar_notificacion("✅ Pedido eliminado correctamente")
                        self.abrir_edicion_cliente(self.cliente_actual_edicion)
                    else:
                        logger.error(f"Error al eliminar pedido: código {response.status_code}")
                        self.mostrar_error(f"❌ Error al eliminar pedido: {response.json().get('error', 'Error desconocido')}")
                except Exception as ex:
                    logger.error(f"Error en confirmar_eliminar: {str(ex)}")
                    logger.error(traceback.format_exc())
                    self.cerrar_dialogo()
                    self.mostrar_error(f"❌ Error: {str(ex)}")
            
            # Diálogo de confirmación
            dlg = ft.AlertDialog(
                title=ft.Text("Confirmar eliminación"),
                content=ft.Text("¿Está seguro de que desea eliminar este pedido?"),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: self.cerrar_dialogo()),
                    ft.ElevatedButton(
                        "Eliminar",
                        style=ft.ButtonStyle(color=Colors.WHITE, bgcolor=Colors.RED),
                        on_click=confirmar_eliminar
                    )
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )
            
            self.page.dialog = dlg
            dlg.open = True
            self.page.update()
        

        
    @safe_button_handler
    def generar_pdf_cliente(self, cliente):
            """Genera un PDF para el cliente seleccionado"""
            logger.info(f"Generando PDF para cliente: {cliente}")
            try:
                # Mostrar indicador de carga
                self.mostrar_cargando("Generando PDF...")
                
                # Abrir URL del PDF en una nueva pestaña del navegador
                url_pdf = f"{API_URL}/pdf/cliente/{cliente}"
                logger.debug(f"Abriendo URL para PDF: {url_pdf}")
                self.page.launch_url(url_pdf)
                
                # Quitar indicador de carga
                self.cerrar_dialogo()
                
                # Mostrar mensaje
                self.mostrar_notificacion("✅ PDF generado y descargado")
            except Exception as e:
                logger.error(f"Error al generar PDF: {str(e)}")
                logger.error(traceback.format_exc())
                self.cerrar_dialogo()
                self.mostrar_error(f"❌ Error al generar PDF: {str(e)}")
        
    @safe_button_handler
    def generar_pdf_todos_clientes(self, clientes):
            """Genera PDFs para todos los clientes"""
            logger.info("Generando PDFs para todos los clientes")
            try:
                # Mostrar indicador de carga
                self.mostrar_cargando("Generando PDFs para todos los clientes...")
                
                # Abrir URL para generar PDFs para todos los clientes
                url_pdf = f"{API_URL}/pdf/todos_clientes"
                logger.debug(f"Abriendo URL para PDFs de todos los clientes: {url_pdf}")
                self.page.launch_url(url_pdf)
                
                # Quitar indicador de carga
                self.cerrar_dialogo()
                
                # Mostrar mensaje
                self.mostrar_notificacion("✅ PDFs generados y descargados")
            except Exception as e:
                logger.error(f"Error al generar PDFs para todos: {str(e)}")
                logger.error(traceback.format_exc())
                self.cerrar_dialogo()
                self.mostrar_error(f"❌ Error al generar PDFs: {str(e)}")
        
    def mostrar_clientes_para_editar(self, e):
            """Muestra la lista de clientes para editar sus pedidos"""
            logger.info("Mostrando clientes para editar pedidos")
            try:
                # Mostrar indicador de carga
                self.mostrar_cargando("Cargando clientes...")
                
                # Obtener los clientes desde la API
                logger.debug("Consultando API para clientes con pedidos hoy")
                response = requests.get(f"{API_URL}/pedidos/hoy")
                
                # Quitar indicador de carga
                self.cerrar_dialogo()
                
                if response.status_code == 200:
                    clientes = response.json()
                    logger.debug(f"Se obtuvieron {len(clientes)} clientes para editar")
                    
                    if not clientes:
                        self.mostrar_notificacion("🙈 No hay pedidos registrados hoy.")
                        return
                    
                    # Crear la ventana de diálogo con los clientes
                    dlg_content = ft.Column(
                        scroll="auto",
                        height=400,
                        width=400,
                        spacing=10
                    )
                    
                    # Título informativo
                    dlg_content.controls.append(
                        ft.Container(
                            content=ft.Text("Seleccione un cliente para editar sus pedidos:", weight="bold"),
                            padding=ft.padding.only(bottom=10)
                        )
                    )
                    
                    # Lista de clientes
                    for cliente in clientes:
                        btn = ft.Container(
                            content=ft.Row([
                                ft.Icon(Icons.EDIT, color=Colors.ORANGE),
                                ft.Text(cliente, size=16)
                            ]),
                            padding=10,
                            border_radius=5,
                            bgcolor=Colors.ORANGE,
                            ink=True,
                            on_click=lambda _, c=cliente: self.abrir_edicion_cliente(c)
                        )
                        dlg_content.controls.append(btn)
                    
                    # Mostrar el diálogo
                    dlg = ft.AlertDialog(
                        title=ft.Text("Editar pedidos"),
                        content=dlg_content,
                        actions=[
                            ft.TextButton("Cancelar", on_click=lambda _: self.cerrar_dialogo())
                        ],
                        actions_alignment=ft.MainAxisAlignment.END
                    )
                    
                    self.page.dialog = dlg
                    dlg.open = True
                    self.page.update()
                else:
                    logger.error(f"Error al obtener clientes: código {response.status_code}")
                    self.mostrar_error("❌ Error al obtener clientes")
            except Exception as e:
                logger.error(f"Error en mostrar_clientes_para_editar: {str(e)}")
                logger.error(traceback.format_exc())
                self.cerrar_dialogo()
                self.mostrar_error(f"❌ Error: {str(e)}")
                
def main(page: ft.Page):
    logger.info("Iniciando aplicación DistriApp")
    app = DistriApp(page)
if __name__ == "__main__":
        ft.app(target=main)
