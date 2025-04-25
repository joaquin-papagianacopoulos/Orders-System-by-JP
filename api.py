from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import json
from datetime import datetime, date, timedelta
import tempfile
from fpdf import FPDF
import os
import requests

app = Flask(__name__)
CORS(app)  # Permitir solicitudes de diferentes dominios

# Configuración de la base de datos MySQL
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'distriapp'
}
# Prueba de conexión
response = requests.get("http://localhost:5000/api/ping")
print(f"Ping: {response.status_code}, {response.json()}")

# Prueba de búsqueda de productos
response = requests.get("http://localhost:5000/api/productos?buscar=a")
print(f"Búsqueda: {response.status_code}, {response.json()}")
def conectar_db():
    try:
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="distriapp"  # Ajusta el nombre de la base de datos si es diferente
        )
        return conexion
    except Error as e:
        print(f"Error al conectar a MySQL: {e}")
        return None

# Función para conectar a la base de datos
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# Función auxiliar para convertir fechas a string en JSON
def json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type not serializable")

# --- Rutas de la API ---

@app.route("/api/ping")
def ping():
    return {"success": True}

@app.route('/api/clientes', methods=['GET'])
def buscar_clientes():
    try:
        busqueda = request.args.get('buscar', '')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre FROM clientes WHERE nombre LIKE %s LIMIT 5", (f"%{busqueda}%",))
        clientes = [cliente[0] for cliente in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify(clientes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/productos', methods=['GET'])
def buscar_productos():
    try:
        busqueda = request.args.get('buscar', '')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre FROM productos WHERE nombre LIKE %s LIMIT 5", (f"%{busqueda}%",))
        productos = [producto[0] for producto in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify(productos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/productos/costo/<nombre_producto>', methods=['GET'])
def obtener_costo_producto(nombre_producto):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT costo FROM productos WHERE nombre = %s", (nombre_producto,))
        resultado = cursor.fetchone()
        cursor.close()
        conn.close()
        if resultado:
            return jsonify({'costo': resultado[0]})
        else:
            return jsonify({'costo': 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# Endpoint para pedidos de hoy
# Endpoint para pedidos de hoy
@app.route('/api/pedidos/hoy', methods=['GET'])
def pedidos_hoy():
    try:
        conexion = conectar_db()
        if conexion is None:
            return jsonify({"error": "Error de conexión a la base de datos"}), 500
            
        cursor = conexion.cursor(dictionary=True)
        fecha_hoy = datetime.now().strftime('%Y-%m-%d')
        
        # Consulta adaptada a tu estructura real de tablas
        query = """
        SELECT 
            id,
            cliente,
            producto,
            cantidad,
            costo,
            zona,
            fecha
        FROM 
            pedidos
        WHERE 
            fecha = %s
        ORDER BY 
            id DESC
        """
        
        cursor.execute(query, (fecha_hoy,))
        pedidos = cursor.fetchall()
        
        # Formatear fechas para JSON
        for pedido in pedidos:
            if isinstance(pedido['fecha'], datetime):
                pedido['fecha'] = pedido['fecha'].strftime('%Y-%m-%d')
        
        cursor.close()
        conexion.close()
        
        return jsonify(pedidos)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint para estadísticas
@app.route('/api/estadisticas', methods=['GET'])
def estadisticas():
    try:
        conexion = conectar_db()
        if conexion is None:
            return jsonify({"error": "Error de conexión a la base de datos"}), 500
            
        cursor = conexion.cursor(dictionary=True)
        fecha_hoy = datetime.now().strftime('%Y-%m-%d')
        semana_anterior = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Objeto para almacenar todas las estadísticas
        stats = {}
        
        # 1. Total de ventas de hoy
        query_ventas_hoy = """
        SELECT 
            COALESCE(SUM(costo), 0) as total_ventas_hoy,
            COUNT(*) as total_pedidos_hoy
        FROM 
            pedidos
        WHERE 
            fecha = %s
        """
        cursor.execute(query_ventas_hoy, (fecha_hoy,))
        resultado = cursor.fetchone()
        stats['ventas_hoy'] = float(resultado['total_ventas_hoy']) if resultado['total_ventas_hoy'] is not None else 0
        stats['pedidos_hoy'] = resultado['total_pedidos_hoy']
        
        # 2. Producto más vendido hoy
        query_producto_top = """
        SELECT 
            producto,
            SUM(cantidad) as cantidad_total
        FROM 
            pedidos
        WHERE 
            fecha = %s
        GROUP BY 
            producto
        ORDER BY 
            cantidad_total DESC
        LIMIT 1
        """
        cursor.execute(query_producto_top, (fecha_hoy,))
        producto_top = cursor.fetchone()
        stats['producto_top'] = {
            'nombre': producto_top['producto'] if producto_top else "Sin ventas hoy",
            'cantidad': producto_top['cantidad_total'] if producto_top else 0
        }
        
        # 3. Ventas por día en la última semana
        query_ventas_semana = """
        SELECT 
            fecha,
            COUNT(*) as num_pedidos,
            SUM(costo) as total_ventas
        FROM 
            pedidos
        WHERE 
            fecha BETWEEN %s AND %s
        GROUP BY 
            fecha
        ORDER BY 
            fecha
        """
        cursor.execute(query_ventas_semana, (semana_anterior, fecha_hoy))
        ventas_semana = cursor.fetchall()
        
        # Formatear fechas para JSON
        stats['ventas_semana'] = []
        for dia in ventas_semana:
            stats['ventas_semana'].append({
                'fecha': dia['fecha'].strftime('%Y-%m-%d') if isinstance(dia['fecha'], datetime) else str(dia['fecha']),
                'pedidos': dia['num_pedidos'],
                'total': float(dia['total_ventas']) if dia['total_ventas'] is not None else 0
            })
        
        # 4. Zonas con más pedidos hoy
        query_zonas = """
        SELECT 
            zona,
            COUNT(*) as total_pedidos,
            SUM(costo) as total_ventas
        FROM 
            pedidos
        WHERE 
            fecha = %s
        GROUP BY 
            zona
        ORDER BY 
            total_pedidos DESC
        """
        cursor.execute(query_zonas, (fecha_hoy,))
        stats['zonas'] = []
        for zona in cursor.fetchall():
            stats['zonas'].append({
                'nombre': zona['zona'],
                'pedidos': zona['total_pedidos'],
                'total': float(zona['total_ventas']) if zona['total_ventas'] is not None else 0
            })
        
        cursor.close()
        conexion.close()
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/api/productos/stock/<nombre_producto>', methods=['GET'])
def obtener_stock_producto(nombre_producto):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT stock FROM productos WHERE nombre = %s", (nombre_producto,))
        resultado = cursor.fetchone()
        cursor.close()
        conn.close()
        if resultado:
            return jsonify({'stock': resultado[0]})
        else:
            return jsonify({'stock': 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pedidos', methods=['POST'])
def insertar_pedido():
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar que vengan todos los campos necesarios
        if not all([data.get('cliente'), data.get('producto'), data.get('cantidad'), data.get('costo'), data.get('zona')]):
            return jsonify({'success': False, 'error': 'Faltan campos requeridos'}), 400
        
        # Insertar cliente si no existe
        cursor.execute("INSERT IGNORE INTO clientes (nombre) VALUES (%s)", (data['cliente'],))
        
        # Insertar pedido
        cursor.execute("""
            INSERT INTO pedidos (cliente, producto, cantidad, costo, zona) 
            VALUES (%s, %s, %s, %s, %s)
        """, (data['cliente'], data['producto'], data['cantidad'], data['costo'], data['zona']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Pedido registrado correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Ruta para subir CSV
@app.route('/api/productos/csv', methods=['POST'])
def procesar_csv():
    try:
        data = request.json
        datos_csv = data.get('datos_csv', '')
        
        if not datos_csv:
            return jsonify({'success': False, 'error': 'No se proporcionaron datos CSV'}), 400
        
        # Procesar datos CSV
        filas = datos_csv.strip().split('\n')
        encabezados = filas[0].split(',')
        required = {'nombre', 'costo', 'precio_venta', 'stock'}
        
        # Comprobar que estén todos los campos requeridos
        if not required.issubset(set(encabezados)):
            missing = required - set(encabezados)
            return jsonify({'success': False, 'error': f"Faltan columnas: {', '.join(missing)}"}), 400
            
        # Crear un diccionario de índices para cada campo
        indices = {campo: indice for indice, campo in enumerate(encabezados)}
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Procesar cada fila (excepto la de encabezados)
        for i, fila in enumerate(filas[1:], 2):
            if not fila.strip():  # Saltar filas vacías
                continue
                
            valores = fila.split(',')
            if len(valores) != len(encabezados):
                return jsonify({'success': False, 'error': f"Fila {i}: número incorrecto de valores"}), 400
                
            # Extraer valores
            nombre = valores[indices['nombre']].strip()
            costo = float(valores[indices['costo']])
            precio_venta = float(valores[indices['precio_venta']])
            stock = int(valores[indices['stock']])
            
            # Verificar si ya existe el producto
            cursor.execute("SELECT id FROM productos WHERE nombre = %s", (nombre,))
            producto_existe = cursor.fetchone()
            
            if producto_existe:
                # Actualizar producto existente
                cursor.execute('''
                    UPDATE productos SET 
                        costo = %s,
                        precio_venta = %s,
                        stock = %s
                    WHERE nombre = %s
                ''', (costo, precio_venta, stock, nombre))
            else:
                # Insertar nuevo producto
                cursor.execute('''
                    INSERT INTO productos (nombre, costo, precio_venta, stock)
                    VALUES (%s, %s, %s, %s)
                ''', (nombre, costo, precio_venta, stock))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Datos CSV procesados correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
# Endpoint para productos del día
@app.route('/api/productos/dia', methods=['GET'])
def productos_dia():
    try:
        conexion = conectar_db()
        if conexion is None:
            return jsonify({"error": "Error de conexión a la base de datos"}), 500
            
        cursor = conexion.cursor(dictionary=True)
        fecha_hoy = datetime.now().strftime('%Y-%m-%d')
        
        # Consulta adaptada a tu estructura real de tablas
        query = """
        SELECT 
            p.nombre,
            SUM(ped.cantidad) as cantidad_vendida,
            SUM(ped.costo) as total_vendido
        FROM 
            productos p
        INNER JOIN 
            pedidos ped ON p.nombre = ped.producto
        WHERE 
            ped.fecha = %s
        GROUP BY 
            p.nombre
        ORDER BY 
            cantidad_vendida DESC
        """
        
        cursor.execute(query, (fecha_hoy,))
        productos = cursor.fetchall()
        
        cursor.close()
        conexion.close()
        
        return jsonify(productos)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)