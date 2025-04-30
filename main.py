import flet as ft
import os
import logging
from datetime import datetime, date
import pandas as pd
import io
import time
import threading
from pathlib import Path

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('distriapp.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constantes de la aplicación
APP_TITLE = "DistriApp - Sistema de Gestión de Distribución"
ZONAS = ["Bernal", "Avellaneda #1", "Avellaneda #2", "Quilmes Centro", "Solano"]
PDF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pdfs')
os.makedirs(PDF_DIR, exist_ok=True)

# Para evitar conflictos de importación durante el desarrollo
try:
    from database.db_connection import initialize_database, db
    from database.models.cliente import Cliente
    from database.models.producto import Producto
    from database.models.pedido import Pedido
    from utils.csv_handler import CSVHandler
    from utils.pdf_generator import PDFGenerator
except ImportError:
    # Importaciones en línea para modo de desarrollo rápido
    # En una aplicación real, es mejor usar las importaciones modulares
    
    # Clase para simular la conexión a MySQL
    class DatabaseConnection:
        def __init__(self):
            self.connection = None
            self.productos = []
            self.clientes = []
            self.pedidos = []
            self.initialize_demo_data()
        
        def initialize_demo_data(self):
            # Productos de demostración
            self.productos = [
                {"id": 1, "nombre": "Producto 1", "costo": 100.0, "precio_venta": 150.0, "stock": 50, "codigo": "P001"},
                {"id": 2, "nombre": "Producto 2", "costo": 200.0, "precio_venta": 300.0, "stock": 30, "codigo": "P002"},
                {"id": 3, "nombre": "Producto 3", "costo": 50.0, "precio_venta": 80.0, "stock": 100, "codigo": "P003"},
            ]
            
            # Clientes de demostración
            self.clientes = [
                {"id": 1, "nombre": "Cliente A"},
                {"id": 2, "nombre": "Cliente B"},
                {"id": 3, "nombre": "Cliente C"},
            ]
    
    db = DatabaseConnection()
    
    def initialize_database():
        pass
    
    # Clases de modelos simplificadas para demostración
    class Cliente:
        @classmethod
        def search_by_name(cls, nombre, limit=5):
            return [type('Cliente', (), c) for c in db.clientes if nombre.lower() in c['nombre'].lower()][:limit]
    
    class Producto:
        @classmethod
        def search_by_name(cls, nombre, limit=5):
            return [type('Producto', (), p) for p in db.productos if nombre.lower() in p['nombre'].lower()][:limit]
        
        @classmethod
        def get_by_name(cls, nombre):
            for p in db.productos:
                if p['nombre'] == nombre:
                    return type('Producto', (), p)
            return None
    
    class Pedido:
        @classmethod
        def get_clientes_by_date(cls, fecha=None):
            return ["Cliente A", "Cliente B"]
        
        @classmethod
        def get_by_cliente(cls, cliente, fecha=None):
            return []
    
    class CSVHandler:
        @staticmethod
        def procesar_csv_productos(contenido_csv):
            return (True, "CSV procesado correctamente", 2, 1)
    
    class PDFGenerator:
        @staticmethod
        def generar_pedido_cliente(cliente, fecha=None):
            return os.path.join(PDF_DIR, f"pedido_{cliente}_{int(time.time())}.pdf")
        
        @staticmethod
        def generar_productos_por_dia(fecha=None):
            return os.path.join(PDF_DIR, f"productos_por_dia_{int(time.time())}.pdf")
        
        @staticmethod
        def generar_estadisticas():
            return os.path.join(PDF_DIR, f"estadisticas_{int(time.time())}.pdf")

# Variables globales para datos de sesión
pedidos_temporales = []
cliente_actual = None
zona_actual = None

class DistriAppV3:
    """Aplicación principal de gestión de distribución usando Flet."""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.setup_page()
        self.initialize_database()
        self.setup_controls()
        self.build_ui()
    
    def setup_page(self):
        """Configura las propiedades básicas de la página."""
        self.page.title = APP_TITLE
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window_width = 1000
        self.page.window_height = 800
        self.page.padding = 0
        self.page.bgcolor = ft.Colors.BLUE_GREY_50
        self.page.scroll = ft.ScrollMode.AUTO  # Habilitar scroll en la página
        
        # Tema personalizado
        self.page.theme = ft.Theme(
            color_scheme_seed=ft.Colors.BLUE
        )
    
    def initialize_database(self):
        """Inicializa la conexión a la base de datos."""
        try:
            initialize_database()
            logger.info("Base de datos inicializada correctamente")
        except Exception as e:
            logger.error(f"Error al inicializar la base de datos: {e}")
            self.show_message(f"Error de conexión a la base de datos: {e}", is_error=True)
    
    def setup_controls(self):
        """Inicializa los controles de la interfaz."""
        # Fila superior: Controles de cliente, producto, cantidad, costo y zona
        self.cliente_field = ft.TextField(
            label="Cliente ✍️",
            hint_text="Nombre del cliente",
            expand=True,
            on_change=self.search_clientes
        )
        
        self.cliente_dropdown = ft.Container(
            content=ft.ListView(            
                height=200,
                visible=False,
                spacing=2,
                padding=10,
            ),            
            padding=5,
            visible=False  # Inicialmente oculto
        )
        
        self.producto_field = ft.TextField(
            label="Producto 🔍",
            hint_text="Buscar producto",
            expand=True,
            on_change=self.search_productos
        )
        
        self.producto_dropdown = ft.Container(
            content=ft.ListView(

                spacing=5,
                visible=False
            ),
            height=200,
            padding=10,
            visible=False  # Inicialmente oculto
        )
        
        self.cantidad_field = ft.TextField(
            label="Cantidad 🔢",
            hint_text="0",
            width=170,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.costo_field = ft.TextField(
            label="Costo 💲",
            hint_text="0.00",
            width=170,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.zona_dropdown = ft.Dropdown(
            label="📍 Zona",
            width=340,
            options=[ft.dropdown.Option(zona) for zona in ZONAS],
        )
        
        # Botones de acción primarios
        self.btn_registrar = ft.ElevatedButton(
            "REGISTRAR",
            icon=ft.icons.ADD_CIRCLE,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.BLUE,
                padding=15,
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=self.registrar_pedido,
            width=170
        )
        
        self.btn_pedidos_hoy = ft.ElevatedButton(
            "PEDIDOS HOY",
            icon=ft.icons.LIST_ALT,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.GREEN,
                padding=15,
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=self.ver_pedidos_dia,
            width=170
        )
        
        # Botones de funciones secundarias
        self.btn_modificar = ft.ElevatedButton(
            "MODIFICAR",
            icon=ft.icons.EDIT,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.ORANGE,
                padding=15,
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=self.mostrar_clientes_para_editar,
            width=170
        )
        
        self.btn_csv = ft.ElevatedButton(
            "SUBIR CSV",
            icon=ft.icons.UPLOAD_FILE,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.PURPLE,
                padding=15,
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=self.subir_csv,
            width=170
        )
        
        self.btn_estadisticas = ft.ElevatedButton(
            "ESTADÍSTICAS",
            icon=ft.icons.BAR_CHART,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.TEAL,
                padding=15,
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=self.mostrar_estadisticas,
            width=170
        )
        
        self.btn_productos = ft.ElevatedButton(
            "PRODUCTOS",
            icon=ft.icons.INVENTORY,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.RED,
                padding=15,
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=self.generar_productos_por_dia,
            width=170
        )
        
        # Lista de productos en pedido actual
        self.lista_productos = ft.ListView(
            spacing=10,
            padding=10,
            auto_scroll=True,
            expand=True
        )
        
        # Botones de control para la orden actual
        self.btn_editar_orden = ft.ElevatedButton(
            "Editar",
            icon=ft.icons.EDIT,
            style=ft.ButtonStyle(
                padding=10,
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=self.editar_orden_actual,
            width=110
        )
        
        self.btn_vaciar_orden = ft.ElevatedButton(
            "Vaciar",
            icon=ft.icons.DELETE,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.RED,
                padding=10,
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=self.vaciar_orden_actual,
            width=110
        )
        
        self.btn_enviar_orden = ft.ElevatedButton(
            "Enviar",
            icon=ft.icons.SEND,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.GREEN,
                padding=10,
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=self.guardar_pedido_completo,
            width=110
        )
        
        # Inicializar file picker para CSV
        self.file_picker = ft.FilePicker(on_result=self.on_file_picked)
        self.page.overlay.append(self.file_picker)
        
        # Indicador de progreso para operaciones largas
        self.progress_ring = ft.ProgressRing(visible=False)
    
    def build_ui(self):
        """Construye la interfaz de usuario completa."""
        # Limpiar controles existentes
        self.page.controls.clear()
        
        # AppBar superior
        app_bar = ft.AppBar(
            title=ft.Text("DistriApp", size=20, weight=ft.FontWeight.BOLD),
            center_title=True,
            bgcolor=ft.Colors.BLUE,
            color=ft.Colors.WHITE,
            actions=[
                ft.IconButton(
                    icon=ft.icons.SETTINGS,
                    tooltip="Configuración",
                    on_click=self.show_settings
                ),
                ft.IconButton(
                    icon=ft.icons.INFO,
                    tooltip="Acerca de",
                    on_click=self.show_about
                ),
            ]
        )
        
        # Diseño principal de la aplicación
        main_content = ft.Column([
            # Panel superior - Formulario de pedido
            ft.Container(
                ft.Column([
                    # Encabezado de sección
                    ft.Row([
                        ft.Icon(ft.icons.SHOPPING_CART, color=ft.Colors.BLUE),
                        ft.Text("Registro de Pedido", size=20, weight=ft.FontWeight.BOLD),
                    ]),
                    
                    # Cliente
                    ft.Container(
                        ft.Column([
                            [self.cliente_field],
                            [self.cliente_dropdown],
                        ], spacing=0),
                        padding=ft.padding.only(bottom=10)
                    ),
                    
                    # Producto
                    ft.Container(
                        ft.Column([
                            [self.producto_field],
                            [self.producto_dropdown],
                        ], spacing=0),
                        padding=ft.padding.only(bottom=10)
                    ),
                    
                    # Cantidad y Costo
                    ft.Row([
                        [self.cantidad_field],
                        ft.Container(width=10),
                        [self.costo_field],
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    
                    # Zona
                    ft.Container(
                        [self.zona_dropdown],
                        padding=ft.padding.only(top=10, bottom=10)
                    ),
                    
                    # Botones de registro
                    ft.Row([
                        [self.btn_registrar],
                        [self.btn_pedidos_hoy],
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    
                    # Botones adicionales
                    ft.Row([
                        [self.btn_modificar],
                        [self.btn_csv],
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                    
                    ft.Row([
                        [self.btn_estadisticas],
                        [self.btn_productos],
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                ], spacing=15),
                padding=20,
                bgcolor=ft.Colors.WHITE,
                shadow=ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=10,
                    color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK)
                ),
                margin=ft.margin.only(bottom=15)
            ),
            
            # Panel inferior - Lista de productos en el pedido actual
            ft.Container(
                ft.Column([
                    # Encabezado de sección
                    ft.Row([
                        ft.Icon(ft.icons.LIST, color=ft.Colors.BLUE),
                        ft.Text("Productos en pedido actual", size=20, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            [self.progress_ring],
                            alignment=ft.alignment.center_right,
                            expand=True
                        )
                    ]),
                    
                    # Lista de productos con scroll
                    ft.Container(ft.ListView(ft.Column(
                        [self.lista_productos],

                        # Agregamos scroll a la lista de productos
                        auto_scroll=True),),
                        height=300,
                        border_radius=10,
                        padding=10,
                        
                    ),
                    
                    # Botones de control
                    ft.Row([
                        [self.btn_editar_orden],
                        [self.btn_vaciar_orden],
                        [self.btn_enviar_orden],
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                ], spacing=15),
                padding=20,
                bgcolor=ft.Colors.WHITE,
                shadow=ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=10,
                    color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK)
                )
            ),
        ], spacing=10)  # Reducido el espaciado para mejor visualización
        
        # Construir el layout principal con scroll
        self.page.add(
            app_bar,
            ft.Container(
                [main_content],
                expand=True,
                # Aseguramos que el contenedor tenga scroll si es necesario
                auto_scroll=True
            ),
        padding=20,
        )
        
        # Actualizar lista de productos temporales
        self.actualizar_lista_temporal()
    
    # ======== Funciones de búsqueda y sugerencias ========
    
    def search_clientes(self, e):
        """Busca clientes que coincidan con el texto ingresado."""
        texto = self.cliente_field.value
        if texto and len(texto) >= 2:
            try:
                clientes = Cliente.search_by_name(texto)
                
                # Limpiar lista actual
                self.cliente_dropdown.content.controls.clear()
                
                if clientes:
                    for cliente in clientes:
                        self.cliente_dropdown.content.controls.append(
                            ft.Container(
                                ft.ListTile(
                                    title=ft.Text(cliente.nombre),
                                    on_click=lambda _, c=cliente.nombre: self.select_cliente(c)
                                ),
                                bgcolor=ft.Colors.WHITE,

                                margin=2
                            )
                        )
                    self.cliente_dropdown.visible = True
                else:
                    self.cliente_dropdown.visible = False
            except Exception as e:
                logger.error(f"Error al buscar clientes: {e}")
                self.cliente_dropdown.visible = False
        else:
            self.cliente_dropdown.visible = False
        
        self.page.update()
    
    def select_cliente(self, nombre_cliente):
        """Selecciona un cliente de la lista de sugerencias."""
        self.cliente_field.value = nombre_cliente
        self.cliente_dropdown.visible = False
        
        # Actualizar variable global
        global cliente_actual
        cliente_actual = nombre_cliente
        
        self.page.update()
    
    def search_productos(self, e):
        """Busca productos que coincidan con el texto ingresado."""
        texto = self.producto_field.value
        if texto and len(texto) >= 2:
            try:
                productos = Producto.search_by_name(texto)
                
                # Limpiar lista actual
                self.producto_dropdown.content.controls.clear()
                
                if productos:
                    for producto in productos:
                        self.producto_dropdown.content.controls.append(
                            ft.Container(
                                ft.ListTile(
                                    title=ft.Text(producto.nombre),
                                    subtitle=ft.Text(f"Precio: ${producto.costo} | Stock: {producto.stock}"),
                                    on_click=lambda _, p=producto.nombre: self.select_producto(p)
                                ),
                                bgcolor=ft.Colors.WHITE,
                                margin=2
                            )
                        )
                    self.producto_dropdown.visible = True
                else:
                    self.producto_dropdown.visible = False
            except Exception as e:
                logger.error(f"Error al buscar productos: {e}")
                self.producto_dropdown.visible = False
        else:
            self.producto_dropdown.visible = False
        
        self.page.update()
    
    def select_producto(self, nombre_producto):
        """Selecciona un producto de la lista de sugerencias."""
        self.producto_field.value = nombre_producto
        self.producto_dropdown.visible = False
        
        # Obtener y establecer el costo del producto
        try:
            producto = Producto.get_by_name(nombre_producto)
            if producto:
                self.costo_field.value = str(producto.costo)
        except Exception as e:
            logger.error(f"Error al obtener costo del producto: {e}")
        
        self.page.update()
    
    # ======== Funciones de gestión de pedidos ========
    
    def registrar_pedido(self, e):
        """Registra un producto en el pedido actual."""
        global pedidos_temporales, cliente_actual, zona_actual
        
        # Validar campos
        if (not self.cliente_field.value or 
            not self.producto_field.value or 
            not self.cantidad_field.value or 
            not self.costo_field.value or 
            not self.zona_dropdown.value):
            self.show_message("Todos los campos son obligatorios")
            return
        
        try:
            # Verificar stock disponible
            producto = Producto.get_by_name(self.producto_field.value)
            if not producto:
                self.show_message("El producto no existe")
                return
            
            cantidad = int(self.cantidad_field.value)
            if producto.stock < cantidad:
                self.show_message(f"Stock insuficiente. Disponible: {producto.stock}")
                return
            
            # Validar que la cantidad sea positiva
            if cantidad <= 0:
                self.show_message("La cantidad debe ser mayor a 0")
                return
                
            # Validar que el costo sea positivo
            costo = float(self.costo_field.value)
            if costo <= 0:
                self.show_message("El costo debe ser mayor a 0")
                return
            
            # Insertar cliente si no existe
            try:
                cliente = Cliente(nombre=self.cliente_field.value)
                cliente.save()
            except:
                # En caso de errores continuamos de todos modos
                pass
            
            # Actualizar variables globales
            cliente_actual = self.cliente_field.value
            zona_actual = self.zona_dropdown.value
            
            # Agregar a lista temporal
            pedidos_temporales.append({
                'producto': self.producto_field.value,
                'cantidad': cantidad,
                'costo': costo,
                'zona': self.zona_dropdown.value,
                'stock': producto.stock
            })
            
            # Limpiar campos y actualizar lista
            self.producto_field.value = ''
            self.cantidad_field.value = ''
            self.costo_field.value = ''
            self.actualizar_lista_temporal()
            
            # Mostrar mensaje y actualizar UI
            self.show_message(f"Producto '{producto.nombre}' agregado al pedido")
            self.page.update()
            
        except ValueError:
            self.show_message("Ingrese valores numéricos válidos para cantidad y costo", is_error=True)
        except Exception as e:
            logger.error(f"Error al registrar pedido: {e}")
            self.show_message(f"Error al registrar: {e}", is_error=True)
    
    def actualizar_lista_temporal(self):
        """Actualiza la lista visual de productos en el pedido temporal."""
        global pedidos_temporales
        
        # Limpiar lista actual
        self.lista_productos.controls.clear()
        
        if not pedidos_temporales:
            self.lista_productos.controls.append(
                ft.Container(
                    ft.Text("No hay productos en el pedido actual", 
                           italic=True, color=ft.Colors.GREY),
                    alignment=ft.alignment.center,
                    padding=20,
                    expand=True
                )
            )
        else:
            total_pedido = 0
            
            for i, producto in enumerate(pedidos_temporales):
                subtotal = producto['cantidad'] * producto['costo']
                total_pedido += subtotal
                
                self.lista_productos.controls.append(
                    ft.Card(
                        content=ft.Container(
                            ft.Column([
                                ft.Row([
                                    ft.Icon(ft.icons.SHOPPING_BAG, color=ft.Colors.BLUE),
                                    ft.Text(producto['producto'], 
                                          weight=ft.FontWeight.BOLD,
                                          size=16),
                                    ft.Container(
                                        ft.IconButton(
                                            icon=ft.icons.DELETE,
                                            icon_color=ft.Colors.RED,
                                            tooltip="Eliminar",
                                            on_click=lambda e, idx=i: self.eliminar_de_orden_actual(idx)
                                        ),
                                        alignment=ft.alignment.center_right,
                                        expand=True
                                    )
                                ]),
                                ft.Container(
                                    ft.Row([
                                        ft.Text(f"Cantidad: {producto['cantidad']}"),
                                        ft.Container(width=10),
                                        ft.Text(f"Costo: ${producto['costo']:.2f}"),
                                        ft.Container(width=10),
                                        ft.Text(f"Subtotal: ${subtotal:.2f}", 
                                               weight=ft.FontWeight.BOLD,
                                               color=ft.Colors.GREEN)
                                    ]),
                                    padding=ft.padding.only(top=5)
                                ),
                                ft.Container(
                                    ft.Text(f"Zona: {producto['zona']}", 
                                           color=ft.Colors.GREY),
                                    padding=ft.padding.only(top=5)
                                )
                            ]),
                            padding=15,
                            bgcolor=ft.Colors.WHITE
                        ),
                        margin=5,
                        elevation=2
                    )
                )
            
            # Agregar el total al final
            self.lista_productos.controls.append(
                ft.Container(
                    ft.Row([
                        ft.Text("TOTAL:", 
                               weight=ft.FontWeight.BOLD,
                               size=18),
                        ft.Text(f"${total_pedido:.2f}", 
                               weight=ft.FontWeight.BOLD,
                               size=18,
                               color=ft.Colors.GREEN)
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    padding=10,
                    bgcolor=ft.Colors.BLUE_50,
                    margin=10
                )
            )
        
        self.page.update()
    
    def eliminar_de_orden_actual(self, index):
        """Elimina un producto de la orden actual."""
        global pedidos_temporales
        
        if 0 <= index < len(pedidos_temporales):
            producto_eliminado = pedidos_temporales[index]['producto']
            pedidos_temporales.pop(index)
            self.actualizar_lista_temporal()
            self.show_message(f"Producto '{producto_eliminado}' eliminado de la orden")
    
    def vaciar_orden_actual(self, e):
        """Elimina todos los productos de la orden actual."""
        global pedidos_temporales
        
        if not pedidos_temporales:
            self.show_message("No hay productos para eliminar")
            return
            
        # Confirmar antes de vaciar
        def confirm_vaciar(e):
            global pedidos_temporales
            pedidos_temporales.clear()
            self.actualizar_lista_temporal()
            self.show_message("Orden vaciada completamente")
            dlg_confirm.open = False
            self.page.update()
        
        def cancel_vaciar(e):
            dlg_confirm.open = False
            self.page.update()
        
        dlg_confirm = ft.AlertDialog(
            title=ft.Text("Confirmar"),
            content=ft.Text("¿Está seguro de vaciar la orden actual?"),
            actions=[
                ft.TextButton("Cancelar", on_click=cancel_vaciar),
                ft.ElevatedButton(
                    "Vaciar",
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.RED,
                    on_click=confirm_vaciar
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        self.page.dialog = dlg_confirm
        dlg_confirm.open = True
        self.page.update()
    
    def editar_orden_actual(self, e):
        """Muestra un diálogo para editar la orden actual."""
        global pedidos_temporales
        
        if not pedidos_temporales:
            self.show_message("No hay productos en la orden actual")
            return
        
        # Crear contenido del diálogo
        dlg_content = ft.ListView(
            expand=True,
            spacing=10,
            auto_scroll=True
        )
        
        for i, producto in enumerate(pedidos_temporales):
            subtotal = producto['cantidad'] * producto['costo']
            
            cantidad_field = ft.TextField(
                label="Cantidad",
                value=str(producto['cantidad']),
                width=100,
                keyboard_type=ft.KeyboardType.NUMBER
            )
            
            costo_field = ft.TextField(
                label="Costo",
                value=str(producto['costo']),
                width=100,
                keyboard_type=ft.KeyboardType.NUMBER
            )
            
            # Función para actualizar en tiempo real
            def update_producto(e, idx=i, c_field=cantidad_field, p_field=costo_field):
                try:
                    nueva_cantidad = int(c_field.value)
                    nuevo_costo = float(p_field.value)
                    
                    if nueva_cantidad <= 0 or nuevo_costo <= 0:
                        self.show_message("Los valores deben ser mayores a 0")
                        return
                    
                    # Verificar stock disponible
                    producto_obj = Producto.get_by_name(pedidos_temporales[idx]['producto'])
                    stock_original = pedidos_temporales[idx]['stock']
                    cantidad_original = pedidos_temporales[idx]['cantidad']
                    
                    # Si aumentó la cantidad, verificar que haya stock suficiente
                    if nueva_cantidad > cantidad_original:
                        stock_adicional = nueva_cantidad - cantidad_original
                        if stock_original < stock_adicional:
                            self.show_message(f"Stock insuficiente. Disponible: {stock_original}")
                            return
                    
                    # Actualizar datos
                    pedidos_temporales[idx]['cantidad'] = nueva_cantidad
                    pedidos_temporales[idx]['costo'] = nuevo_costo
                    
                    # Actualizar subtotal
                    nuevo_subtotal = nueva_cantidad * nuevo_costo
                    subtotal_text.value = f"Subtotal: ${nuevo_subtotal:.2f}"
                    self.page.update()
                    
                except ValueError:
                    self.show_message("Ingrese valores numéricos válidos")
            
            # Crear texto de subtotal que se actualizará
            subtotal_text = ft.Text(
                f"Subtotal: ${subtotal:.2f}", 
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.GREEN
            )
            
            # Conectar eventos de cambio
            cantidad_field.on_change = update_producto
            costo_field.on_change = update_producto
            
            dlg_content.controls.append(
                ft.Card(
                    ft.Container(
                    content=
                        ft.Column([
                            ft.Row([
                                ft.Icon(ft.icons.SHOPPING_BAG, color=ft.Colors.BLUE),
                                ft.Text(producto['producto'], 
                                      weight=ft.FontWeight.BOLD,
                                      size=16),
                                ft.IconButton(
                                    icon=ft.icons.DELETE,
                                    icon_color=ft.Colors.RED,
                                    tooltip="Eliminar",
                                    on_click=lambda e, idx=i: self.eliminar_y_cerrar_dialogo(idx, dlg)
                                )
                            ]),
                            ft.Row([
                                [cantidad_field],
                                ft.Container(width=10),
                                [costo_field]
                            ]),
                            ft.Container(
                                [subtotal_text],
                                padding=ft.padding.only(top=5)
                            ),
                            ft.Container(
                                ft.Text(f"Zona: {producto['zona']}", 
                                       color=ft.Colors.GREY),
                                padding=ft.padding.only(top=5)
                            )
                        ]),
                        padding=15
                    ),
                    elevation=3
                )
            )
        
        # Crear diálogo
        dlg = ft.AlertDialog(
            title=ft.Text("Editar pedido actual"),
            content=ft.Container(ft.Column(
                [dlg_content],

                # Agregamos scroll al contenedor del diálogo
                auto_scroll=True),
                height=400,
                width=400,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: self.cerrar_dialogo(dlg)),
                ft.ElevatedButton(
                    "Guardar",
                    icon=ft.icons.SAVE,
                    on_click=lambda e: self.guardar_y_cerrar_dialogo(dlg)
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        # Mostrar diálogo
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
    
    def eliminar_y_cerrar_dialogo(self, index, dialogo):
        """Elimina un producto y actualiza el diálogo."""
        self.eliminar_de_orden_actual(index)
        
        # Si no quedan productos, cerrar el diálogo
        if not pedidos_temporales:
            self.cerrar_dialogo(dialogo)
        else:
            # Recrear el diálogo para que refleje los cambios
            dialogo.open = False
            self.page.update()
            self.editar_orden_actual(None)
    
    def cerrar_dialogo(self, dialogo):
        """Cierra un diálogo."""
        dialogo.open = False
        self.page.update()
    
    def guardar_y_cerrar_dialogo(self, dialogo):
        """Guarda los cambios y cierra el diálogo."""
        self.actualizar_lista_temporal()
        self.cerrar_dialogo(dialogo)
        self.show_message("Cambios guardados")
    
    def guardar_pedido_completo(self, e):
        """Guarda todos los productos de la orden actual como pedidos individuales."""
        global pedidos_temporales, cliente_actual, zona_actual
        
        if not pedidos_temporales:
            self.show_message("No hay productos en la orden")
            return
        
        if not cliente_actual:
            self.show_message("Debe seleccionar un cliente")
            return
        
        if not zona_actual:
            self.show_message("Debe seleccionar una zona")
            return
        
        try:
            # Mostrar indicador de progreso
            self.progress_ring.visible = True
            self.page.update()
            
            # Ejecutar en segundo plano para no bloquear la UI
            def background_task():
                try:
                    # Guardar cada producto como un pedido individual
                    for producto_temp in pedidos_temporales:
                        pedido = Pedido(
                            cliente=cliente_actual,
                            producto=producto_temp['producto'],
                            cantidad=producto_temp['cantidad'],
                            costo=producto_temp['costo'],
                            zona=zona_actual
                        )
                        pedido.save()
                    
                    # Limpiar orden actual
                    pedidos_temporales.clear()
                    
                    # Actualizar UI en el hilo principal
                    self.page.invoke_async(self.finalizar_guardar_pedido)
                    
                except Exception as e:
                    logger.error(f"Error en el guardado: {e}")
                    # Notificar error en el hilo principal
                    self.page.invoke_async(
                        lambda: self.show_message(f"Error al guardar: {e}", is_error=True)
                    )
                finally:
                    # Ocultar progreso en el hilo principal
                    self.page.invoke_async(
                        lambda: self.set_progress_visible(False)
                    )
            
            # Iniciar en segundo plano
            threading.Thread(target=background_task).start()
            
        except Exception as e:
            logger.error(f"Error al guardar pedido completo: {e}")
            self.progress_ring.visible = False
            self.show_message(f"Error al guardar: {e}", is_error=True)
            self.page.update()
    
    def finalizar_guardar_pedido(self):
        """Actualiza la UI después de guardar el pedido."""
        self.actualizar_lista_temporal()
        self.show_message("✅ Pedido guardado exitosamente!")
    
    def set_progress_visible(self, visible):
        """Cambia la visibilidad del indicador de progreso."""
        self.progress_ring.visible = visible
        self.page.update()
    
    # ======== Funciones para ver y editar pedidos ========
    
    def ver_pedidos_dia(self, e):
        """Muestra los clientes con pedidos del día actual."""
        try:
            # Mostrar indicador de progreso
            self.progress_ring.visible = True
            self.page.update()
            
            # Ejecutar en segundo plano
            def background_task():
                try:
                    # Obtener clientes con pedidos hoy
                    clientes = Pedido.get_clientes_by_date()
                    
                    # Actualizar UI en el hilo principal
                    self.page.invoke_async(
                        lambda: self.mostrar_lista_clientes(clientes)
                    )
                except Exception as e:
                    logger.error(f"Error al obtener clientes: {e}")
                    self.page.invoke_async(
                        lambda: self.show_message(f"Error: {e}", is_error=True)
                    )
                finally:
                    # Ocultar progreso
                    self.page.invoke_async(
                        lambda: self.set_progress_visible(False)
                    )
            
            # Iniciar en segundo plano
            threading.Thread(target=background_task).start()
            
        except Exception as e:
            logger.error(f"Error al ver pedidos del día: {e}")
            self.progress_ring.visible = False
            self.show_message(f"Error: {e}", is_error=True)
            self.page.update()
    
    def mostrar_lista_clientes(self, clientes):
        """Muestra un diálogo con la lista de clientes."""
        if not clientes:
            self.show_message("No hay pedidos registrados hoy")
            return
        
        # Crear contenido del diálogo
        dlg_content = ft.ListView(ft.Container(
            ft.Column(            
                expand=True,

                auto_scroll=True),

                
            ),                padding=10,                 spacing=10,
  # Habilitar scroll
        )
        
        for cliente in clientes:
            dlg_content.controls.append(
                ft.ElevatedButton(
                    [cliente],
                    icon=ft.icons.PERSON,
                    style=ft.ButtonStyle(
                        padding=15,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    width=300,
                    on_click=lambda e, c=cliente: self.mostrar_detalle_cliente(c)
                )
            )
        
        # Botón para generar PDF de todos los clientes
        dlg_content.controls.append(
            ft.Container(
                ft.ElevatedButton(
                    "Descargar PDF para cada cliente",
                    icon=ft.icons.PICTURE_AS_PDF,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.BLUE,
                        color=ft.Colors.WHITE,

                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    padding=15,
                    width=300,
                    on_click=lambda e: self.generar_pdf_todos_clientes(clientes)
                ),
                padding=ft.padding.only(top=20)
            )
        )
        
        # Crear diálogo
        dlg = ft.AlertDialog(
            title=ft.Text("Pedidos del día"),
            content=ft.Container(
                [dlg_content],
                height=400, 
                width=350
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda e: self.cerrar_dialogo(dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        # Mostrar diálogo
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
    
    def mostrar_detalle_cliente(self, cliente):
        """Muestra los detalles de los pedidos de un cliente."""
        try:
            # Mostrar indicador de progreso
            self.progress_ring.visible = True
            self.page.update()
            
            # Cerrar diálogo anterior si está abierto
            if self.page.dialog and self.page.dialog.open:
                self.page.dialog.open = False
            
            # Ejecutar en segundo plano
            def background_task():
                try:
                    # Obtener pedidos del cliente para hoy
                    pedidos = Pedido.get_by_cliente(cliente, date.today())
                    
                    # Actualizar UI en el hilo principal
                    self.page.invoke_async(
                        lambda: self.mostrar_detalle_pedidos(cliente, pedidos)
                    )
                except Exception as e:
                    logger.error(f"Error al obtener pedidos: {e}")
                    self.page.invoke_async(
                        lambda: self.show_message(f"Error: {e}", is_error=True)
                    )
                finally:
                    # Ocultar progreso
                    self.page.invoke_async(
                        lambda: self.set_progress_visible(False)
                    )
            
            # Iniciar en segundo plano
            threading.Thread(target=background_task).start()
            
        except Exception as e:
            logger.error(f"Error al mostrar detalles del cliente {cliente}: {e}")
            self.progress_ring.visible = False
            self.show_message(f"Error: {e}", is_error=True)
            self.page.update()
    
    def mostrar_detalle_pedidos(self, cliente, pedidos):
        """Muestra un diálogo con los detalles de los pedidos."""
        if not pedidos:
            self.show_message(f"No hay pedidos para {cliente} en la fecha actual")
            return
        
        # Calcular total
        total_cliente = sum(p.cantidad * p.costo for p in pedidos)
        
        # Crear contenido del diálogo
        dlg_content = ft.ListView(ft.Container(
            ft.Column(
                expand=True,

                auto_scroll=True),
),                padding=10,                spacing=10,
              # Habilitar scroll
    )   
        
        for pedido in pedidos:
            total = pedido.cantidad * pedido.costo
            dlg_content.controls.append(
                ft.Card(
                    content=ft.Container(
                        ft.Column([
                            ft.Row([
                                ft.Icon(ft.icons.SHOPPING_BAG, color=ft.Colors.BLUE),
                                ft.Text(pedido.producto, 
                                      weight=ft.FontWeight.BOLD,
                                      size=16)
                            ]),
                            ft.Container(
                                ft.Row([
                                    ft.Text(f"Cantidad: {pedido.cantidad}"),
                                    ft.Container(width=10),
                                    ft.Text(f"Costo: ${pedido.costo:.2f}"),
                                ]),
                                padding=ft.padding.only(top=5)
                            ),
                            ft.Container(
                                ft.Row([
                                    ft.Text(f"Total: ${total:.2f}", 
                                          weight=ft.FontWeight.BOLD,
                                          color=ft.Colors.GREEN),
                                    ft.Container(width=10),
                                    ft.Text(f"Zona: {pedido.zona}")
                                ]),
                                padding=ft.padding.only(top=5)
                            )
                        ]),
                        padding=15
                    ),
                    elevation=3
                )
            )
        
        # Agregar total al final
        dlg_content.controls.append(
            ft.Container(
                ft.Row([
                    ft.Text("TOTAL:", 
                           weight=ft.FontWeight.BOLD,
                           size=18),
                    ft.Text(f"${total_cliente:.2f}", 
                           weight=ft.FontWeight.BOLD,
                           size=18,
                           color=ft.Colors.GREEN)
                ], alignment=ft.MainAxisAlignment.CENTER),
                padding=10,
                bgcolor=ft.Colors.BLUE_50,
                margin=10
            )
        )
        
        # Crear diálogo
        dlg = ft.AlertDialog(
            title=ft.Text(f"Pedidos de {cliente}"),
            content=ft.Container(
                [dlg_content],
                height=400,
                width=350
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda e: self.cerrar_dialogo(dlg)),
                ft.ElevatedButton(
                    "Generar PDF",
                    icon=ft.icons.PICTURE_AS_PDF,
                    on_click=lambda e: self.generar_pdf_cliente(cliente)
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        # Mostrar diálogo
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
    
    def generar_pdf_cliente(self, cliente):
        """Genera un PDF con los pedidos del cliente."""
        try:
            # Mostrar indicador de progreso
            self.progress_ring.visible = True
            self.page.update()
            
            # Ejecutar en segundo plano
            def background_task():
                try:
                    filename = PDFGenerator.generar_pedido_cliente(cliente)
                    
                    # Actualizar UI en el hilo principal
                    if filename:
                        self.page.invoke_async(
                            lambda: self.show_message(f"PDF generado: {Path(filename).name}")
                        )
                    else:
                        self.page.invoke_async(
                            lambda: self.show_message("No se pudo generar el PDF")
                        )
                except Exception as e:
                    logger.error(f"Error al generar PDF: {e}")
                    self.page.invoke_async(
                        lambda: self.show_message(f"Error al generar PDF: {e}", is_error=True)
                    )
                finally:
                    # Ocultar progreso
                    self.page.invoke_async(
                        lambda: self.set_progress_visible(False)
                    )
            
            # Iniciar en segundo plano
            threading.Thread(target=background_task).start()
            
        except Exception as e:
            logger.error(f"Error al generar PDF para {cliente}: {e}")
            self.progress_ring.visible = False
            self.show_message(f"Error: {e}", is_error=True)
            self.page.update()
    
    def generar_pdf_todos_clientes(self, clientes):
        """Genera un PDF para cada cliente con pedidos del día."""
        try:
            # Mostrar indicador de progreso
            self.progress_ring.visible = True
            self.page.update()
            
            # Ejecutar en segundo plano
            def background_task():
                try:
                    pdfs_generados = []
                    
                    for cliente in clientes:
                        filename = PDFGenerator.generar_pedido_cliente(cliente)
                        if filename:
                            pdfs_generados.append(filename)
                    
                    # Actualizar UI en el hilo principal
                    if pdfs_generados:
                        self.page.invoke_async(
                            lambda: self.show_message(f"Se generaron {len(pdfs_generados)} archivos PDF")
                        )
                    else:
                        self.page.invoke_async(
                            lambda: self.show_message("No se pudo generar ningún PDF")
                        )
                except Exception as e:
                    logger.error(f"Error al generar PDFs: {e}")
                    self.page.invoke_async(
                        lambda: self.show_message(f"Error: {e}", is_error=True)
                    )
                finally:
                    # Ocultar progreso
                    self.page.invoke_async(
                        lambda: self.set_progress_visible(False)
                    )
            
            # Iniciar en segundo plano
            threading.Thread(target=background_task).start()
            
        except Exception as e:
            logger.error(f"Error al generar PDFs para todos los clientes: {e}")
            self.progress_ring.visible = False
            self.show_message(f"Error: {e}", is_error=True)
            self.page.update()
    
    def mostrar_clientes_para_editar(self, e):
        """Muestra los clientes con pedidos del día para editarlos."""
        try:
            # Mostrar indicador de progreso
            self.progress_ring.visible = True
            self.page.update()
            
            # Ejecutar en segundo plano
            def background_task():
                try:
                    # Obtener clientes con pedidos hoy
                    clientes = Pedido.get_clientes_by_date()
                    
                    # Actualizar UI en el hilo principal
                    self.page.invoke_async(
                        lambda: self.mostrar_lista_clientes_edicion(clientes)
                    )
                except Exception as e:
                    logger.error(f"Error al obtener clientes: {e}")
                    self.page.invoke_async(
                        lambda: self.show_message(f"Error: {e}", is_error=True)
                    )
                finally:
                    # Ocultar progreso
                    self.page.invoke_async(
                        lambda: self.set_progress_visible(False)
                    )
            
            # Iniciar en segundo plano
            threading.Thread(target=background_task).start()
            
        except Exception as e:
            logger.error(f"Error al mostrar clientes para editar: {e}")
            self.progress_ring.visible = False
            self.show_message(f"Error: {e}", is_error=True)
            self.page.update()
    
    def mostrar_lista_clientes_edicion(self, clientes):
        """Muestra un diálogo con la lista de clientes para editar."""
        if not clientes:
            self.show_message("No hay pedidos registrados hoy")
            return
        
        # Crear contenido del diálogo
        dlg_content = ft.ListView(ft.Column(
            expand=True,
            spacing=10,
            padding=10,
            ),auto_scroll=True
              # Habilitar scroll
        )
        
        for cliente in clientes:
            dlg_content.controls.append(
                ft.ElevatedButton(
                    cliente,
                    icon=ft.icons.EDIT,
                    style=ft.ButtonStyle(
                        padding=15,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    width=300,
                    on_click=lambda e, c=cliente: self.abrir_edicion_cliente(c)
                )
            )
        
        # Crear diálogo
        dlg = ft.AlertDialog(
            title=ft.Text("Seleccione un cliente para editar"),
            content=ft.Container(
                [dlg_content],
                height=400,
                width=350
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: self.cerrar_dialogo(dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        # Mostrar diálogo
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
    
    def abrir_edicion_cliente(self, cliente):
        """Abre la pantalla de edición de pedidos de un cliente."""
        try:
            # Mostrar indicador de progreso
            self.progress_ring.visible = True
            self.page.update()
            
            # Cerrar diálogo anterior si está abierto
            if self.page.dialog and self.page.dialog.open:
                self.page.dialog.open = False
            
            # Guardar el cliente actual para futuras operaciones
            self.cliente_actual_edicion = cliente
            
            # Ejecutar en segundo plano
            def background_task():
                try:
                    # Obtener pedidos del cliente
                    pedidos = Pedido.get_by_cliente(cliente, date.today())
                    
                    # Actualizar UI en el hilo principal
                    self.page.invoke_async(
                        lambda: self.mostrar_formulario_edicion(cliente, pedidos)
                    )
                except Exception as e:
                    logger.error(f"Error al obtener pedidos: {e}")
                    self.page.invoke_async(
                        lambda: self.show_message(f"Error: {e}", is_error=True)
                    )
                finally:
                    # Ocultar progreso
                    self.page.invoke_async(
                        lambda: self.set_progress_visible(False)
                    )
            
            # Iniciar en segundo plano
            threading.Thread(target=background_task).start()
            
        except Exception as e:
            logger.error(f"Error al abrir edición para {cliente}: {e}")
            self.progress_ring.visible = False
            self.show_message(f"Error: {e}", is_error=True)
            self.page.update()
    
    def mostrar_formulario_edicion(self, cliente, pedidos):
        """Muestra un formulario para editar los pedidos de un cliente."""
        if not pedidos:
            self.show_message("No hay pedidos para este cliente hoy")
            return
        
        # Lista para mantener los controles y datos de edición
        forms = []
        
        # Crear contenido del diálogo
        dlg_content = ft.ListView(ft.Column(
            expand=True,
            spacing=15,
            padding=10,
            auto_scroll=True)
              # Habilitar scroll
        )
        
        for pedido in pedidos:
            # Crear controles para editar este pedido
            cantidad_field = ft.TextField(
                label="Cantidad",
                value=str(pedido.cantidad),
                keyboard_type=ft.KeyboardType.NUMBER,
                width=150
            )
            
            costo_field = ft.TextField(
                label="Costo",
                value=str(pedido.costo),
                keyboard_type=ft.KeyboardType.NUMBER,
                width=150
            )
            
            # Guardar referencia para edición
            forms.append((pedido.id, cantidad_field, costo_field))
            
            # Crear tarjeta para este pedido
            card = ft.Card(
                content=ft.Container(
                    ft.Column([
                        ft.Row([
                            ft.Icon(ft.icons.SHOPPING_BAG, color=ft.Colors.BLUE),
                            ft.Text(pedido.producto, 
                                  weight=ft.FontWeight.BOLD,
                                  size=16)
                        ]),
                        ft.Text(f"Zona: {pedido.zona}"),
                        ft.Row([
                            [cantidad_field],
                            ft.Container(width=10),
                            [costo_field]
                        ]),
                        ft.ElevatedButton(
                            "Eliminar pedido",
                            icon=ft.icons.DELETE,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.RED,
                                color=ft.Colors.WHITE,
                                padding=10,
                                shape=ft.RoundedRectangleBorder(radius=8),
                            ),
                            on_click=lambda e, pid=pedido.id: self.confirmar_eliminar_pedido(pid)
                        )
                    ], spacing=10),
                    padding=15
                ),
                elevation=3
            )
            
            dlg_content.controls.append(card)
        
        # Crear diálogo
        dlg = ft.AlertDialog(
            title=ft.Text(f"Editar pedidos de {cliente}"),
            content=ft.Container(
                [dlg_content],
                height=500,
                width=400
            ),
            actions=[
                ft.ElevatedButton(
                    "Guardar",
                    icon=ft.icons.SAVE,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.GREEN,
                        color=ft.Colors.WHITE,
                        padding=10,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=lambda e: self.guardar_cambios_pedidos(forms, cliente, dlg)
                ),
                ft.TextButton("Cancelar", on_click=lambda e: self.cerrar_dialogo(dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        # Mostrar diálogo
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
    
    def guardar_cambios_pedidos(self, forms, cliente, dialogo):
        """Guarda los cambios realizados a los pedidos."""
        try:
            # Mostrar indicador de progreso
            self.progress_ring.visible = True
            self.page.update()
            
            # Ejecutar en segundo plano
            def background_task():
                try:
                    for pedido_id, cantidad_field, costo_field in forms:
                        try:
                            # Obtener pedido
                            pedido = Pedido.get_by_id(pedido_id)
                            if not pedido:
                                continue
                            
                            # Obtener valores
                            nueva_cantidad = int(cantidad_field.value)
                            nuevo_costo = float(costo_field.value)
                            
                            # Validar valores
                            if nueva_cantidad <= 0 or nuevo_costo <= 0:
                                raise ValueError("Los valores deben ser mayores a 0")
                            
                            # Verificar si hubo cambios
                            if nueva_cantidad != pedido.cantidad or nuevo_costo != pedido.costo:
                                # Obtener producto para actualizar stock
                                producto = Producto.get_by_name(pedido.producto)
                                
                                if producto:
                                    # Calcular diferencia de stock
                                    diff_cantidad = pedido.cantidad - nueva_cantidad
                                    if diff_cantidad != 0:
                                        producto.update_stock(diff_cantidad)
                                
                                # Actualizar pedido
                                pedido.cantidad = nueva_cantidad
                                pedido.costo = nuevo_costo
                                pedido.save()
                        except ValueError as ve:
                            raise ValueError(f"Error en pedido {pedido_id}: {str(ve)}")
                    
                    # Actualizar UI en el hilo principal
                    self.page.invoke_async(
                        lambda: self.finalizar_guardar_cambios(dialogo)
                    )
                except Exception as e:
                    logger.error(f"Error al guardar cambios: {e}")
                    self.page.invoke_async(

                lambda: self.show_message(f"Error al guardar: {e}", is_error=True)
                    )
                finally:
                    # Ocultar progreso
                    self.page.invoke_async(
                        lambda: self.set_progress_visible(False)
                    )
            
            # Iniciar en segundo plano
            threading.Thread(target=background_task).start()
            
        except Exception as e:
            logger.error(f"Error al guardar cambios de pedidos: {e}")
            self.progress_ring.visible = False
            self.show_message(f"Error: {e}", is_error=True)
            self.page.update()
    
    def finalizar_guardar_cambios(self, dialogo):
        """Finaliza el proceso de guardar cambios."""
        self.cerrar_dialogo(dialogo)
        self.show_message("Cambios guardados exitosamente")
    
    def confirmar_eliminar_pedido(self, pedido_id):
        """Muestra un diálogo de confirmación para eliminar un pedido."""
        dlg_confirm = ft.AlertDialog(
            title=ft.Text("Confirmar eliminación"),
            content=ft.Text("¿Está seguro de que desea eliminar este pedido? Esta acción no se puede deshacer."),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: self.cerrar_dialogo(dlg_confirm)),
                ft.ElevatedButton(
                    "Eliminar",
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.RED,
                        color=ft.Colors.WHITE
                    ),
                    on_click=lambda e: self.eliminar_pedido_confirmado(pedido_id, dlg_confirm)
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        # Mostrar diálogo de confirmación
        self.page.dialog = dlg_confirm
        dlg_confirm.open = True
        self.page.update()
    
    def eliminar_pedido_confirmado(self, pedido_id, dialogo):
        """Elimina un pedido después de la confirmación."""
        try:
            # Mostrar indicador de progreso
            self.progress_ring.visible = True
            self.page.update()
            
            # Cerrar diálogo de confirmación
            self.cerrar_dialogo(dialogo)
            
            # Ejecutar en segundo plano
            def background_task():
                try:
                    # Eliminar el pedido
                    resultado = Pedido.delete(pedido_id)
                    
                    # Actualizar UI en el hilo principal
                    if resultado:
                        self.page.invoke_async(
                            lambda: self.finalizar_eliminar_pedido()
                        )
                    else:
                        self.page.invoke_async(
                            lambda: self.show_message("No se pudo eliminar el pedido")
                        )
                except Exception as e:
                    logger.error(f"Error al eliminar pedido: {e}")
                    self.page.invoke_async(
                        lambda: self.show_message(f"Error: {e}", is_error=True)
                    )
                finally:
                    # Ocultar progreso
                    self.page.invoke_async(
                        lambda: self.set_progress_visible(False)
                    )
            
            # Iniciar en segundo plano
            threading.Thread(target=background_task).start()
            
        except Exception as e:
            logger.error(f"Error al eliminar pedido {pedido_id}: {e}")
            self.progress_ring.visible = False
            self.show_message(f"Error: {e}", is_error=True)
            self.page.update()
    
    def finalizar_eliminar_pedido(self):
        """Finaliza el proceso de eliminar un pedido."""
        self.show_message("Pedido eliminado correctamente")
        
        # Refrescar la vista si hay un cliente en edición
        if hasattr(self, 'cliente_actual_edicion') and self.cliente_actual_edicion:
            self.abrir_edicion_cliente(self.cliente_actual_edicion)
    
    # ======== Funciones para estadísticas y reportes ========
    
    def generar_productos_por_dia(self, e):
        """Genera un PDF con los productos vendidos en el día."""
        try:
            # Mostrar indicador de progreso
            self.progress_ring.visible = True
            self.page.update()
            
            # Ejecutar en segundo plano
            def background_task():
                try:
                    filename = PDFGenerator.generar_productos_por_dia()
                    
                    # Actualizar UI en el hilo principal
                    if filename:
                        self.page.invoke_async(
                            lambda: self.show_message(f"Reporte generado: {Path(filename).name}")
                        )
                    else:
                        self.page.invoke_async(
                            lambda: self.show_message("No hay datos para generar el reporte")
                        )
                except Exception as e:
                    logger.error(f"Error al generar reporte: {e}")
                    self.page.invoke_async(
                        lambda: self.show_message(f"Error: {e}", is_error=True)
                    )
                finally:
                    # Ocultar progreso
                    self.page.invoke_async(
                        lambda: self.set_progress_visible(False)
                    )
            
            # Iniciar en segundo plano
            threading.Thread(target=background_task).start()
            
        except Exception as e:
            logger.error(f"Error al generar reporte de productos por día: {e}")
            self.progress_ring.visible = False
            self.show_message(f"Error: {e}", is_error=True)
            self.page.update()
    
    def mostrar_estadisticas(self, e):
        """Muestra un panel de estadísticas con diferentes métricas."""
        try:
            # Mostrar indicador de progreso
            self.progress_ring.visible = True
            self.page.update()
            
            # Ejecutar en segundo plano
            def background_task():
                try:
                    # Obtener datos para las estadísticas
                    ventas_diarias = Pedido.get_ventas_diarias(30)
                    
                    # Actualizar UI en el hilo principal
                    self.page.invoke_async(
                        lambda: self.mostrar_panel_estadisticas(ventas_diarias)
                    )
                except Exception as e:
                    logger.error(f"Error al obtener estadísticas: {e}")
                    self.page.invoke_async(
                        lambda: self.show_message(f"Error: {e}", is_error=True)
                    )
                finally:
                    # Ocultar progreso
                    self.page.invoke_async(
                        lambda: self.set_progress_visible(False)
                    )
            
            # Iniciar en segundo plano
            threading.Thread(target=background_task).start()
            
        except Exception as e:
            logger.error(f"Error al mostrar estadísticas: {e}")
            self.progress_ring.visible = False
            self.show_message(f"Error: {e}", is_error=True)
            self.page.update()
    
    def mostrar_panel_estadisticas(self, ventas_diarias):
        """Muestra un panel con estadísticas de ventas."""
        # Calcular total de ventas
        total_ventas = sum(venta['total'] for venta in ventas_diarias) if ventas_diarias else 0
        
        # Crear contenido del diálogo
        dlg_content = ft.Column(ft.Column(
            spacing=20,
            auto_scroll=True)
            
        )
        
        # 1. Sección: Resumen de ventas
        resumen_section = ft.Container(
            ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.TRENDING_UP, color=ft.Colors.BLUE, size=30),
                    ft.Text("📊 Resumen de Ventas", 
                           size=20, 
                           weight=ft.FontWeight.BOLD)
                ]),
                ft.Card(
                    content=ft.Container(
                        ft.Column([
                            ft.Text("Total Facturado (30 días)", 
                                   weight=ft.FontWeight.BOLD),
                            ft.Container(
                                ft.Text(f"${total_ventas:.2f}", 
                                      size=24, 
                                      color=ft.Colors.WHITE,
                                      weight=ft.FontWeight.BOLD),
                                bgcolor=ft.Colors.GREEN,
                                padding=20,
                                alignment=ft.alignment.center
                            )
                        ]),
                        padding=20
                    )
                )
            ]),
            padding=10
        )
        dlg_content.controls.append(resumen_section)
        
        # 2. Sección: Ventas por día
        ventas_section = ft.Container(
            ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.DATE_RANGE, color=ft.Colors.BLUE, size=30),
                    ft.Text("📅 Ventas por Día", 
                           size=20, 
                           weight=ft.FontWeight.BOLD)
                ]),
                ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Fecha", weight=ft.FontWeight.BOLD)),
                        ft.DataColumn(ft.Text("Total", weight=ft.FontWeight.BOLD)),
                        ft.DataColumn(ft.Text("Variación", weight=ft.FontWeight.BOLD))
                    ],
                    rows=self.generar_filas_tabla_ventas(ventas_diarias[:15])
                )
            ]),
            padding=10
        )
        dlg_content.controls.append(ventas_section)
        
        # 3. Sección: Botón para generar PDF
        dlg_content.controls.append(
            ft.Container(
                ft.ElevatedButton(
                    "Exportar a PDF",
                    icon=ft.icons.PICTURE_AS_PDF,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.BLUE,
                        color=ft.Colors.WHITE,
                        padding=15,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=self.exportar_estadisticas_pdf
                ),
                alignment=ft.alignment.center
            )
        )
        
        # Crear diálogo
        dlg = ft.AlertDialog(
            title=ft.Text("Estadísticas y Análisis"),
            content=ft.Container(ft.Column(
                [dlg_content],

                auto_scroll=True ),                height=500,
                width=500,
                 # Habilitar scroll
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda e: self.cerrar_dialogo(dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        # Mostrar diálogo
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
    
    def generar_filas_tabla_ventas(self, ventas_diarias):
        """Genera las filas para la tabla de ventas diarias."""
        rows = []
        ultimo_valor = None
        
        for venta in ventas_diarias:
            fecha_str = venta['dia']
            if hasattr(fecha_str, 'strftime'):
                fecha_str = fecha_str.strftime('%d/%m/%Y')
            
            total = venta['total']
            variacion = "---"
            color = ft.Colors.BLACK
            
            if ultimo_valor is not None:
                if total > ultimo_valor:
                    porcentaje = ((total/ultimo_valor)-1)*100
                    variacion = f"↑ {porcentaje:.1f}%"
                    color = ft.Colors.GREEN
                elif total < ultimo_valor:
                    porcentaje = ((ultimo_valor/total)-1)*100
                    variacion = f"↓ {porcentaje:.1f}%"
                    color = ft.Colors.RED
                else:
                    variacion = "= 0%"
            
            ultimo_valor = total
            
            rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(fecha_str)),
                    ft.DataCell(ft.Text(f"${total:.2f}")),
                    ft.DataCell(ft.Text(variacion, color=color))
                ])
            )
        
        return rows
    
    def exportar_estadisticas_pdf(self, e):
        """Exporta las estadísticas actuales a un PDF."""
        try:
            # Mostrar indicador de progreso
            self.progress_ring.visible = True
            self.page.update()
            
            # Ejecutar en segundo plano
            def background_task():
                try:
                    filename = PDFGenerator.generar_estadisticas()
                    
                    # Actualizar UI en el hilo principal
                    if filename:
                        self.page.invoke_async(
                            lambda: self.show_message(f"Estadísticas exportadas: {Path(filename).name}")
                        )
                    else:
                        self.page.invoke_async(
                            lambda: self.show_message("No se pudieron exportar las estadísticas")
                        )
                except Exception as e:
                    logger.error(f"Error al exportar estadísticas: {e}")
                    self.page.invoke_async(
                        lambda: self.show_message(f"Error: {e}", is_error=True)
                    )
                finally:
                    # Ocultar progreso
                    self.page.invoke_async(
                        lambda: self.set_progress_visible(False)
                    )
            
            # Iniciar en segundo plano
            threading.Thread(target=background_task).start()
            
        except Exception as e:
            logger.error(f"Error al exportar estadísticas a PDF: {e}")
            self.progress_ring.visible = False
            self.show_message(f"Error: {e}", is_error=True)
            self.page.update()
    
    # ======== Funciones para importación de CSV ========
    
    def subir_csv(self, e):
        """Abre un diálogo para subir un archivo CSV de productos."""
        # Mostrar mensaje informativo
        self.show_message("Seleccione un archivo CSV para importar productos")
        
        # Preparar file picker
        self.file_picker.pick_files(
            allowed_extensions=["csv"],
            allow_multiple=False,
            dialog_title="Seleccionar archivo CSV"
        )
    
    def on_file_picked(self, e: ft.FilePickerResultEvent):
        """Maneja el resultado de seleccionar un archivo."""
        if not e.files:
            return  # Usuario canceló la selección
            
        try:
            # Mostrar indicador de progreso
            self.progress_ring.visible = True
            self.page.update()
            
            # Obtener archivo seleccionado
            file_path = e.files[0].path
            file_name = e.files[0].name
            
            # Mostrar nombre del archivo seleccionado
            self.show_message(f"Procesando archivo: {file_name}")
            
            # Ejecutar en segundo plano
            def background_task():
                try:
                    # Leer contenido del archivo
                    logger.info(f"Leyendo archivo CSV: {file_path}")
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    # Verificar que el archivo tenga contenido
                    if not content:
                        self.page.invoke_async(
                            lambda: self.show_message("El archivo está vacío", is_error=True)
                        )
                        return
                    
                    # Procesar el contenido
                    logger.info(f"Procesando CSV con tamaño: {len(content)} bytes")
                    success, message, actualizados, creados = CSVHandler.procesar_csv_productos(content)
                    
                    # Mostrar detalles del proceso
                    logger.info(f"Resultado del procesamiento: {success}, {message}, actualizados: {actualizados}, creados: {creados}")
                    
                    # Actualizar UI en el hilo principal
                    if success:
                        self.page.invoke_async(
                            lambda: self.show_message(f"✅ {message}")
                        )
                    else:
                        self.page.invoke_async(
                            lambda: self.show_message(f"Error: {message}", is_error=True)
                        )
                except Exception as e:
                    logger.error(f"Error al procesar CSV: {e}", exc_info=True)
                    self.page.invoke_async(
                        lambda: self.show_message(f"Error al procesar archivo: {str(e)}", is_error=True)
                    )
                finally:
                    # Ocultar progreso
                    self.page.invoke_async(
                        lambda: self.set_progress_visible(False)
                    )
            
            # Iniciar en segundo plano
            threading.Thread(target=background_task).start()
            
        except Exception as e:
            logger.error(f"Error al procesar el archivo CSV: {e}", exc_info=True)
            self.progress_ring.visible = False
            self.show_message(f"Error: {e}", is_error=True)
            self.page.update()
    
    # ======== Funciones de interfaz y utilidad ========
    
    def show_message(self, mensaje, is_error=False):
        """Muestra un mensaje en un banner."""
        color = ft.Colors.RED if is_error else ft.Colors.BLUE
        
        self.page.show_snack_bar(
            ft.SnackBar(
                content=ft.Text(mensaje, color=ft.Colors.WHITE),
                bgcolor=color,
                action="OK",
                action_color=ft.Colors.WHITE
            )
        )
    
    def show_settings(self, e):
        """Muestra el diálogo de configuración."""
        dlg = ft.AlertDialog(
            title=ft.Text("Configuración"),
            content=ft.Column([
                ft.Text("Esta función estará disponible en próximas versiones."),
                ft.Container(height=10),
                ft.Text("DirectiApp v1.0.0", italic=True, color=ft.Colors.GREY)
            ], spacing=10, width=400),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda e: self.cerrar_dialogo(dlg)),
            ]
        )
        
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
    
    def show_about(self, e):
        """Muestra información sobre la aplicación."""
        dlg = ft.AlertDialog(
            title=ft.Text("Acerca de DistriApp"),
            content=ft.Column([
                ft.Text("DistriApp - Sistema de Gestión de Distribución", weight=ft.FontWeight.BOLD),
                ft.Container(height=10),
                ft.Text("Desarrollado con Python, Flet y MySQL"),
                ft.Container(height=10),
                ft.Text("Versión 1.0.0"),
                ft.Container(height=20),
                ft.Text("© 2025 - Todos los derechos reservados", color=ft.Colors.GREY)
            ], spacing=5, width=400),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda e: self.cerrar_dialogo(dlg)),
            ]
        )
        
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

def main(page: ft.Page):
    """Función principal que inicia la aplicación."""
    print("Iniciando DistriApp...")
    app = DistriAppV3(page)
    print("DistriApp inicializada correctamente. Si no ves la interfaz, visita http://localhost:8550")
    return app

if __name__ == "__main__":
    print("Iniciando servidor Flet...")
    ft.app(target=main, view=ft.AppView.WEB_BROWSER)
    print("Servidor Flet finalizado.")                