import csv
import mysql.connector

def importar_productos_csv(ruta_csv):
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='distriñulpi'
    )
    cursor = conn.cursor()

    with open(ruta_csv, newline='', encoding='utf-8') as csvfile:
        lector = csv.DictReader(csvfile)
        for fila in lector:
            nombre = fila['Nombre del producto'].strip()
            costo = float(fila['Precio de Compra'].replace(',', '.'))  # Usamos 'precio' como costo
            precio_venta = float(fila['Precio de Venta'].replace(',', '.'))  # Usamos 'venta' como precio de venta

            cursor.execute('''
                INSERT INTO productos (nombre, costo, precio_venta)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    costo = VALUES(costo),
                    precio_venta = VALUES(precio_venta)
            ''', (nombre, costo, precio_venta))

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Productos importados con éxito.")

# Ejecutar la función con el archivo que subiste
importar_productos_csv('31-03-2025 lista distrisulpi (1).csv')
