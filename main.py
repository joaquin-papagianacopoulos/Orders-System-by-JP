from kivymd.app import MDApp
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.list import OneLineListItem, TwoLineListItem
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.screen import Screen
from kivymd.uix.scrollview import MDScrollView
from kivy.metrics import dp
import mysql.connector
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle
from functools import partial
from reportlab.lib import colors
import os
from fpdf import FPDF
from datetime import datetime
import csv
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.config import Config
from kivy.utils import platform
import sys

try:
    from android.permissions import request_permissions, Permission
    request_permissions([Permission.INTERNET, Permission.WRITE_EXTERNAL_STORAGE])
except ImportError:
    print("No se están gestionando permisos porque no estamos en Android.")


def check_permissions():
    request_permissions([
        Permission.INTERNET,
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.READ_EXTERNAL_STORAGE
    ])

def get_app_dir():
    """Obtiene el directorio adecuado para almacenar datos de la aplicación"""
    if platform == 'android':
        try:
            from android.storage import app_storage_path
            return app_storage_path()
        except ImportError:
            print("No se pudo importar android.storage (no estás en Android o falta dependencia)")
            return os.getcwd()
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_db_path():
    app_dir = get_app_dir()
    return os.path.join(app_dir, conectar_bd())

# Evitar que escanee archivos del sistema
Config.set('kivy', 'log_level', 'warning')
Config.set('kivy', 'log_dir', 'logs')
Config.set('kivy', 'log_name', 'kivy_%y-%m-%d_%_.txt')
Config.set('kivy', 'log_enable', 0)
# Desactivar círculos de contacto
Config.set('input', 'mouse', 'mouse,disable_multitouch')

import sqlite3

def conectar_bd():
    app_dir = get_app_dir()
    db_path = os.path.join(app_dir, 'distriapp.db')
    return sqlite3.connect(db_path)
def inicializar_bd():
    conn = conectar_bd()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE,
        costo REAL,
        precio_venta REAL,
        stock INTEGER DEFAULT 0
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente TEXT,
        producto TEXT,
        cantidad INTEGER,
        costo REAL,
        zona TEXT,
        fecha DATE DEFAULT (date('now'))
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE
    )''')
    
    conn.commit()
    cursor.close()
    conn.close()
def obtener_clientes(texto_ingresado):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT nombre FROM clientes WHERE nombre LIKE %s LIMIT 5", (f"%{texto_ingresado}%",))
    clientes = [cliente[0] for cliente in cursor.fetchall()]
    cursor.close()
    conn.close()
    return clientes

def obtener_productos(texto_ingresado):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT nombre FROM productos WHERE nombre LIKE %s LIMIT 5", (f"%{texto_ingresado}%",))
    productos = [producto[0] for producto in cursor.fetchall()]
    cursor.close()
    conn.close()
    return productos

def insertar_pedido(cliente, producto, cantidad, costo, zona):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pedidos (cliente, producto, cantidad, costo, zona) VALUES (%s, %s, %s, %s, %s)",
                   (cliente, producto, cantidad, costo, zona))
    conn.commit()
    cursor.close()
    conn.close()

def obtener_costo_producto(nombre_producto):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT costo FROM productos WHERE nombre = %s", (nombre_producto,))
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()
    return resultado[0] if resultado else ""

def obtener_stock_producto(nombre_producto):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT stock FROM productos WHERE nombre = %s", (nombre_producto,))
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()
    return resultado[0] if resultado else 0

# --- Funciones de utilidad ---
def mostrar_notificacion(mensaje):
    dialog = MDDialog(
        title="Notificación",
        text=mensaje,
        buttons=[MDFlatButton(text="OK", on_release=lambda x: dialog.dismiss())]
    )
    dialog.open()


def crear_menu_sugerencias(app, items, campo):
    menu_items = [
        {"text": item, "viewclass": "OneLineListItem", "on_release": lambda x=item: app.seleccionar_sugerencia(x, campo)}
        for item in items
    ]
    if hasattr(app, 'menu') and app.menu:
        app.menu.dismiss()
    app.menu = MDDropdownMenu(caller=campo, items=menu_items, width_mult=4)
    app.menu.open()

def actualizar_stock_desde_csv(archivo):
    conn = conectar_bd()
    cursor = conn.cursor()
    try:
        with open(archivo, 'r', encoding='utf-8-sig') as f:
            lector = csv.DictReader(f)
            required = {'nombre', 'costo', 'precio_venta', 'stock'}
            
            if not required.issubset(lector.fieldnames):
                missing = required - set(lector.fieldnames)
                raise ValueError(f"Faltan columnas: {', '.join(missing)}")

            for idx, fila in enumerate(lector, 2):
                try:
                    cursor.execute('''
                        INSERT INTO productos (nombre, costo, precio_venta, stock)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            costo = VALUES(costo),
                            precio_venta = VALUES(precio_venta),
                            stock = VALUES(stock)
                    ''', (
                        fila['nombre'].strip(),
                        float(fila['costo']),
                        float(fila['precio_venta']),
                        int(fila['stock'])
                    ))
                except Exception as e:
                    raise ValueError(f"Línea {idx}: {str(e)}")
                    
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def obtener_ventas_diarias():
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DATE(fecha) as dia, SUM(cantidad * costo) as total
        FROM pedidos
        GROUP BY dia
        ORDER BY dia DESC
        LIMIT 30
    ''')
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultados

