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
import base64
import tempfile
import uuid
import webbrowser
import urllib.parse
from datetime import date, timedelta

PDF_DOWNLOADS = {}  # Diccionario para almacenar PDFs temporalmente

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

    def guardar_pedido(self, cliente, zona, detalles, fecha_personalizada=None):
        """Guarda un pedido en la base de datos, con opción de fecha personalizada"""
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
            
            # Determinar la fecha a usar (personalizada o actual)
            fecha_pedido = fecha_personalizada if fecha_personalizada else datetime.datetime.now()
            
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

    def get_ventas_diarias(self, fecha_especifica=None):
        """Obtiene las ventas del día actual o una fecha específica"""
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            
            # Usar fecha específica o la actual
            fecha_consulta = fecha_especifica.strftime("%Y-%m-%d") if fecha_especifica else datetime.datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute("""
            SELECT p.id, p.cliente, p.zona, p.fecha, p.total,
                   pr.nombre as producto, dp.cantidad, dp.precio_unitario, dp.subtotal
            FROM pedidos p
            JOIN detalle_pedido dp ON p.id = dp.pedido_id
            JOIN productos pr ON dp.producto_id = pr.id
            WHERE DATE(p.fecha) = %s
            ORDER BY p.fecha DESC
            """, (fecha_consulta,))
            
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

    def get_ganancia_diaria(self, fecha_especifica=None):
        """Obtiene la ganancia del día actual o una fecha específica"""
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            
            # Usar fecha específica o la actual
            fecha_consulta = fecha_especifica.strftime("%Y-%m-%d") if fecha_especifica else datetime.datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute("""
            SELECT SUM((dp.precio_unitario - p.costo) * dp.cantidad) as ganancia
            FROM pedidos ped
            JOIN detalle_pedido dp ON ped.id = dp.pedido_id
            JOIN productos p ON dp.producto_id = p.id
            WHERE DATE(ped.fecha) = %s
            """, (fecha_consulta,))
            
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

    def get_facturacion_diaria(self, fecha_especifica=None):
        """Obtiene el total facturado del día actual o una fecha específica"""
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            
            # Usar fecha específica o la actual
            fecha_consulta = fecha_especifica.strftime("%Y-%m-%d") if fecha_especifica else datetime.datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute("""
            SELECT SUM(total) as facturacion
            FROM pedidos
            WHERE DATE(fecha) = %s
            """, (fecha_consulta,))
            
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

    def generar_pdf_pedidos_hoy(self, fecha_especifica=None):
        """Genera un PDF con todos los pedidos del día actual o una fecha específica"""
        try:
            # Obtener ventas del día específico o actual
            ventas_dia = self.get_ventas_diarias(fecha_especifica)
            
            if not ventas_dia:
                return None, "No hay ventas registradas en la fecha seleccionada"
            
            # Crear diccionario agrupado por producto
            productos_vendidos = {}
            for venta in ventas_dia:
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
            fecha_str = fecha_especifica.strftime("%d/%m/%Y") if fecha_especifica else datetime.datetime.now().strftime("%d/%m/%Y")
            elements.append(Paragraph(f"<b>DistriSulpi - Ventas del día {fecha_str}</b>", styles['Title']))
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

    def get_pedidos_por_fecha(self, fecha):
        """Obtiene todos los pedidos por fecha específica"""
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
            SELECT id, cliente, zona, fecha, total 
            FROM pedidos 
            WHERE DATE(fecha) = %s
            ORDER BY fecha DESC
            """, (fecha,))
            
            pedidos = cursor.fetchall()
            cursor.close()
            conn.close()
            return pedidos
        return []

    def generar_pdf_multiple_pedidos(self, pedidos_ids):
        """Genera un único PDF con múltiples pedidos"""
        try:
            # Crear directorio para PDFs si no existe
            os.makedirs("temp", exist_ok=True)
            
            # Crear PDF en memoria
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            elements = []
            
            # Estilos
            styles = getSampleStyleSheet()
            
            # Título
            elements.append(Paragraph(f"<b>DistriSulpi - Resumen de Pedidos</b>", styles['Title']))
            elements.append(Paragraph(f"Fecha: {datetime.datetime.now().strftime('%d/%m/%Y')}", styles['Normal']))
            elements.append(Paragraph("<br/>", styles['Normal']))
            
            # Procesar cada pedido
            conn = self.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            for pedido_id in pedidos_ids:
                # Obtener información del pedido
                cursor.execute("""
                SELECT p.id, p.cliente, p.zona, p.fecha, p.total
                FROM pedidos p
                WHERE p.id = %s
                """, (pedido_id,))
                
                pedido = cursor.fetchone()
                if not pedido:
                    continue
                
                # Obtener detalles del pedido
                cursor.execute("""
                SELECT dp.*, pr.nombre as producto_nombre
                FROM detalle_pedido dp
                JOIN productos pr ON dp.producto_id = pr.id
                WHERE dp.pedido_id = %s
                """, (pedido_id,))
                
                detalles = cursor.fetchall()
                
                # Información del pedido
                elements.append(Paragraph(f"<b>Pedido #{pedido_id}</b>", styles['Heading2']))
                
                # Información del cliente
                data_cliente = [
                    [Paragraph("<b>Cliente:</b>", styles['Normal']), pedido['cliente']],
                    [Paragraph("<b>Zona:</b>", styles['Normal']), pedido['zona']],
                    [Paragraph("<b>Fecha:</b>", styles['Normal']), pedido['fecha'].strftime('%d/%m/%Y %H:%M')]
                ]
                
                tabla_cliente = Table(data_cliente, colWidths=[doc.width*0.2, doc.width*0.8])
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
                
                # Detalles del pedido
                data = [["Producto", "Cantidad", "Precio Unit.", "Subtotal"]]
                
                for detalle in detalles:
                    nombre_producto = detalle['producto_nombre']
                    if len(nombre_producto) > 30:
                        nombre_producto = nombre_producto[:27] + "..."
                    
                    data.append([
                        nombre_producto,
                        str(detalle['cantidad']),
                        f"${float(detalle['precio_unitario']):.2f}",
                        f"${float(detalle['subtotal']):.2f}"
                    ])
                
                # Fila de total
                data.append(["", "", "TOTAL", f"${float(pedido['total']):.2f}"])
                
                # Crear tabla de detalles
                col_widths = [doc.width*0.5, doc.width*0.1, doc.width*0.2, doc.width*0.2]
                table = Table(data, colWidths=col_widths)
                
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                    ('ALIGN', (2, 0), (3, -1), 'RIGHT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -2), 1, colors.black),
                    ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
                    ('GRID', (2, -1), (-1, -1), 1, colors.black),
                ]))
                
                elements.append(table)
                elements.append(Paragraph("<br/><br/>", styles['Normal']))
                
                # Separador entre pedidos
                if pedido_id != pedidos_ids[-1]:
                    elements.append(Paragraph("<hr/>", styles['Normal']))
                    elements.append(Paragraph("<br/>", styles['Normal']))
            
            cursor.close()
            conn.close()
            
            # Generar PDF
            doc.build(elements)
            
            # Obtener el contenido del PDF
            pdf_content = buffer.getvalue()
            buffer.close()
            
            return pdf_content, "Reporte múltiple generado correctamente"
        except Exception as e:
            return None, f"Error al generar reporte múltiple: {e}"

# Implementación de la interfaz de usuario con Flet
def main(page: ft.Page):
    # Instancia de la aplicación
    app = DistriSulpiApp()
    
    # Configuración de la página con tema personalizado
    page.title = "DistriSulpi 📦"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 10
    page.scroll = ft.ScrollMode.AUTO
    
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
    fecha_pedido = datetime.datetime.now()  # Nueva variable para la fecha personalizada
    
    # Para prevenir la carga múltiple de componentes
    components_loaded = False
    
    # Referencia a la página principal para menú lateral
    principal_view = None
    
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
        auto_scroll=True,
        visible=False  # Inicialmente oculta
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
    
    # Contenedor para fecha de pedido
    fecha_pedido_container = ft.Container(
        content=ft.Row([
            ft.Text("Fecha del pedido:", size=14),
            ft.IconButton(
                icon=ft.Icons.CALENDAR_TODAY,
                icon_color=ft.Colors.BLUE,
                tooltip="Cambiar fecha",
                on_click=lambda _: mostrar_calendario()
            ),
            ft.Text(
                datetime.datetime.now().strftime('%d/%m/%Y'),
                size=16,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.BLUE
            )
        ]),
        padding=10,
        border=ft.border.all(1, ft.Colors.BLUE_100),
        border_radius=10,
        margin=5,
        visible=False  # Inicialmente oculto
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
        "Cargar Productos",
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
        "Estadísticas",
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
        "Predicción",
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
        "Ver Pedidos",
        icon=ft.Icons.LIST_ALT,
        on_click=lambda _: toggle_ver_pedidos()
    )
    
    # Botón para compartir pedidos
    compartir_pedidos_btn = ft.ElevatedButton(
        "Compartir",
        icon=ft.Icons.SHARE,
        on_click=lambda _: seleccionar_pedidos_para_compartir()
    )
    
    # Botón para borrar todos los productos del pedido
    borrar_productos_btn = ft.ElevatedButton(
        "Borrar todo",
        icon=ft.Icons.DELETE_SWEEP,
        style=ft.ButtonStyle(
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.RED
        ),
        on_click=lambda _: confirmar_borrar_todos_productos()
    )
    
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
    
    # Nueva función para mostrar el calendario y seleccionar fecha
    def mostrar_calendario():
        """Muestra el calendario personalizado para seleccionar fecha del pedido"""
        def on_fecha_seleccionada(fecha_seleccionada):
            nonlocal fecha_pedido
            # Preservar la hora actual
            fecha_actual = fecha_pedido if isinstance(fecha_pedido, datetime.datetime) else datetime.datetime.now()
            nueva_fecha = datetime.datetime.combine(fecha_seleccionada.date(), fecha_actual.time())
            fecha_pedido = nueva_fecha
            
            # Actualizar el texto de la fecha
            fecha_label = fecha_pedido_container.content.controls[2]
            fecha_label.value = fecha_pedido.strftime('%d/%m/%Y')
            fecha_pedido_container.update()
            
            # Mostrar confirmación
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Fecha cambiada a: {fecha_pedido.strftime('%d/%m/%Y')}"),
                bgcolor=ft.Colors.GREEN
            )
            page.snack_bar.open = True
            page.update()
        
        mostrar_calendario_personalizado(on_fecha_seleccionada, fecha_pedido)

    
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
        
        # Mostrar u ocultar contenedor de fecha
        if current_order:
            fecha_pedido_container.visible = True
        else:
            fecha_pedido_container.visible = False
        fecha_pedido_container.update()
    
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
                try:
                    actualizar_tabla_pedido()
                    pedido_actual_table.update()
                except Exception as e:
                    print(f"Error actualizando tabla: {e}")
                
                # Mostrar panel flotante con la información actualizada
                total = sum(item["subtotal"] for item in current_order)
                actualizar_panel_flotante(total)
                
                # Mostrar el contenedor de fecha si es el primer producto
                if len(current_order) == 1:
                    fecha_pedido_container.visible = True
                    fecha_pedido_container.update()
                
                # Restablecer cantidad a 1 para el próximo producto
                cantidad_field.value = "1"
                cantidad_field.update()
                
                # Ocultar lista de productos después de agregar (solo en móvil)
                is_mobile = page.width < 800
                if is_mobile:
                    productos_list.visible = False
                    productos_list.update()
                
            except Exception as e:
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Error: {str(e)}"))
                page.snack_bar.open = True
                page.update()
        
        # Detectar si estamos en móvil
        is_mobile = page.width < 800
        
        if is_mobile:
            # VERSIÓN MÓVIL COMPACTA - Elementos más pequeños
            productos_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        # Icono más pequeño
                        ft.Icon(
                            ft.Icons.INVENTORY_2, 
                            color=ft.Colors.GREEN if producto["stock"] > 10 
                            else ft.Colors.ORANGE if producto["stock"] > 0 
                            else ft.Colors.RED,
                            size=16  # Icono más pequeño
                        ),
                        # Información del producto en una columna compacta
                        ft.Column([
                            # Nombre del producto (más pequeño)
                            ft.Text(
                                producto["nombre"][:20] + ('...' if len(producto["nombre"]) > 20 else ''),
                                size=12,  # Texto más pequeño
                                weight=ft.FontWeight.BOLD,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                max_lines=1
                            ),
                            # Precio y stock en una fila horizontal para ahorrar espacio
                            ft.Row([
                                ft.Text(f"${producto['precio_venta']:.1f}", 
                                    color=ft.Colors.BLUE,
                                    size=11),  # Texto más pequeño
                                ft.Text(" | ", color=ft.Colors.GREY, size=10),
                                ft.Text(f"Stock: {producto['stock']}", 
                                    color=ft.Colors.GREEN if producto["stock"] > 10 
                                    else ft.Colors.ORANGE if producto["stock"] > 0 
                                    else ft.Colors.RED,
                                    size=10)  # Texto más pequeño
                            ], spacing=2)
                        ], 
                        spacing=2,  # Reducir espaciado
                        expand=True),
                        # Botón + para agregar (más pequeño)
                        ft.IconButton(
                            icon=ft.Icons.ADD_CIRCLE,
                            icon_color=ft.Colors.GREEN,
                            icon_size=18,  # Botón más pequeño
                            tooltip="Agregar",
                            on_click=on_producto_click
                        )
                    ], 
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    spacing=5),  # Reducir espaciado
                    
                    # Contenedor más compacto
                    border=ft.border.all(0.5, ft.Colors.BLACK26),  # Borde más fino
                    border_radius=5,  # Esquinas menos redondeadas
                    margin=2,  # Margen más pequeño
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),  # Padding más pequeño
                    bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.BLUE_GREY),
                    height=45,  # Altura fija más pequeña
                    on_click=on_producto_click  # También permite hacer clic en todo el contenedor
                )
            )
        else:
            # VERSIÓN ESCRITORIO - Sin cambios (mantener el diseño original)
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
                        on_click=on_producto_click
                    ),
                    border=ft.border.all(1, ft.Colors.BLACK26),
                    border_radius=10,
                    margin=5,
                    padding=10
                )
            )

    # También necesitas modificar la función filtrar_productos para aumentar ligeramente la altura en móvil
    def filtrar_productos(query):
        try:
            productos_list.controls.clear()
            productos_list.update()  # Actualizar la lista primero
        except:
            pass  # Ignorar errores de limpieza
        
        # Resto del código igual...
        is_mobile = page.width < 800
        if is_mobile:
            if query:
                productos_list.visible = True
                productos_list.height = 500
            else:
                productos_list.visible = False
        
        # Mostrar la lista solo si hay texto para filtrar (en móvil)
        productos_list.controls = []  # Usar esto en su lugar
        productos = app.get_productos()
        
        if not query:
            if not is_mobile:  # En escritorio siempre mostramos productos
                for producto in productos:
                    add_product_to_list(producto)
        else:
            query = query.lower()
            for producto in productos:
                if query in producto["nombre"].lower():
                    add_product_to_list(producto)
        
        # Actualizar la página
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
            # CORRECCIÓN: Sintaxis correcta para animación en Flet actual
            # Eliminamos la animación que causa problemas
            visible=False,  # Inicialmente oculto hasta que haya productos
        )
        
        return panel

    def crear_enlace_descarga_pdf(pdf_content, filename):
        """
        Crea un enlace de descarga para PDF que funciona en móvil
        """
        try:
            # Generar ID único para el archivo
            file_id = str(uuid.uuid4())
            
            # Almacenar el PDF en memoria temporalmente
            PDF_DOWNLOADS[file_id] = {
                'content': pdf_content,
                'filename': filename,
                'timestamp': datetime.datetime.now()
            }
            
            # Limpiar archivos antiguos (más de 1 hora)
            current_time = datetime.datetime.now()
            expired_ids = [
                fid for fid, data in PDF_DOWNLOADS.items() 
                if (current_time - data['timestamp']).seconds > 3600
            ]
            for fid in expired_ids:
                del PDF_DOWNLOADS[fid]
            
            return file_id
        except Exception as e:
            print(f"Error creando enlace de descarga: {e}")
            return None
    
    # MODIFICACIÓN: Actualizar tabla de pedidos con edición directa de cantidad
    def actualizar_tabla_pedido():
        """Actualiza la tabla de pedidos con mejor visualización para móviles"""
        try:
            pedido_actual_table.rows.clear()
        except:
            pedido_actual_table.rows = []
        
        # Detectar si estamos en móvil
        is_mobile = page.width < 800
        
        for i, item in enumerate(current_order):
            # Cantidad para editar - hacer más compacto
            cantidad_campo = ft.TextField(
                value=str(item["cantidad"]),
                width=40 if is_mobile else 60,  # Reducir ancho en móvil
                height=30 if is_mobile else None,
                text_align=ft.TextAlign.CENTER,
                border_color=ft.Colors.BLUE_200,
                keyboard_type=ft.KeyboardType.NUMBER,
                on_submit=lambda e, idx=i: actualizar_cantidad_directa(e.control.value, idx),
                text_size=12 if is_mobile else None  # Texto más pequeño
            )
            
            # Botón de eliminar más pequeño en móvil
            boton_eliminar = ft.IconButton(
                icon=ft.Icons.DELETE,
                tooltip="Eliminar",
                on_click=lambda _, idx=i: eliminar_item_pedido(idx),
                icon_color=ft.Colors.RED,
                icon_size=16 if is_mobile else 20  # Tamaño más pequeño en móvil
            )
            
            if is_mobile:
                # Versión móvil con 4 columnas compactas
                pedido_actual_table.rows.append(
                    ft.DataRow(
                        cells=[
                            # Nombre producto (más estrecho)
                            ft.DataCell(
                                ft.Text(
                                    item["producto_nombre"][:12] + ('...' if len(item["producto_nombre"]) > 12 else ''),  # Acortar más
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    max_lines=1,
                                    size=11  # Texto más pequeño
                                )
                            ),
                            # Cantidad
                            ft.DataCell(cantidad_campo),
                            # Precio unitario - ahora con texto más pequeño
                            ft.DataCell(
                                ft.Text(
                                    f"${item['precio_unitario']:.1f}",  # Reducir a 1 decimal
                                    size=11
                                )
                            ),
                            # Botón eliminar separado para asegurar que sea visible
                            ft.DataCell(boton_eliminar)
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
                            ft.DataCell(boton_eliminar)
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
                            ft.DataCell(ft.Text("TOTAL", weight=ft.FontWeight.BOLD, size=12)),
                            ft.DataCell(ft.Text(f"{len(current_order)}", size=12)),  # Más compacto
                            ft.DataCell(ft.Text("")),
                            ft.DataCell(
                                ft.Text(
                                    f"${total:.1f}",  # Reducir a 1 decimal
                                    weight=ft.FontWeight.BOLD, 
                                    size=12,
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
        
        # Actualizar visibilidad del botón para borrar productos
        if current_order:
            borrar_productos_btn.visible = True
        else:
            borrar_productos_btn.visible = False
        borrar_productos_btn.update()
        
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
        
        # Ocultar contenedor de fecha si no hay productos
        if not current_order:
            fecha_pedido_container.visible = False
            fecha_pedido_container.update()

    def close_dlg(dlg):
        dlg.open = False
        page.update()
    
    # Nueva función para confirmar antes de borrar todos los productos
    def confirmar_borrar_todos_productos():
        if not current_order:
            return
            
        dlg = ft.AlertDialog(
            title=ft.Text("Confirmar eliminación"),
            content=ft.Text("¿Está seguro de eliminar todos los productos del pedido actual?"),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dlg(dlg)),
                ft.ElevatedButton(
                    "Eliminar Todo", 
                    icon=ft.Icons.DELETE_FOREVER,
                    on_click=lambda _: borrar_todos_productos(dlg),
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
    
    def borrar_todos_productos(dlg):
        """Borra todos los productos del pedido actual"""
        current_order.clear()
        actualizar_tabla_pedido()
        fecha_pedido_container.visible = False
        fecha_pedido_container.update()
        close_dlg(dlg)
        
        # Notificar
        page.snack_bar = ft.SnackBar(
            content=ft.Text("Se han eliminado todos los productos"),
            bgcolor=ft.Colors.RED_400
        )
        page.snack_bar.open = True
        page.update()
    
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
        
        # Guardar pedido en la base de datos con la fecha personalizada
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
                
                # Mostrar mensaje de éxito con opciones
                dlg_success = ft.AlertDialog(
                    title=ft.Text("Pedido Completado"),
                    content=ft.Column([
                        ft.Text(f"Pedido #{pedido_id} guardado correctamente"),
                        ft.Row([
                            ft.ElevatedButton(
                                "Descargar Factura",
                                icon=ft.Icons.DOWNLOAD,
                                on_click=lambda _: download_file(temp_file, f"factura_{pedido_id}.pdf")
                            ),
                            ft.ElevatedButton(
                                "Compartir por WhatsApp",
                                icon=ft.Icons.WHATSAPP,
                                on_click=lambda _: compartir_por_whatsapp(pedido_id, cliente_actual)
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
    
    # Nueva función para compartir pedido por WhatsApp
    def compartir_por_whatsapp(pedido_id, cliente):
        try:
            # Obtener información del pedido
            conn = app.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
            SELECT p.*, DATE_FORMAT(p.fecha, '%d/%m/%Y') as fecha_formateada
            FROM pedidos p
            WHERE p.id = %s
            """, (pedido_id,))
            
            pedido = cursor.fetchone()
            
            if not pedido:
                page.snack_bar = ft.SnackBar(content=ft.Text("No se pudo obtener información del pedido"))
                page.snack_bar.open = True
                page.update()
                return
            
            # Obtener detalles del pedido
            cursor.execute("""
            SELECT dp.*, p.nombre as producto_nombre
            FROM detalle_pedido dp
            JOIN productos p ON dp.producto_id = p.id
            WHERE dp.pedido_id = %s
            """, (pedido_id,))
            
            detalles = cursor.fetchall()
            cursor.close()
            conn.close()
            
            # Crear mensaje con formato para WhatsApp
            mensaje = f"*PEDIDO #{pedido_id} - DistriSulpi*\n"
            mensaje += f"*Cliente:* {cliente}\n"
            mensaje += f"*Zona:* {pedido['zona']}\n"
            mensaje += f"*Fecha:* {pedido['fecha_formateada']}\n\n"
            
            mensaje += "*Detalles del pedido:*\n"
            for detalle in detalles:
                mensaje += f"• {detalle['cantidad']} x {detalle['producto_nombre']} - ${float(detalle['precio_unitario']):.2f} c/u = ${float(detalle['subtotal']):.2f}\n"
            
            mensaje += f"\n*TOTAL: ${float(pedido['total']):.2f}*"
            
            # Codificar mensaje para URL
            mensaje_codificado = urllib.parse.quote(mensaje)
            
            # Crear URL de WhatsApp
            url_whatsapp = f"https://wa.me/?text={mensaje_codificado}"
            
            # Abrir en el navegador predeterminado
            webbrowser.open(url_whatsapp)
            
        except Exception as e:
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Error al compartir: {str(e)}"))
            page.snack_bar.open = True
            page.update()
    
    # Nueva función para seleccionar pedidos y compartirlos juntos
    def seleccionar_pedidos_para_compartir():
        """Permite seleccionar varios pedidos para compartir o descargar"""
        # Obtener todos los pedidos del día
        conn = app.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute("""
        SELECT id, cliente, zona, fecha, total
        FROM pedidos
        WHERE DATE(fecha) = %s
        ORDER BY fecha DESC
        """, (today,))
        
        pedidos_hoy = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not pedidos_hoy:
            page.snack_bar = ft.SnackBar(content=ft.Text("No hay pedidos para compartir hoy"))
            page.snack_bar.open = True
            page.update()
            return
        
        # Crear checkboxes para seleccionar pedidos
        lista_seleccion = ft.ListView(
            spacing=5,
            padding=10,
            auto_scroll=True,
            height=400
        )
        
        # Mapa para asociar checkboxes con pedidos
        mapa_checkboxes = {}
        
        for pedido in pedidos_hoy:
            checkbox = ft.Checkbox(
                label=f"#{pedido['id']} - {pedido['cliente']} - ${float(pedido['total']):.2f}",
                value=False
            )
            mapa_checkboxes[checkbox] = pedido['id']
            
            lista_seleccion.controls.append(ft.Container(
                content=checkbox,
                border=ft.border.all(1, ft.Colors.GREY_400),
                border_radius=5,
                padding=10,
                margin=5
            ))
        
        # Función para manejar la selección
        def confirmar_seleccion():
            # Recopilar pedidos seleccionados
            pedidos_seleccionados = []
            for checkbox, pedido_id in mapa_checkboxes.items():
                if checkbox.value:
                    pedidos_seleccionados.append(pedido_id)
            
            if not pedidos_seleccionados:
                page.snack_bar = ft.SnackBar(content=ft.Text("Selecciona al menos un pedido"))
                page.snack_bar.open = True
                page.update()
                return
            
            # Cerrar diálogo de selección
            close_dlg(dlg_seleccion)
            
            # Mostrar opciones: WhatsApp o Descargar PDF
            dlg_opciones = ft.AlertDialog(
                title=ft.Text("¿Qué deseas hacer con los pedidos seleccionados?"),
                content=ft.Column([
                    ft.ElevatedButton(
                        "Enviar por WhatsApp",
                        icon=ft.Icons.WHATSAPP,
                        on_click=lambda _: compartir_multiple_pedidos_whatsapp(pedidos_seleccionados, dlg_opciones)
                    ),
                    ft.ElevatedButton(
                        "Descargar PDF",
                        icon=ft.Icons.PICTURE_AS_PDF,
                        on_click=lambda _: descargar_multiple_pedidos_pdf(pedidos_seleccionados, dlg_opciones)
                    ),
                    ft.TextButton("Cancelar", on_click=lambda _: close_dlg(dlg_opciones))
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                modal=True
            )
            
            page.dialog = dlg_opciones
            dlg_opciones.open = True
            page.update()
        
        # Diálogo para selección de pedidos
        dlg_seleccion = ft.AlertDialog(
            title=ft.Text("Selecciona pedidos para compartir"),
            content=ft.Column([
                ft.Text("Selecciona los pedidos que deseas compartir:"),
                lista_seleccion
            ]),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dlg(dlg_seleccion)),
                ft.ElevatedButton(
                    "Continuar",
                    on_click=lambda _: confirmar_seleccion()
                )
            ],
            modal=True
        )
        
        page.dialog = dlg_seleccion
        dlg_seleccion.open = True
        page.update()
    
    # Función para compartir múltiples pedidos por WhatsApp
    def compartir_multiple_pedidos_whatsapp(pedidos_ids, dlg):
        try:
            close_dlg(dlg)
            
            # Obtener información de los pedidos
            conn = app.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Crear mensaje con formato para WhatsApp
            mensaje = f"*RESUMEN DE PEDIDOS - DistriSulpi*\n"
            mensaje += f"*Fecha:* {datetime.datetime.now().strftime('%d/%m/%Y')}\n\n"
            
            # Procesar cada pedido
            total_general = 0
            
            for pedido_id in pedidos_ids:
                cursor.execute("""
                SELECT p.*, DATE_FORMAT(p.fecha, '%d/%m/%Y') as fecha_formateada, c.cliente
                FROM pedidos p
                JOIN (SELECT id, cliente FROM pedidos WHERE id = %s) c ON p.id = c.id
                WHERE p.id = %s
                """, (pedido_id, pedido_id))
                
                pedido = cursor.fetchone()
                
                if not pedido:
                    continue
                
                mensaje += f"*PEDIDO #{pedido_id} - {pedido['cliente']}*\n"
                mensaje += f"*Zona:* {pedido['zona']}\n"
                
                # Obtener detalles del pedido
                cursor.execute("""
                SELECT dp.cantidad, dp.precio_unitario, dp.subtotal, p.nombre as producto_nombre
                FROM detalle_pedido dp
                JOIN productos p ON dp.producto_id = p.id
                WHERE dp.pedido_id = %s
                """, (pedido_id,))
                
                detalles = cursor.fetchall()
                
                for detalle in detalles:
                    mensaje += f"• {detalle['cantidad']} x {detalle['producto_nombre']} - ${float(detalle['subtotal']):.2f}\n"
                
                mensaje += f"*Subtotal: ${float(pedido['total']):.2f}*\n\n"
                total_general += float(pedido['total'])
            
            cursor.close()
            conn.close()
            
            mensaje += f"*TOTAL GENERAL: ${total_general:.2f}*"
            
            # Codificar mensaje para URL
            mensaje_codificado = urllib.parse.quote(mensaje)
            
            # Crear URL de WhatsApp
            url_whatsapp = f"https://wa.me/?text={mensaje_codificado}"
            
            # Abrir en el navegador predeterminado
            webbrowser.open(url_whatsapp)
            
        except Exception as e:
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Error al compartir: {str(e)}"))
            page.snack_bar.open = True
            page.update()
    
    # Función para descargar múltiples pedidos como PDF
    def descargar_multiple_pedidos_pdf(pedidos_ids, dlg):
        try:
            close_dlg(dlg)
            
            # Mostrar diálogo de progreso
            progress_dlg = ft.AlertDialog(
                title=ft.Text("Generando PDF"),
                content=ft.Column([
                    ft.Text("Preparando documento..."),
                    ft.ProgressBar(width=300)
                ], tight=True, spacing=20),
                modal=True
            )
            
            page.dialog = progress_dlg
            progress_dlg.open = True
            page.update()
            
            # Generar PDF
            pdf_content, mensaje = app.generar_pdf_multiple_pedidos(pedidos_ids)
            
            # Cerrar diálogo de progreso
            progress_dlg.open = False
            page.update()
            
            if pdf_content:
                # Crear directorio para PDFs si no existe
                os.makedirs("temp", exist_ok=True)
                
                # Guardar PDF temporalmente
                temp_file = os.path.join("temp", f"pedidos_multiples_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.pdf")
                with open(temp_file, "wb") as f:
                    f.write(pdf_content)
                
                # Descargar archivo
                download_file(temp_file, f"pedidos_multiples.pdf")
            else:
                page.snack_bar = ft.SnackBar(content=ft.Text(mensaje))
                page.snack_bar.open = True
                page.update()
            
        except Exception as e:
            # Cerrar diálogo de progreso si sigue abierto
            if 'progress_dlg' in locals() and progress_dlg.open:
                progress_dlg.open = False
                page.update()
                
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Error al generar PDF: {str(e)}"))
            page.snack_bar.open = True
            page.update()
    
    # Nueva función para cerrar diálogo y ver pedidos
    def close_dlg_and_ver_pedidos(dlg):
        # Cerrar diálogo
        dlg.open = False
        page.update()
        
        # Resetear pedido actual
        current_order.clear()
        actualizar_tabla_pedido()
        
        # Limpiar campos
        cliente_field.value = ""
        zona_dropdown.value = None
        producto_search.value = ""
        cantidad_field.value = "1"
        precio_field.value = ""
        
        # Ocultar contenedor de fecha
        fecha_pedido_container.visible = False
        fecha_pedido_container.update()
        
        # Actualizar pantalla
        page.update()
        
        # Mostrar todos los pedidos
        toggle_ver_pedidos()
    
    def close_dlg_and_reset(dlg):
        # Cerrar diálogo
        dlg.open = False
        
        # Limpiar pedido actual
        current_order.clear()
        actualizar_tabla_pedido()
        
        # Limpiar campos
        cliente_field.value = ""
        zona_dropdown.value = None
        producto_search.value = ""
        cantidad_field.value = "1"
        precio_field.value = ""
        
        # Ocultar contenedor de fecha
        fecha_pedido_container.visible = False
        fecha_pedido_container.update()
        
        # Actualizar pantalla
        page.update()
    
    # 1. Mejorar la función download_file para que funcione en dispositivos móviles
    
    def download_file(path, filename):
        """Función actualizada que usa el nuevo sistema móvil"""
        download_file_mobile(path, filename)
            
    def configurar_tabla_pedido_responsivo():
            """Configura la estructura de la tabla de pedidos para dispositivos móviles"""
            # Verificar si estamos en móvil
            is_mobile = page.width < 800
            
            # Limpiar las columnas existentes
            try:
                pedido_actual_table.rows.clear()
            except:
                pedido_actual_table.rows = []
            # ✅ NO limpiar columnas, solo ajustar ancho
            pedido_actual_table.width = min(page.width - 40, 600)
            # ✅ Asegurar que las columnas existan
            if not pedido_actual_table.columns:
                pedido_actual_table.columns = [
                    ft.DataColumn(ft.Text("Producto", weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Cant.", weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Precio", weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Subtotal", weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("", weight=ft.FontWeight.BOLD))
                ]
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
                    # Acciones (eliminar)
                    ft.DataColumn(ft.Text("", 
                                        weight=ft.FontWeight.BOLD, 
                                        size=12),
                                numeric=False)
                ]
            else:
                # Configuración original para escritorio (5 columnas)
                pedido_actual_table.columns = [
                    ft.DataColumn(
                        ft.Text("Producto", weight=ft.FontWeight.BOLD)
                    ),
                    ft.DataColumn(
                        ft.Text("Cant.", weight=ft.FontWeight.BOLD),
                        numeric=True
                    ),
                    ft.DataColumn(
                        ft.Text("Precio", weight=ft.FontWeight.BOLD),
                        numeric=True
                    ),
                    ft.DataColumn(
                        ft.Text("Subtotal", weight=ft.FontWeight.BOLD),
                        numeric=True
                    ),
                    ft.DataColumn(
                        ft.Text("", weight=ft.FontWeight.BOLD)
                    )
                ]
            
            # Ajustar el ancho de la tabla según el dispositivo pero no demasiado
            # Limitar para evitar que se extienda fuera de la pantalla
            pedido_actual_table.width = min(page.width - 40, 600)
            
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
            pdf_content, mensaje = app.generar_pdf_factura(pedido_id)
            progress_dlg.open = False
            page.update()
            
            if pdf_content:
                os.makedirs("temp", exist_ok=True)
                temp_file = os.path.join("temp", f"factura_{pedido_id}.pdf")
                with open(temp_file, "wb") as f:
                    f.write(pdf_content)
                
                download_file_mobile(temp_file, f"factura_{pedido_id}.pdf")
            else:
                page.snack_bar = ft.SnackBar(content=ft.Text(mensaje))
                page.snack_bar.open = True
                page.update()
        except Exception as e:
            progress_dlg.open = False
            page.update()
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Error: {e}"))
            page.snack_bar.open = True
            page.update()
        
    def compartir_pdf_base64(content, filename, dlg=None):
        """
        Comparte el PDF usando base64 (funciona en móvil)
        """
        try:
            if dlg:
                close_dlg(dlg)
            
            # Convertir PDF a base64
            pdf_base64 = base64.b64encode(content).decode('utf-8')
            
            # Crear HTML con enlace de descarga
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Descargar PDF</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        text-align: center;
                        padding: 50px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                    }}
                    .container {{
                        background: white;
                        color: black;
                        padding: 30px;
                        border-radius: 10px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                        max-width: 400px;
                        margin: 0 auto;
                    }}
                    .download-btn {{
                        background: #4CAF50;
                        color: white;
                        padding: 15px 30px;
                        border: none;
                        border-radius: 5px;
                        font-size: 18px;
                        cursor: pointer;
                        text-decoration: none;
                        display: inline-block;
                        margin: 20px 0;
                    }}
                    .download-btn:hover {{
                        background: #45a049;
                    }}
                    .info {{
                        font-size: 14px;
                        color: #666;
                        margin-top: 20px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>📄 PDF Listo para Descargar</h2>
                    <p>Archivo: <strong>{filename}</strong></p>
                    <a href="data:application/pdf;base64,{pdf_base64}" 
                    download="{filename}" 
                    class="download-btn">
                        ⬇️ Descargar PDF
                    </a>
                    <div class="info">
                        <p>• En Android: Se guardará en 'Descargas'</p>
                        <p>• En iPhone: Se abrirá para compartir</p>
                        <p>• Puedes cerrar esta página después de descargar</p>
                    </div>
                </div>
                <script>
                    // Auto-click en móvil
                    if(/Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {{
                        setTimeout(function() {{
                            document.querySelector('.download-btn').click();
                        }}, 1000);
                    }}
                </script>
            </body>
            </html>
            """
            
            # Crear archivo HTML temporal
            temp_dir = tempfile.gettempdir()
            html_file = os.path.join(temp_dir, f"download_{uuid.uuid4().hex[:8]}.html")
            
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Abrir en navegador
            import webbrowser
            webbrowser.open(f"file://{html_file}")
            
            # Mostrar confirmación
            page.snack_bar = ft.SnackBar(
                content=ft.Text("PDF preparado para descarga - Se abrió en tu navegador"),
                bgcolor=ft.Colors.GREEN
            )
            page.snack_bar.open = True
            page.update()
            
        except Exception as e:
            print(f"Error compartiendo PDF: {e}")
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error al preparar PDF: {str(e)}"),
                bgcolor=ft.Colors.RED
            )
            page.snack_bar.open = True
            page.update()
        def abrir_url_descarga(url, dlg):
            """Abre la URL de descarga en el navegador"""
            try:
                import webbrowser
                webbrowser.open(url)
                close_dlg(dlg)
                
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Se ha abierto la descarga en tu navegador"),
                    bgcolor=ft.Colors.GREEN
                )
                page.snack_bar.open = True
                page.update()
            except Exception as e:
                print(f"Error abriendo URL: {e}")
                close_dlg(dlg)
    def abrir_url_descarga(url, dlg):
        """Abre la URL de descarga en el navegador"""
        try:
            import webbrowser
            webbrowser.open(url)
            close_dlg(dlg)
            
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Se ha abierto la descarga en tu navegador"),
                bgcolor=ft.Colors.GREEN
            )
            page.snack_bar.open = True
            page.update()
        except Exception as e:
            print(f"Error abriendo URL: {e}")
            close_dlg(dlg)
    def download_file_mobile(file_path, filename):
        """
        Función mejorada para descargar archivos en móvil
        """
        try:
            # Leer el archivo
            with open(file_path, "rb") as f:
                content = f.read()
            
            # Detectar si estamos en móvil
            is_mobile = page.width < 800
            
            if is_mobile:
                # SOLUCIÓN MÓVIL: Crear enlace de descarga
                file_id = crear_enlace_descarga_pdf(content, filename)
                
                if file_id:
                    # Crear URL de descarga (ajustar según tu configuración)
                    # Esto asume que tu app corre en el puerto 8550
                    download_url = f"http://localhost:8550/download/{file_id}"
                    
                    # Mostrar diálogo con opciones de descarga
                    dlg_descarga = ft.AlertDialog(
                        title=ft.Text("Descargar PDF", size=18),
                        content=ft.Column([
                            ft.Text("Elige cómo descargar el archivo:", size=14),
                            ft.ElevatedButton(
                                "Descargar directamente",
                                icon=ft.Icons.DOWNLOAD,
                                on_click=lambda _: abrir_url_descarga(download_url, dlg_descarga),
                                width=250,
                                style=ft.ButtonStyle(
                                    color=ft.Colors.WHITE,
                                    bgcolor=ft.Colors.GREEN
                                )
                            ),
                            ft.ElevatedButton(
                                "Compartir PDF",
                                icon=ft.Icons.SHARE,
                                on_click=lambda _: compartir_pdf_base64(content, filename, dlg_descarga),
                                width=250,
                                style=ft.ButtonStyle(
                                    color=ft.Colors.WHITE,
                                    bgcolor=ft.Colors.BLUE
                                )
                            ),
                            ft.Text("Nota: Si la descarga no funciona, usa 'Compartir PDF'", 
                                size=11, italic=True, color=ft.Colors.GREY)
                        ], spacing=15),
                        actions=[
                            ft.TextButton("Cancelar", on_click=lambda _: close_dlg(dlg_descarga))
                        ],
                        modal=True
                    )
                    
                    page.dialog = dlg_descarga
                    dlg_descarga.open = True
                    page.update()
                else:
                    # Fallback: mostrar error
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("Error al preparar descarga"),
                        bgcolor=ft.Colors.RED
                    )
                    page.snack_bar.open = True
                    page.update()
            else:
                # SOLUCIÓN ESCRITORIO: Usar el método original
                try:
                    save_file_dialog = ft.FilePicker()
                    if save_file_dialog not in page.overlay:
                        page.overlay.append(save_file_dialog)
                        page.update()
                    
                    save_file_dialog.save_file(
                        dialog_title="Guardar archivo",
                        file_name=filename,
                        allowed_extensions=["pdf"],
                        data=content
                    )
                except Exception as e:
                    print(f"Error en descarga escritorio: {e}")
                    # Fallback para escritorio
                    compartir_pdf_base64(content, filename)
                    
        except Exception as e:
            print(f"Error general en descarga: {e}")
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error al descargar: {str(e)}"),
                bgcolor=ft.Colors.RED
            )
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
        """PDF de pedidos con calendario personalizado"""
        def on_fecha_seleccionada(fecha_seleccionada):
            progress_dlg = ft.AlertDialog(
                title=ft.Text("Generando reporte"),
                content=ft.Column([
                    ft.Text(f"Preparando reporte para {fecha_seleccionada.strftime('%d/%m/%Y')}..."),
                    ft.ProgressBar(width=300)
                ], tight=True, spacing=20),
                modal=True
            )
            
            page.dialog = progress_dlg
            progress_dlg.open = True
            page.update()
            
            try:
                pdf_content, mensaje = app.generar_pdf_pedidos_hoy(fecha_seleccionada)
                progress_dlg.open = False
                page.update()
                
                if pdf_content:
                    os.makedirs("temp", exist_ok=True)
                    temp_file = os.path.join("temp", f"pedidos_{fecha_seleccionada.strftime('%Y%m%d')}.pdf")
                    with open(temp_file, "wb") as f:
                        f.write(pdf_content)
                    
                    download_file_mobile(temp_file, f"pedidos_{fecha_seleccionada.strftime('%d_%m_%Y')}.pdf")
                else:
                    page.snack_bar = ft.SnackBar(content=ft.Text(mensaje))
                    page.snack_bar.open = True
                    page.update()
                    
            except Exception as e:
                progress_dlg.open = False
                page.update()
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Error: {e}"))
                page.snack_bar.open = True
                page.update()
        
        mostrar_calendario_personalizado(on_fecha_seleccionada)
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
            
            # Botón de calendario para fecha
            fecha_btn = ft.IconButton(
                icon=ft.Icons.CALENDAR_TODAY,
                tooltip="Seleccionar fecha",
                on_click=lambda _: mostrar_calendario_filtro(fecha_filtro)
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
                    fecha_btn,
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
    
    # Función para mostrar calendario para el filtro de fecha
    def mostrar_calendario_filtro(campo_fecha):
        """Muestra el calendario personalizado para filtrar pedidos"""
        def on_fecha_seleccionada(fecha_seleccionada):
            fecha_str = fecha_seleccionada.strftime("%Y-%m-%d")
            campo_fecha.value = fecha_str
            campo_fecha.update()
            
            # Cargar pedidos de la fecha seleccionada
            cargar_pedidos(fecha_str)
        
        mostrar_calendario_personalizado(on_fecha_seleccionada)
    
    def mostrar_calendario_personalizado(callback_function, fecha_actual=None):
        """
        Muestra un calendario personalizado que funciona en móvil
        callback_function: función que se llama cuando se selecciona una fecha
        fecha_actual: fecha inicial a mostrar
        """
        if fecha_actual is None:
            fecha_actual = datetime.datetime.now()
        
        # Variables para el calendario
        año_actual = fecha_actual.year
        mes_actual = fecha_actual.month
        
        # Crear controles para año y mes
        año_dropdown = ft.Dropdown(
            label="Año",
            width=100,
            options=[
                ft.dropdown.Option(str(año)) 
                for año in range(2023, 2031)
            ],
            value=str(año_actual)
        )
        
        meses = [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]
        
        mes_dropdown = ft.Dropdown(
            label="Mes",
            width=150,
            options=[
                ft.dropdown.Option(str(i+1), meses[i]) 
                for i in range(12)
            ],
            value=str(mes_actual)
        )
        
        # Contenedor para los días
        dias_container = ft.Container(
            content=ft.Column([]),
            height=200,
            width=300
        )
        
        def generar_dias():
            """Genera los botones de días para el mes seleccionado"""
            try:
                año = int(año_dropdown.value)
                mes = int(mes_dropdown.value)
                
                # Limpiar días anteriores
                dias_container.content.controls.clear()
                
                # Obtener primer día del mes y número de días
                primer_dia = datetime.datetime(año, mes, 1)
                if mes == 12:
                    ultimo_dia = datetime.datetime(año + 1, 1, 1) - datetime.timedelta(days=1)
                else:
                    ultimo_dia = datetime.datetime(año, mes + 1, 1) - datetime.timedelta(days=1)
                
                días_del_mes = ultimo_dia.day
                día_semana_inicio = primer_dia.weekday()  # 0 = lunes, 6 = domingo
                
                # Crear encabezados de días de la semana
                encabezados = ft.Row([
                    ft.Container(ft.Text("L", size=12, weight=ft.FontWeight.BOLD), width=35, alignment=ft.alignment.center),
                    ft.Container(ft.Text("M", size=12, weight=ft.FontWeight.BOLD), width=35, alignment=ft.alignment.center),
                    ft.Container(ft.Text("M", size=12, weight=ft.FontWeight.BOLD), width=35, alignment=ft.alignment.center),
                    ft.Container(ft.Text("J", size=12, weight=ft.FontWeight.BOLD), width=35, alignment=ft.alignment.center),
                    ft.Container(ft.Text("V", size=12, weight=ft.FontWeight.BOLD), width=35, alignment=ft.alignment.center),
                    ft.Container(ft.Text("S", size=12, weight=ft.FontWeight.BOLD), width=35, alignment=ft.alignment.center),
                    ft.Container(ft.Text("D", size=12, weight=ft.FontWeight.BOLD), width=35, alignment=ft.alignment.center),
                ], alignment=ft.MainAxisAlignment.CENTER)
                
                dias_container.content.controls.append(encabezados)
                
                # Generar semanas
                día_actual = 1
                while día_actual <= días_del_mes:
                    semana = ft.Row([], alignment=ft.MainAxisAlignment.CENTER)
                    
                    # Llenar la semana
                    for día_semana in range(7):
                        if (día_actual == 1 and día_semana < día_semana_inicio) or día_actual > días_del_mes:
                            # Día vacío
                            semana.controls.append(
                                ft.Container(width=35, height=35)
                            )
                        else:
                            # Día con número
                            día_btn = ft.Container(
                                content=ft.Text(str(día_actual), size=14, text_align=ft.TextAlign.CENTER),
                                width=35,
                                height=35,
                                border=ft.border.all(1, ft.Colors.GREY_400),
                                border_radius=5,
                                alignment=ft.alignment.center,
                                bgcolor=ft.Colors.BLUE_100 if día_actual == fecha_actual.day and mes == fecha_actual.month and año == fecha_actual.year else None,
                                on_click=lambda e, d=día_actual: seleccionar_dia(d)
                            )
                            día_btn.data = día_actual  # Guardar el día en los datos del contenedor
                            semana.controls.append(día_btn)
                            día_actual += 1
                    
                    dias_container.content.controls.append(semana)
                
                dias_container.update()
                
            except Exception as e:
                print(f"Error generando días: {e}")
        
        def seleccionar_dia(dia):
            """Maneja la selección de un día"""
            try:
                año = int(año_dropdown.value)
                mes = int(mes_dropdown.value)
                fecha_seleccionada = datetime.datetime(año, mes, dia)
                
                # Llamar al callback con la fecha seleccionada
                callback_function(fecha_seleccionada)
                
                # Cerrar el diálogo
                close_dlg(dlg_calendario)
                
            except Exception as e:
                print(f"Error seleccionando día: {e}")
        
        def actualizar_calendario(e):
            """Actualiza el calendario cuando cambia el año o mes"""
            generar_dias()
        
        # Asignar eventos a los dropdowns
        año_dropdown.on_change = actualizar_calendario
        mes_dropdown.on_change = actualizar_calendario
        
        # Crear el diálogo
        dlg_calendario = ft.AlertDialog(
            title=ft.Text("Seleccionar Fecha", size=18),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        año_dropdown,
                        mes_dropdown
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Divider(),
                    dias_container
                ]),
                width=320,
                height=280
            ),
            actions=[
                ft.TextButton("Hoy", on_click=lambda _: callback_function(datetime.datetime.now()) or close_dlg(dlg_calendario)),
                ft.TextButton("Cancelar", on_click=lambda _: close_dlg(dlg_calendario))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=True
        )
        
        # Generar días iniciales
        generar_dias()
        
        # Mostrar diálogo
        page.dialog = dlg_calendario
        dlg_calendario.open = True
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
        
        query_base = "SELECT id, cliente, zona, fecha, total FROM pedidos "
        
        if fecha_str:
            query_base += " WHERE DATE(fecha) = %s"
            cursor.execute(query_base + " ORDER BY fecha DESC", (fecha_str,))
        else:
            cursor.execute(query_base + " ORDER BY fecha DESC")
        
        pedidos = cursor.fetchall()
        cursor.close()
        conn.close()
        
        print(f"Se encontraron {len(pedidos)} pedidos")
        
        if not pedidos:
            lista_pedidos.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.INFO_OUTLINE, color=ft.Colors.BLUE_200, size=32),
                            ft.Text("No hay pedidos para mostrar", size=18)
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Text("Prueba con otra fecha o crea un nuevo pedido", 
                            size=14, color=ft.Colors.GREY_400, text_align=ft.TextAlign.CENTER)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    padding=30,
                    border=ft.border.all(2, ft.Colors.BLUE_200),
                    border_radius=15,
                    margin=15
                )
            )
        else:
            # Agrupar pedidos por fecha
            pedidos_por_fecha = {}
            for pedido in pedidos:
                fecha_str = pedido['fecha'].strftime('%d/%m/%Y')
                if fecha_str not in pedidos_por_fecha:
                    pedidos_por_fecha[fecha_str] = []
                pedidos_por_fecha[fecha_str].append(pedido)
            
            # Mostrar pedidos agrupados por fecha
            for fecha in pedidos_por_fecha.keys():
                lista = pedidos_por_fecha[fecha]
                
                # Cabecera de fecha más visible
                lista_pedidos.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.CALENDAR_TODAY, color=ft.Colors.WHITE, size=20),
                            ft.Text(fecha, weight=ft.FontWeight.BOLD, size=18, color=ft.Colors.WHITE)
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        padding=15,
                        bgcolor=ft.Colors.PURPLE,
                        border_radius=10,
                        margin=ft.margin.only(top=15, bottom=10, left=5, right=5)
                    )
                )
                
                # ✅ PEDIDOS CON ÁREA TÁCTIL MEJORADA
                for pedido in lista:
                    pedido_id = pedido['id']
                    
                    lista_pedidos.controls.append(
                        ft.Container(
                            content=ft.Column([
                                # Información principal más grande
                                ft.Row([
                                    ft.Icon(ft.Icons.RECEIPT, color=ft.Colors.PURPLE, size=24),
                                    ft.Column([
                                        ft.Text(f"Pedido #{pedido_id}", 
                                            weight=ft.FontWeight.BOLD, size=18),
                                        ft.Text(pedido['fecha'].strftime('%H:%M'), 
                                            color=ft.Colors.GREY_600, size=14)
                                    ], spacing=2),
                                    ft.Container(expand=True),
                                    ft.Text(f"${float(pedido['total']):.2f}", 
                                        size=18, weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.GREEN)
                                ], alignment=ft.MainAxisAlignment.START),
                                
                                ft.Container(height=8),  # Espacio
                                
                                # Información del cliente más legible
                                ft.Row([
                                    ft.Icon(ft.Icons.PERSON, color=ft.Colors.BLUE, size=18),
                                    ft.Text(f"{pedido['cliente']}", size=16),
                                    ft.Container(expand=True),
                                    ft.Icon(ft.Icons.LOCATION_ON, color=ft.Colors.RED, size=18),
                                    ft.Text(f"{pedido['zona']}", size=16)
                                ]),
                                
                                ft.Container(height=10),  # Espacio
                                
                                # ✅ BOTONES MÁS GRANDES Y TÁCTILES
                                ft.Row([
                                    ft.Container(
                                        content=ft.ElevatedButton(
                                            "Ver Detalles",
                                            icon=ft.Icons.VISIBILITY,
                                            on_click=lambda e, pid=pedido_id: ver_detalles_pedido(pid),
                                            style=ft.ButtonStyle(
                                                color=ft.Colors.WHITE,
                                                bgcolor=ft.Colors.PURPLE_400,
                                                shape=ft.RoundedRectangleBorder(radius=8)
                                            )
                                        ),
                                        # ✅ Área táctil más grande
                                        padding=ft.padding.all(5),
                                        expand=True
                                    ),
                                    ft.Container(width=10),  # Espacio entre botones
                                    ft.Container(
                                        content=ft.OutlinedButton(
                                            "Descargar",
                                            icon=ft.Icons.DOWNLOAD,
                                            on_click=lambda e, pid=pedido_id: descargar_factura_pedido(pid),
                                            style=ft.ButtonStyle(
                                                shape=ft.RoundedRectangleBorder(radius=8)
                                            )
                                        ),
                                        # ✅ Área táctil más grande
                                        padding=ft.padding.all(5),
                                        expand=True
                                    )
                                ], spacing=0)
                            ]),
                            # ✅ CONTENEDOR CON ÁREA TÁCTIL GRANDE
                            border=ft.border.all(2, ft.Colors.GREY_300),
                            border_radius=12,
                            padding=20,  # ✅ Padding generoso
                            margin=ft.margin.symmetric(vertical=8, horizontal=5),
                            bgcolor=ft.Colors.WHITE,
                            # ✅ Sombra para mejor visibilidad
                            shadow=ft.BoxShadow(
                                spread_radius=1,
                                blur_radius=3,
                                color=ft.Colors.BLACK26,
                                offset=ft.Offset(0, 2)
                            ),
                            # ✅ HACER TODO EL CONTENEDOR CLICKEABLE (OPCIONAL)
                            # on_click=lambda e, pid=pedido_id: ver_detalles_pedido(pid)
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
        
        # Inicialmente el botón para borrar productos está oculto
        borrar_productos_btn.visible = False
        
        # Si estamos en móvil, creamos un layout específico
        if is_mobile:
            # Crear panel flotante solo para móviles y añadirlo como un componente fijo
            panel_flotante = crear_panel_flotante()
            # Guardar referencia al panel flotante
            page.panel_flotante = panel_flotante
            
            # Crear botones de menú
            menu_btn = ft.Container(
                content=ft.IconButton(
                    icon=ft.Icons.MENU,
                    icon_size=32,  # ✅ Icono más grande
                    icon_color=ft.Colors.WHITE,
                    tooltip="Menú Principal",
                    on_click=lambda e: toggle_menu_drawer()
                ),
                # ✅ Área táctil más grande
                width=60,
                height=50,
                bgcolor=ft.Colors.PURPLE,
                border_radius=10,
                alignment=ft.alignment.center,
                # ✅ Padding generoso para fácil acceso
                margin=ft.margin.only(left=15, right=10, top=5, bottom=5)
            )
            
            # Crear drawer para menú en móvil
            drawer = ft.NavigationDrawer(
                bgcolor=ft.Colors.BLUE_GREY_900,
                selected_index=0,
                controls=[
                    # Cabecera más atractiva
                    ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.STORE, size=40, color=ft.Colors.WHITE),
                            ft.Text("DistriSulpi", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ft.Text("Sistema de Gestión", size=14, italic=True, color=ft.Colors.WHITE70)
                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=5),
                        padding=20,
                        bgcolor=ft.Colors.PURPLE,
                        border_radius=ft.border_radius.only(bottom_left=15, bottom_right=15),
                        margin=ft.margin.only(bottom=15)
                    ),
                    
                    # Opciones del menú con mejor espaciado
                    ft.NavigationDrawerDestination(icon=ft.Icons.SHOPPING_CART, label="Nuevo Pedido", selected_icon=ft.Icons.SHOPPING_CART_OUTLINED),
                    ft.NavigationDrawerDestination(icon=ft.Icons.LIST_ALT, label="Ver Pedidos", selected_icon=ft.Icons.LIST_ALT_OUTLINED),
                    ft.NavigationDrawerDestination(icon=ft.Icons.RECEIPT_LONG, label="Pedidos HOY", selected_icon=ft.Icons.RECEIPT_LONG_OUTLINED),
                    ft.NavigationDrawerDestination(icon=ft.Icons.SHARE, label="Compartir Pedidos", selected_icon=ft.Icons.SHARE_OUTLINED),
                    ft.Divider(color=ft.Colors.WHITE30),
                    ft.NavigationDrawerDestination(icon=ft.Icons.UPLOAD_FILE, label="Cargar Productos", selected_icon=ft.Icons.UPLOAD_FILE_OUTLINED),
                    ft.NavigationDrawerDestination(icon=ft.Icons.BAR_CHART, label="Estadísticas", selected_icon=ft.Icons.BAR_CHART_OUTLINED),
                    ft.NavigationDrawerDestination(icon=ft.Icons.TRENDING_UP, label="Predicción", selected_icon=ft.Icons.TRENDING_UP_OUTLINED),
                ],
                on_change=lambda e: handle_drawer_change(e)
            )
            
            # Función para mostrar/ocultar el drawer
            def toggle_menu_drawer():
                page.drawer.open = not page.drawer.open
                page.update()
            
            # Función para manejar la selección en el drawer
            def handle_drawer_change(e):
                    selected_index = e.control.selected_index
                    page.drawer.open = False
                    
                    # Ocultar todos los contenedores especiales
                    estadisticas_container.visible = False
                    prediccion_container.visible = False
                    pedidos_container.visible = False
                    
                    if selected_index == 0:  # Nuevo Pedido
                        pass
                    elif selected_index == 1:  # Ver Pedidos
                        toggle_ver_pedidos()
                    elif selected_index == 2:  # Pedidos HOY
                        generar_pdf_pedidos_hoy()
                    elif selected_index == 3:  # Compartir Pedidos
                        seleccionar_pedidos_para_compartir()
                    elif selected_index == 5:  # Cargar Productos
                        csv_upload.pick_files(allow_multiple=False, allowed_extensions=["csv"])
                    elif selected_index == 6:  # Estadísticas
                        toggle_estadisticas()
                    elif selected_index == 7:  # Predicción
                        toggle_prediccion()
                    
                    page.update()
        
            page.drawer = drawer
            
            # VERSIÓN MÓVIL
            contenido_principal = ft.Column([
            # ✅ ESPACIO SUPERIOR - Para comodidad
            ft.Container(height=10),  # Espacio inicial
            
            # ✅ PANEL FLOTANTE en la parte superior (si hay productos)
            panel_flotante if panel_flotante else ft.Container(height=0),
            
            # ✅ BARRA SUPERIOR con menú hamburguesa más accesible
            ft.Container(
                content=ft.Row([
                    menu_btn,  # Botón más grande y accesible
                        ft.Container(
                        content=ft.Text(
                            "DistriSulpi", 
                            size=20, 
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER
                        ),
                        expand=True  # ✅ Usar expand=True en lugar de ft.Expanded
                    ),
                    # Espacio para balance visual
                    ft.Container(width=60)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                margin=ft.margin.only(bottom=15),  # Más espacio debajo
                padding=ft.padding.symmetric(horizontal=5)
            ),
            
            # ✅ CONTENEDOR FECHA - Mejor espaciado
            ft.Container(
                content=fecha_pedido_container,
                margin=ft.margin.only(bottom=10)
            ),
            
            # ✅ PEDIDO ACTUAL - Más compacto pero visible
            ft.Container(
                content=ft.Column([
                    # Cabecera más pequeña pero visible
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.SHOPPING_CART, color=ft.Colors.WHITE, size=18),
                            ft.Text("Pedido Actual", 
                                size=16, 
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE)
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        bgcolor=ft.Colors.PURPLE,
                        padding=ft.padding.symmetric(vertical=8, horizontal=10),
                        border_radius=ft.border_radius.only(top_left=8, top_right=8)
                    ),
                    # Tabla de pedidos compacta
                    ft.Container(
                        content=ft.Column(
                            [pedido_actual_table],
                            scroll=ft.ScrollMode.AUTO,
                            spacing=0
                        ),
                        height=120,  # Más compacto
                        padding=5,
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PURPLE)
                    ),
                    # Botones de control
                    ft.Container(
                        content=ft.Row([
                            borrar_productos_btn,
                            finalizar_pedido_btn
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        padding=ft.padding.symmetric(horizontal=10, vertical=5)
                    ),
                ]),
                border=ft.border.all(2, ft.Colors.PURPLE),
                border_radius=8,
                margin=ft.margin.only(bottom=15),
                width=page.width - 20
            ),
            
            # ✅ DATOS DEL CLIENTE - Más compacto
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.PERSON, color=ft.Colors.BLUE, size=18),
                        ft.Text("Cliente y Zona", size=14, weight=ft.FontWeight.BOLD)
                    ], spacing=5),
                    ft.Container(height=5),  # Pequeño espacio
                    ft.Row([
                        ft.Container(cliente_field, expand=True),
                        ft.Container(zona_dropdown, width=100)
                    ], spacing=10),
                    sugerencias_clientes_container,
                ]),
                padding=12,
                border=ft.border.all(1, ft.Colors.BLUE_200),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.BLUE),
                margin=ft.margin.only(bottom=15)
            ),
            
            # ✅ BÚSQUEDA DE PRODUCTOS - Expandido y cómodo
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.SEARCH, color=ft.Colors.GREEN, size=20),
                        ft.Text("Buscar Productos", size=16, weight=ft.FontWeight.BOLD)
                    ], spacing=5),
                    ft.Container(height=8),
                    producto_search,
                    ft.Container(height=5),
                    # ✅ LISTA DE PRODUCTOS - Más grande y cómoda
                    ft.Container(
                        content=productos_list, 
                        margin=ft.margin.symmetric(vertical=5),
                        expand=True  # Se expande para usar todo el espacio disponible
                    ),
                    ft.Row([
                        ft.Text("Cantidad:", size=14),
                        cantidad_field
                    ], alignment=ft.MainAxisAlignment.START, spacing=10)
                ]),
                padding=12,
                border=ft.border.all(1, ft.Colors.GREEN_200),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.GREEN),
                margin=ft.margin.only(bottom=15),
                expand=True  # ✅ IMPORTANTE: Se expande para usar espacio disponible
            ),
            
            # Contenedores para funciones especiales
            estadisticas_container,
            prediccion_container,
            pedidos_container,
            
            # ✅ ESPACIO INFERIOR - Para comodidad
            ft.Container(height=20),
        ], 
        expand=True,  # ✅ IMPORTANTE: Permite que la columna use todo el espacio
        spacing=0)  # Sin espaciado extra entre elementos principales
        
        # Añadir el contenido principal a la página
            page.add(contenido_principal)
        
        else:
            # VERSIÓN ESCRITORIO - Layout original con mejoras
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
                        
                        # Barra de herramientas
                        ft.Container(
                            content=ft.Row([
                                csv_upload_btn,
                                estadisticas_btn,
                                prediccion_btn,
                                pedidos_hoy_btn,
                                ver_pedidos_btn,
                                compartir_pedidos_btn
                            ], wrap=True, spacing=10, alignment=ft.MainAxisAlignment.CENTER),
                            padding=10,
                            border=ft.border.all(1, ft.Colors.GREY_400),
                            border_radius=10,
                            margin=ft.margin.only(bottom=20),
                            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.GREY)
                        ),
                        
                        # Contenedor para la fecha del pedido (inicialmente oculto)
                        fecha_pedido_container,
                        
                        # Estructura con 2 columnas para escritorio
                        ft.Row([
                            # Columna izquierda
                            ft.Column([
                                # Sección de búsqueda de productos
                                ft.Container(
                                    content=ft.Column([
                                        ft.Text("Selección de Productos", 
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
                                
                                # Sección de datos del cliente
                                ft.Container(
                                    content=ft.Column([
                                        ft.Text("Datos del Cliente", size=18, weight=ft.FontWeight.BOLD),
                                        cliente_field,
                                        sugerencias_clientes_container,
                                        zona_dropdown
                                    ]),
                                    padding=10,
                                    border=ft.border.all(1, ft.Colors.BLACK26),
                                    border_radius=5,
                                    margin=ft.margin.only(bottom=20)
                                ),
                                
                            ], 
                            width=page.width * 0.45),
                            
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
                                    # Botones de acciones
                                    ft.Row([
                                        borrar_productos_btn,
                                        finalizar_pedido_btn
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=10)
                                ]),
                                padding=ft.padding.only(bottom=10),
                                border=ft.border.all(2, ft.Colors.PURPLE),
                                border_radius=5,
                                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PURPLE),
                                width=page.width * 0.53,
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
ft.app(target=main, port=8550, view=ft.AppView.FLET_APP)