from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import mysql.connector
import json
from datetime import datetime, date
import tempfile
from fpdf import FPDF
import os

app = Flask(__name__)
CORS(app)  # Permitir solicitudes de diferentes dominios

# Configuración de la base de datos MySQL
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'distriñulpi'
}

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

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)