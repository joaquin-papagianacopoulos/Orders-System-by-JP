from kivymd.app import MDApp
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.list import OneLineListItem, TwoLineListItem
from kivymd.uix.dialog import MDDialog
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

def get_app_dir():
    """Obtiene el directorio adecuado para almacenar datos de la aplicación"""
    if platform == 'android':
        from android.storage import app_storage_path
        return app_storage_path()
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

# --- Funciones de base de datos ---
def conectar_bd():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='distriñulpi'
    )

def inicializar_bd():
    conn = conectar_bd()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nombre VARCHAR(255) UNIQUE,
        costo DECIMAL(10,2),
        precio_venta DECIMAL(10,2),
        stock INT DEFAULT 0
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS pedidos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        cliente VARCHAR(255),
        producto VARCHAR(255),
        cantidad INT,
        costo DECIMAL(10,2),
        zona VARCHAR(100),
        fecha DATE DEFAULT (CURRENT_DATE)
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS clientes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nombre VARCHAR(255) UNIQUE
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
        left_panel = MDBoxLayout(orientation='vertical', size_hint=(0.4, 1), spacing=15)
        self.cliente = MDTextField(hint_text='Cliente ✍️')
        self.cliente.bind(text=self.sugerir_clientes)
        
        self.producto = MDTextField(hint_text='Producto 🔍')
        self.producto.bind(text=self.sugerir_productos)
        
        self.cantidad = MDTextField(hint_text='Cantidad 🔢', input_filter='int')
        self.costo = MDTextField(hint_text='Costo 💲', input_filter='float')
        self.zona = MDRaisedButton(text='📍 Zona', on_release=self.mostrar_zonas)
        
        # Botones principales
        left_panel.add_widget(self.cliente)
        left_panel.add_widget(self.producto)
        left_panel.add_widget(self.cantidad)
        left_panel.add_widget(self.costo)
        left_panel.add_widget(self.zona)
        
        # Crear botones y guardarlos con ids para acceso posterior
        self.boton_registrar = MDRaisedButton(text='✅ Registrar', on_release=self.registrar_pedido)
        self.boton_pedidos_hoy = MDRaisedButton(text='📄 Pedidos Hoy', on_release=self.ver_pedidos_dia)
        self.boton_modificar = MDRaisedButton(text='✏️ Modificar', on_release=self.mostrar_clientes_para_editar)
        self.boton_csv = MDRaisedButton(text='📤 Subir CSV', on_release=self.mostrar_file_chooser)
        self.boton_estadisticas = MDRaisedButton(text='📊 Estadísticas', on_release=self.mostrar_estadisticas)
        
        left_panel.add_widget(self.boton_registrar)
        left_panel.add_widget(self.boton_pedidos_hoy)
        left_panel.add_widget(self.boton_modificar)
        left_panel.add_widget(self.boton_csv)
        left_panel.add_widget(self.boton_estadisticas)

        # Panel derecho
        right_panel = MDBoxLayout(orientation='vertical', size_hint=(0.6, 1))
        self.lista_productos = MDScrollView()
        self.contenedor_productos = MDBoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        self.contenedor_productos.bind(minimum_height=self.contenedor_productos.setter('height'))
        self.lista_productos.add_widget(self.contenedor_productos)
        right_panel.add_widget(self.lista_productos)
        
        # Botones de control
        controles = MDBoxLayout(size_hint_y=None, height=dp(60), spacing=10)
        for btn in [
            MDRaisedButton(text='✏️ Editar', on_release=self.editar_orden_actual),
            MDRaisedButton(text='🗑️ Vaciar', on_release=self.vaciar_orden_actual),
            MDRaisedButton(text='🚀 Enviar', on_release=self.guardar_pedido_completo)
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
            
        content = MDBoxLayout(orientation='vertical', spacing=10)
        for producto in self.productos_temporal:
            item = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(60))
            item.add_widget(TwoLineListItem(
                text=producto['producto'],
                secondary_text=f"Cant: {producto['cantidad']} | Costo: ${producto['costo']}"
            ))
            
            btn_eliminar = MDIconButton(
                icon='delete',
                on_release=partial(self.eliminar_de_orden_actual, producto)
            )
            item.add_widget(btn_eliminar)
            content.add_widget(item)
        
        self.dialog_edicion_actual = MDDialog(
            title="Editar orden actual",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="Cerrar", on_release=lambda x: self.dialog_edicion_actual.dismiss())
            ]
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
            item = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40))
            item.add_widget(TwoLineListItem(
                text=producto['producto'],
                secondary_text=f"Cant: {producto['cantidad']} | Costo: ${producto['costo']}"
            ))
            btn_eliminar = MDIconButton(
                icon="delete",
                theme_text_color="Error",
                on_release=partial(self.eliminar_de_orden_actual, producto)
            )
            item.add_widget(btn_eliminar)
            self.contenedor_productos.add_widget(item)

    def mostrar_estadisticas(self, instance):
        datos = obtener_ventas_diarias()
        content = MDBoxLayout(orientation='vertical', spacing=10)
        
        if not datos:
            content.add_widget(OneLineListItem(text="No hay datos históricos"))
        else:
            for dia, total in datos:
                item = TwoLineListItem(
                    text=f"{dia.strftime('%d/%m/%Y')}",
                    secondary_text=f"Total: ${total:.2f}"
                )
                content.add_widget(item)
        
        MDDialog(
            title="📊 Ventas últimos 30 días",
            type="custom",
            content_cls=content,
            size_hint=(0.8, 0.8)
        ).open()

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
            text="Descargar todos los pedidos",
            on_release=lambda x: self.generar_pdf_pedidos()
        )
        content.add_widget(btn_descargar)
        
        MDDialog(
            title="Pedidos del día",
            type="custom",
            content_cls=content,
            size_hint=(0.8, None)
        ).open()
            
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

        
        
            
    def generar_productos_por_dia(self):
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
    def agregar_boton_productos_por_dia(self):
        # Obtener una referencia a la pantalla principal
        main_screen = self.root  # o self.screen_manager.current_screen si usas ScreenManager
        
        # Crear el botón con estilo destacado
        btn = MDRaisedButton(
            text="PRODUCTOS POR DÍA",
            pos_hint={"center_x": 0.5, "center_y": 0.5},  # Centrado en la pantalla
            size_hint=(0.8, None),
            height="60dp",  # Más alto para ser más visible
            md_bg_color=(1, 0, 0, 1),  # Rojo para ser muy visible
            on_release=lambda x: self.generar_productos_por_dia()
        )
        
        # Añadir directamente a la pantalla principal
        main_screen.add_widget(btn)
        print("Botón añadido directamente a la pantalla principal")
    def on_start(self):
        # Este método se llama automáticamente cuando la aplicación inicia
        self.agregar_boton_productos_por_dia()
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
        
        content = MDBoxLayout(orientation='vertical', spacing=10, size_hint_y=None)
        content.height = len(pedidos) * dp(80)
        self.edicion_pedidos = []
        
        for pedido in pedidos:
            id_pedido, producto, cantidad, costo, zona = pedido
            item = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(60))
            item.add_widget(TwoLineListItem(text=producto, secondary_text=zona, size_hint_x=0.4))
            
            cantidad_input = MDTextField(text=str(cantidad), input_filter='int', size_hint_x=0.2)
            item.add_widget(cantidad_input)
            
            costo_input = MDTextField(text=str(costo), input_filter='float', size_hint_x=0.3)
            item.add_widget(costo_input)
            
            content.add_widget(item)
            self.edicion_pedidos.append((id_pedido, cantidad_input, costo_input))
        
        self.dialog_edicion = MDDialog(
            title=f"Editar pedidos de {cliente}",
            type="custom",
            content_cls=content,
            buttons=[
                MDRaisedButton(text="Guardar", on_release=self.guardar_cambios),
                MDFlatButton(text="Cancelar", on_release=lambda x: self.dialog_edicion.dismiss())
            ]
        )
        self.dialog_edicion.open()

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
    def generar_reporte_productos_por_dia(self):
        try:
            # Obtener la fecha actual
            fecha_actual = datetime.now().strftime("%Y-%m-%d")
            
            # Crear un diccionario para acumular productos y cantidades
            productos_acumulados = {}
            
            # Suponiendo que tienes una lista de pedidos del día
            # Puedes filtrar los pedidos por fecha si es necesario
            for pedido in self.pedidos:  # Reemplaza con tu estructura de datos de pedidos
                if pedido['fecha'] == fecha_actual:  # Ajusta según cómo almacenas la fecha
                    for item in pedido['items']:  # Ajusta según cómo almacenas los items de pedido
                        nombre_producto = item['producto']
                        cantidad = item['cantidad']
                        
                        if nombre_producto in productos_acumulados:
                            productos_acumulados[nombre_producto] += cantidad
                        else:
                            productos_acumulados[nombre_producto] = cantidad
            
            # Crear el PDF
            pdf = ProductosPorDiaPDF()
            pdf.add_page()
            
            # Título con fecha
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, f"Fecha: {fecha_actual}", 0, 1)
            pdf.ln(5)
            
            # Encabezados de tabla
            pdf.set_fill_color(200, 200, 200)
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(120, 10, "Producto", 1, 0, 'C', 1)
            pdf.cell(70, 10, "Cantidad", 1, 1, 'C', 1)
            
            # Datos de la tabla
            pdf.set_font('Arial', '', 10)
            for producto, cantidad in productos_acumulados.items():
                pdf.cell(120, 10, producto, 1, 0)
                pdf.cell(70, 10, str(cantidad), 1, 1, 'C')
            
            # Guardar el PDF
            directorio = "reportes"
            if not os.path.exists(directorio):
                os.makedirs(directorio)
            
            nombre_archivo = f"{directorio}/productos_por_dia_{fecha_actual}.pdf"
            pdf.output(nombre_archivo)
            
            # Mostrar mensaje de éxito
            self.mostrar_dialogo("Éxito", f"Reporte generado exitosamente.\nGuardado en: {nombre_archivo}")
            
        except Exception as e:
            self.mostrar_dialogo("Error", f"No se pudo generar el reporte: {str(e)}")
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
                
    def agregar_boton_reporte_diario(self, layout):
        btn_reporte_diario = MDRaisedButton(
            text="PRODUCTOS POR DÍA",
            pos_hint={"center_x": 0.5},
            size_hint=(0.8, None),
            height="48dp",
            on_release=lambda x: self.generar_reporte_productos_por_dia()
        )
        layout.add_widget(btn_reporte_diario)        
            
            
            
            
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