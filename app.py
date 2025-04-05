from kivymd.app import MDApp
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.list import OneLineListItem
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.screen import Screen
from kivy.metrics import dp
from kivy.animation import Animation
import mysql.connector
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
import os
import re

# --- Funciones de base de datos ---
def conectar_bd():
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='distriñulpi'
    )
    return conn

def inicializar_bd():
    conn = conectar_bd()
    cursor = conn.cursor()
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
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nombre VARCHAR(255) UNIQUE,
        costo DECIMAL(10,2),
        precio_venta DECIMAL(10,2)
    )''')
    conn.commit()
    cursor.close()
    conn.close()

def obtener_clientes(texto_ingresado):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT nombre FROM clientes WHERE nombre LIKE %s LIMIT 5", (f"%{texto_ingresado}%",))
    clientes = cursor.fetchall()
    cursor.close()
    conn.close()
    return [cliente[0] for cliente in clientes]

def obtener_productos(texto_ingresado):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT nombre FROM productos WHERE nombre LIKE %s LIMIT 5", (f"%{texto_ingresado}%",))
    productos = cursor.fetchall()
    cursor.close()
    conn.close()
    return [producto[0] for producto in productos]

def insertar_pedido(cliente, producto, cantidad, costo, zona):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pedidos (cliente, producto, cantidad, costo, zona) VALUES (%s, %s, %s, %s, %s)",
                   (cliente, producto, cantidad, costo, zona))
    conn.commit()
    cursor.close()
    conn.close()

# --- Funciones de notificación y menú ---
def mostrar_notificacion(mensaje):
    dialog = MDDialog(title="📢 Notificación", text=mensaje, buttons=[MDFlatButton(text="OK", on_release=lambda x: dialog.dismiss())])
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
def obtener_costo_producto(nombre_producto):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT costo FROM productos WHERE nombre = %s", (nombre_producto,))
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()
    return resultado[0] if resultado else ""

# --- Clase principal de la aplicación ---
class PedidoApp(MDApp):


    def build(self):
        inicializar_bd()
        self.menu = None
        self.menu_clientes_editar = None
        self.edicion_pedidos = []  # Almacenará tuplas (id, campo_cantidad, campo_costo)
        self.screen = Screen()
        return self.crear_interfaz()

    def crear_interfaz(self):
        layout = MDBoxLayout(orientation='vertical', padding=20, spacing=20)
        
        # Campo para cliente con autocompletar
        self.cliente = MDTextField(hint_text='Nombre del cliente ✍️', size_hint_x=0.9, pos_hint={"center_x": 0.5})
        self.cliente.bind(text=self.sugerir_clientes)
        
        # Campo para producto con autocompletar
        self.producto = MDTextField(hint_text='Producto 🔍', helper_text='Escribe para autocompletar', helper_text_mode='on_focus', size_hint_x=0.9, pos_hint={"center_x": 0.5})
        self.producto.bind(text=self.sugerir_productos)
        
        self.cantidad = MDTextField(hint_text='Cantidad 🔢', input_filter='int', size_hint_x=0.9, pos_hint={"center_x": 0.5})
        self.costo = MDTextField(hint_text='Costo por producto 💲', input_filter='float', size_hint_x=0.9, pos_hint={"center_x": 0.5})
        
        self.zona = MDRaisedButton(text='📍 Seleccionar Zona', size_hint=(0.6, None), height=dp(40),
                                   pos_hint={"center_x": 0.5}, on_release=self.mostrar_zonas)
        
        boton_enviar = MDRaisedButton(text='✅ Registrar Pedido', size_hint=(0.6, None), height=dp(40),
                                      pos_hint={"center_x": 0.5}, on_release=self.registrar_pedido)
        boton_ver_pedidos = MDRaisedButton(text='📄 Ver Pedidos del Día', size_hint=(0.6, None), height=dp(40),
                                          pos_hint={"center_x": 0.5}, on_release=self.ver_pedidos_dia)
        self.boton_modificar_pedidos = MDRaisedButton(text='✏️ Modificar Pedidos', size_hint=(0.6, None), height=dp(40),
                                                      pos_hint={"center_x": 0.5}, on_release=self.mostrar_clientes_para_editar)
        
        layout.add_widget(self.cliente)
        layout.add_widget(self.producto)
        layout.add_widget(self.cantidad)
        layout.add_widget(self.costo)
        layout.add_widget(self.zona)
        layout.add_widget(boton_enviar)
        layout.add_widget(boton_ver_pedidos)
        layout.add_widget(self.boton_modificar_pedidos)
        
        self.screen.add_widget(layout)
        return self.screen

    def registrar_pedido(self, instance):
        cliente = self.cliente.text.strip()
        producto = self.producto.text.strip()
        cantidad = self.cantidad.text.strip()
        costo = self.costo.text.strip()
        zona = self.zona.text.strip()
        if not all([cliente, producto, cantidad, costo, zona]):
            mostrar_notificacion("⚠️ Todos los campos son obligatorios.")
            return
        # Insertar cliente si no existe y registrar el pedido
        conn_db = conectar_bd()
        cur = conn_db.cursor()
        cur.execute("INSERT IGNORE INTO clientes (nombre) VALUES (%s)", (cliente,))
        cur.close()
        conn_db.commit()
        insertar_pedido(cliente, producto, cantidad, costo, zona)
        mostrar_notificacion("✅ Pedido registrado con éxito.")
        anim = Animation(opacity=0.5, duration=0.1) + Animation(opacity=1, duration=0.1)
        anim.start(self.zona)

    def sugerir_clientes(self, instance, texto):
        texto = texto.strip()
        if not texto:
            return
        clientes = obtener_clientes(texto)
        if clientes:
            crear_menu_sugerencias(self, clientes, self.cliente)

    def sugerir_productos(self, instance, texto):
        texto = texto.strip()
        if not texto:
            return
        productos = obtener_productos(texto)
        if productos:
            crear_menu_sugerencias(self, productos, self.producto)
            
    
    def seleccionar_sugerencia(self, texto, campo):
        campo.text = texto
        if self.menu:
            self.menu.dismiss()
        # Si el campo seleccionado es el producto, autocompletar el costo
        if campo == self.producto:
            costo = obtener_costo_producto(texto)
            self.costo.text = str(costo)


    def mostrar_zonas(self, instance):
        zonas = ["Bernal", "Avellaneda #1", "Avellaneda #2", "Quilmes Centro", "Solano"]
        menu_items = [
            {"text": zona, "viewclass": "OneLineListItem", "on_release": lambda x=zona: self.seleccionar_zona(x)}
            for zona in zonas
        ]
        if hasattr(self, "menu_zonas") and self.menu_zonas:
            self.menu_zonas.dismiss()
        self.menu_zonas = MDDropdownMenu(caller=self.zona, items=menu_items, width_mult=4)
        self.menu_zonas.open()

    def seleccionar_producto(self, producto_text):
        self.producto.text = producto_text
        if hasattr(self, "menu_productos") and self.menu_productos:
            self.menu_productos.dismiss()
        conn_db = conectar_bd()
        cur = conn_db.cursor()
        # Obtener el precio de venta desde la tabla 'productos'
        cur.execute("SELECT precio_venta FROM productos WHERE nombre = %s ORDER BY id DESC LIMIT 1", (producto_text,))
        res = cur.fetchone()
        cur.close()
        conn_db.close()
        if res:
            self.costo.text = str(res[0])


    def ver_pedidos_dia(self, instance):
        conn_db = conectar_bd()
        cur = conn_db.cursor()
        cur.execute("SELECT cliente, producto, cantidad, costo, zona FROM pedidos WHERE fecha = CURDATE()")
        pedidos = cur.fetchall()
        cur.close()
        conn_db.close()
        if not pedidos:
            mostrar_notificacion("📄 No hay pedidos registrados hoy.")
            return
        mensaje = "\n".join([f"{p[0]} - {p[1]} x{p[2]} - ${p[3]} ({p[4]})" for p in pedidos])
        mostrar_notificacion(mensaje)

    # --- Funcionalidad para modificar pedidos ---
    def mostrar_clientes_para_editar(self, instance):
        conn_db = conectar_bd()
        cur = conn_db.cursor()
        cur.execute("SELECT DISTINCT nombre FROM clientes WHERE nombre IN (SELECT cliente FROM pedidos WHERE fecha = CURDATE())")
        clientes = cur.fetchall()
        cur.close()
        conn_db.close()
        if not clientes:
            mostrar_notificacion("🙈 No hay pedidos registrados hoy.")
            return
        menu_items = [
            {"text": cliente[0], "viewclass": "OneLineListItem", "on_release": lambda x=cliente[0]: self.abrir_edicion_cliente(x)}
            for cliente in clientes
        ]
        if hasattr(self, "menu_clientes_editar") and self.menu_clientes_editar:
            self.menu_clientes_editar.dismiss()
        self.menu_clientes_editar = MDDropdownMenu(caller=self.boton_modificar_pedidos, items=menu_items, width_mult=4)
        self.menu_clientes_editar.open()

    def abrir_edicion_cliente(self, cliente):
        if hasattr(self, "menu_clientes_editar") and self.menu_clientes_editar:
            self.menu_clientes_editar.dismiss()
        conn_db = conectar_bd()
        cur = conn_db.cursor()
        cur.execute("SELECT id, producto, cantidad, costo, zona FROM pedidos WHERE cliente = %s AND fecha = CURDATE()", (cliente,))
        pedidos = cur.fetchall()
        cur.close()
        conn_db.close()
        if not pedidos:
            mostrar_notificacion("🙈 No hay pedidos para este cliente hoy.")
            return
        contenido = MDBoxLayout(orientation='vertical', spacing=10, padding=10)
        self.edicion_pedidos = []  # Para almacenar (id, campo_cantidad, campo_costo)
        for pedido in pedidos:
            id_pedido, producto, cantidad, costo, zona = pedido
            order_layout = MDBoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=dp(40))
            etiqueta = OneLineListItem(text=f"{producto} ({zona})", size_hint_x=0.5)
            order_layout.add_widget(etiqueta)
            campo_cantidad = MDTextField(text=str(cantidad), hint_text="Cantidad", size_hint_x=0.25, input_filter='int')
            order_layout.add_widget(campo_cantidad)
            campo_costo = MDTextField(text=str(costo), hint_text="Costo", size_hint_x=0.25, input_filter='float')
            order_layout.add_widget(campo_costo)
            contenido.add_widget(order_layout)
            self.edicion_pedidos.append((id_pedido, campo_cantidad, campo_costo))
        
        def guardar_cambios(instance_button):
            conn_db = conectar_bd()
            cur = conn_db.cursor()
            for id_pedido, campo_cantidad, campo_costo in self.edicion_pedidos:
                nueva_cantidad = campo_cantidad.text.strip()
                nuevo_costo = campo_costo.text.strip()
                if not nueva_cantidad or not nuevo_costo:
                    mostrar_notificacion("⚠️ Los campos no pueden estar vacíos.")
                    return
                cur.execute("UPDATE pedidos SET cantidad=%s, costo=%s WHERE id=%s", (nueva_cantidad, nuevo_costo, id_pedido))
            conn_db.commit()
            cur.close()
            conn_db.close()
            self.dialog_edicion.dismiss()
            mostrar_notificacion("✅ Pedidos actualizados correctamente.")
        
        self.dialog_edicion = MDDialog(
            title=f"✏️ Editar pedidos de {cliente}",
            type="custom",
            content_cls=contenido,
            buttons=[
                MDRaisedButton(text="Guardar", on_release=guardar_cambios),
                MDFlatButton(text="Cancelar", on_release=lambda x: self.dialog_edicion.dismiss())
            ]
        )
        self.dialog_edicion.open()

PedidoApp().run()
