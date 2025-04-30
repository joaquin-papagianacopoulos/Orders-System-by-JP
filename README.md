# DistriApp - Sistema de Gestión de Distribución

DistriApp es una aplicación completa para la gestión de distribución de productos, desarrollada con Python, Flet (interfaz gráfica) y MySQL (base de datos).

![DistriApp Screenshot](https://via.placeholder.com/800x450?text=DistriApp+Sistema+de+Gestión+de+Distribución)

## Características principales

- ✅ **Registro de pedidos**: Agregue productos a pedidos con cliente, zona, cantidad y precio
- 📦 **Control de inventario**: Gestión automática de stock al registrar y modificar pedidos
- 📄 **Reportes en PDF**: Genere informes para clientes, productos diarios y estadísticas
- 📊 **Estadísticas de ventas**: Visualice tendencias y totales de ventas 
- 📤 **Importación desde CSV**: Actualice su inventario de productos masivamente
- 🧾 **Gestión de clientes**: Base de datos de clientes con autocompletado

## Requisitos del sistema

- **Python**: 3.8 o superior
- **MySQL**: 5.7 o superior
- **Espacio en disco**: ~100MB para la aplicación y sus dependencias
- **Memoria**: Mínimo 2GB RAM recomendado

## Instalación

### 1. Clonar o descargar el repositorio

```bash
git clone https://github.com/usuariogit/distriapp.git
cd distriapp
```

### 2. Crear y activar un entorno virtual

```bash
# En Windows
python -m venv venv
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
venv\Scripts\activate

# En macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar las dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar la base de datos MySQL

1. Cree una base de datos MySQL:

```sql
CREATE DATABASE distriapp;
CREATE USER 'distriapp_user'@'localhost' IDENTIFIED BY '';
GRANT ALL PRIVILEGES ON distriapp.* TO 'distriapp_user'@'localhost';
FLUSH PRIVILEGES;
```

2. Copie el archivo `.env.example` a `.env`:

```bash
cp .env.example .env
```

3. Edite el archivo `.env` con sus credenciales de MySQL:

```
DB_HOST=localhost
DB_USER=distriapp_user
DB_PASSWORD=tu_contraseña
DB_NAME=distriapp
DB_PORT=3306
```

### 5. Ejecutar la aplicación

```bash
python main.py
```

La aplicación inicializará automáticamente la estructura de la base de datos la primera vez que se ejecute.

## Guía de uso

### Registrar un pedido

1. En la pantalla principal, ingrese el nombre del cliente (aparecerán sugerencias de clientes existentes)
2. Seleccione un producto del catálogo (se completará automáticamente el costo)
3. Ingrese la cantidad deseada
4. Verifique o ajuste el costo si es necesario
5. Seleccione la zona de entrega
6. Haga clic en "REGISTRAR" para añadir el producto al pedido actual
7. Repita los pasos 2-6 para añadir más productos al mismo pedido
8. Cuando termine, haga clic en "ENVIAR" para finalizar el pedido completo

### Consultar pedidos del día

1. Haga clic en "PEDIDOS HOY"
2. Aparecerá una lista de clientes con pedidos para el día actual
3. Seleccione un cliente para ver los detalles de sus pedidos
4. Podrá generar un PDF con el detalle del pedido del cliente seleccionado

### Modificar pedidos

1. Haga clic en "MODIFICAR"
2. Seleccione el cliente cuyos pedidos desea modificar
3. Ajuste las cantidades o costos según sea necesario
4. Elimine pedidos individuales si es necesario
5. Haga clic en "GUARDAR" para aplicar los cambios

### Importar productos desde CSV

1. Prepare un archivo CSV con las siguientes columnas:
   - `nombre`: Nombre del producto (obligatorio)
   - `costo`: Costo del producto (obligatorio)
   - `precio_venta`: Precio de venta (obligatorio)
   - `stock`: Cantidad en inventario (obligatorio)
   - `codigo`: Código de barras o SKU (opcional)

2. Haga clic en "SUBIR CSV" y seleccione el archivo
3. El sistema procesará el archivo y actualizará el inventario

### Ver estadísticas

1. Haga clic en "ESTADÍSTICAS"
2. Podrá ver:
   - Resumen de ventas totales
   - Detalle de ventas por día
   - Variación porcentual entre días
3. Puede exportar las estadísticas a PDF para su posterior consulta

### Generar informe de productos por día

1. Haga clic en "PRODUCTOS"
2. Se generará automáticamente un PDF con todos los productos vendidos en el día actual, agrupados por tipo de producto

## Estructura del proyecto

```
distriapp/
├── main.py                  # Punto de entrada principal
├── requirements.txt         # Dependencias de Python
├── .env.example             # Ejemplo de configuración
├── database/                # Módulos de base de datos
│   ├── db_connection.py     # Conexión a MySQL
│   ├── models/              # Modelos de datos
│   │   ├── cliente.py       # Modelo para Clientes
│   │   ├── producto.py      # Modelo para Productos
│   │   └── pedido.py        # Modelo para Pedidos
├── utils/                   # Utilidades
│   ├── pdf_generator.py     # Generador de PDFs
│   └── csv_handler.py       # Manejo de archivos CSV
└── pdfs/                    # Directorio para PDFs generados
```

## Solución de problemas comunes

### Error de conexión a la base de datos

**Problema**: La aplicación muestra "Error de conexión a la base de datos"

**Solución**:
1. Verifique que el servidor MySQL esté en ejecución
2. Confirme que las credenciales en `.env` sean correctas
3. Asegúrese de que el usuario tenga los permisos adecuados
4. Verifique que el firewall no esté bloqueando la conexión

### Error al generar PDFs

**Problema**: La aplicación muestra "Error al generar PDF"

**Solución**:
1. Verifique que el directorio `pdfs/` exista y tenga permisos de escritura
2.