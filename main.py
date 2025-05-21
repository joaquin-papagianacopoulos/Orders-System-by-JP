import flet as ft
import mysql.connector
import pandas as pd
import os
import datetime
import matplotlib
# Configurar el backend 'Agg' de matplotlib (no requiere interfaz gráfica)
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from io import BytesIO

# Configuración de la conexión a la base de datos
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'joacoelmascapo',
    'database': 'distrisulpi'
}

# Clase principal para la aplicación
class DistriSulpiApp:
    def __init__(self):
        self.initialize_database()
        
    def initialize_database(self):
        """Inicializa la base de datos si no existe"""
        try:
            conn = mysql.connector.connect(
                host=DB_CONFIG['host'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password']
            )
            cursor = conn.cursor()
            
            # Crear la base de datos si no existe
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
            
            # Conectar a la base de datos
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            # Crear tablas necesarias
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nombre VARCHAR(255) NOT NULL,
                precio_venta DECIMAL(10, 2) NOT NULL,
                costo DECIMAL(10, 2) NOT NULL,
                stock INT NOT NULL
            )
            """)
            
            # Modificación importante: Asegurarnos de que la tabla pedidos tenga la columna 'total'
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                cliente VARCHAR(255) NOT NULL,
                zona VARCHAR(50) NOT NULL,
                fecha DATETIME NOT NULL,
                total DECIMAL(10, 2) NOT NULL
            )
            """)
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS detalle_pedido (
                id INT AUTO_INCREMENT PRIMARY KEY,
                pedido_id INT NOT NULL,
                producto_id INT NOT NULL,
                cantidad INT NOT NULL,
                precio_unitario DECIMAL(10, 2) NOT NULL,
                subtotal DECIMAL(10, 2) NOT NULL,
                FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
                FOREIGN KEY (producto_id) REFERENCES productos(id)
            )
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            print("Base de datos inicializada correctamente")
        except Exception as e:
            print(f"Error al inicializar la base de datos: {e}")

    def get_db_connection(self):
        """Establece una conexión a la base de datos"""
        try:
            return mysql.connector.connect(**DB_CONFIG)
        except Exception as e:
            print(f"Error de conexión a la base de datos: {e}")
            return None

    def get_productos(self):
        """Obtiene todos los productos de la base de datos"""
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, nombre, precio_venta, costo, stock FROM productos")
            productos = cursor.fetchall()
            cursor.close()
            conn.close()
            return productos
        return []

    def get_zonas(self):
        """Devuelve las zonas disponibles"""
        return ["Bernal", "Avellaneda #1", "Avellaneda #2", "Quilmes", "Solano"]


    # Necesitamos modificarla para que acepte un parámetro de fecha:
    def guardar_pedido(self, cliente, zona, detalles, fecha=None):
        """Guarda un pedido en la base de datos"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Calcular el total del pedido
            total_pedido = sum(item["subtotal"] for item in detalles)
            
            # Verificar primero si la columna 'total' existe en la tabla pedidos
            cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME = 'pedidos'
            AND COLUMN_NAME = 'total'
            """, (DB_CONFIG['database'],))
            
            column_exists = cursor.fetchone()[0] > 0
            
            # Si la columna no existe, agregarla
            if not column_exists:
                cursor.execute("ALTER TABLE pedidos ADD COLUMN total DECIMAL(10, 2) NOT NULL")
                print("Columna 'total' agregada a la tabla 'pedidos'")
            
            # Usar fecha proporcionada o la actual
            fecha_pedido = fecha if fecha else datetime.datetime.now()
            
            # Insertar el pedido
            cursor.execute(
                "INSERT INTO pedidos (cliente, zona, fecha, total) VALUES (%s, %s, %s, %s)",
                (cliente, zona, fecha_pedido, total_pedido)
            )
            
            # Obtener el ID del pedido insertado
            pedido_id = cursor.lastrowid
            
            # Insertar los detalles del pedido
            for item in detalles:
                cursor.execute(
                    """INSERT INTO detalle_pedido 
                    (pedido_id, producto_id, cantidad, precio_unitario, subtotal) 
                    VALUES (%s, %s, %s, %s, %s)""",
                    (pedido_id, item["producto_id"], item["cantidad"], 
                    item["precio_unitario"], item["subtotal"])
                )
                
                # Actualizar el stock
                cursor.execute(
                    "UPDATE productos SET stock = stock - %s WHERE id = %s",
                    (item["cantidad"], item["producto_id"])
                )
            
            conn.commit()
            cursor.close()
            conn.close()
            return pedido_id
        except Exception as e:
            print(f"Error al guardar el pedido: {e}")
            if conn:
                conn.rollback()
                cursor.close()
                conn.close()
            return None

    def cargar_csv_productos(self, file_path):
        """Carga productos desde un archivo CSV a la base de datos"""
        try:
            df = pd.read_csv(file_path)
            
            # Verificar que el CSV tenga las columnas necesarias
            required_columns = ["nombre", "precio_venta", "costo", "stock"]
            if not all(col in df.columns for col in required_columns):
                return False, "El archivo CSV no tiene las columnas requeridas"
            
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Insertar o actualizar productos
            for _, row in df.iterrows():
                cursor.execute(
                    """INSERT INTO productos (nombre, precio_venta, costo, stock) 
                    VALUES (%s, %s, %s, %s) 
                    ON DUPLICATE KEY UPDATE 
                    precio_venta = VALUES(precio_venta),
                    costo = VALUES(costo), 
                    stock = VALUES(stock)""",
                    (row["nombre"], row["precio_venta"], row["costo"], row["stock"])
                )
            
            conn.commit()
            cursor.close()
            conn.close()
            return True, f"Se importaron {len(df)} productos correctamente"
        except Exception as e:
            return False, f"Error al importar CSV: {e}"

    def get_ventas_diarias(self):
        """Obtiene las ventas del día actual"""
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute("""
            SELECT p.id, p.cliente, p.zona, p.fecha, p.total,
                   pr.nombre as producto, dp.cantidad, dp.precio_unitario, dp.subtotal
            FROM pedidos p
            JOIN detalle_pedido dp ON p.id = dp.pedido_id
            JOIN productos pr ON dp.producto_id = pr.id
            WHERE DATE(p.fecha) = %s
            ORDER BY p.fecha DESC
            """, (today,))
            
            ventas = cursor.fetchall()
            cursor.close()
            conn.close()
            return ventas
        return []

    def get_ventas_ultimos_30_dias(self):
        """Obtiene las ventas de los últimos 30 días"""
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            fecha_inicio = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
            
            cursor.execute("""
            SELECT DATE(fecha) as dia, SUM(p.total) as total_ventas, COUNT(*) as num_pedidos
            FROM pedidos p
            WHERE p.fecha >= %s
            GROUP BY DATE(p.fecha)
            ORDER BY dia
            """, (fecha_inicio,))
            
            ventas = cursor.fetchall()
            cursor.close()
            conn.close()
            return ventas
        return []

    def generar_prediccion_ventas(self):
        """Genera una predicción de ventas futuras basada en datos históricos"""
        try:
            # Obtener datos históricos de ventas
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Obtener todas las ventas para tener suficientes datos
            cursor.execute("""
            SELECT DATE(fecha) as dia, SUM(total) as total_ventas
            FROM pedidos
            GROUP BY DATE(fecha)
            ORDER BY dia
            """)
            
            resultados = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if len(resultados) < 10:  # Necesitamos suficientes datos para la predicción
                return None, "No hay suficientes datos históricos para hacer una predicción precisa"
            
            # Preparar datos para el modelo
            fechas = []
            ventas = []
            for dia, total in resultados:
                if isinstance(dia, str):
                    dia = datetime.datetime.strptime(dia, "%Y-%m-%d").date()
                fechas.append((dia - resultados[0][0]).days)  # Convertir fechas a días desde la primera venta
                ventas.append(float(total))
            
            # Convertir a arrays de NumPy
            X = np.array(fechas).reshape(-1, 1)
            y = np.array(ventas)
            
            # Dividir datos para entrenamiento y prueba
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Entrenar modelo de regresión lineal
            model = LinearRegression()
            model.fit(X_train, y_train)
            
            # Evaluar el modelo
            score = model.score(X_test, y_test)
            
            # Predicción para los próximos 30 días
            ultimo_dia = fechas[-1]
            dias_futuros = np.array(range(ultimo_dia + 1, ultimo_dia + 31)).reshape(-1, 1)
            predicciones = model.predict(dias_futuros)
            
            # Convertir días futuros a fechas reales
            primer_dia = resultados[0][0]
            fechas_futuras = [primer_dia + datetime.timedelta(days=int(dia)) for dia in dias_futuros.flatten()]
            
            return {
                'fechas': fechas_futuras,
                'predicciones': predicciones.tolist(),
                'precision': score
            }, "Predicción generada correctamente"
        except Exception as e:
            return None, f"Error al generar predicción: {e}"
    ## ESTADISTICAS ##
    def get_productos_mas_vendidos(self, limit=5):
        """Obtiene los productos más vendidos de todos los tiempos"""
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
            SELECT p.id, p.nombre, SUM(dp.cantidad) as total_vendido
            FROM detalle_pedido dp
            JOIN productos p ON dp.producto_id = p.id
            GROUP BY p.id, p.nombre
            ORDER BY total_vendido DESC
            LIMIT %s
            """, (limit,))
            productos = cursor.fetchall()
            cursor.close()
            conn.close()
            return productos
        return []

    def get_ganancia_diaria(self):
        """Obtiene la ganancia del día actual"""
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute("""
            SELECT SUM((dp.precio_unitario - p.costo) * dp.cantidad) as ganancia
            FROM pedidos ped
            JOIN detalle_pedido dp ON ped.id = dp.pedido_id
            JOIN productos p ON dp.producto_id = p.id
            WHERE DATE(ped.fecha) = %s
            """, (today,))
            
            resultado = cursor.fetchone()
            cursor.close()
            conn.close()
            return resultado['ganancia'] if resultado and resultado['ganancia'] is not None else 0
        return 0

    def get_ganancia_anual(self):
        """Obtiene la ganancia del año actual"""
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            current_year = datetime.datetime.now().year
            
            cursor.execute("""
            SELECT SUM((dp.precio_unitario - p.costo) * dp.cantidad) as ganancia
            FROM pedidos ped
            JOIN detalle_pedido dp ON ped.id = dp.pedido_id
            JOIN productos p ON dp.producto_id = p.id
            WHERE YEAR(ped.fecha) = %s
            """, (current_year,))
            
            resultado = cursor.fetchone()
            cursor.close()
            conn.close()
            return resultado['ganancia'] if resultado and resultado['ganancia'] is not None else 0
        return 0

    def get_facturacion_diaria(self):
        """Obtiene el total facturado del día actual"""
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute("""
            SELECT SUM(total) as facturacion
            FROM pedidos
            WHERE DATE(fecha) = %s
            """, (today,))
            
            resultado = cursor.fetchone()
            cursor.close()
            conn.close()
            return resultado['facturacion'] if resultado and resultado['facturacion'] is not None else 0
        return 0

    def get_facturacion_anual(self):
        """Obtiene el total facturado del año actual"""
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            current_year = datetime.datetime.now().year
            
            cursor.execute("""
            SELECT SUM(total) as facturacion
            FROM pedidos
            WHERE YEAR(fecha) = %s
            """, (current_year,))
            
            resultado = cursor.fetchone()
            cursor.close()
            conn.close()
            return resultado['facturacion'] if resultado and resultado['facturacion'] is not None else 0
        return 0
    # 1. Añade este método a la clase DistriSulpiApp
    def buscar_clientes(self, query):
        """Busca clientes por nombre similar"""
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            # Usar LIKE para buscar clientes con nombres similares
            cursor.execute("""
            SELECT DISTINCT cliente 
            FROM pedidos 
            WHERE cliente LIKE %s 
            ORDER BY cliente
            LIMIT 5
            """, (f"%{query}%",))
            
            clientes = cursor.fetchall()
            cursor.close()
            conn.close()
            return [cliente["cliente"] for cliente in clientes]
        return []
    def generar_pdf_factura(self, pedido_id):
        """Genera un PDF con la factura del pedido"""
        try:
            # Crear directorio para PDFs si no existe
            os.makedirs("temp", exist_ok=True)
            
            conn = self.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Obtener información del pedido
            cursor.execute("""
            SELECT p.*, c.cliente, c.zona, c.fecha, c.total as total_pedido
            FROM detalle_pedido p
            JOIN pedidos c ON p.pedido_id = c.id
            WHERE p.pedido_id = %s
            """, (pedido_id,))
            
            detalles = cursor.fetchall()
            
            if not detalles:
                return None, "Pedido no encontrado"
            
            # Obtener nombres de productos
            for detalle in detalles:
                cursor.execute("SELECT nombre FROM productos WHERE id = %s", (detalle['producto_id'],))
                producto = cursor.fetchone()
                detalle['producto_nombre'] = producto['nombre'] if producto else "Producto desconocido"
            
            cursor.close()
            conn.close()
            
            # Crear PDF en memoria
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            elements = []
            
            # Estilos
            styles = getSampleStyleSheet()
            
            # Título y datos del cliente
            elements.append(Paragraph(f"<b>DistriSulpi - Factura #{pedido_id}</b>", styles['Title']))
            
            # Información del cliente en formato de tabla para mejor presentación
            data_cliente = [
                [Paragraph("<b>Cliente:</b>", styles['Normal']), detalles[0]['cliente']],
                [Paragraph("<b>Zona:</b>", styles['Normal']), detalles[0]['zona']],
                [Paragraph("<b>Fecha:</b>", styles['Normal']), detalles[0]['fecha'].strftime('%d/%m/%Y %H:%M')],
                [Paragraph("<b>Nro. Factura:</b>", styles['Normal']), f"#{pedido_id}"]
            ]
            
            # Crear tabla de datos del cliente
            tabla_cliente = Table(data_cliente, colWidths=[doc.width*0.3, doc.width*0.7])
            tabla_cliente.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lavender),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('BACKGROUND', (1, 0), (1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            
            elements.append(tabla_cliente)
            elements.append(Paragraph("<br/>", styles['Normal']))
            
            # Limitamos la longitud del nombre del producto si es necesario
            max_chars = 30  # Limitar a 30 caracteres
            data = [["Producto", "Cantidad", "Precio Unit.", "Subtotal"]]
            
            total = 0
            for detalle in detalles:
                # Limitar el nombre del producto si es demasiado largo
                nombre_producto = detalle['producto_nombre']
                if len(nombre_producto) > max_chars:
                    nombre_producto = nombre_producto[:max_chars] + "..."
                
                data.append([
                    nombre_producto,
                    str(detalle['cantidad']),
                    f"${detalle['precio_unitario']:.2f}",
                    f"${detalle['subtotal']:.2f}"
                ])
                total += detalle['subtotal']
            
            # Agregar fila de total - corregir el formato para evitar etiquetas HTML
            # Usamos texto simple y aplicamos estilos con TableStyle
            data.append(["", "", "TOTAL", f"${total:.2f}"])
            
            # Crear tabla con anchos mejorados
            col_widths = [doc.width*0.5, doc.width*0.1, doc.width*0.2, doc.width*0.2]
            table = Table(data, colWidths=col_widths)
            
            # Aplicar estilos a la tabla para mejor visualización
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                # Alineaciones específicas por columna
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),     # Producto a la izquierda
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),   # Cantidad centrada
                ('ALIGN', (2, 0), (3, -1), 'RIGHT'),    # Precios a la derecha
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                # Ajustar el formato de la fila de total
                ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -2), 1, colors.black),
                ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
                ('GRID', (2, -1), (-1, -1), 1, colors.black),
            ]))
            
            elements.append(table)
    
            
            # Generar PDF
            doc.build(elements)
            
            # Obtener el contenido del PDF
            pdf_content = buffer.getvalue()
            buffer.close()
            
            return pdf_content, "Factura generada correctamente"
        except Exception as e:
            return None, f"Error al generar factura: {e}"

    def generar_pdf_pedidos_hoy(self):
        """Genera un PDF con todos los pedidos del día"""
        try:
            ventas_hoy = self.get_ventas_diarias()
            
            if not ventas_hoy:
                return None, "No hay ventas registradas hoy"
            
            # Crear diccionario agrupado por producto
            productos_vendidos = {}
            for venta in ventas_hoy:
                if venta['producto'] in productos_vendidos:
                    productos_vendidos[venta['producto']] += venta['cantidad']
                else:
                    productos_vendidos[venta['producto']] = venta['cantidad']
            
            # Crear PDF en memoria
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            elements = []
            
            # Estilos
            styles = getSampleStyleSheet()
            
            # Título
            fecha_hoy = datetime.datetime.now().strftime("%d/%m/%Y")
            elements.append(Paragraph(f"<b>DistriSulpi - Ventas del día {fecha_hoy}</b>", styles['Title']))
            elements.append(Paragraph("<br/>", styles['Normal']))
            
            # Tabla de productos vendidos
            data = [["Producto", "Cantidad Total"]]
            
            for producto, cantidad in productos_vendidos.items():
                data.append([producto, str(cantidad)])
            
            # Crear tabla
            table = Table(data, colWidths=[doc.width*0.7, doc.width*0.3])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            elements.append(table)
            
            # Generar PDF
            doc.build(elements)
            
            # Obtener el contenido del PDF
            pdf_content = buffer.getvalue()
            buffer.close()
            
            return pdf_content, "Reporte generado correctamente"
        except Exception as e:
            return None, f"Error al generar reporte: {e}"

# Implementación de la interfaz de usuario con Flet
def main(page: ft.Page):
    # Instancia de la aplicación
    app = DistriSulpiApp()
    fecha_pedido = datetime.datetime.now()
    # Configuración de la página con tema personalizado
    page.title = "DistriSulpi 📦"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 10
    page.scroll = ft.ScrollMode.AUTO
    # Variable para almacenar la fecha actual del pedido
    fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Variables para el pedido actual
    current_order = []
    cliente_actual = ""
    zona_actual = ""
    # Tema personalizado con colores más atractivos
    page.theme = ft.Theme(
        color_scheme_seed=ft.Colors.PURPLE,
        color_scheme=ft.ColorScheme(
            primary=ft.Colors.PURPLE,
            secondary=ft.Colors.PINK_200
        )
    )
    page.dark_theme = ft.Theme(
        color_scheme_seed=ft.Colors.PURPLE,
        color_scheme=ft.ColorScheme(
            primary=ft.Colors.PURPLE_400,
            secondary=ft.Colors.PINK_300,
            surface=ft.Colors.GREY_900,
            background=ft.Colors.GREY_900,
        )
    )
    
    # Responsive design para móviles
    page.on_resize = lambda _: page.update()
    
    # Variables para el pedido actual
    current_order = []
    cliente_actual = ""
    zona_actual = ""
    
    # Para prevenir la carga múltiple de componentes
    components_loaded = False
    
    # ---------- COMPONENTES DE LA INTERFAZ ----------
    
    # Campo para el nombre del cliente
    cliente_field = ft.TextField(
        label="Nombre del Cliente",
        width=page.width - 20 if page.width < 600 else 400,
        on_change=lambda e: set_cliente(e.control.value)
    )
    sugerencias_clientes_container = ft.Container(
        content=ft.Column([], tight=True),
        visible=False,
        width=page.width - 20 if page.width < 600 else 400,
        bgcolor=ft.Colors.PURPLE,
        border=ft.border.all(1, ft.Colors.GREY_400),
        border_radius=ft.border_radius.only(
            bottom_left=5,
            bottom_right=5
        ),
        padding=5
    )
    # Selector de fecha
    fecha_picker = ft.DatePicker(
        on_change=lambda e: actualizar_fecha(e.control.value),
        first_date=datetime.datetime(2020, 1, 1),
        last_date=datetime.datetime(2030, 12, 31)
    )
    page.overlay.append(fecha_picker)

    fecha_field = ft.TextField(
        label="Fecha (DD/MM/AAAA)",
        value=datetime.datetime.now().strftime("%d/%m/%Y"),
        width=page.width - 20 if page.width < 600 else 250,
        hint_text="Ej: 15/05/2025",
        helper_text="Ingresa la fecha en formato DD/MM/AAAA"
    )

    hora_field = ft.TextField(
        label="Hora (HH:MM)",
        value=datetime.datetime.now().strftime("%H:%M"),
        width=page.width - 20 if page.width < 600 else 150,
        keyboard_type=ft.KeyboardType.NUMBER,
        hint_text="Ej: 14:30",
        helper_text="Ingresa la hora en formato HH:MM"
    )

    # Botón para actualizar la fecha/hora de forma explícita
    actualizar_fecha_btn = ft.ElevatedButton(
        text="Actualizar fecha/hora",
        icon=ft.Icons.UPDATE,
        on_click=lambda _: actualizar_fecha_hora()
    )
    def actualizar_fecha_hora():
        nonlocal fecha_pedido
        try:
            # Obtener valores de los campos
            fecha_str = fecha_field.value
            hora_str = hora_field.value
            
            # Validar que ambos campos tengan valores
            if not fecha_str or not hora_str:
                return
            
            # Completar la hora con segundos si es necesario
            if len(hora_str) == 5:  # formato HH:MM
                hora_str += ":00"
                
            # Intentar convertir a datetime
            nueva_fecha = datetime.datetime.strptime(f"{fecha_str} {hora_str}", "%d/%m/%Y %H:%M:%S")
            
            # Si la conversión fue exitosa, actualizar la variable
            fecha_pedido = nueva_fecha
            
            # Mostrar confirmación al usuario
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Fecha del pedido actualizada: {fecha_str} {hora_str}")
            )
            page.snack_bar.open = True
            page.update()
            
        except ValueError:
            # Si hay un error en el formato, mostrar mensaje
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Error: Formato de fecha u hora inválido. Use DD/MM/AAAA para fecha y HH:MM para hora.")
            )
            page.snack_bar.open = True
            page.update()

    # Eventos para los campos
    def on_fecha_change(e):
        actualizar_fecha_hora()

    def on_hora_change(e):
        actualizar_fecha_hora()

    # Configurar los eventos
    fecha_field.on_blur = on_fecha_change
    fecha_field.on_submit = on_fecha_change
    hora_field.on_blur = on_hora_change
    hora_field.on_submit = on_hora_change

    fecha_btn = ft.IconButton(
        icon=ft.Icons.CALENDAR_MONTH,
        tooltip="Seleccionar fecha",
        # Método correcto según la versión de Flet
        on_click=lambda _: setattr(fecha_picker, 'open', True),  # Usa .open = True en lugar de .pick_date()
        icon_color=ft.Colors.PURPLE_400,
        icon_size=30
    )

    # Botón para abrir el selector de fecha
    abrir_fecha_btn = ft.IconButton(
        icon=ft.Icons.CALENDAR_MONTH,
        tooltip="Seleccionar fecha",
        on_click=lambda _: fecha_picker.pick_date(),
    )
    
    # Dropdown para seleccionar zona
    zona_dropdown = ft.Dropdown(
        label="Zona",
        width=page.width - 20 if page.width < 600 else 400,
        options=[ft.dropdown.Option(zona) for zona in app.get_zonas()],
        on_change=lambda e: set_zona(e.control.value)
    )
    
    # Campo para buscar productos
    producto_search = ft.TextField(
        label="Buscar Producto",
        width=page.width - 20 if page.width < 600 else 400,
        on_change=lambda e: filtrar_productos(e.control.value)
    )
    
    # Lista de productos
    productos_list = ft.ListView(
        height=300,
        spacing=10,
        padding=10,
        auto_scroll=True
    )
    
    # Cantidad de producto
    cantidad_field = ft.TextField(
        label="Cantidad",
        width=100,
        value="1",
        keyboard_type=ft.KeyboardType.NUMBER
    )
    
    # Campo de precio (se puede modificar si es necesario)
    precio_field = ft.TextField(
        label="Precio",
        width=150,
        keyboard_type=ft.KeyboardType.NUMBER,
        read_only=True
    )
    
    # Tabla para mostrar el pedido actual
    pedido_actual_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Producto", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Cant.", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Precio", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Subtotal", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("", weight=ft.FontWeight.BOLD))
        ],
        width=page.width - 20
    )
    
    # Botón para finalizar el pedido
    finalizar_pedido_btn = ft.ElevatedButton(
        text="Finalizar Pedido",
        width=200,
        style=ft.ButtonStyle(
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.GREEN
        ),
        on_click=lambda _: finalizar_pedido()
    )
    
    # ---------- FUNCIONES DE CSV ----------
    
    def on_csv_selected(e):
        if e.files and len(e.files) > 0:
            file_path = e.files[0].path
            
            # Mostrar diálogo de progreso
            progress_dlg = ft.AlertDialog(
                title=ft.Text("Cargando productos"),
                content=ft.Column([
                    ft.Text("Procesando archivo CSV..."),
                    ft.ProgressBar(width=300)
                ], tight=True, spacing=20),
                modal=True
            )
            
            page.dialog = progress_dlg
            progress_dlg.open = True
            page.update()
            
            # Procesar CSV
            success, message = app.cargar_csv_productos(file_path)
            
            # Cerrar diálogo de progreso
            progress_dlg.open = False
            page.update()
            
            # Mostrar resultado
            result_dlg = ft.AlertDialog(
                title=ft.Text("Resultado de importación"),
                content=ft.Text(message),
                actions=[
                    ft.TextButton("Aceptar", on_click=lambda _: close_dlg(result_dlg))
                ],
                modal=True
            )
            
            page.dialog = result_dlg
            result_dlg.open = True
            page.update()
            
            # Actualizar lista de productos
            filtrar_productos("")
    
    # Campo para cargar CSV
    csv_upload = ft.FilePicker(on_result=on_csv_selected)
    page.overlay.append(csv_upload)
    
    csv_upload_btn = ft.ElevatedButton(
        "Cargar Productos desde CSV",
        icon=ft.Icons.UPLOAD_FILE,
        on_click=lambda _: csv_upload.pick_files(
            allow_multiple=False,
            allowed_extensions=["csv"]
        )
    )
    
    # ---------- SECCIÓN DE ESTADÍSTICAS ----------
    
    # Contenedor para estadísticas
    estadisticas_container = ft.Container(
        content=ft.Text("Cargando estadísticas..."),
        visible=False,
        padding=10
    )
    
    # Botón para mostrar estadísticas
    estadisticas_btn = ft.ElevatedButton(
        "Estadísticas de Ventas",
        icon=ft.Icons.BAR_CHART,
        on_click=lambda _: toggle_estadisticas()
    )
    
    # ---------- SECCIÓN DE PREDICCIÓN ----------
    
    # Contenedor para predicción
    prediccion_container = ft.Container(
        content=ft.Text("Cargando predicción..."),
        visible=False,
        padding=10
    )
    
    # Botón para mostrar predicción
    prediccion_btn = ft.ElevatedButton(
        "Predicción de Ventas (BETA)",
        icon=ft.Icons.TRENDING_UP,
        on_click=lambda _: toggle_prediccion()
    )
    
    # ---------- SECCIÓN DE PEDIDOS DE HOY ----------
    
    # Botón para generar PDF de pedidos de hoy
    pedidos_hoy_btn = ft.ElevatedButton(
        "Pedidos HOY",
        icon=ft.Icons.RECEIPT_LONG,
        on_click=lambda _: generar_pdf_pedidos_hoy()
    )
    
    # ---------- SECCIÓN DE VER TODOS LOS PEDIDOS ----------
    
    # Contenedor para todos los pedidos
    pedidos_container = ft.Container(
        content=ft.Text("Cargando pedidos..."),
        visible=False,
        padding=10
    )
    
    # Botón para mostrar todos los pedidos
    ver_pedidos_btn = ft.ElevatedButton(
        "Ver Todos los Pedidos",
        icon=ft.Icons.LIST_ALT,
        on_click=lambda _: toggle_ver_pedidos()
    )
    # ---------- ACTUALIZACIÓN DE FECHA Y HORA ---------
    # Función para actualizar la fecha cuando cambia el DatePicker
    def actualizar_fecha_manual(e):
        fecha_valor = e.control.value
        
        # Validar formato de fecha
        try:
            # Intentar convertir la fecha ingresada
            fecha_dt = datetime.datetime.strptime(fecha_valor, "%d/%m/%Y")
            
            # Si es válida, actualizar
            hora_valor = hora_field.value
            fecha_hora = f"{fecha_dt.strftime('%Y-%m-%d')} {hora_valor}:00"
            
            global fecha_actual
            fecha_actual = datetime.datetime.strptime(fecha_hora, "%Y-%m-%d %H:%M:%S")
            
            # Notificar al usuario
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Fecha cambiada: {fecha_valor}"))
            page.snack_bar.open = True
            page.update()
        except ValueError:
            page.snack_bar = ft.SnackBar(content=ft.Text("Formato de fecha inválido. Use DD/MM/AAAA"))
            page.snack_bar.open = True
            page.update()
    def actualizar_fecha(date_obj):
        if date_obj:
            # La fecha viene como string ISO (YYYY-MM-DD)
            fecha_iso = date_obj.split('T')[0] if 'T' in date_obj else date_obj
            
            try:
                # Convertir a datetime
                fecha_dt = datetime.datetime.strptime(fecha_iso, "%Y-%m-%d")
                
                # Actualizar el campo visible con formato DD/MM/YYYY
                fecha_field.value = fecha_dt.strftime("%d/%m/%Y")
                fecha_field.update()
                
                # Obtener la hora actual del campo
                hora_actual = hora_field.value
                
                # Combinar fecha y hora para tener datetime completo
                fecha_hora = f"{fecha_iso} {hora_actual}:00"
                global fecha_actual
                fecha_actual = datetime.datetime.strptime(fecha_hora, "%Y-%m-%d %H:%M:%S")
                
                # Notificar al usuario
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Fecha cambiada: {fecha_field.value}"))
                page.snack_bar.open = True
                page.update()
            except Exception as e:
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Error al procesar fecha: {e}"))
                page.snack_bar.open = True
                page.update()

    def actualizar_hora(e):
        hora_valor = e.control.value
        
        # Validar formato de hora
        if hora_valor and len(hora_valor) == 5 and ":" in hora_valor:
            try:
                # Obtener la fecha seleccionada actualmente
                fecha_seleccionada = fecha_field.value
                
                # Convertir al formato datetime
                fecha_dt = datetime.datetime.strptime(f"{fecha_seleccionada} {hora_valor}", "%d/%m/%Y %H:%M")
                
                # Guardar el valor completo
                global fecha_actual
                fecha_actual = fecha_dt
                
                # Notificar al usuario
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Hora cambiada: {hora_valor}"))
                page.snack_bar.open = True
                page.update()
            except ValueError:
                page.snack_bar = ft.SnackBar(content=ft.Text("Formato de hora inválido. Use HH:MM"))
                page.snack_bar.open = True
                page.update()

    def setup_hora_field_events():
        hora_field.on_submit = actualizar_hora
        hora_field.on_blur = actualizar_hora
        
    def configurar_eventos_fecha():
        # Añadir eventos para procesamiento manual
        hora_field.on_submit = actualizar_hora
        hora_field.on_blur = actualizar_hora
        fecha_field.on_submit = actualizar_fecha_manual
        fecha_field.on_blur = actualizar_fecha_manual
    # ---------- FUNCIONES DE LA INTERFAZ ----------
    
    def set_cliente(value):
        nonlocal cliente_actual
        cliente_actual = value
        
        # Buscar sugerencias si hay al menos 2 caracteres
        if len(value) >= 2:
            sugerencias = app.buscar_clientes(value)
            mostrar_sugerencias_cliente(sugerencias)
        else:
            sugerencias_clientes_container.visible = False
            sugerencias_clientes_container.update()
    def seleccionar_cliente(e):
        # Obtener el nombre del cliente seleccionado
        nombre_cliente = e.control.content.value
        # Establecer el valor en el campo de texto
        cliente_field.value = nombre_cliente
        cliente_field.update()
        # Actualizar variable
        set_cliente(nombre_cliente)
        # Ocultar sugerencias
        sugerencias_clientes_container.visible = False
        sugerencias_clientes_container.update()
        # Función para mostrar las sugerencias
    def mostrar_sugerencias_cliente(sugerencias):
        # Limpiar contenedor de sugerencias
        contenido = ft.Column([], tight=True)
        
        # Si hay sugerencias, mostrarlas
        if sugerencias:
            for cliente in sugerencias:
                sugerencia = ft.Container(
                    content=ft.Text(cliente),
                    padding=10,
                    width=cliente_field.width,
                    on_click=seleccionar_cliente
                )
                sugerencia.hover_color = ft.Colors.GREY_300
                contenido.controls.append(sugerencia)
            
            sugerencias_clientes_container.content = contenido
            sugerencias_clientes_container.visible = True
        else:
            sugerencias_clientes_container.visible = False
        
        sugerencias_clientes_container.update()
    
    def set_zona(value):
        nonlocal zona_actual
        zona_actual = value
        producto_seleccionado = None
        
    def aplicar_mejoras_movil():
        """Aplica todas las mejoras para dispositivos móviles"""
        # Detectar si estamos en móvil
        is_mobile = page.width < 800
        
        # Configurar la tabla de pedidos según el dispositivo
        configurar_tabla_pedido_responsivo()
        
        # Actualizar si hay productos en el pedido
        if current_order:
            actualizar_tabla_pedido()
            
            # Mostrar panel flotante si hay productos
            if hasattr(page, 'panel_flotante') and page.panel_flotante is not None:
                total = sum(item["subtotal"] for item in current_order)
                actualizar_panel_flotante(total)
        
        # Mostrar el panel flotante desde el principio si hay productos
        if is_mobile and hasattr(page, 'panel_flotante') and page.panel_flotante is not None:
            if len(current_order) > 0:
                page.panel_flotante.visible = True
                page.panel_flotante.update()
            else:
                page.panel_flotante.visible = False
                page.panel_flotante.update()
    # MODIFICACIÓN: Ahora la función add_product_to_list incluye la lógica para agregar al tocar
    def add_product_to_list(producto):
        # Función interna para manejar el clic en el producto
        def on_producto_click(e):
            try:
                # Obtener cantidad actual
                cantidad = 1
                try:
                    if cantidad_field.value:
                        cantidad = int(cantidad_field.value)
                        if cantidad <= 0:
                            cantidad = 1
                except:
                    cantidad = 1
                    
                # Verificar stock
                if cantidad > producto["stock"]:
                    page.snack_bar = ft.SnackBar(content=ft.Text(f"Stock insuficiente. Disponible: {producto['stock']}"))
                    page.snack_bar.open = True
                    page.update()
                    return
                    
                # Calcular subtotal
                precio = float(producto["precio_venta"])
                subtotal = precio * cantidad
                
                # Actualizar campo de precio
                precio_field.value = str(precio)
                precio_field.update()
                
                # Verificar si ya existe en el pedido
                encontrado = False
                for i, item in enumerate(current_order):
                    if item["producto_id"] == producto["id"]:
                        # Actualizar cantidad
                        current_order[i]["cantidad"] += cantidad
                        current_order[i]["subtotal"] = current_order[i]["cantidad"] * current_order[i]["precio_unitario"]
                        encontrado = True
                        break
                        
                # Si no se encontró, agregar como nuevo
                if not encontrado:
                    current_order.append({
                        "producto_id": producto["id"],
                        "producto_nombre": producto["nombre"],
                        "cantidad": cantidad,
                        "precio_unitario": precio,
                        "subtotal": subtotal
                    })
                    
                # Notificar
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Agregado: {producto['nombre']}"),
                    bgcolor=ft.Colors.GREEN
                )
                page.snack_bar.open = True
                
                # Actualizar tabla de pedidos
                actualizar_tabla_pedido()
                
                # Mostrar panel flotante con la información actualizada
                total = sum(item["subtotal"] for item in current_order)
                actualizar_panel_flotante(total)
                
                # Restablecer cantidad a 1 para el próximo producto
                cantidad_field.value = "1"
                cantidad_field.update()
                
            except Exception as e:
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Error: {str(e)}"))
                page.snack_bar.open = True
                page.update()
        
        # Crear el elemento visual mejorado para móviles
        productos_list.controls.append(
            ft.Container(
                content=ft.ListTile(
                    leading=ft.Icon(ft.Icons.INVENTORY_2, 
                                color=ft.Colors.GREEN if producto["stock"] > 10 
                                else ft.Colors.ORANGE if producto["stock"] > 0 
                                else ft.Colors.RED),
                    title=ft.Text(
                        producto["nombre"], 
                        size=16, 
                        weight=ft.FontWeight.BOLD,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    subtitle=ft.Column([
                        ft.Text(f"${producto['precio_venta']:.2f}", 
                            color=ft.Colors.BLUE),
                        ft.Text(f"Stock: {producto['stock']}", 
                            color=ft.Colors.GREEN if producto["stock"] > 10 
                            else ft.Colors.ORANGE if producto["stock"] > 0 
                            else ft.Colors.RED)
                    ]),
                    # Usar la función local para manejar el clic
                    on_click=on_producto_click
                ),
                border=ft.border.all(1, ft.Colors.BLACK26),
                border_radius=10,
                margin=5,
                padding=10
            )
        )


    
    def filtrar_productos(query):
        productos = app.get_productos()
        productos_list.controls.clear()
        
        if not query:
            for producto in productos:
                add_product_to_list(producto)
        else:
            query = query.lower()
            for producto in productos:
                if query in producto["nombre"].lower():
                    add_product_to_list(producto)
        
        # En lugar de actualizar solo el ListView, actualizar la página completa
        # Esto soluciona el problema del AssertionError
        page.update()
    
    # MODIFICACIÓN: Nueva función para actualizar cantidad directa desde la tabla
    def actualizar_cantidad_directa(nueva_cantidad, index):
        try:
            cantidad = int(nueva_cantidad)
            if cantidad <= 0:
                raise ValueError("Cantidad debe ser mayor a 0")
            
            # Actualizar cantidad y subtotal
            current_order[index]["cantidad"] = cantidad
            current_order[index]["subtotal"] = cantidad * current_order[index]["precio_unitario"]
            
            # Notificar al usuario del cambio
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Cantidad actualizada: {current_order[index]['producto_nombre']}")
            )
            page.snack_bar.open = True
            
            # Actualizar tabla
            actualizar_tabla_pedido()
            
        except ValueError as e:
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Error: {e}"))
            page.snack_bar.open = True
            # Revertir al valor anterior
            actualizar_tabla_pedido()
            page.update()
    def actualizar_panel_flotante(total=0):
        """Actualiza la información del panel flotante"""
        if not hasattr(page, 'panel_flotante') or page.panel_flotante is None:
            return
        
        # Actualizar información del panel
        if hasattr(page, 'lbl_total_flotante'):
            page.lbl_total_flotante.value = f"Total: ${total:.2f}"
            page.lbl_productos_flotante.value = f"{len(current_order)} productos"
            
            # Mostrar u ocultar el panel según si hay productos
            if len(current_order) > 0:
                page.panel_flotante.visible = True
            else:
                page.panel_flotante.visible = False
                
            page.panel_flotante.update()
    def finalizar_pedido_desde_dialogo(dlg):
        """Cierra el diálogo y llama a finalizar pedido"""
        close_dlg(dlg)
        finalizar_pedido()

    def mostrar_pedido_completo():
        """Muestra un diálogo con el pedido actual completo"""
        if not current_order:
            page.snack_bar = ft.SnackBar(content=ft.Text("No hay productos en el pedido"))
            page.snack_bar.open = True
            page.update()
            return
        
        # Crear una tabla con el pedido actual
        tabla_completa = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Producto", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Cant.", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Precio", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Subtotal", weight=ft.FontWeight.BOLD))
            ],
            rows=[]
        )
        
        # Agregar filas con los productos
        for i, item in enumerate(current_order):
            tabla_completa.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(item["producto_nombre"])),
                        ft.DataCell(ft.Text(str(item["cantidad"]))),
                        ft.DataCell(ft.Text(f"${item['precio_unitario']:.2f}")),
                        ft.DataCell(ft.Text(f"${item['subtotal']:.2f}"))
                    ],
                    color=ft.Colors.with_opacity(0.03, ft.Colors.BLUE_100) if i % 2 == 0 else None
                )
            )
        
        # Calcular total
        total = sum(item["subtotal"] for item in current_order)
        
        # Agregar fila de total
        tabla_completa.rows.append(
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("TOTAL", weight=ft.FontWeight.BOLD)),
                    ft.DataCell(ft.Text(f"${total:.2f}", weight=ft.FontWeight.BOLD))
                ],
                color=ft.Colors.with_opacity(0.15, ft.Colors.BLUE_100)
            )
        )
        
        # Mostrar diálogo con el pedido completo
        dlg = ft.AlertDialog(
            title=ft.Text("Detalle del Pedido Actual"),
            content=ft.Column(
                [
                    ft.Container(
                        content=tabla_completa,
                        height=300,
                        padding=10,
                        border=ft.border.all(1, ft.Colors.GREY_300),
                        border_radius=5
                    ),
                    ft.Row(
                        [
                            ft.Text(f"Total: ${total:.2f}", 
                                size=18, 
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREEN_700)
                        ],
                        alignment=ft.MainAxisAlignment.END
                    )
                ],
                scroll=ft.ScrollMode.AUTO,
                height=350,
                width=page.width - 40
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda _: close_dlg(dlg)),
                ft.ElevatedButton(
                    "Finalizar Pedido", 
                    icon=ft.Icons.CHECK_CIRCLE,
                    on_click=lambda _: finalizar_pedido_desde_dialogo(dlg),
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        bgcolor=ft.Colors.GREEN
                    )
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        page.dialog = dlg
        dlg.open = True
        page.update()

    def crear_panel_flotante():
        """Crea un panel flotante que muestra resumen del pedido actual"""
        # Detectar si estamos en móvil (solo crear en móvil)
        is_mobile = page.width < 800
        if not is_mobile:
            return None
        
        # Etiquetas para la información
        page.lbl_productos_flotante = ft.Text(
            "0 productos", 
            size=12, 
            color=ft.Colors.WHITE
        )
        
        page.lbl_total_flotante = ft.Text(
            "Total: $0.00", 
            size=14, 
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE
        )
        
        # Crear el panel flotante
        panel = ft.Container(
            content=ft.Row(
                [
                    ft.IconButton(
                        icon=ft.Icons.SHOPPING_CART,
                        icon_color=ft.Colors.WHITE,
                        icon_size=20,
                        tooltip="Ver pedido actual",
                        on_click=lambda _: mostrar_pedido_completo()
                    ),
                    ft.Column(
                        [
                            page.lbl_productos_flotante,
                            page.lbl_total_flotante
                        ],
                        spacing=0,
                        tight=True
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CHECK_CIRCLE,
                        icon_color=ft.Colors.WHITE,
                        icon_size=20,
                        tooltip="Finalizar Pedido",
                        on_click=lambda _: finalizar_pedido()
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            width=page.width,
            padding=ft.padding.only(left=10, right=10, top=5, bottom=5),
            bgcolor=ft.Colors.PURPLE,
            border_radius=ft.border_radius.only(bottom_left=10, bottom_right=10),
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=5,
                color=ft.Colors.BLACK54,
                offset=ft.Offset(0, 2)
            ),
            animate=ft.animation.Animation(500, ft.AnimationCurve.DECELERATE),
            visible=False,  # Inicialmente oculto hasta que haya productos
        )
        
        return panel



    
    # MODIFICACIÓN: Actualizar tabla de pedidos con edición directa de cantidad
    def actualizar_tabla_pedido():
        """Actualiza la tabla de pedidos con mejor visualización para móviles"""
        pedido_actual_table.rows.clear()
        
        # Detectar si estamos en móvil
        is_mobile = page.width < 800
        
        for i, item in enumerate(current_order):
            # Cantidad para editar
            cantidad_campo = ft.TextField(
                value=str(item["cantidad"]),
                width=50 if is_mobile else 60,
                height=30 if is_mobile else None,
                text_align=ft.TextAlign.CENTER,
                border_color=ft.Colors.BLUE_200,
                keyboard_type=ft.KeyboardType.NUMBER,
                on_submit=lambda e, idx=i: actualizar_cantidad_directa(e.control.value, idx),
                text_size=13 if is_mobile else None
            )
            
            if is_mobile:
                # Versión móvil con 4 columnas compactas
                pedido_actual_table.rows.append(
                    ft.DataRow(
                        cells=[
                            # Nombre producto (más estrecho)
                            ft.DataCell(
                                ft.Text(
                                    item["producto_nombre"][:15] + ('...' if len(item["producto_nombre"]) > 15 else ''),
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    max_lines=1,
                                    size=12
                                )
                            ),
                            # Cantidad
                            ft.DataCell(cantidad_campo),
                            # Precio unitario
                            ft.DataCell(
                                ft.Text(
                                    f"${item['precio_unitario']:.2f}",
                                    size=12
                                )
                            ),
                            # Subtotal con botón eliminar
                            ft.DataCell(
                                ft.Row([
                                    ft.Text(
                                        f"${item['subtotal']:.2f}", 
                                        size=12,
                                        weight=ft.FontWeight.BOLD
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE,
                                        tooltip="Eliminar",
                                        on_click=lambda _, idx=i: eliminar_item_pedido(idx),
                                        icon_color=ft.Colors.RED,
                                        icon_size=16
                                    )
                                ], spacing=2, alignment=ft.MainAxisAlignment.END)
                            )
                        ],
                        # Alternar colores para mejor visibilidad
                        color=ft.Colors.with_opacity(0.03, ft.Colors.BLUE_100) if i % 2 == 0 else None
                    )
                )
            else:
                # Versión original para escritorio
                pedido_actual_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(item["producto_nombre"], overflow=ft.TextOverflow.ELLIPSIS)),
                            ft.DataCell(cantidad_campo),
                            ft.DataCell(ft.Text(f"${item['precio_unitario']:.2f}")),
                            ft.DataCell(ft.Text(f"${item['subtotal']:.2f}")),
                            ft.DataCell(
                                ft.IconButton(
                                    icon=ft.Icons.DELETE,
                                    tooltip="Eliminar",
                                    on_click=lambda _, idx=i: eliminar_item_pedido(idx),
                                    icon_color=ft.Colors.RED
                                )
                            )
                        ]
                    )
                )
        
        # Agregar fila de total con fondo destacado para mejor visibilidad
        total = sum(item["subtotal"] for item in current_order)
        if current_order:
            if is_mobile:
                # Versión móvil del total (más visible)
                pedido_actual_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text("TOTAL", weight=ft.FontWeight.BOLD, size=13)),
                            ft.DataCell(ft.Text(f"{len(current_order)} items", size=12)),
                            ft.DataCell(ft.Text("")),
                            ft.DataCell(
                                ft.Text(
                                    f"${total:.2f}", 
                                    weight=ft.FontWeight.BOLD, 
                                    size=15,
                                    color=ft.Colors.GREEN_700
                                )
                            )
                        ],
                        # Fondo destacado para el total
                        color=ft.Colors.with_opacity(0.15, ft.Colors.BLUE_100)
                    )
                )
            else:
                # Versión escritorio de la fila de total
                pedido_actual_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text("")),
                            ft.DataCell(ft.Text("")),
                            ft.DataCell(ft.Text("TOTAL", weight=ft.FontWeight.BOLD)),
                            ft.DataCell(ft.Text(f"${total:.2f}", weight=ft.FontWeight.BOLD)),
                            ft.DataCell(ft.Text(""))
                        ],
                        color=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_GREY)
                    )
                )
        
        pedido_actual_table.update()
        
        # Actualizar contador de productos en el panel flotante si existe
        if hasattr(page, 'panel_flotante') and page.panel_flotante is not None:
            actualizar_panel_flotante(total)

    
    def editar_item_pedido(index):
        item = current_order[index]
        
        # Diálogo para editar cantidad
        dlg = ft.AlertDialog(
            title=ft.Text(f"Editar: {item['producto_nombre']}"),
            content=ft.Column([
                ft.TextField(
                    label="Cantidad",
                    value=str(item["cantidad"]),
                    keyboard_type=ft.KeyboardType.NUMBER,
                    width=300,
                    autofocus=True,
                    on_submit=lambda e, idx=index: guardar_edicion(e.control.value, idx, dlg)
                ),
                ft.TextField(
                    label="Precio Unitario",
                    value=str(item["precio_unitario"]),
                    keyboard_type=ft.KeyboardType.NUMBER,
                    width=300,
                    on_submit=lambda e, idx=index: guardar_edicion_precio(e.control.value, idx, dlg)
                )
            ], tight=True, spacing=20, width=300),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dlg(dlg)),
                ft.TextButton("Guardar", on_click=lambda _, idx=index, d=dlg: 
                            guardar_edicion(d.content.controls[0].value, idx, d))
            ],
            modal=True
        )
        
        page.dialog = dlg
        dlg.open = True
        page.update()

    def guardar_edicion(nueva_cantidad, index, dlg):
        try:
            cantidad = int(nueva_cantidad)
            if cantidad <= 0:
                raise ValueError("Cantidad debe ser mayor a 0")
            
            # Verificar stock disponible
            conn = app.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT stock FROM productos WHERE id = %s", (current_order[index]["producto_id"],))
            producto = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if cantidad > producto["stock"]:
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Stock insuficiente. Disponible: {producto['stock']}"))
                page.snack_bar.open = True
                page.update()
                return
            
            current_order[index]["cantidad"] = cantidad
            current_order[index]["subtotal"] = cantidad * current_order[index]["precio_unitario"]
            actualizar_tabla_pedido()
            close_dlg(dlg)
        except ValueError:
            page.snack_bar = ft.SnackBar(content=ft.Text("Ingresa una cantidad válida"))
            page.snack_bar.open = True
            page.update()
    
    def guardar_edicion_precio(nuevo_precio, index, dlg):
        try:
            precio = float(nuevo_precio)
            if precio <= 0:
                raise ValueError("Precio debe ser mayor a 0")
            
            current_order[index]["precio_unitario"] = precio
            current_order[index]["subtotal"] = current_order[index]["cantidad"] * precio
            actualizar_tabla_pedido()
            close_dlg(dlg)
        except ValueError:
            page.snack_bar = ft.SnackBar(content=ft.Text("Ingresa un precio válido"))
            page.snack_bar.open = True
            page.update()
    
    def eliminar_item_pedido(index):
        # Eliminar el item del pedido
        current_order.pop(index)
        
        # Actualizar tabla de pedidos
        actualizar_tabla_pedido()
        
        # Actualizar panel flotante
        total = sum(item["subtotal"] for item in current_order) if current_order else 0
        actualizar_panel_flotante(total)

    def close_dlg(dlg):
        dlg.open = False
        page.update()
    
    # Nueva función para reiniciar los campos
    def reset_campos_pedido():
        """Reinicia todos los campos del pedido y variables relacionadas"""
        global cliente_actual, zona_actual
        
        # Limpiar variables globales
        cliente_actual = ""
        zona_actual = ""
        
        # Limpiar pedido actual
        current_order.clear()
        actualizar_tabla_pedido()
        
        # Limpiar campos del formulario
        cliente_field.value = ""
        zona_dropdown.value = None
        producto_search.value = ""
        cantidad_field.value = "1"
        precio_field.value = ""
        
        # NO resetear la fecha para facilitar múltiples ventas en la misma fecha
        # fecha_field y hora_field se mantienen con sus valores actuales
        
        # Actualizar los controles
        cliente_field.update()
        zona_dropdown.update()
        producto_search.update()
        cantidad_field.update()
        precio_field.update()
        
        # Actualizar el panel flotante si existe
        if hasattr(page, 'panel_flotante') and page.panel_flotante is not None:
            actualizar_panel_flotante(0)
        
    # MODIFICACIÓN: Agregar opción para ver pedidos después de finalizar
    def finalizar_pedido():
        if not current_order:
            page.snack_bar = ft.SnackBar(content=ft.Text("Agrega productos al pedido primero"))
            page.snack_bar.open = True
            page.update()
            return
        
        if not cliente_actual:
            page.snack_bar = ft.SnackBar(content=ft.Text("Ingresa el nombre del cliente"))
            page.snack_bar.open = True
            page.update()
            return
        
        if not zona_actual:
            page.snack_bar = ft.SnackBar(content=ft.Text("Selecciona una zona"))
            page.snack_bar.open = True
            page.update()
            return
        
        
        
        
        # Convertir fecha_actual a objeto datetime
        try:
            fecha_obj = datetime.datetime.strptime(fecha_actual, "%Y-%m-%d %H:%M:%S")
            # Guardar pedido en la base de datos con la fecha personalizada
            pedido_id = app.guardar_pedido(cliente_actual, zona_actual, current_order, fecha_obj)
        except ValueError:
            # Si hay un error con la fecha, usar la fecha actual del sistema | Usar la fecha personalizada
            pedido_id = app.guardar_pedido(cliente_actual, zona_actual, current_order, fecha_pedido)
        if pedido_id:
            # Generar PDF de factura
            pdf_content, mensaje = app.generar_pdf_factura(pedido_id)
            
            if pdf_content:
                # Crear directorio para PDFs si no existe
                os.makedirs("temp", exist_ok=True)
                
                # Guardar PDF temporalmente
                temp_file = os.path.join("temp", f"factura_{pedido_id}.pdf")
                with open(temp_file, "wb") as f:
                    f.write(pdf_content)
                
                # Mostrar mensaje de éxito
                dlg_success = ft.AlertDialog(
                    title=ft.Text("Pedido Completado"),
                    content=ft.Column([
                        ft.Text(f"Pedido #{pedido_id} guardado correctamente"),
                        ft.Row([
                            ft.TextButton(
                                "Descargar Factura",
                                on_click=lambda _: download_file(temp_file, f"factura_{pedido_id}.pdf")
                            )
                        ], alignment=ft.MainAxisAlignment.CENTER)
                    ], tight=True, spacing=20),
                    actions=[
                        # Botón para ver pedidos
                        ft.TextButton("Ver todos los pedidos", on_click=lambda _: close_dlg_and_ver_pedidos(dlg_success)),
                        # Botón para cerrar
                        ft.TextButton("Aceptar", on_click=lambda _: close_dlg_and_reset(dlg_success))
                    ],
                    modal=True
                )
                
                # Limpiar los campos y el pedido INMEDIATAMENTE después de guardar
                # (independientemente de la acción del usuario en el diálogo)
                reset_campos_pedido()
                
                # Mostrar el diálogo de éxito
                page.dialog = dlg_success
                dlg_success.open = True
                page.update()
            else:
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Error al generar factura: {mensaje}"))
                page.snack_bar.open = True
                page.update()
        else:
            page.snack_bar = ft.SnackBar(content=ft.Text("Error al guardar el pedido"))
            page.snack_bar.open = True
            page.update()
    
    # Nueva función para cerrar diálogo y ver pedidos
    def close_dlg_and_ver_pedidos(dlg):
        # Cerrar diálogo
        dlg.open = False
        page.update()
        
        # Ya no necesitamos resetear aquí porque lo hacemos inmediatamente después de guardar
        # Pero lo mantenemos por consistencia
        reset_campos_pedido()
        
        # Mostrar todos los pedidos
        toggle_ver_pedidos()
    
    def close_dlg_and_reset(dlg):
        # Cerrar diálogo
        dlg.open = False
        
        # Ya no necesitamos resetear aquí porque lo hacemos inmediatamente después de guardar
        # Pero por si acaso, lo llamamos de nuevo
        reset_campos_pedido()
        
        # Actualizar pantalla
        page.update()
    
    # 1. Mejorar la función download_file para que funcione en dispositivos móviles
    def download_file(path, filename):
        """Función mejorada para descargar archivos que funciona en móviles y web"""
        try:
            # Mostrar diálogo de progreso
            progress_dlg = ft.AlertDialog(
                title=ft.Text("Preparando archivo"),
                content=ft.Column([
                    ft.Text("Preparando descarga..."),
                    ft.ProgressBar(width=300)
                ], tight=True, spacing=20),
                modal=True
            )
            
            page.dialog = progress_dlg
            progress_dlg.open = True
            page.update()
            
            # Leer el archivo como bytes
            with open(path, "rb") as f:
                content = f.read()
            
            # Cerrar diálogo de progreso
            progress_dlg.open = False
            page.update()
            
            # Crear un control FilePicker para descargar
            save_file_dialog = ft.FilePicker()
            
            # Añadir el picker a los overlays si no está ya
            if save_file_dialog not in page.overlay:
                page.overlay.append(save_file_dialog)
                page.update()
            
            # Iniciar la descarga
            save_file_dialog.save_file(
                dialog_title="Guardar archivo",
                file_name=filename,
                allowed_extensions=["pdf"],
                data=content
            )
            
            # Mostrar información sobre la descarga
            info_dlg = ft.AlertDialog(
                title=ft.Text("Descarga iniciada"),
                content=ft.Column([
                    ft.Text("El archivo se está descargando."),
                    ft.Text("En dispositivos móviles, el archivo se guardará en:", weight=ft.FontWeight.BOLD),
                    ft.Text("• Android: Carpeta 'Descargas' o 'Download'"),
                    ft.Text("• iOS: En la app 'Archivos' o 'Files'")
                ]),
                actions=[
                    ft.TextButton("Entendido", on_click=lambda _: close_dlg(info_dlg))
                ],
                modal=True
            )
            
            page.dialog = info_dlg
            info_dlg.open = True
            page.update()
            
        except Exception as e:
            print(f"Error al descargar: {e}")
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Error al descargar: {str(e)}"))
            page.snack_bar.open = True
            page.update()
            
    def configurar_tabla_pedido_responsivo():
        """Configura la estructura de la tabla de pedidos para dispositivos móviles"""
        # Verificar si estamos en móvil
        is_mobile = page.width < 800
        
        # Limpiar las columnas existentes
        pedido_actual_table.columns.clear()
        
        if is_mobile:
            # Configuración de columnas para móvil (4 columnas compactas)
            pedido_actual_table.columns = [
                # Producto (más estrecho)
                ft.DataColumn(ft.Text("Producto", 
                                    weight=ft.FontWeight.BOLD, 
                                    size=12),
                            numeric=False),
                # Cantidad
                ft.DataColumn(ft.Text("Cant", 
                                    weight=ft.FontWeight.BOLD, 
                                    size=12),
                            numeric=True),
                # Precio unitario
                ft.DataColumn(ft.Text("Precio", 
                                    weight=ft.FontWeight.BOLD, 
                                    size=12),
                            numeric=True),
                # Subtotal
                ft.DataColumn(ft.Text("Total", 
                                    weight=ft.FontWeight.BOLD, 
                                    size=12),
                            numeric=True)
            ]
        else:
            # Configuración original para escritorio (5 columnas)
            pedido_actual_table.columns = [
                ft.DataColumn(ft.Text("Producto", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Cant.", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Precio", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Subtotal", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("", weight=ft.FontWeight.BOLD))
            ]
        
        # Ajustar el ancho de la tabla según el dispositivo
        pedido_actual_table.width = page.width - 20
        
        # Configurar el estilo de la tabla para mejor visualización
        pedido_actual_table.bgcolor = ft.Colors.with_opacity(0.03, ft.Colors.BLACK)
        pedido_actual_table.border = ft.border.all(0.5, ft.Colors.GREY_400)
        pedido_actual_table.border_radius = 5
        pedido_actual_table.horizontal_lines = ft.border.BorderSide(0.5, ft.Colors.GREY_300)


    # 2. Función para abrir archivos PDF
    def open_pdf_file(path, dlg=None):
        """Abre un archivo PDF directamente"""
        try:
            # Cerrar diálogo si existe
            if dlg:
                close_dlg(dlg)
            
            # Leer archivo
            with open(path, "rb") as f:
                content = f.read()
            
            # Crear un documento temporal en la página
            pdf_viewer = ft.Container(
                content=ft.Text("Visualizando PDF..."),
                width=page.width,
                height=page.height * 0.8,
                bgcolor=ft.Colors.WHITE,
                border=ft.border.all(1, ft.Colors.BLACK),
                border_radius=10,
                padding=20
            )
            
            # Mostrar el PDF
            dlg = ft.AlertDialog(
                title=ft.Text("Factura"),
                content=ft.Column([
                    ft.Text("El PDF se está visualizando. Si no se abre automáticamente, utilice su visor de PDF predeterminado."),
                    pdf_viewer
                ]),
                actions=[
                    ft.TextButton("Cerrar", on_click=lambda _: close_dlg(dlg))
                ],
                on_dismiss=lambda _: True
            )
            page.dialog = dlg
            dlg.open = True
            page.update()
            
        except Exception as e:
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Error al abrir PDF: {e}"))
            page.snack_bar.open = True
            page.update()

    # 3. Mejorar la función para descargar facturas
    def descargar_factura_pedido(pedido_id):
        """Función mejorada para descargar facturas"""
        # Mostrar diálogo de progreso
        progress_dlg = ft.AlertDialog(
            title=ft.Text("Generando factura"),
            content=ft.Column([
                ft.Text("Preparando su factura..."),
                ft.ProgressBar(width=300)
            ], tight=True, spacing=20),
            modal=True
        )
        
        page.dialog = progress_dlg
        progress_dlg.open = True
        page.update()
        
        try:
            # Generar factura
            pdf_content, mensaje = app.generar_pdf_factura(pedido_id)
            
            # Cerrar diálogo de progreso
            progress_dlg.open = False
            page.update()
            
            if pdf_content:
                # Crear directorio para PDFs si no existe
                os.makedirs("temp", exist_ok=True)
                
                # Guardar PDF temporalmente
                temp_file = os.path.join("temp", f"factura_{pedido_id}.pdf")
                with open(temp_file, "wb") as f:
                    f.write(pdf_content)
                
                # Preguntar al usuario cómo quiere recibir la factura - simplificado para móviles
                options_dlg = ft.AlertDialog(
                    title=ft.Text("Factura lista"),
                    content=ft.Text("La factura está lista para descargar"),
                    actions=[
                        ft.ElevatedButton(
                            "Descargar",
                            icon=ft.Icons.DOWNLOAD,
                            on_click=lambda _: handle_download_choice(temp_file, f"factura_{pedido_id}.pdf", options_dlg)
                        ),
                        ft.TextButton("Cancelar", on_click=lambda _: close_dlg(options_dlg))
                    ],
                    modal=True
                )
                
                page.dialog = options_dlg
                options_dlg.open = True
                page.update()
            else:
                # Mostrar mensaje de error
                page.snack_bar = ft.SnackBar(content=ft.Text(mensaje))
                page.snack_bar.open = True
                page.update()
        except Exception as e:
            # Cerrar diálogo de progreso
            progress_dlg.open = False
            page.update()
            
            # Mostrar error
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Error: {e}"))
            page.snack_bar.open = True
            page.update()
    # 4. Funciones auxiliares para manejar opciones de factura
    def handle_download_choice(file_path, file_name, dlg):
        """Descarga un archivo"""
        close_dlg(dlg)
        download_file(file_path, file_name)

    def handle_view_choice(file_path, dlg):
        """Maneja la visualización de la factura"""
        close_dlg(dlg)
        open_pdf_file(file_path)
    
    # ---------- FUNCIONES DE ESTADÍSTICAS ----------
    
    def toggle_estadisticas():
        # Mostrar u ocultar panel de estadísticas
        if estadisticas_container.visible:
            estadisticas_container.visible = False
        else:
            # Cargar estadísticas
            cargar_estadisticas()
            estadisticas_container.visible = True
            
            # Ocultar otros paneles
            prediccion_container.visible = False
            pedidos_container.visible = False
        
        page.update()
    
    def cargar_estadisticas():
        # Obtener datos de ventas de los últimos 30 días
        ventas = app.get_ventas_ultimos_30_dias()
        
        # Obtener ventas de hoy
        ventas_hoy = app.get_ventas_diarias()
        total_hoy = sum(venta["subtotal"] for venta in ventas_hoy)
        
        # Obtener productos más vendidos
        productos_mas_vendidos = app.get_productos_mas_vendidos(5)
        
        # Obtener ganancias y facturación
        ganancia_diaria = app.get_ganancia_diaria()
        ganancia_anual = app.get_ganancia_anual()
        facturacion_diaria = app.get_facturacion_diaria()
        facturacion_anual = app.get_facturacion_anual()
        
        # Limpiar contenedor
        estadisticas_container.content = ft.Column([
            ft.Text("Estadísticas de Ventas", size=20, weight=ft.FontWeight.BOLD),
            
            # Resumen general - ganancia y facturación
            ft.Container(
                content=ft.Column([
                    ft.Text("Resumen de Resultados", size=16, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        # Hoy
                        ft.Container(
                            content=ft.Column([
                                ft.Text("HOY", size=14, weight=ft.FontWeight.BOLD),
                                ft.Text(f"Facturado: ${facturacion_diaria:.2f}", size=14),
                                ft.Text(f"Ganancia: ${ganancia_diaria:.2f}", 
                                    size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
                            ]),
                            padding=10,
                            border=ft.border.all(1, ft.Colors.GREEN_100),
                            border_radius=5,
                            expand=True
                        ),
                        # Separador
                        ft.VerticalDivider(width=10),
                        # Año
                        ft.Container(
                            content=ft.Column([
                                ft.Text("AÑO " + str(datetime.datetime.now().year), 
                                    size=14, weight=ft.FontWeight.BOLD),
                                ft.Text(f"Facturado: ${facturacion_anual:.2f}", size=14),
                                ft.Text(f"Ganancia: ${ganancia_anual:.2f}", 
                                    size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
                            ]),
                            padding=10,
                            border=ft.border.all(1, ft.Colors.BLUE_100),
                            border_radius=5,
                            expand=True
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ]),
                padding=10,
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PURPLE),
                border_radius=5,
                margin=ft.margin.only(bottom=10)
            ),
            
            # Ventas del día
            ft.Container(
                content=ft.Column([
                    ft.Text("Detalle de Hoy", size=16, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Número de pedidos: {len(set(venta['id'] for venta in ventas_hoy)) if ventas_hoy else 0}", size=14),
                    ft.Text(f"Total facturado: ${total_hoy:.2f}", size=14)
                ]),
                padding=10,
                border=ft.border.all(1, ft.Colors.BLACK26),
                border_radius=5,
                margin=ft.margin.only(bottom=10)
            ),
            
            # Productos más vendidos
            ft.Container(
                content=ft.Column([
                    ft.Text("Productos Más Vendidos", size=16, weight=ft.FontWeight.BOLD),
                    *[ft.Container(
                        content=ft.Row([
                            ft.Text(f"{i+1}.", size=14, weight=ft.FontWeight.BOLD),
                            ft.Text(producto['nombre'], size=14, expand=True),
                            ft.Container(
                                content=ft.Text(f"{producto['total_vendido']} unidades", 
                                            size=14, weight=ft.FontWeight.BOLD),
                                padding=ft.padding.only(left=5, right=5),
                                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE),
                                border_radius=5
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        padding=5,
                        border_radius=5,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PURPLE) if i % 2 == 0 else None
                    ) for i, producto in enumerate(productos_mas_vendidos)]
                ]),
                padding=10,
                border=ft.border.all(1, ft.Colors.BLACK26),
                border_radius=5,
                margin=ft.margin.only(bottom=10)
            ),
            
            # Gráfico de ventas (si hay datos)
            ft.Container(
                content=ft.Column([
                    ft.Text("Ventas de los últimos 30 días", size=16, weight=ft.FontWeight.BOLD),
                    generate_chart_container(ventas) if ventas else ft.Text("No hay datos de ventas")
                ]),
                padding=10,
                border=ft.border.all(1, ft.Colors.BLACK26),
                border_radius=5
            )
        ], scroll=ft.ScrollMode.AUTO, spacing=10)
        
        estadisticas_container.update()
    
    def generate_chart_container(ventas):
        """Genera un gráfico de ventas y devuelve un contenedor con la imagen"""
        try:
            # Crear directorio para gráficos si no existe
            os.makedirs("temp", exist_ok=True)
            
            # Configurar matplotlib para usar 'Agg' como backend
            # Crear figura y ejes
            fig, ax = plt.subplots(figsize=(10, 5))
            
            # Extraer fechas y totales
            fechas = [venta["dia"] for venta in ventas]
            totales = [float(venta["total_ventas"]) for venta in ventas]
            
            # Crear gráfico
            ax.plot(fechas, totales, marker='o')
            ax.set_title('Ventas de los últimos 30 días')
            ax.set_xlabel('Fecha')
            ax.set_ylabel('Total ($)')
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # Guardar gráfico como imagen
            chart_path = os.path.join("temp", "ventas_chart.png")
            plt.savefig(chart_path)
            plt.close(fig)
            
            # Mostrar gráfico en la interfaz
            return ft.Image(src=chart_path, width=600)
        except Exception as e:
            print(f"Error al generar gráfico: {e}")
            return ft.Text(f"No se pudo generar el gráfico: {e}")
    
    
    # ---------- FUNCIONES DE PREDICCIÓN ----------
    
    def toggle_prediccion():
        # Mostrar u ocultar panel de predicción
        if prediccion_container.visible:
            prediccion_container.visible = False
        else:
            # Cargar predicción
            cargar_prediccion()
            prediccion_container.visible = True
            
            # Ocultar otros paneles
            estadisticas_container.visible = False
            pedidos_container.visible = False
        
        page.update()
    
    def cargar_prediccion():
        """Carga y muestra la predicción de ventas"""
        # Mostrar mensaje de carga
        prediccion_container.content = ft.Column([
            ft.Text("Generando predicción de ventas...", size=20, weight=ft.FontWeight.BOLD),
            ft.ProgressBar(width=300)
        ])
        prediccion_container.update()
        
        try:
            # Generar predicción
            prediccion, mensaje = app.generar_prediccion_ventas()
            
            if prediccion:
                # Crear directorio para gráficos si no existe
                os.makedirs("temp", exist_ok=True)
                
                # Configurar matplotlib para usar 'Agg' como backend
                # Crear figura y ejes
                fig, ax = plt.subplots(figsize=(10, 5))
                
                # Extraer fechas y predicciones
                fechas = [fecha.strftime("%d/%m") for fecha in prediccion["fechas"]]
                valores = prediccion["predicciones"]
                
                # Crear gráfico
                ax.plot(fechas, valores, marker='o', color='green')
                ax.set_title('Predicción de Ventas para los próximos 30 días')
                ax.set_xlabel('Fecha')
                ax.set_ylabel('Ventas Estimadas ($)')
                plt.xticks(rotation=45)
                plt.tight_layout()
                
                # Guardar gráfico como imagen
                chart_path = os.path.join("temp", "prediccion_chart.png")
                plt.savefig(chart_path)
                plt.close(fig)
                
                # Mostrar gráfico y detalles en la interfaz
                prediccion_container.content = ft.Column([
                    ft.Text("Predicción de Ventas (BETA)", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Precisión del modelo: {prediccion['precision']*100:.2f}%", 
                           color=ft.Colors.GREEN if prediccion['precision'] > 0.7 else ft.Colors.ORANGE),
                    ft.Image(src=chart_path, width=600),
                    ft.Text("Nota: Esta predicción se basa en datos históricos y puede variar. Considere factores externos.", 
                           size=12, italic=True, color=ft.Colors.GREY)
                ])
            else:
                # Mostrar mensaje de error
                prediccion_container.content = ft.Column([
                    ft.Text("Predicción de Ventas (BETA)", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(mensaje, color=ft.Colors.RED),
                    ft.Text("Recomendación: Necesitas más datos históricos para generar una predicción precisa.", 
                           size=12, italic=True)
                ])
            
            prediccion_container.update()
        except Exception as e:
            prediccion_container.content = ft.Column([
                ft.Text("Error al generar predicción", size=20, weight=ft.FontWeight.BOLD),
                ft.Text(str(e), color=ft.Colors.RED),
            ])
            prediccion_container.update()
            print(f"Error en predicción: {e}")
    
        else:
            # Mostrar mensaje de error
            prediccion_container.content = ft.Column([
                ft.Text("Predicción de Ventas (BETA)", size=20, weight=ft.FontWeight.BOLD),
                ft.Text(mensaje, color=ft.Colors.RED),
                ft.Text("Recomendación: Necesitas más datos históricos para generar una predicción precisa.", 
                       size=12, italic=True)
            ])
        
        prediccion_container.update()
    
    # ---------- FUNCIONES DE PEDIDOS HOY ----------
    
    def generar_pdf_pedidos_hoy():
        """Genera un PDF con todos los pedidos del día"""
        try:
            # Mostrar diálogo de progreso
            progress_dlg = ft.AlertDialog(
                title=ft.Text("Generando reporte"),
                content=ft.Column([
                    ft.Text("Preparando reporte de pedidos..."),
                    ft.ProgressBar(width=300)
                ], tight=True, spacing=20),
                modal=True
            )
            
            page.dialog = progress_dlg
            progress_dlg.open = True
            page.update()
            
            # Generar PDF
            pdf_content, mensaje = app.generar_pdf_pedidos_hoy()
            
            # Cerrar diálogo de progreso
            progress_dlg.open = False
            page.update()
            
            if pdf_content:
                # Crear directorio para PDFs si no existe
                os.makedirs("temp", exist_ok=True)
                
                # Guardar PDF temporalmente
                temp_file = os.path.join("temp", "pedidos_hoy.pdf")
                with open(temp_file, "wb") as f:
                    f.write(pdf_content)
                
                # Llamar a la función mejorada de descarga
                download_file(temp_file, "pedidos_hoy.pdf")
            else:
                # Mostrar mensaje de error
                page.snack_bar = ft.SnackBar(content=ft.Text(mensaje))
                page.snack_bar.open = True
                page.update()
        except Exception as e:
            # Cerrar diálogo de progreso si sigue abierto
            if 'progress_dlg' in locals() and progress_dlg.open:
                progress_dlg.open = False
                page.update()
                
            # Mostrar error
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Error: {e}"))
            page.snack_bar.open = True
            page.update()

    # ---------- FUNCIONES DE VER TODOS LOS PEDIDOS ----------
    
    def toggle_ver_pedidos():
        # Si el contenedor está visible, ocultarlo
        if pedidos_container.visible:
            pedidos_container.visible = False
            page.update()
            return
            
        # Si no está visible, mostrarlo y preparar su contenido
        pedidos_container.visible = True
        
        # Primero actualizamos el contenedor si está vacío o es solo texto
        if not hasattr(pedidos_container, 'content') or pedidos_container.content is None or isinstance(pedidos_container.content, ft.Text):
            # Crear el campo de filtro de fecha
            fecha_filtro = ft.TextField(
                label="Filtrar por fecha (YYYY-MM-DD)",
                width=page.width - 40 if page.width < 600 else 300
            )
            
            # Crear botón de filtro
            filtrar_btn = ft.ElevatedButton(
                "Aplicar Filtro",
                on_click=lambda _: cargar_pedidos(fecha_filtro.value)
            )
            
            # Crear una lista vacía para los pedidos
            lista_pedidos = ft.ListView(
                spacing=5,
                padding=10,
                auto_scroll=True,
                expand=True
            )
            
            # Crear un contenedor que contendrá la lista
            contenedor_lista = ft.Container(
                content=lista_pedidos,
                height=400,
                expand=True
            )
            
            # Configurar el contenido del contenedor principal
            pedidos_container.content = ft.Column([
                ft.Text("Todos los Pedidos", size=20, weight=ft.FontWeight.BOLD),
                ft.Row([
                    fecha_filtro,
                    filtrar_btn
                ]),
                contenedor_lista  # Añadir el contenedor con la lista
            ])
            
            # Actualizar la página para asegurar que el contenedor y sus controles estén agregados
            page.update()
        
        # Una vez que la página está actualizada, buscar la lista_pedidos en la estructura
        fecha_valor = None
        lista_pedidos = None
        
        # Buscar el campo de fecha y la lista en la estructura
        for control in pedidos_container.content.controls:
            if isinstance(control, ft.Row):
                for item in control.controls:
                    if isinstance(item, ft.TextField):
                        fecha_valor = item.value
            elif isinstance(control, ft.Container) and hasattr(control, 'content'):
                if isinstance(control.content, ft.ListView):
                    lista_pedidos = control.content
        
        # Asegurarse de que lista_pedidos exista antes de cargar los pedidos
        if lista_pedidos:
            # Ahora cargar los pedidos
            cargar_pedidos(fecha_valor)
        else:
            # Si no se encuentra, mostrar un mensaje de error
            pedidos_container.content = ft.Column([
                ft.Text("Error al cargar la vista de pedidos", size=20, color=ft.Colors.RED),
                ft.ElevatedButton("Intentar de nuevo", on_click=lambda _: toggle_ver_pedidos())
            ])
        
        # Ocultar otros paneles
        estadisticas_container.visible = False
        prediccion_container.visible = False
        
        # Actualizar la página
        page.update()
    
    def cargar_pedidos(fecha_str=None):
        # Buscar la lista de pedidos en la estructura
        lista_pedidos = None
        for control in pedidos_container.content.controls:
            if isinstance(control, ft.Container) and hasattr(control, 'content'):
                if isinstance(control.content, ft.ListView):
                    lista_pedidos = control.content
                    break
        
        if not lista_pedidos:
            print("No se encontró lista_pedidos")
            return
                
        # Limpiar la lista
        lista_pedidos.controls.clear()
        
        # Obtener todos los pedidos
        conn = app.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Consulta base sin filtro de fecha - ordenando por fecha descendente (más recientes primero)
        query_base = """
        SELECT id, cliente, zona, fecha, total 
        FROM pedidos 
        """
        
        # Verificar si hay filtro de fecha
        if fecha_str:
            query_base += " WHERE DATE(fecha) = %s"
            cursor.execute(query_base + " ORDER BY fecha DESC", (fecha_str,))  # DESC para invertir orden
        else:
            cursor.execute(query_base + " ORDER BY fecha DESC")  # DESC para invertir orden
        
        pedidos = cursor.fetchall()
        cursor.close()
        conn.close()
        
        print(f"Se encontraron {len(pedidos)} pedidos")
        
        if not pedidos:
            lista_pedidos.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.INFO_OUTLINE, color=ft.Colors.BLUE_200),
                            ft.Text("No hay pedidos para mostrar", size=16)
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Text("Prueba con otra fecha o crea un nuevo pedido", 
                            size=14, color=ft.Colors.GREY_400)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                    border=ft.border.all(1, ft.Colors.BLUE_200),
                    border_radius=10,
                    margin=10
                )
            )
        else:
            # Agrupar pedidos por fecha
            pedidos_por_fecha = {}
            for pedido in pedidos:  # Pedidos ya vienen ordenados por fecha DESC
                fecha_str = pedido['fecha'].strftime('%d/%m/%Y')
                if fecha_str not in pedidos_por_fecha:
                    pedidos_por_fecha[fecha_str] = []
                pedidos_por_fecha[fecha_str].append(pedido)
            
            # Mostrar pedidos agrupados por fecha
            for fecha in pedidos_por_fecha.keys():  # No necesitamos ordenar, ya vienen en orden descendente
                lista = pedidos_por_fecha[fecha]
                
                # Cabecera de fecha
                lista_pedidos.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.CALENDAR_TODAY, color=ft.Colors.PURPLE_200),
                            ft.Text(fecha, weight=ft.FontWeight.BOLD, size=16)
                        ]),
                        padding=10,
                        bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.PURPLE_200),
                        border_radius=5,
                        margin=ft.margin.only(top=10, bottom=5)
                    )
                )
                
                # Mostrar pedidos de esa fecha
                for pedido in lista:
                    # Capturar el ID en una variable local para asegurar su correcto uso en la lambda
                    pedido_id = pedido['id']
                    
                    lista_pedidos.controls.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Text(f"📋 Pedido #{pedido_id}", 
                                        weight=ft.FontWeight.BOLD, size=16),
                                    ft.Text(pedido['fecha'].strftime('%H:%M'), 
                                        color=ft.Colors.GREY_400)
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([
                                    ft.Container(
                                        content=ft.Column([
                                            ft.Text(f"👤 {pedido['cliente']}", size=14),
                                            ft.Text(f"📍 {pedido['zona']}", size=14),
                                            ft.Text(f"💰 ${float(pedido['total']):.2f}", 
                                                size=16, weight=ft.FontWeight.BOLD,
                                                color=ft.Colors.PINK_200)
                                        ]),
                                        expand=True
                                    ),
                                    # Contenedor de botones con ID capturado correctamente
                                    ft.Container(
                                        content=ft.Column([
                                            ft.ElevatedButton(
                                                "Ver Detalles",
                                                icon=ft.Icons.VISIBILITY,
                                                on_click=lambda e, pid=pedido_id: ver_detalles_pedido(pid),
                                                style=ft.ButtonStyle(
                                                    color=ft.Colors.WHITE,
                                                    bgcolor=ft.Colors.PURPLE_400
                                                )
                                            ),
                                            ft.OutlinedButton(
                                                "Descargar Factura",
                                                icon=ft.Icons.DOWNLOAD,
                                                on_click=lambda e, pid=pedido_id: descargar_factura_pedido(pid)
                                            )
                                        ]),
                                        alignment=ft.alignment.center_right
                                    )
                                ])
                            ]),
                            border=ft.border.all(1, ft.Colors.GREY_400),
                            border_radius=8,
                            padding=10,
                            margin=5
                        )
                    )
        
        # Actualizar lista
        lista_pedidos.update()
        page.update()
    
    def ver_detalles_pedido(pedido_id):
        """Muestra un diálogo con los detalles del pedido y permite modificarlo"""
        try:
            print(f"Mostrando detalles del pedido #{pedido_id}")
            
            # Verificar si estamos en móvil
            is_mobile = page.width < 800
            
            # Obtener detalles del pedido
            conn = app.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Obtener información general del pedido
            cursor.execute("""
            SELECT id, cliente, zona, fecha, total 
            FROM pedidos 
            WHERE id = %s
            """, (pedido_id,))
            
            pedido = cursor.fetchone()
            if not pedido:
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Pedido #{pedido_id} no encontrado"))
                page.snack_bar.open = True
                page.update()
                return
            
            # Obtener detalles de los productos
            cursor.execute("""
            SELECT dp.*, p.nombre as producto_nombre, p.stock as stock_actual
            FROM detalle_pedido dp
            JOIN productos p ON dp.producto_id = p.id
            WHERE dp.pedido_id = %s
            """, (pedido_id,))
            
            detalles = cursor.fetchall()
            cursor.close()
            conn.close()
            
            # Lista para almacenar controles de fila para cada producto
            filas_productos = []
            
            # Variable para almacenar los detalles modificados
            detalles_modificados = []
            for detalle in detalles:
                detalles_modificados.append({
                    "id": detalle["id"],
                    "pedido_id": detalle["pedido_id"],
                    "producto_id": detalle["producto_id"],
                    "producto_nombre": detalle["producto_nombre"],
                    "cantidad": detalle["cantidad"],
                    "precio_unitario": float(detalle["precio_unitario"]),
                    "subtotal": float(detalle["subtotal"]),
                    "stock_actual": detalle["stock_actual"],
                    "cantidad_original": detalle["cantidad"]
                })
            
            # Total del pedido
            total_text = ft.Text(
                f"Total: ${float(pedido['total']):.2f}",
                size=18,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.GREEN
            )
            
            # Función para actualizar interfaz de detalles (mejorada para móvil)
            def actualizar_interfaz():
                # Limpiar filas existentes
                for fila in filas_productos:
                    contenedor_detalles.controls.remove(fila)
                filas_productos.clear()
                
                # Recrear filas con diseño específico para móvil
                for i, detalle in enumerate(detalles_modificados):
                    if is_mobile:
                        # Diseño vertical y simplificado para móvil
                        fila = ft.Container(
                            content=ft.Column([
                                # Nombre del producto
                                ft.Text(
                                    detalle["producto_nombre"],
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    max_lines=1,
                                    weight=ft.FontWeight.BOLD,
                                    size=16  # Texto más grande
                                ),
                                # Detalles en filas separadas para mejor visibilidad
                                ft.Container(
                                    content=ft.Column([
                                        ft.Row([
                                            ft.Text("Cantidad:", size=14),
                                            ft.Text(str(detalle["cantidad"]), 
                                                weight=ft.FontWeight.BOLD, size=16)
                                        ]),
                                        ft.Row([
                                            ft.Text("Precio:", size=14),
                                            ft.Text(f"${detalle['precio_unitario']:.2f}", 
                                                weight=ft.FontWeight.BOLD, size=16)
                                        ]),
                                        ft.Row([
                                            ft.Text("Subtotal:", size=14),
                                            ft.Text(f"${detalle['subtotal']:.2f}", 
                                                weight=ft.FontWeight.BOLD, size=16,
                                                color=ft.Colors.BLUE)
                                        ])
                                    ]),
                                    padding=10,
                                    margin=5
                                ),
                                # Botones más grandes y espaciados para facilitar el toque
                                ft.Row([
                                    ft.ElevatedButton(
                                        "Editar",
                                        icon=ft.Icons.EDIT,
                                        icon_color=ft.Colors.BLUE,
                                        on_click=lambda e, idx=i: editar_detalle_existente(idx),
                                        style=ft.ButtonStyle(
                                            shape=ft.RoundedRectangleBorder(radius=10)
                                        )
                                    ),
                                    ft.OutlinedButton(
                                        "Eliminar",
                                        icon=ft.Icons.DELETE,
                                        icon_color=ft.Colors.RED,
                                        on_click=lambda e, idx=i: eliminar_detalle_existente(idx),
                                        style=ft.ButtonStyle(
                                            shape=ft.RoundedRectangleBorder(radius=10)
                                        )
                                    )
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=10)
                            ]),
                            border=ft.border.all(1, ft.Colors.GREY_400),
                            border_radius=10,
                            margin=ft.margin.only(bottom=10),
                            padding=15,  # Padding mayor para facilitar el toque
                            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE_GREY)
                        )
                    else:
                        # Diseño original para escritorio (sin cambios)
                        fila = ft.Container(
                            content=ft.Row([
                                ft.Container(
                                    ft.Text(
                                        detalle["producto_nombre"],
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                        max_lines=1
                                    ), 
                                    width=210, 
                                    padding=10
                                ),
                                ft.Container(
                                    ft.Text(str(detalle["cantidad"])), 
                                    width=60,
                                    padding=10,
                                    alignment=ft.alignment.center
                                ),
                                ft.Container(
                                    ft.Text(f"${detalle['precio_unitario']:.2f}"), 
                                    width=80,
                                    padding=10,
                                    alignment=ft.alignment.center
                                ),
                                ft.Container(
                                    ft.Text(f"${detalle['subtotal']:.2f}"), 
                                    width=80,
                                    padding=10,
                                    alignment=ft.alignment.center
                                ),
                                ft.Container(
                                    ft.Row([
                                        ft.IconButton(
                                            icon=ft.Icons.EDIT,
                                            tooltip="Editar",
                                            icon_color=ft.Colors.BLUE,
                                            on_click=lambda e, idx=i: editar_detalle_existente(idx)
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.DELETE,
                                            tooltip="Eliminar",
                                            icon_color=ft.Colors.RED,
                                            on_click=lambda e, idx=i: eliminar_detalle_existente(idx)
                                        )
                                    ]),
                                    width=100
                                )
                            ]),
                            border=ft.border.all(1, ft.Colors.GREY_400),
                            border_radius=5,
                            margin=ft.margin.only(bottom=5)
                        )
                    
                    filas_productos.append(fila)
                    contenedor_detalles.controls.append(fila)
                
                # Actualizar total
                total = sum(detalle["subtotal"] for detalle in detalles_modificados)
                total_text.value = f"Total: ${total:.2f}"
                
                # Actualizar la página
                page.update()
            
            # Diálogo para editar producto mejorado para móvil
            def editar_detalle_existente(index):
                """Edita un detalle existente - versión mejorada para móvil"""
                detalle = detalles_modificados[index]
                
                # Campos de texto con valores actuales
                campo_cantidad = ft.TextField(
                    label="Cantidad",
                    value=str(detalle["cantidad"]),
                    keyboard_type=ft.KeyboardType.NUMBER,
                    width=300 if not is_mobile else page.width - 80,
                    autofocus=True,
                    border=ft.InputBorder.OUTLINE,
                    height=60 if is_mobile else None,  # Más alto en móvil
                    text_size=18 if is_mobile else None  # Texto más grande en móvil
                )
                
                campo_precio = ft.TextField(
                    label="Precio Unitario",
                    value=str(detalle["precio_unitario"]),
                    keyboard_type=ft.KeyboardType.NUMBER,
                    width=300 if not is_mobile else page.width - 80,
                    border=ft.InputBorder.OUTLINE,
                    height=60 if is_mobile else None,  # Más alto en móvil
                    text_size=18 if is_mobile else None  # Texto más grande en móvil
                )
                
                # Diálogo adaptado para móvil
                dlg = ft.AlertDialog(
                    title=ft.Text(f"Editar: {detalle['producto_nombre']}", size=20),
                    content=ft.Column([
                        campo_cantidad,
                        ft.Container(height=15),  # Separación
                        campo_precio,
                        ft.Container(height=10),  # Separación
                        ft.Text(f"Stock disponible: {detalle['stock_actual'] + detalle['cantidad_original']}", 
                            color=ft.Colors.GREY)
                    ], 
                    tight=True, 
                    spacing=10, 
                    width=300 if not is_mobile else page.width - 40),
                    actions=[
                        ft.TextButton(
                            "Cancelar", 
                            on_click=lambda _: close_dlg(dlg),
                            style=ft.ButtonStyle(
                                color=ft.Colors.RED
                            )
                        ),
                        ft.ElevatedButton(
                            "Guardar", 
                            on_click=lambda _: guardar_edicion_existente(index, campo_cantidad.value, campo_precio.value, dlg),
                            style=ft.ButtonStyle(
                                color=ft.Colors.WHITE,
                                bgcolor=ft.Colors.GREEN
                            )
                        )
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                    modal=True
                )
                
                page.dialog = dlg
                dlg.open = True
                page.update()
            
            # Función mejorada para guardar ediciones
            def guardar_edicion_existente(index, nueva_cantidad_str, nuevo_precio_str, dlg):
                """Guarda la edición de un detalle - versión mejorada"""
                try:
                    # Obtener y validar valores ingresados
                    try:
                        nueva_cantidad = int(nueva_cantidad_str)
                        nuevo_precio = float(nuevo_precio_str)
                    except ValueError:
                        page.snack_bar = ft.SnackBar(content=ft.Text("Ingrese valores numéricos válidos"))
                        page.snack_bar.open = True
                        page.update()
                        return
                    
                    # Validaciones
                    if nueva_cantidad <= 0:
                        raise ValueError("La cantidad debe ser mayor a 0")
                    
                    if nuevo_precio <= 0:
                        raise ValueError("El precio debe ser mayor a 0")
                    
                    # Verificar stock disponible (stock actual + cantidad original)
                    stock_disponible = detalles_modificados[index]["stock_actual"] + detalles_modificados[index]["cantidad_original"]
                    if nueva_cantidad > stock_disponible:
                        raise ValueError(f"Stock insuficiente. Disponible: {stock_disponible}")
                    
                    # Actualizar detalle
                    detalles_modificados[index]["cantidad"] = nueva_cantidad
                    detalles_modificados[index]["precio_unitario"] = nuevo_precio
                    detalles_modificados[index]["subtotal"] = nueva_cantidad * nuevo_precio
                    
                    # Mostrar notificación de éxito
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("Producto actualizado correctamente"),
                        bgcolor=ft.Colors.GREEN
                    )
                    page.snack_bar.open = True
                    
                    # Actualizar interfaz
                    actualizar_interfaz()
                    close_dlg(dlg)
                    
                except ValueError as e:
                    page.snack_bar = ft.SnackBar(content=ft.Text(str(e)))
                    page.snack_bar.open = True
                    page.update()
            
            # Mantener el resto de las funciones

            def eliminar_detalle_existente(index):
                """Elimina un detalle del pedido - versión mejorada para móvil"""
                # Confirmar eliminación con un diálogo más claro
                dlg = ft.AlertDialog(
                    title=ft.Text("Confirmar eliminación", size=18, color=ft.Colors.RED),
                    content=ft.Column([
                        ft.Text(f"¿Está seguro de eliminar este producto del pedido?"),
                        ft.Text(detalles_modificados[index]['producto_nombre'], 
                            weight=ft.FontWeight.BOLD, size=16)
                    ]),
                    actions=[
                        ft.TextButton(
                            "Cancelar", 
                            on_click=lambda _: close_dlg(dlg)
                        ),
                        ft.ElevatedButton(
                            "Eliminar", 
                            icon=ft.Icons.DELETE,
                            on_click=lambda _: confirmar_eliminacion(index, dlg),
                            style=ft.ButtonStyle(
                                color=ft.Colors.WHITE,
                                bgcolor=ft.Colors.RED
                            )
                        )
                    ],
                    modal=True
                )
                
                page.dialog = dlg
                dlg.open = True
                page.update()
            
            def confirmar_eliminacion(index, dlg):
                """Confirma la eliminación de un detalle"""
                detalles_modificados.pop(index)
                close_dlg(dlg)
                actualizar_interfaz()
                
                # Mostrar notificación
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Producto eliminado"),
                    bgcolor=ft.Colors.RED_400
                )
                page.snack_bar.open = True
                page.update()
            
            def guardar_cambios_pedido():
                """Guarda los cambios realizados al pedido"""
                try:
                    conn = app.get_db_connection()
                    cursor = conn.cursor()
                    
                    # Calcular nuevo total
                    nuevo_total = sum(detalle["subtotal"] for detalle in detalles_modificados)
                    
                    # Actualizar total del pedido
                    cursor.execute(
                        "UPDATE pedidos SET total = %s WHERE id = %s",
                        (nuevo_total, pedido_id)
                    )
                    
                    # Obtener detalles actuales para comparar
                    cursor.execute(
                        "SELECT id, cantidad FROM detalle_pedido WHERE pedido_id = %s",
                        (pedido_id,)
                    )
                    detalles_actuales = {row[0]: row[1] for row in cursor.fetchall()}
                    
                    # Identificar detalles a actualizar y eliminar
                    ids_modificados = [d["id"] for d in detalles_modificados]
                    ids_a_eliminar = [id_detalle for id_detalle in detalles_actuales if id_detalle not in ids_modificados]
                    
                    # Eliminar detalles que ya no están
                    for id_detalle in ids_a_eliminar:
                        # Obtener información del detalle antes de eliminarlo
                        cursor.execute(
                            "SELECT producto_id, cantidad FROM detalle_pedido WHERE id = %s",
                            (id_detalle,)
                        )
                        detalle_a_eliminar = cursor.fetchone()
                        if detalle_a_eliminar:
                            # Restaurar stock
                            cursor.execute(
                                "UPDATE productos SET stock = stock + %s WHERE id = %s",
                                (detalle_a_eliminar[1], detalle_a_eliminar[0])
                            )
                        
                        # Eliminar detalle
                        cursor.execute(
                            "DELETE FROM detalle_pedido WHERE id = %s",
                            (id_detalle,)
                        )
                    
                    # Actualizar detalles modificados
                    for detalle in detalles_modificados:
                        if detalle["id"] in detalles_actuales:
                            # Es un detalle existente, actualizarlo
                            diferencia_cantidad = detalle["cantidad"] - detalles_actuales[detalle["id"]]
                            
                            # Actualizar detalle
                            cursor.execute(
                                """UPDATE detalle_pedido 
                                SET cantidad = %s, precio_unitario = %s, subtotal = %s
                                WHERE id = %s""",
                                (detalle["cantidad"], detalle["precio_unitario"], 
                                detalle["subtotal"], detalle["id"])
                            )
                            
                            # Actualizar stock (restar si se aumentó la cantidad, sumar si se disminuyó)
                            if diferencia_cantidad != 0:
                                cursor.execute(
                                    "UPDATE productos SET stock = stock - %s WHERE id = %s",
                                    (diferencia_cantidad, detalle["producto_id"])
                                )
                    
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    # Mostrar mensaje de éxito
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("¡Pedido actualizado correctamente!"),
                        bgcolor=ft.Colors.GREEN
                    )
                    page.snack_bar.open = True
                    
                    # Cerrar diálogo
                    close_dlg(dlg_detalles)
                    
                    # Actualizar lista de pedidos
                    cargar_pedidos()
                    
                except Exception as e:
                    page.snack_bar = ft.SnackBar(content=ft.Text(f"Error al actualizar pedido: {e}"))
                    page.snack_bar.open = True
                    page.update()
            
            # Personalización específica para móvil del título y encabezados
            if is_mobile:
                # Diseño específico para móvil
                titulo_dlg = ft.Row([
                    ft.Icon(ft.Icons.RECEIPT_LONG, color=ft.Colors.PURPLE),
                    ft.Text(f"Pedido #{pedido_id}", size=20, weight=ft.FontWeight.BOLD)
                ], alignment=ft.MainAxisAlignment.CENTER)
                
                info_cliente = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.PERSON, color=ft.Colors.BLUE, size=18),
                            ft.Text(f"Cliente: ", size=14),
                            ft.Text(pedido['cliente'], weight=ft.FontWeight.BOLD, size=16),
                        ]),
                        ft.Row([
                            ft.Icon(ft.Icons.LOCATION_ON, color=ft.Colors.RED, size=18),
                            ft.Text(f"Zona: ", size=14),
                            ft.Text(pedido['zona'], weight=ft.FontWeight.BOLD, size=16),
                        ]),
                        ft.Row([
                            ft.Icon(ft.Icons.CALENDAR_TODAY, color=ft.Colors.GREEN, size=18),
                            ft.Text(f"Fecha: ", size=14),
                            ft.Text(pedido['fecha'].strftime('%d/%m/%Y %H:%M'), 
                                weight=ft.FontWeight.BOLD, size=16),
                        ]),
                    ]),
                    padding=15,
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE_GREY),
                    border_radius=10,
                    border=ft.border.all(1, ft.Colors.BLUE_GREY_200)
                )
                
                cabecera = ft.Container(
                    content=ft.Text("Productos del pedido", 
                        weight=ft.FontWeight.BOLD, size=18),
                    margin=ft.margin.only(top=10, bottom=10),
                    alignment=ft.alignment.center
                )
            else:
                # Diseño original para escritorio
                titulo_dlg = ft.Text(f"Pedido #{pedido_id}", size=20)
                
                info_cliente = ft.Column([
                    ft.Text(f"Cliente: {pedido['cliente']}", weight=ft.FontWeight.BOLD),
                    ft.Text(f"Zona: {pedido['zona']}"),
                    ft.Text(f"Fecha: {pedido['fecha'].strftime('%d/%m/%Y %H:%M')}"),
                ])
                
                cabecera = ft.Container(
                    content=ft.Row([
                        ft.Container(ft.Text("Producto", weight=ft.FontWeight.BOLD), width=210, padding=10),
                        ft.Container(ft.Text("Cant.", weight=ft.FontWeight.BOLD), width=60, padding=10, alignment=ft.alignment.center),
                        ft.Container(ft.Text("Precio", weight=ft.FontWeight.BOLD), width=80, padding=10, alignment=ft.alignment.center),
                        ft.Container(ft.Text("Subtotal", weight=ft.FontWeight.BOLD), width=80, padding=10, alignment=ft.alignment.center),
                        ft.Container(ft.Text("Acciones", weight=ft.FontWeight.BOLD), width=100, padding=10, alignment=ft.alignment.center),
                    ]),
                    bgcolor=ft.Colors.BLUE_GREY_200 if page.theme_mode == ft.ThemeMode.LIGHT else ft.Colors.BLUE_GREY_700,
                    border_radius=ft.border_radius.only(top_left=5, top_right=5),
                    margin=ft.margin.only(bottom=5)
                )
            
            # Contenedor para las filas de detalles
            contenedor_detalles = ft.Column(
                scroll=ft.ScrollMode.AUTO,
                height=240 if is_mobile else 250
            )
            
            # Botones para acciones finales
            botones_acciones = [
                ft.TextButton(
                    "Cancelar", 
                    on_click=lambda _: close_dlg(dlg_detalles)
                ),
                ft.ElevatedButton(
                    "Guardar Cambios", 
                    icon=ft.Icons.SAVE,
                    on_click=lambda _: guardar_cambios_pedido(),
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        bgcolor=ft.Colors.GREEN
                    )
                )
            ]
            
            # Añadir información de ayuda en móvil
            if is_mobile:
                ayuda_texto = ft.Container(
                    content=ft.Text(
                        "Toca los botones para editar o eliminar productos",
                        size=12,
                        italic=True,
                        text_align=ft.TextAlign.CENTER
                    ),
                    margin=ft.margin.only(bottom=5)
                )
            else:
                ayuda_texto = ft.Container(height=0)  # No mostrar en escritorio
            
            # Diálogo principal mejorado para móvil
            dlg_ancho = page.width - 40 if is_mobile else 550
            dlg_alto = 550 if is_mobile else 450  # Mayor altura en móvil
            
            dlg_detalles = ft.AlertDialog(
                title=titulo_dlg,
                content=ft.Column([
                    info_cliente,
                    ft.Divider(),
                    cabecera,
                    ayuda_texto,
                    contenedor_detalles,
                    ft.Divider(),
                    total_text,
                ], width=dlg_ancho, height=dlg_alto),
                actions=botones_acciones,
                actions_alignment=ft.MainAxisAlignment.END,
                modal=True
            )
            
            # Cargar detalles iniciales
            actualizar_interfaz()
            
            # Mostrar diálogo
            page.dialog = dlg_detalles
            dlg_detalles.open = True
            page.update()
                
        except Exception as e:
            print(f"Error al cargar detalles del pedido: {e}")
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Error: {e}"))
            page.snack_bar.open = True
            page.update()
    

    def load_components():
        nonlocal components_loaded
        if components_loaded:
            return
        
        # Detectar si estamos en dispositivo móvil
        is_mobile = page.width < 800
        
        # Cargar lista inicial de productos
        filtrar_productos("")
        
        # Configurar la tabla del pedido adecuadamente
        configurar_tabla_pedido_responsivo()
        
        # Aquí configuramos los eventos para el campo de hora
        setup_hora_field_events()
        
        # Si estamos en móvil, creamos un layout específico
        if is_mobile:
            # Crear panel flotante solo para móviles y añadirlo como un componente fijo
            panel_flotante = crear_panel_flotante()
            # Guardar referencia al panel flotante
            page.panel_flotante = panel_flotante
            
            # VERSIÓN MÓVIL
            contenido_principal = ft.Column([
                # Panel flotante fijo en la parte superior
                panel_flotante if panel_flotante else ft.Container(height=0),
                
                # Título
                ft.Container(
                    content=ft.Row([
                        ft.Text("DistriSulpi", size=28, weight=ft.FontWeight.BOLD),
                        ft.Text("Sistema de Gestión", size=16, italic=True)
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    margin=ft.margin.only(bottom=10)
                ),
                
                # PRIMERO: Sección de datos del cliente
                # Para versión móvil:
                ft.Container(
                    content=ft.Column([
                        ft.Text("Datos del Cliente", size=18, weight=ft.FontWeight.BOLD),
                        cliente_field,
                        sugerencias_clientes_container,
                        zona_dropdown,
                        # Añadir la sección de fecha
                        ft.Container(
                            content=ft.Column([
                                ft.Text("Fecha del pedido", size=16, weight=ft.FontWeight.BOLD),
                                fecha_field,
                                hora_field,
                                actualizar_fecha_btn
                            ]),
                            margin=ft.margin.only(top=10)
                        )
                    ]),
                    padding=10,
                    border=ft.border.all(1, ft.Colors.BLACK26),
                    border_radius=5,
                    margin=ft.margin.only(bottom=10)
                ),
                
                # SEGUNDO: Pedido actual (visible pero no tan prominente)
                ft.Container(
                    content=ft.Column([
                        # Cabecera destacada
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.SHOPPING_CART, color=ft.Colors.WHITE),
                                ft.Text("Pedido Actual", 
                                    size=20, 
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE)
                            ], alignment=ft.MainAxisAlignment.CENTER),
                            bgcolor=ft.Colors.PURPLE,
                            padding=10,
                            border_radius=ft.border_radius.only(top_left=5, top_right=5)
                        ),
                        # Tabla de pedidos con scroll
                        ft.Container(
                            content=ft.Column(
                                [pedido_actual_table],
                                scroll=ft.ScrollMode.AUTO,
                                expand=True,
                                spacing=0
                            ),
                            height=150,  # Altura reducida
                            padding=5
                        ),
                        # Botón de finalizar
                        ft.Container(
                            content=finalizar_pedido_btn,
                            alignment=ft.alignment.center,
                            margin=ft.margin.only(bottom=5, top=5),
                            width=page.width
                        )
                    ]),
                    padding=0,
                    border=ft.border.all(2, ft.Colors.PURPLE),
                    border_radius=5,
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PURPLE),
                    width=page.width,
                    margin=ft.margin.only(bottom=10),
                    expand=False
                ),
                
                # TERCERO: Sección de productos
                ft.Container(
                    content=ft.Column([
                        ft.Text("Selección de Productos (toca para agregar)", 
                            size=18, weight=ft.FontWeight.BOLD),
                        producto_search,
                        ft.Container(content=productos_list, margin=ft.margin.only(top=10, bottom=10)),
                        ft.Row([
                            ft.Text("Cantidad:"),
                            cantidad_field,
                            precio_field
                        ], alignment=ft.MainAxisAlignment.START)
                    ]),
                    padding=10,
                    border=ft.border.all(1, ft.Colors.BLACK26),
                    border_radius=5,
                    margin=ft.margin.only(bottom=10)
                ),
                
                # CUARTO: Sección de herramientas
                ft.Container(
                    content=ft.Column([
                        ft.Text("Herramientas", size=18, weight=ft.FontWeight.BOLD),
                        ft.Row([
                            csv_upload_btn,
                            estadisticas_btn,
                            prediccion_btn,
                            pedidos_hoy_btn,
                            ver_pedidos_btn
                        ], wrap=True, spacing=10)
                    ]),
                    padding=10,
                    border=ft.border.all(1, ft.Colors.BLACK26),
                    border_radius=5,
                    margin=ft.margin.only(bottom=10)
                ),
                
                # Contenedores para funciones especiales
                estadisticas_container,
                prediccion_container,
                pedidos_container,
            ])
            
            # Añadir el contenido principal a la página
            page.add(contenido_principal)
        else:
            # VERSIÓN ESCRITORIO - Layout original
            page.add(
                ft.Column([
                    # Título
                    ft.Container(
                        content=ft.Row([
                            ft.Text("DistriSulpi", size=28, weight=ft.FontWeight.BOLD),
                            ft.Text("Sistema de Gestión", size=16, italic=True)
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        margin=ft.margin.only(bottom=20)
                    ),
                    
                    # Estructura con 2 columnas para escritorio
                    ft.Row([
                        # Columna izquierda (datos cliente y productos)
                        ft.Column([
                            # Sección de datos del cliente
                            # Para versión escritorio:
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("Datos del Cliente", size=18, weight=ft.FontWeight.BOLD),
                                    cliente_field,
                                    sugerencias_clientes_container,
                                    zona_dropdown,
                                    # Añadir la sección de fecha
                                    ft.Container(
                                        content=ft.Column([
                                            ft.Text("Fecha del pedido", size=16, weight=ft.FontWeight.BOLD),
                                            fecha_field,
                                            hora_field,
                                            actualizar_fecha_btn
                                        ]),
                                        margin=ft.margin.only(top=10)
                                    )
                                ]),
                                padding=10,
                                border=ft.border.all(1, ft.Colors.BLACK26),
                                border_radius=5,
                                margin=ft.margin.only(bottom=10)
                            ),
                            
                            # Sección de productos
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("Selección de Productos (toca para agregar)", 
                                        size=18, weight=ft.FontWeight.BOLD),
                                    producto_search,
                                    ft.Container(content=productos_list, margin=ft.margin.only(top=10, bottom=10)),
                                    ft.Row([
                                        ft.Text("Cantidad:"),
                                        cantidad_field,
                                        precio_field
                                    ], alignment=ft.MainAxisAlignment.START)
                                ]),
                                padding=10,
                                border=ft.border.all(1, ft.Colors.BLACK26),
                                border_radius=5,
                                margin=ft.margin.only(bottom=20)
                            ),
                            
                            # Sección de herramientas
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("Herramientas", size=18, weight=ft.FontWeight.BOLD),
                                    ft.Row([
                                        csv_upload_btn,
                                        estadisticas_btn,
                                        prediccion_btn,
                                        pedidos_hoy_btn,
                                        ver_pedidos_btn
                                    ], wrap=True, spacing=10)
                                ]),
                                padding=10,
                                border=ft.border.all(1, ft.Colors.BLACK26),
                                border_radius=5,
                                margin=ft.margin.only(bottom=20)
                            ),
                        ], 
                        width=page.width * 0.58),
                        
                        # Columna derecha (pedido actual)
                        ft.Container(
                            content=ft.Column([
                                # Cabecera destacada
                                ft.Container(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.SHOPPING_CART, color=ft.Colors.WHITE),
                                        ft.Text("Pedido Actual", 
                                            size=20, 
                                            weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.WHITE)
                                    ], alignment=ft.MainAxisAlignment.CENTER),
                                    bgcolor=ft.Colors.PURPLE,
                                    padding=10,
                                    border_radius=ft.border_radius.only(top_left=5, top_right=5)
                                ),
                                # Texto explicativo
                                ft.Text("Toca la cantidad para modificarla", 
                                    size=12, italic=True, 
                                    text_align=ft.TextAlign.CENTER),
                                # Tabla de pedidos dentro de un Column con scroll
                                ft.Column(
                                    [pedido_actual_table],
                                    scroll=ft.ScrollMode.AUTO,
                                    expand=True,
                                    spacing=0,
                                    height=350
                                ),
                                # Botón de finalizar
                                ft.Container(
                                    content=finalizar_pedido_btn,
                                    alignment=ft.alignment.center_right,
                                    margin=ft.margin.only(bottom=10, right=10)
                                )
                            ]),
                            padding=ft.padding.only(bottom=10),
                            border=ft.border.all(2, ft.Colors.PURPLE),
                            border_radius=5,
                            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PURPLE),
                            width=page.width * 0.4,
                            margin=ft.margin.only(left=10, top=0),
                            expand=False
                        )
                    ], 
                    wrap=False),
                    
                    # Contenedores para funciones especiales
                    estadisticas_container,
                    prediccion_container,
                    pedidos_container,
                ], 
                scroll=ft.ScrollMode.AUTO,
                expand=False)
            )
        
        components_loaded = True

    # Actualizar si hay productos en el pedido
    if current_order:
        actualizar_tabla_pedido()

        aplicar_mejoras_movil()
    # Inicializar la interfaz
    page.on_route_change = lambda _: load_components()
    load_components()

# Ejecutar la aplicación
ft.app(target=main, view=ft.AppView.FLET_APP)