class PedidoApp(MDApp):
    def build(self):
        inicializar_bd()
        self.menu = None
        self.productos_temporal = []
        
        self.screen = Screen()
        main_layout = MDBoxLayout(orientation='horizontal', spacing=20, padding=20)
        
        # Panel izquierdo
        left_panel = MDBoxLayout(orientation='vertical', size_hint=(0.4, 1), spacing=15, padding=(10, 10, 10, 10))
        self.cliente = MDTextField(hint_text='Cliente ✍️')
        self.cliente.bind(text=self.sugerir_clientes)
        
        self.producto = MDTextField(hint_text='Producto 🔍')
        self.producto.bind(text=self.sugerir_productos)
        
        self.cantidad = MDTextField(hint_text='Cantidad 🔢', input_filter='int')
        self.costo = MDTextField(hint_text='Costo 💲', input_filter='float')
        self.zona = MDRaisedButton(text='📍 Zona', on_release=self.mostrar_zonas)
        
        # Botones principales - Primera fila
        left_panel.add_widget(self.cliente)
        left_panel.add_widget(self.producto)
        left_panel.add_widget(self.cantidad)
        left_panel.add_widget(self.costo)
        left_panel.add_widget(self.zona)
        
        # Crear botones principales con MDBoxLayout para una mejor organización
        buttons_layout1 = MDBoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=dp(48))
        buttons_layout2 = MDBoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=dp(48))
        buttons_layout3 = MDBoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=dp(48))
        
        # Organizar botones en filas
        self.boton_registrar = MDRaisedButton(text='✅ Registrar', on_release=self.registrar_pedido, size_hint_x=0.5)
        self.boton_pedidos_hoy = MDRaisedButton(text='📄 Pedidos Hoy', on_release=self.ver_pedidos_dia, size_hint_x=0.5)
        buttons_layout1.add_widget(self.boton_registrar)
        buttons_layout1.add_widget(self.boton_pedidos_hoy)
        
        self.boton_modificar = MDRaisedButton(text='✏️ Modificar', on_release=self.mostrar_clientes_para_editar, size_hint_x=0.5)
        self.boton_csv = MDRaisedButton(text='📤 Subir CSV', on_release=self.mostrar_file_chooser, size_hint_x=0.5)
        buttons_layout2.add_widget(self.boton_modificar)
        buttons_layout2.add_widget(self.boton_csv)
        
        self.boton_estadisticas = MDRaisedButton(text='📊 Estadísticas', on_release=self.mostrar_estadisticas, size_hint_x=0.5)
        self.boton_productos_dia = MDRaisedButton(
            text='📦 PRODUCTOS POR DÍA', 
            on_release=self.generar_productos_por_dia,
            md_bg_color=(0.8, 0.2, 0.2, 1),  # Color rojo más discreto
            size_hint_x=0.5
        )
        buttons_layout3.add_widget(self.boton_estadisticas)
        buttons_layout3.add_widget(self.boton_productos_dia)
        
        left_panel.add_widget(buttons_layout1)
        left_panel.add_widget(buttons_layout2)
        left_panel.add_widget(buttons_layout3)

        # Panel derecho
        right_panel = MDBoxLayout(orientation='vertical', size_hint=(0.6, 1), padding=(10, 10, 10, 10))
        self.lista_productos = MDScrollView()
        self.contenedor_productos = MDBoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        self.contenedor_productos.bind(minimum_height=self.contenedor_productos.setter('height'))
        self.lista_productos.add_widget(self.contenedor_productos)
        right_panel.add_widget(self.lista_productos)
        
        # Botones de control
        controles = MDBoxLayout(size_hint_y=None, height=dp(60), spacing=10, padding=(0, 10, 0, 0))
        for btn in [
            MDRaisedButton(text='✏️ Editar', on_release=self.editar_orden_actual, size_hint_x=1/3),
            MDRaisedButton(text='🗑️ Vaciar', on_release=self.vaciar_orden_actual, size_hint_x=1/3),
            MDRaisedButton(text='🚀 Enviar', on_release=self.guardar_pedido_completo, size_hint_x=1/3)
        ]:
            controles.add_widget(btn)
        right_panel.add_widget(controles)

        main_layout.add_widget(left_panel)
        main_layout.add_widget(right_panel)
        self.screen.add_widget(main_layout)
        return self.screen

    def mostrar_file_chooser(self, instance):
        content = MDBoxLayout(orientation='vertical')
        file_chooser = FileChooserListView(filters=['*.csv'])
        btn = MDRaisedButton(
            text="Cargar CSV",
            on_release=lambda x: self.procesar_csv(file_chooser.selection, popup))
        
        content.add_widget(file_chooser)
        content.add_widget(btn)
        popup = Popup(title="Seleccionar CSV", content=content, size_hint=(0.9, 0.9))
        popup.open()

    def editar_orden_actual(self, instance):
        if not self.productos_temporal:
            mostrar_notificacion("⚠️ No hay productos en la orden actual")
            return
        
        # Crear un BoxLayout con padding superior adicional para evitar superposición con el título
        scroll_container = MDScrollView(size_hint=(1, None), height=dp(300))
        main_container = MDBoxLayout(orientation='vertical', spacing=10, size_hint_y=None)
        main_container.bind(minimum_height=main_container.setter('height'))
        
        # Añadir un espacio vacío en la parte superior para evitar superposición con el título
        spacer = MDBoxLayout(size_hint_y=None, height=dp(20))
        main_container.add_widget(spacer)
        
        for producto in self.productos_temporal:
            item = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(70), padding=(5, 5, 5, 5))
            
            # Contenedor para el texto con padding superior
            texto_container = MDBoxLayout(orientation='vertical', size_hint_x=0.8, padding=(0, 10, 0, 0))
            texto_container.add_widget(TwoLineListItem(
                text=producto['producto'],
                secondary_text=f"Cant: {producto['cantidad']} | Costo: ${producto['costo']}",
                divider=None,
                _no_ripple_effect=True
            ))
            item.add_widget(texto_container)
            
            btn_eliminar = MDIconButton(
                icon='delete',
                on_release=partial(self.eliminar_de_orden_actual, producto),
                size_hint_x=0.2
            )
            item.add_widget(btn_eliminar)
            main_container.add_widget(item)
        
        scroll_container.add_widget(main_container)
        
        self.dialog_edicion_actual = MDDialog(
            title="Editar orden actual",
            type="custom",
            content_cls=scroll_container,
            buttons=[
                MDFlatButton(text="Cerrar", on_release=lambda x: self.dialog_edicion_actual.dismiss())
            ],
            size_hint=(0.9, None),
            height=dp(400)
        )
        self.dialog_edicion_actual.open()

    def eliminar_de_orden_actual(self, producto, instance):
        self.productos_temporal.remove(producto)
        self.actualizar_lista_temporal()
        if hasattr(self, 'dialog_edicion_actual') and self.dialog_edicion_actual:
            self.dialog_edicion_actual.dismiss()
        mostrar_notificacion("Producto eliminado de la orden actual")

    def vaciar_orden_actual(self, instance):
        self.productos_temporal.clear()
        self.contenedor_productos.clear_widgets()
        mostrar_notificacion("Orden vaciada completamente")

    def guardar_pedido_completo(self, instance):
        if not self.productos_temporal:
            mostrar_notificacion("⚠️ No hay productos en la orden")
            return
            
        cliente = self.cliente.text.strip()
        zona = self.zona.text.strip()
        
        if not cliente:
            mostrar_notificacion("⚠️ Debe seleccionar un cliente")
            return
        
        if zona == "📍 Zona":
            mostrar_notificacion("⚠️ Debe seleccionar una zona")
            return
        
        try:
            for producto in self.productos_temporal:
                insertar_pedido(
                    cliente=cliente,
                    producto=producto['producto'],
                    cantidad=producto['cantidad'],
                    costo=producto['costo'],
                    zona=zona
                )
            mostrar_notificacion("✅ Pedido guardado exitosamente!")
            self.vaciar_orden_actual(None)
        except Exception as e:
            mostrar_notificacion(f"❌ Error al guardar: {str(e)}")

    def actualizar_lista_temporal(self):
        self.contenedor_productos.clear_widgets()
        for producto in self.productos_temporal:
            item = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(60), padding=(0, 10, 0, 0))
            
            # Crear un contenedor box para el TwoLineListItem con padding superior
            texto_container = MDBoxLayout(orientation='vertical', size_hint_x=0.85, padding=(0, 8, 0, 0))
            
            # Agregar el TwoLineListItem al contenedor
            lista_item = TwoLineListItem(
                text=producto['producto'],
                secondary_text=f"Cant: {producto['cantidad']} | Costo: ${producto['costo']}",
                divider=None,
                _no_ripple_effect=True
            )
            
            texto_container.add_widget(lista_item)
            item.add_widget(texto_container)
            
            # Botón eliminar
            btn_eliminar = MDIconButton(
                icon="delete",
                theme_text_color="Error",
                on_release=partial(self.eliminar_de_orden_actual, producto),
                size_hint_x=0.15
            )
            item.add_widget(btn_eliminar)
            
            self.contenedor_productos.add_widget(item)

    def mostrar_estadisticas(self, instance):
        """Muestra un panel completo de estadísticas con diferentes métricas y gráficos"""
        try:
            # Crear un contenedor con tabs para diferentes tipos de estadísticas
            from kivymd.uix.tab import MDTabsBase
            from kivymd.uix.floatlayout import MDFloatLayout
            
            class Tab(MDFloatLayout, MDTabsBase):
                '''Clase para implementar cada pestaña'''
                pass
            
            # Obtener datos para las estadísticas
            datos_ventas = self.obtener_datos_estadisticas()
            
            # Creamos un contenedor principal con scroll
            scroll_container = MDScrollView(size_hint=(1, None), height=dp(500))
            main_container = MDBoxLayout(orientation='vertical', spacing=10, size_hint_y=None)
            main_container.bind(minimum_height=main_container.setter('height'))
            
            # --- Sección 1: Resumen de ventas ---
            seccion_resumen = MDBoxLayout(orientation='vertical', size_hint_y=None, height=dp(200), padding=(10, 10, 10, 10))
            
            # Título de la sección
            titulo_resumen = MDBoxLayout(size_hint_y=None, height=dp(40))
            titulo_resumen.add_widget(OneLineListItem(
                text="📊 Resumen de Ventas",
                font_style="H6",
                divider=None
            ))
            seccion_resumen.add_widget(titulo_resumen)
            
            # Datos del resumen en una cuadrícula
            datos_grid = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(150))
            
            # Obtener datos para el resumen
            total_ventas, ganancia_total, prod_mas_vendidos = datos_ventas['resumen']
            
            # Columna 1: Total Facturado
            col1 = MDBoxLayout(orientation='vertical', padding=(5, 5, 5, 5))
            col1.add_widget(OneLineListItem(text="Total Facturado", divider=None))
            col1.add_widget(MDRaisedButton(
                text=f"${total_ventas:.2f}",
                size_hint=(1, 0.6),
                md_bg_color=(0.2, 0.6, 0.2, 1)
            ))
            datos_grid.add_widget(col1)
            
            # Columna 2: Ganancia
            col2 = MDBoxLayout(orientation='vertical', padding=(5, 5, 5, 5))
            col2.add_widget(OneLineListItem(text="Ganancia Total", divider=None))
            col2.add_widget(MDRaisedButton(
                text=f"${ganancia_total:.2f}",
                size_hint=(1, 0.6),
                md_bg_color=(0.2, 0.4, 0.8, 1)
            ))
            datos_grid.add_widget(col2)
            
            # Columna 3: Productos Vendidos - Calculamos la suma total de cantidades
            col3 = MDBoxLayout(orientation='vertical', padding=(5, 5, 5, 5))
            col3.add_widget(OneLineListItem(text="Productos Vendidos", divider=None))
            
            # Calcular total de productos vendidos de forma segura
            total_unidades = 0
            for producto_info in prod_mas_vendidos:
                if len(producto_info) >= 2:  # Asegurarse de que hay al menos 2 elementos
                    total_unidades += producto_info[1]  # El segundo elemento debería ser la cantidad
            
            col3.add_widget(MDRaisedButton(
                text=f"{total_unidades} unidades",
                size_hint=(1, 0.6),
                md_bg_color=(0.8, 0.4, 0.2, 1)
            ))
            datos_grid.add_widget(col3)
            
            seccion_resumen.add_widget(datos_grid)
            main_container.add_widget(seccion_resumen)
            
            # Separador
            separador1 = MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=(0.7, 0.7, 0.7, 1))
            main_container.add_widget(separador1)
            
            # --- Sección 2: Productos más vendidos ---
            seccion_productos = MDBoxLayout(orientation='vertical', size_hint_y=None, height=dp(250), padding=(10, 10, 10, 10))
            
            # Título de la sección
            titulo_productos = MDBoxLayout(size_hint_y=None, height=dp(40))
            titulo_productos.add_widget(OneLineListItem(
                text="🏆 Productos Más Vendidos",
                font_style="H6",
                divider=None
            ))
            seccion_productos.add_widget(titulo_productos)
            
            # Lista de productos más vendidos
            lista_productos = MDBoxLayout(orientation='vertical', size_hint_y=None, height=dp(200))
            
            # Encabezados
            encabezados = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30))
            encabezados.add_widget(MDLabel(text="Producto", size_hint_x=0.5))
            encabezados.add_widget(MDLabel(text="Cantidad", size_hint_x=0.25))
            encabezados.add_widget(MDLabel(text="Ingresos", size_hint_x=0.25))
            lista_productos.add_widget(encabezados)
            
            # Mostrar los 5 productos más vendidos
            for idx, producto_info in enumerate(datos_ventas['productos_top'][:5]):
                if len(producto_info) >= 3:  # Verificar que tiene al menos 3 elementos
                    producto, cantidad, ingreso = producto_info
                    item = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30), 
                                    md_bg_color=(0.9, 0.9, 0.9, 1) if idx % 2 == 0 else (1, 1, 1, 1))
                    item.add_widget(MDLabel(text=producto, size_hint_x=0.5))
                    item.add_widget(MDLabel(text=str(cantidad), size_hint_x=0.25))
                    item.add_widget(MDLabel(text=f"${ingreso:.2f}", size_hint_x=0.25))
                    lista_productos.add_widget(item)
            
            seccion_productos.add_widget(lista_productos)
            main_container.add_widget(seccion_productos)
            
            # Separador
            separador2 = MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=(0.7, 0.7, 0.7, 1))
            main_container.add_widget(separador2)
            
            # --- Sección 3: Ventas por día ---
            seccion_dias = MDBoxLayout(orientation='vertical', size_hint_y=None, height=dp(250), padding=(10, 10, 10, 10))
            
            # Título de la sección
            titulo_dias = MDBoxLayout(size_hint_y=None, height=dp(40))
            titulo_dias.add_widget(OneLineListItem(
                text="📅 Ventas por Día",
                font_style="H6",
                divider=None
            ))
            seccion_dias.add_widget(titulo_dias)
            
            # Lista de ventas por día
            lista_dias = MDBoxLayout(orientation='vertical', size_hint_y=None, height=dp(200))
            
            # Encabezados
            encabezados_dias = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30))
            encabezados_dias.add_widget(MDLabel(text="Fecha", size_hint_x=0.33))
            encabezados_dias.add_widget(MDLabel(text="Ventas", size_hint_x=0.33))
            encabezados_dias.add_widget(MDLabel(text="Variación", size_hint_x=0.34))
            lista_dias.add_widget(encabezados_dias)
            
            # Mostrar las ventas de los últimos 7 días
            ventas_dias = datos_ventas.get('ventas_dias', [])
            ultimo_valor = None
            
            for idx, dia_info in enumerate(ventas_dias[:7]):  # Limitar a 7 días
                if len(dia_info) >= 2:  # Verificar que tiene al menos 2 elementos
                    fecha, total = dia_info
                    variacion = "---"
                    color = (0, 0, 0, 1)  # Negro por defecto
                    
                    if ultimo_valor is not None:
                        if total > ultimo_valor:
                            variacion = f"↑ {((total/ultimo_valor)-1)*100:.1f}%"
                            color = (0, 0.7, 0, 1)  # Verde para aumento
                        elif total < ultimo_valor:
                            variacion = f"↓ {((ultimo_valor/total)-1)*100:.1f}%"
                            color = (0.7, 0, 0, 1)  # Rojo para disminución
                        else:
                            variacion = "= 0%"
                            
                    ultimo_valor = total
                    
                    item = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30),
                                     md_bg_color=(0.9, 0.9, 0.9, 1) if idx % 2 == 0 else (1, 1, 1, 1))
                    item.add_widget(MDLabel(text=fecha.strftime('%d/%m/%Y'), size_hint_x=0.33))
                    item.add_widget(MDLabel(text=f"${total:.2f}", size_hint_x=0.33))
                    variacion_label = MDLabel(text=variacion, size_hint_x=0.34, theme_text_color="Custom", 
                                            text_color=color)
                    item.add_widget(variacion_label)
                    lista_dias.add_widget(item)
            
            seccion_dias.add_widget(lista_dias)
            main_container.add_widget(seccion_dias)
            
            # Separador
            separador3 = MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=(0.7, 0.7, 0.7, 1))
            main_container.add_widget(separador3)
            
            # --- Sección 4: Predicciones ---
            seccion_predicciones = MDBoxLayout(orientation='vertical', size_hint_y=None, height=dp(200), padding=(10, 10, 10, 10))
            
            # Título con indicador BETA
            titulo_predicciones = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40))
            titulo_predicciones.add_widget(MDLabel(
                text="🔮 Predicciones de Venta",
                font_style="H6"
            ))
            
            # Etiqueta BETA
            beta_label = MDRaisedButton(
                text="BETA",
                md_bg_color=(0.8, 0.2, 0.8, 1),
                text_color=(1, 1, 1, 1),
                size_hint=(None, None),
                size=(dp(60), dp(30)),
                pos_hint={'center_y': 0.5}
            )
            titulo_predicciones.add_widget(beta_label)
            seccion_predicciones.add_widget(titulo_predicciones)
            
            # Mostrar predicciones
            predicciones_container = MDBoxLayout(orientation='vertical', spacing=10)
            
            if 'predicciones' in datos_ventas and datos_ventas['predicciones']:
                # Mostrar las predicciones calculadas
                for fecha, valor_esperado in datos_ventas['predicciones']:
                    pred_item = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40))
                    pred_item.add_widget(MDLabel(
                        text=f"Predicción para {fecha.strftime('%d/%m/%Y')}:",
                        size_hint_x=0.6
                    ))
                    pred_item.add_widget(MDRaisedButton(
                        text=f"${valor_esperado:.2f}",
                        size_hint_x=0.4,
                        md_bg_color=(0.6, 0.3, 0.8, 1)
                    ))
                    predicciones_container.add_widget(pred_item)
            else:
                # Si no hay suficientes datos para predicciones
                predicciones_container.add_widget(MDLabel(
                    text="No hay suficientes datos históricos para realizar predicciones precisas.\n"
                         "Continúe registrando ventas para habilitar esta función.",
                    halign="center"
                ))
            
            seccion_predicciones.add_widget(predicciones_container)
            main_container.add_widget(seccion_predicciones)
            
            # Ajustar altura total
            main_container.height = sum(child.height for child in main_container.children) + dp(50)
            
            scroll_container.add_widget(main_container)
            
            # Crear y mostrar el diálogo
            self.dialog_estadisticas = MDDialog(
                title="Estadísticas y Análisis",
                type="custom",
                content_cls=scroll_container,
                buttons=[
                    MDRaisedButton(
                        text="Exportar PDF",
                        on_release=self.exportar_estadisticas_pdf
                    ),
                    MDFlatButton(
                        text="Cerrar",
                        on_release=lambda x: self.dialog_estadisticas.dismiss()
                    )
                ],
                size_hint=(0.9, None),
                height=dp(600)
            )
            self.dialog_estadisticas.open()
            
        except Exception as e:
            import traceback
            error_detalle = traceback.format_exc()
            mostrar_notificacion(f"❌ Error al mostrar estadísticas: {str(e)}")
            print(error_detalle)
            
    def obtener_datos_estadisticas(self):
        """Obtiene todos los datos necesarios para las estadísticas"""
        resultado = {}
        
        try:
            conn = conectar_bd()
            cursor = conn.cursor()
            
            # 1. Obtener ventas de los últimos 30 días
            cursor.execute("""
                SELECT DATE(fecha) as dia, SUM(cantidad * costo) as total
                FROM pedidos
                GROUP BY dia
                ORDER BY dia DESC
                LIMIT 30
            """)
            ventas_dias = cursor.fetchall()
            resultado['ventas_dias'] = ventas_dias
            
            # 2. Obtener productos más vendidos
            cursor.execute("""
                SELECT producto, SUM(cantidad) as total_cantidad, 
                       SUM(cantidad * costo) as ingreso_total
                FROM pedidos
                GROUP BY producto
                ORDER BY total_cantidad DESC
                LIMIT 10
            """)
            productos_top = cursor.fetchall()
            resultado['productos_top'] = productos_top
            
            # 3. Calcular ganancia (asumiendo que tenemos datos de costo y precio de venta)
            cursor.execute("""
                SELECT SUM(p.cantidad * (pr.precio_venta - pr.costo)) as ganancia_total
                FROM pedidos p
                JOIN productos pr ON p.producto = pr.nombre
            """)
            ganancia_result = cursor.fetchone()
            ganancia = ganancia_result[0] if ganancia_result and ganancia_result[0] is not None else 0
            
            # 4. Calcular facturación total
            cursor.execute("""
                SELECT SUM(cantidad * costo) as total_facturado
                FROM pedidos
            """)
            facturacion_result = cursor.fetchone()
            facturacion = facturacion_result[0] if facturacion_result and facturacion_result[0] is not None else 0
            
            # Datos para resumen
            resultado['resumen'] = (facturacion, ganancia, productos_top)
            
            # 5. Datos para predicciones - Necesitamos histórico por fecha
            cursor.execute("""
                SELECT DATE(fecha) as dia, SUM(cantidad * costo) as total
                FROM pedidos
                GROUP BY dia
                ORDER BY dia ASC
            """)
            datos_historicos = cursor.fetchall()
            
            # Si tenemos suficientes datos, hacer predicciones
            if len(datos_historicos) >= 5:  # Necesitamos al menos 5 puntos para una regresión simple
                predicciones = self.calcular_predicciones(datos_historicos)
                resultado['predicciones'] = predicciones
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"Error obteniendo datos de estadísticas: {str(e)}")
            import traceback
            traceback.print_exc()
            
        return resultado
    
    def calcular_predicciones(self, datos_historicos):
        """
        Implementa una regresión lineal simple para predecir ventas futuras
        basándose en los datos históricos.
        """
        try:
            import numpy as np
            from datetime import datetime, timedelta
            
            # Convertir fechas a números (días desde el primer registro)
            fecha_base = datos_historicos[0][0]  # Primera fecha como referencia
            x = [(fecha - fecha_base).days for fecha, _ in datos_historicos]
            y = [venta for _, venta in datos_historicos]
            
            # Si no hay suficiente variación en los datos, no podemos predecir
            if len(set(y)) <= 1:
                return []
                
            # Convertir a arrays de numpy
            x = np.array(x).reshape(-1, 1)
            y = np.array(y)
            
            # Calcular la regresión lineal (y = mx + b)
            n = len(x)
            m = (n * np.sum(x * y) - np.sum(x) * np.sum(y)) / (n * np.sum(x * x) - np.sum(x) ** 2)
            b = (np.sum(y) - m * np.sum(x)) / n
            
            # Predecir para los próximos 7 días
            ultima_fecha = datos_historicos[-1][0]
            predicciones = []
            
            for i in range(1, 8):
                fecha_prediccion = ultima_fecha + timedelta(days=i)
                dias_desde_base = (fecha_prediccion - fecha_base).days
                valor_predicho = m * dias_desde_base + b
                
                # Asegurar que las predicciones no sean negativas
                valor_predicho = max(0, valor_predicho)
                
                predicciones.append((fecha_prediccion, valor_predicho))
                
            return predicciones
            
        except Exception as e:
            print(f"Error en el cálculo de predicciones: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
            
    def exportar_estadisticas_pdf(self, instance):
        """Exporta las estadísticas actuales a un PDF"""
        try:
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors
            
            # Obtener datos para el PDF
            datos = self.obtener_datos_estadisticas()
            
            # Crear nombre de archivo con timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"reportes/Estadisticas_{timestamp}.pdf"
            
            # Asegurar que el directorio exista
            os.makedirs("reportes", exist_ok=True)
            
            # Crear el documento
            doc = SimpleDocTemplate(filename, pagesize=letter)
            styles = getSampleStyleSheet()
            elements = []
            
            # Título
            titulo = Paragraph("Reporte de Estadísticas", styles['Title'])
            elements.append(titulo)
            elements.append(Spacer(1, 20))
            
            # Fecha del reporte
            fecha = Paragraph(f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal'])
            elements.append(fecha)
            elements.append(Spacer(1, 20))
            
            # 1. Resumen de ventas
            elements.append(Paragraph("Resumen de Ventas", styles['Heading2']))
            total_ventas, ganancia_total, _ = datos['resumen']
            
            # Verificar que la facturación no sea cero para evitar división por cero
            rentabilidad = 0
            if total_ventas > 0:
                rentabilidad = (ganancia_total/total_ventas*100)
            
            data = [
                ["Total Facturado", "Ganancia Total", "Rentabilidad"],
                [f"${total_ventas:.2f}", f"${ganancia_total:.2f}", f"{rentabilidad:.1f}%"]
            ]
            
            t = Table(data, colWidths=[150, 150, 150])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ]))
            
            elements.append(t)
            elements.append(Spacer(1, 20))
            
            # 2. Productos más vendidos
            elements.append(Paragraph("Productos Más Vendidos", styles['Heading2']))
            
            data = [["Producto", "Cantidad", "Ingresos"]]
            for producto_info in datos['productos_top'][:5]:  # Top 5
                if len(producto_info) >= 3:
                    producto, cantidad, ingreso = producto_info
                    data.append([producto, str(cantidad), f"${ingreso:.2f}"])
                
            t = Table(data, colWidths=[250, 100, 100])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ]))
            
            elements.append(t)
            elements.append(Spacer(1, 20))
            
            # 3. Ventas por día
            elements.append(Paragraph("Ventas de los Últimos Días", styles['Heading2']))
            
            data = [["Fecha", "Total"]]
            for dia_info in datos.get('ventas_dias', [])[:7]:  # Últimos 7 días
                if len(dia_info) >= 2:
                    fecha, total = dia_info
                    data.append([fecha.strftime('%d/%m/%Y'), f"${total:.2f}"])
                
            t = Table(data, colWidths=[200, 200])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ]))
            
            elements.append(t)
            elements.append(Spacer(1, 20))
            
            # 4. Predicciones (si hay disponibles)
            if 'predicciones' in datos and datos['predicciones']:
                elements.append(Paragraph("Predicciones de Ventas (BETA)", styles['Heading2']))
                
                # Nota sobre las predicciones
                nota_predicciones = Paragraph(
                    "Nota: Las predicciones se basan en un modelo simple de regresión lineal y deben considerarse como estimaciones aproximadas.",
                    styles['Italic']
                )
                elements.append(nota_predicciones)
                elements.append(Spacer(1, 10))
                
                data = [["Fecha", "Venta Esperada"]]
                for pred_info in datos['predicciones']:
                    if len(pred_info) >= 2:
                        fecha, valor = pred_info
                        data.append([fecha.strftime('%d/%m/%Y'), f"${valor:.2f}"])
                    
                t = Table(data, colWidths=[200, 200])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BOX', (0, 0), (-1, -1), 1, colors.black),
                    ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
                ]))
                
                elements.append(t)
            
            # Generar PDF
            doc.build(elements)
            
            mostrar_notificacion(f"✅ Reporte exportado exitosamente: {filename}")
            
        except Exception as e:
            import traceback
            error_detalle = traceback.format_exc()
            mostrar_notificacion(f"❌ Error al exportar estadísticas: {str(e)}")
            print(error_detalle)

    def registrar_pedido(self, instance):
        cliente = self.cliente.text.strip()
        producto = self.producto.text.strip()
        cantidad = self.cantidad.text.strip()
        costo = self.costo.text.strip()
        zona = self.zona.text.strip()
        
        if not all([cliente, producto, cantidad, costo]) or zona == "📍 Zona":
            mostrar_notificacion("⚠️ Todos los campos son obligatorios.")
            return
        
        # Verificar stock disponible
        stock_actual = obtener_stock_producto(producto)
        if stock_actual < int(cantidad):
            mostrar_notificacion(f"⚠️ Stock insuficiente. Disponible: {stock_actual}")
            return
        
        # Insertar cliente si no existe
        conn = conectar_bd()
        cursor = conn.cursor()
        cursor.execute("INSERT IGNORE INTO clientes (nombre) VALUES (%s)", (cliente,))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Agregar a lista temporal
        self.productos_temporal.append({
            'producto': producto,
            'cantidad': int(cantidad),
            'costo': float(costo),
            'zona': zona,
            'stock': stock_actual
        })
        
        self.actualizar_lista_temporal()
        
        # Limpiar campos
        self.producto.text = ''
        self.cantidad.text = ''
        self.costo.text = ''

    def sugerir_clientes(self, instance, texto):
        if texto.strip():
            clientes = obtener_clientes(texto.strip())
            if clientes:
                crear_menu_sugerencias(self, clientes, self.cliente)

    def sugerir_productos(self, instance, texto):
        if texto.strip():
            productos = obtener_productos(texto.strip())
            if productos:
                crear_menu_sugerencias(self, productos, self.producto)

    def seleccionar_sugerencia(self, texto, campo):
        campo.text = texto
        if self.menu:
            self.menu.dismiss()
        if campo == self.producto:
            self.costo.text = str(obtener_costo_producto(texto))

    def mostrar_zonas(self, instance):
        zonas = ["Bernal", "Avellaneda #1", "Avellaneda #2", "Quilmes Centro", "Solano"]
        menu_items = [
            {"text": zona, "viewclass": "OneLineListItem", "on_release": partial(self.seleccionar_zona, zona)}
            for zona in zonas
        ]
        if hasattr(self, "menu_zonas") and self.menu_zonas:
            self.menu_zonas.dismiss()
        self.menu_zonas = MDDropdownMenu(caller=self.zona, items=menu_items, width_mult=4)
        self.menu_zonas.open()

    def seleccionar_zona(self, zona, *args):
        self.zona.text = zona
        if hasattr(self, "menu_zonas") and self.menu_zonas:
            self.menu_zonas.dismiss()

    def ver_pedidos_dia(self, instance):
        conn = conectar_bd()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT cliente FROM pedidos WHERE fecha = CURDATE()")
        clientes = [cliente[0] for cliente in cursor.fetchall()]
        cursor.close()
        conn.close()
        
        if not clientes:
            mostrar_notificacion("📄 No hay pedidos registrados hoy.")
            return
        
        content = MDBoxLayout(orientation='vertical', spacing=15, size_hint_y=None)
        content.height = (len(clientes) + 1) * dp(50)  # +1 para el botón de descarga
        
        for cliente in clientes:
            btn = MDRaisedButton(
                text=cliente,
                on_release=partial(self.mostrar_detalle_cliente, cliente)
            )
            content.add_widget(btn)
        
        btn_descargar = MDRaisedButton(
            text="Descargar PDF para cada cliente",
            on_release=lambda x: self.generar_pdf_todos_clientes(clientes)
        )
        content.add_widget(btn_descargar)
        
        MDDialog(
            title="Pedidos del día",
            type="custom",
            content_cls=content,
            size_hint=(0.8, None)
        ).open()
        
    def generar_pdf_todos_clientes(self, clientes):
        """Genera un PDF individual para cada cliente con sus pedidos del día"""
        try:
            # Crear directorio para guardar los PDFs si no existe
            directorio = "pedidos_clientes"
            if not os.path.exists(directorio):
                os.makedirs(directorio)
                
            # Contador de PDFs generados
            pdfs_generados = 0
            
            # Generar un PDF para cada cliente
            for cliente in clientes:
                # Obtener los pedidos del cliente
                conn = conectar_bd()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT producto, cantidad, costo, zona 
                    FROM pedidos 
                    WHERE cliente = %s AND fecha = CURDATE()
                """, (cliente,))
                pedidos = cursor.fetchall()
                cursor.close()
                conn.close()
                
                if not pedidos:
                    continue
                
                # Generar nombre de archivo único para cada cliente
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{directorio}/Pedido_{cliente}_{timestamp}.pdf"
                
                # Crear el PDF
                c = canvas.Canvas(filename, pagesize=letter)
                
                # Encabezado
                c.setFont("Helvetica-Bold", 16)
                c.drawString(50, 750, f"Pedido de {cliente} - {datetime.now().strftime('%d/%m/%Y')}")
                
                # Tabla de productos
                data = [["Producto", "Cantidad", "Costo Unit.", "Total", "Zona"]]
                total_cliente = 0
                
                for producto, cantidad, costo, zona in pedidos:
                    total = cantidad * costo
                    total_cliente += total
                    data.append([
                        producto,
                        str(cantidad),
                        f"${costo:.2f}",
                        f"${total:.2f}",
                        zona
                    ])
                
                # Fila de total
                data.append(["TOTAL", "", "", f"${total_cliente:.2f}", ""])
                
                table = Table(data, colWidths=[150, 70, 80, 80, 100])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.grey),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTSIZE', (0,0), (-1,-1), 10),
                    ('BOX', (0,0), (-1,-1), 1, colors.black),
                    ('GRID', (0,0), (-1,-2), 1, colors.lightgrey)
                ]))
                
                table.wrapOn(c, 50, 600)
                table.drawOn(c, 50, 600)
                
                c.save()
                pdfs_generados += 1
            
            # Mostrar notificación con el resultado
            if pdfs_generados > 0:
                mostrar_notificacion(f"✅ Se generaron {pdfs_generados} archivos PDF en la carpeta '{directorio}'")
            else:
                mostrar_notificacion("⚠️ No se generó ningún PDF. No hay pedidos para procesar.")
                
        except Exception as e:
            import traceback
            error_detalle = traceback.format_exc()
            mostrar_notificacion(f"❌ Error al generar PDFs: {str(e)}")
            
    def mostrar_dialogo_simple(self, titulo, texto):
        """Muestra un diálogo simple con un botón para cerrar."""
        # Crear el diálogo
        self.dialog = MDDialog(
            title=titulo,
            text=texto,
            buttons=[
                MDFlatButton(
                    text="Cerrar",
                    on_release=lambda x: self.dialog.dismiss()
                ),
            ],
        )
        self.dialog.open()
            
    def generar_productos_por_dia(self, *args):
        """Genera un PDF con los productos vendidos en el día actual, acumulando cantidades."""
        try:
            # Obtener la fecha actual
            fecha_actual = datetime.now().strftime("%Y-%m-%d")
            
            conn = conectar_bd()
            cursor = conn.cursor()
            # Consulta SQL para obtener productos vendidos hoy agrupados y sumados
            consulta = """
            SELECT producto, SUM(cantidad) as cantidad_total
            FROM pedidos
            WHERE fecha = %s
            GROUP BY producto
            ORDER BY producto
            """
            
            cursor.execute(consulta, (fecha_actual,))
            resultados = cursor.fetchall()
            
            # Cerrar la conexión a la base de datos
            conn.close()
            
            # Verificar si hay resultados
            if not resultados:
                self.mostrar_dialogo_simple("Información", "No hay productos vendidos registrados para hoy.")
                return
            
            # Crear el PDF
            pdf = FPDF()
            pdf.add_page()
            
            # Configurar márgenes y fuentes
            pdf.set_margins(10, 10, 10)
            pdf.set_auto_page_break(True, margin=15)
            
            # Título
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(0, 10, 'Reporte de Productos por Día', 0, 1, 'C')
            
            # Fecha
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, f'Fecha: {fecha_actual}', 0, 1, 'L')
            pdf.ln(5)
            
            # Crear la tabla
            # Encabezados
            pdf.set_fill_color(200, 200, 200)
            pdf.set_font('Arial', 'B', 11)
            
            # Definir anchos de columnas
            ancho_producto = 120
            ancho_cantidad = 60
            altura_celda = 10
            
            # Dibujar encabezados
            pdf.cell(ancho_producto, altura_celda, 'Producto', 1, 0, 'C', 1)
            pdf.cell(ancho_cantidad, altura_celda, 'Cantidad', 1, 1, 'C', 1)
            
            # Dibujar filas de datos
            pdf.set_font('Arial', '', 10)
            for producto, cantidad in resultados:
                pdf.cell(ancho_producto, altura_celda, producto, 1, 0, 'L')
                pdf.cell(ancho_cantidad, altura_celda, str(cantidad), 1, 1, 'C')
            
            # Crear directorio para reportes si no existe
            directorio = "reportes"
            if not os.path.exists(directorio):
                os.makedirs(directorio)
            
            # Generar nombre de archivo único
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_archivo = f"{directorio}/productos_por_dia_{timestamp}.pdf"
            
            # Guardar el PDF
            pdf.output(nombre_archivo)
            
            # Mostrar mensaje de éxito
            self.mostrar_dialogo_simple("Éxito", f"Reporte generado exitosamente.\nArchivo: {nombre_archivo}")
            
        except Exception as e:
            # Mostrar mensaje de error con detalles para ayudar en la depuración
            import traceback
            error_detalle = traceback.format_exc()
            self.mostrar_dialogo_simple("Error", f"No se pudo generar el reporte: {str(e)}\n\nDetalles: {error_detalle}")

    def mostrar_detalle_cliente(self, cliente, instance):
        conn = conectar_bd()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT producto, cantidad, costo, zona 
            FROM pedidos 
            WHERE cliente = %s AND fecha = CURDATE()
        """, (cliente,))
        pedidos = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not pedidos:
            mostrar_notificacion(f"No hay pedidos para {cliente} en la fecha actual")
            return
        
        content = MDBoxLayout(orientation='vertical', spacing=10, size_hint_y=None)
        content.height = len(pedidos) * dp(50) + dp(20)
        
        for producto, cantidad, costo, zona in pedidos:
            total = cantidad * costo
            item = TwoLineListItem(
                text=f"{producto} - {cantidad} unidades",
                secondary_text=f"Costo: ${costo:.2f} | Total: ${total:.2f} | Zona: {zona}"
            )
            content.add_widget(item)
        
        # Corrección clave: guardar referencia al diálogo
        dialog = MDDialog(
            title=f"Detalle de pedidos de {cliente}",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="Cerrar", 
                    on_release=lambda x: dialog.dismiss()  # Usar la referencia directa
                ),
                MDRaisedButton(
                    text="PDF", 
                    on_release=lambda x: self.generar_pdf_cliente(cliente)
                )
            ],
            size_hint=(0.8, None)
        )
        dialog.open()
        
    def generar_pdf_cliente(self, cliente):
        conn = conectar_bd()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT producto, cantidad, costo, zona 
            FROM pedidos 
            WHERE cliente = %s AND fecha = CURDATE()
        """, (cliente,))
        pedidos = cursor.fetchall()
        cursor.close()
        conn.close()
        
        filename = f"Pedido_{cliente}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
        c = canvas.Canvas(filename, pagesize=letter)
        
        # Encabezado
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, f"Pedido de {cliente} - {datetime.now().strftime('%d/%m/%Y')}")
        
        # Tabla de productos
        data = [["Producto", "Cantidad", "Costo Unit.", "Total", "Zona"]]
        total_cliente = 0
        
        for producto, cantidad, costo, zona in pedidos:
            total = cantidad * costo
            total_cliente += total
            data.append([
                producto,
                str(cantidad),
                f"${costo:.2f}",
                f"${total:.2f}",
                zona
            ])
        
        # Fila de total
        data.append(["TOTAL", "", "", f"${total_cliente:.2f}", ""])
        
        table = Table(data, colWidths=[150, 70, 80, 80, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BOX', (0,0), (-1,-1), 1, colors.black),
            ('GRID', (0,0), (-1,-2), 1, colors.lightgrey)
        ]))
        
        table.wrapOn(c, 50, 600)
        table.drawOn(c, 50, 600)
        
        c.save()
        mostrar_notificacion(f"✅ PDF generado: {os.path.abspath(filename)}")

    def generar_pdf_pedidos(self):
        conn = conectar_bd()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cliente, producto, SUM(cantidad) as cantidad_total, AVG(costo) as costo_prom, zona 
            FROM pedidos 
            WHERE fecha = CURDATE()
            GROUP BY cliente, producto, zona
        """)
        pedidos = cursor.fetchall()
        cursor.close()
        conn.close()
        
        filename = f"Resumen_Pedidos_{datetime.now().strftime('%Y-%m-%d')}.pdf"
        c = canvas.Canvas(filename, pagesize=letter)
        
        # Encabezado
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, f"Resumen Diario de Pedidos - {datetime.now().strftime('%d/%m/%Y')}")
        
        # Tabla principal
        data = [["Cliente", "Producto", "Cantidad", "Costo Prom.", "Zona", "Total"]]
        total_general = 0
        
        for pedido in pedidos:
            cliente, producto, cantidad, costo, zona = pedido
            total = cantidad * costo
            total_general += total
            data.append([
                cliente,
                producto,
                str(int(cantidad)),
                f"${costo:.2f}",
                zona,
                f"${total:.2f}"
            ])
        
        # Fila de total general
        data.append(["TOTAL GENERAL", "", "", "", "", f"${total_general:.2f}"])
        
        # Crear tabla
        table = Table(data, colWidths=[120, 120, 60, 70, 80, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#3B5998")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('BOX', (0,0), (-1,-1), 1, colors.black),
            ('GRID', (0,0), (-1,-2), 1, colors.lightgrey)
        ]))
        
        table.wrapOn(c, 50, 600)
        table.drawOn(c, 50, 600)
        
        c.save()
        mostrar_notificacion(f"✅ PDF generado: {os.path.abspath(filename)}")

    def mostrar_clientes_para_editar(self, instance):
        conn = conectar_bd()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT cliente FROM pedidos WHERE fecha = CURDATE()")
        clientes = [cliente[0] for cliente in cursor.fetchall()]
        cursor.close()
        conn.close()
        
        if not clientes:
            mostrar_notificacion("🙈 No hay pedidos registrados hoy.")
            return
        
        content = MDBoxLayout(orientation='vertical', spacing=10, size_hint_y=None)
        content.height = len(clientes) * dp(50)
        
        for cliente in clientes:
            btn = MDRaisedButton(
                text=cliente,
                on_release=lambda x, c=cliente: self.abrir_edicion_cliente(c)
            )
            content.add_widget(btn)
        
        self.dialog_seleccion_cliente = MDDialog(
            title="Seleccione un cliente para editar",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="Cancelar", on_release=lambda x: self.dialog_seleccion_cliente.dismiss())
            ],
            size_hint=(0.8, None)
        )
        self.dialog_seleccion_cliente.open()

    def abrir_edicion_cliente(self, cliente):
        conn = conectar_bd()
        cursor = conn.cursor()
        cursor.execute("SELECT id, producto, cantidad, costo, zona FROM pedidos WHERE cliente = %s AND fecha = CURDATE()", (cliente,))
        pedidos = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if hasattr(self, 'dialog_seleccion_cliente') and self.dialog_seleccion_cliente:
            self.dialog_seleccion_cliente.dismiss()
        
        # Crear un BoxLayout con scroll para admitir muchos elementos
        scroll_container = MDScrollView(size_hint=(1, None), height=dp(300))
        main_container = MDBoxLayout(orientation='vertical', spacing=10, size_hint_y=None)
        main_container.bind(minimum_height=main_container.setter('height'))
        
        # Añadir un espacio vacío en la parte superior
        spacer = MDBoxLayout(size_hint_y=None, height=dp(20))
        main_container.add_widget(spacer)
        
        self.edicion_pedidos = []
        self.cliente_actual_edicion = cliente
        
        for pedido in pedidos:
            id_pedido, producto, cantidad, costo, zona = pedido
            
            # Contenedor principal para el ítem
            item = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(80), padding=(5, 10, 5, 5))
            
            # Columna izquierda: Información del producto y zona (30% del ancho)
            info_container = MDBoxLayout(orientation='vertical', size_hint_x=0.3)
            producto_label = TwoLineListItem(
                text=producto,
                secondary_text=f"Zona: {zona}",
                divider=None,
                _no_ripple_effect=True
            )
            info_container.add_widget(producto_label)
            item.add_widget(info_container)
            
            # Columna central: Campos de edición (55% del ancho)
            campos_container = MDBoxLayout(orientation='horizontal', size_hint_x=0.55, spacing=10)
            
            # Campo de cantidad
            cantidad_container = MDBoxLayout(orientation='vertical', size_hint_x=0.5, spacing=2)
            cantidad_label = MDBoxLayout(size_hint_y=None, height=dp(24), padding=(5, 0, 0, 0))
            cantidad_label.add_widget(MDRaisedButton(
                text="Cantidad",
                disabled=True,
                size_hint_x=1,
                md_bg_color=(0.3, 0.3, 0.3, 1),
                _no_ripple_effect=True
            ))
            cantidad_container.add_widget(cantidad_label)
            
            cantidad_input = MDTextField(
                text=str(cantidad),
                input_filter='int',
                size_hint_y=None,
                height=dp(40),
                mode="rectangle",
                halign="center"
            )
            cantidad_container.add_widget(cantidad_input)
            campos_container.add_widget(cantidad_container)
            
            # Campo de costo
            costo_container = MDBoxLayout(orientation='vertical', size_hint_x=0.5, spacing=2)
            costo_label = MDBoxLayout(size_hint_y=None, height=dp(24), padding=(5, 0, 0, 0))
            costo_label.add_widget(MDRaisedButton(
                text="Costo",
                disabled=True,
                size_hint_x=1,
                md_bg_color=(0.3, 0.3, 0.3, 1),
                _no_ripple_effect=True
            ))
            costo_container.add_widget(costo_label)
            
            costo_input = MDTextField(
                text=str(costo),
                input_filter='float',
                size_hint_y=None,
                height=dp(40),
                mode="rectangle",
                halign="center"
            )
            costo_container.add_widget(costo_input)
            campos_container.add_widget(costo_container)
            
            item.add_widget(campos_container)
            
            # Columna derecha: Botón de eliminar (15% del ancho)
            botones_container = MDBoxLayout(orientation='vertical', size_hint_x=0.15, padding=(0, 10, 0, 0))
            btn_eliminar = MDIconButton(
                icon='delete-forever',
                theme_text_color="Error",
                icon_size=dp(30),
                on_release=partial(self.eliminar_pedido, id_pedido)
            )
            botones_container.add_widget(btn_eliminar)
            item.add_widget(botones_container)
            
            # Añadir un separador visual entre elementos
            separador = MDBoxLayout(
                size_hint_y=None,
                height=dp(1),
                md_bg_color=(0.7, 0.7, 0.7, 1)
            )
            
            main_container.add_widget(item)
            main_container.add_widget(separador)
            self.edicion_pedidos.append((id_pedido, cantidad_input, costo_input))
        
        scroll_container.add_widget(main_container)
        
        self.dialog_edicion = MDDialog(
            title=f"Editar pedidos de {cliente}",
            type="custom",
            content_cls=scroll_container,
            buttons=[
                MDRaisedButton(text="Guardar", on_release=self.guardar_cambios),
                MDFlatButton(text="Cancelar", on_release=lambda x: self.dialog_edicion.dismiss())
            ],
            size_hint=(0.9, None),
            height=dp(400)
        )
        self.dialog_edicion.open()
        
    def eliminar_pedido(self, id_pedido, instance):
        """Muestra un diálogo de confirmación antes de eliminar un pedido"""
        try:
            # Crear el diálogo de confirmación
            self.dialog_confirmacion = MDDialog(
                title="Confirmar eliminación",
                text="¿Estás seguro de que deseas eliminar este pedido? Esta acción no se puede deshacer.",
                buttons=[
                    MDFlatButton(
                        text="Cancelar",
                        on_release=lambda x: self.dialog_confirmacion.dismiss()
                    ),
                    MDRaisedButton(
                        text="Eliminar",
                        theme_text_color="Error",
                        on_release=lambda x: self.confirmar_eliminacion(id_pedido)
                    ),
                ]
            )
            # Mostrar el diálogo
            self.dialog_confirmacion.open()
        except Exception as e:
            mostrar_notificacion(f"❌ Error al intentar eliminar: {str(e)}")
            
    def confirmar_eliminacion(self, id_pedido):
        """Elimina el pedido después de la confirmación del usuario"""
        try:
            # Cerrar el diálogo de confirmación
            if hasattr(self, 'dialog_confirmacion') and self.dialog_confirmacion:
                self.dialog_confirmacion.dismiss()
            
            # Eliminar el pedido de la base de datos
            conn = conectar_bd()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pedidos WHERE id = %s", (id_pedido,))
            conn.commit()
            cursor.close()
            conn.close()
            
            # Cerrar el diálogo de edición
            if hasattr(self, 'dialog_edicion') and self.dialog_edicion:
                self.dialog_edicion.dismiss()
            
            # Mostrar notificación y reabrir la pantalla de edición para refrescar
            mostrar_notificacion("✅ Pedido eliminado correctamente")
            
            # Volver a abrir la pantalla de edición actualizada
            if hasattr(self, 'cliente_actual_edicion'):
                self.abrir_edicion_cliente(self.cliente_actual_edicion)
                
        except Exception as e:
            mostrar_notificacion(f"❌ Error al eliminar: {str(e)}")
        
    def guardar_cambios(self, instance):
        conn = conectar_bd()
        cursor = conn.cursor()
        try:
            for id_pedido, cantidad_input, costo_input in self.edicion_pedidos:
                cursor.execute(
                    "UPDATE pedidos SET cantidad = %s, costo = %s WHERE id = %s",
                    (int(cantidad_input.text), float(costo_input.text), id_pedido)
                )
            conn.commit()
            mostrar_notificacion("✅ Cambios guardados exitosamente!")
        except Exception as e:
            conn.rollback()
            mostrar_notificacion(f"❌ Error: {str(e)}")
        finally:
            cursor.close()
            conn.close()
            self.dialog_edicion.dismiss()
            
    def procesar_csv(self, seleccion, popup):
        try:
            popup.dismiss()
            if not seleccion:
                raise ValueError("No se seleccionó archivo")
            
            ruta = seleccion[0]
            if not ruta.lower().endswith('.csv'):
                raise ValueError("Solo archivos CSV")
            
            actualizar_stock_desde_csv(ruta)
            mostrar_notificacion("✅ CSV procesado correctamente")
            
        except Exception as e:
            mostrar_notificacion(f"❌ Error: {str(e)}")
            
    def mostrar_dialogo(self, titulo, texto):
        dialog = MDDialog(
            title=titulo,
            text=texto,
            buttons=[
                MDFlatButton(
                    text="Cerrar",
                    on_release=lambda x: dialog.dismiss()
                )
            ]
        )
        dialog.open()
            
class ProductosPorDiaPDF(FPDF):
    def header(self):
        # Configurar márgenes
        self.set_margins(10, 15, 10)  # (izquierda, arriba, derecha)
        
        # Encabezado
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Reporte de Productos Vendidos por Día', 0, 1, 'C')
        self.ln(5)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')      

PedidoApp().run()