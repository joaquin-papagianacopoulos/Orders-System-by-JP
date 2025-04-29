# Estructura de la Base de Datos de DistriApp

Este documento detalla la estructura de la base de datos MySQL utilizada por DistriApp, incluyendo tablas, campos, tipos de datos y relaciones.

## Diagrama Entidad-Relación

```
+-------------+       +---------------+       +-------------+
|   clientes  |       |    pedidos    |       |  productos  |
+-------------+       +---------------+       +-------------+
| id          |<----->| cliente       |       | id          |
| nombre      |       | producto      |<----->| nombre      |
+-------------+       | cantidad      |       | costo       |
                      | costo         |       | precio_venta|
+-------------+       | zona          |       | stock       |
|    zonas    |<----->| fecha         |       | codigo      |
+-------------+       +---------------+       +-------------+
| id          |
| nombre      |
+-------------+
```

## Tablas

### Tabla: clientes

Almacena la información de los clientes.

| Campo      | Tipo                 | Restricciones           | Descripción                  |
|------------|----------------------|-------------------------|------------------------------|
| id         | INTEGER              | PRIMARY KEY AUTOINCREMENT| Identificador único          |
| nombre     | VARCHAR(100)         | UNIQUE NOT NULL         | Nombre del cliente           |

### Tabla: productos

Almacena la información de los productos disponibles.

| Campo       | Tipo                 | Restricciones           | Descripción                  |
|-------------|----------------------|-------------------------|------------------------------|
| id          | INTEGER              | PRIMARY KEY AUTOINCREMENT| Identificador único          |
| nombre      | VARCHAR(100)         | UNIQUE NOT NULL         | Nombre del producto          |
| costo       | DECIMAL(10, 2)       | NOT NULL                | Costo de adquisición         |
| precio_venta| DECIMAL(10, 2)       | NOT NULL                | Precio de venta al público   |
| stock       | INTEGER              | DEFAULT 0               | Cantidad disponible          |
| codigo      | VARCHAR(50)          | NULL                    | Código de barras o SKU       |

### Tabla: pedidos

Almacena los pedidos realizados.

| Campo       | Tipo                 | Restricciones           | Descripción                  |
|-------------|----------------------|-------------------------|------------------------------|
| id          | INTEGER              | PRIMARY KEY AUTOINCREMENT| Identificador único          |
| cliente     | VARCHAR(100)         | NOT NULL                | Nombre del cliente           |
| producto    | VARCHAR(100)         | NOT NULL                | Nombre del producto          |
| cantidad    | INTEGER              | NOT NULL                | Cantidad pedida              |
| costo       | DECIMAL(10, 2)       | NOT NULL                | Costo unitario               |
| zona        | VARCHAR(50)          | NOT NULL                | Zona de entrega              |
| fecha       | DATE                 | DEFAULT CURRENT_DATE    | Fecha del pedido             |

### Tabla: zonas

Almacena las zonas de distribución disponibles.

| Campo       | Tipo                 | Restricciones           | Descripción                  |
|-------------|----------------------|-------------------------|------------------------------|
| id          | INTEGER              | PRIMARY KEY AUTOINCREMENT| Identificador único          |
| nombre      | VARCHAR(50)          | UNIQUE NOT NULL         | Nombre de la zona            |

## Índices

Para mejorar el rendimiento de las consultas, se recomiendan los siguientes índices:

```sql
-- Índices para clientes
CREATE INDEX idx_cliente_nombre ON clientes(nombre);

-- Índices para productos
CREATE INDEX idx_producto_nombre ON productos(nombre);
CREATE INDEX idx_producto_codigo ON productos(codigo);

-- Índices para pedidos
CREATE INDEX idx_pedido_cliente ON pedidos(cliente);
CREATE INDEX idx_pedido_fecha ON pedidos(fecha);
CREATE INDEX idx_pedido_zona ON pedidos(zona);
```

## Relaciones

Las relaciones entre tablas se mantienen a nivel de aplicación debido a la simplicidad del esquema:

- Un **cliente** puede tener múltiples **pedidos**
- Un **producto** puede estar en múltiples **pedidos**
- Una **zona** puede tener múltiples **pedidos**

## Operaciones comunes

### Obtener los pedidos de un cliente en una fecha específica

```sql
SELECT * FROM pedidos 
WHERE cliente = 'Nombre Cliente' AND fecha = '2025-04-29';
```

### Verificar stock disponible de un producto

```sql
SELECT stock FROM productos WHERE nombre = 'Nombre Producto';
```

### Actualizar stock después de un pedido

```sql
UPDATE productos 
SET stock = stock - [cantidad] 
WHERE nombre = 'Nombre Producto';
```

### Obtener ventas por día

```sql
SELECT fecha, SUM(cantidad * costo) as total
FROM pedidos
GROUP BY fecha
ORDER BY fecha DESC;
```

### Obtener productos vendidos por día

```sql
SELECT producto, SUM(cantidad) as cantidad_total
FROM pedidos
WHERE fecha = '2025-04-29'
GROUP BY producto
ORDER BY producto;
```

## Gestión de la base de datos

### Copia de seguridad

Para realizar una copia de seguridad de la base de datos:

```bash
mysqldump -u [usuario] -p distriapp > distriapp_backup_$(date +"%Y%m%d").sql
```

### Restauración

Para restaurar una copia de seguridad:

```bash
mysql -u [usuario] -p distriapp < distriapp_backup_20250429.sql
```

### Optimización

Para optimizar las tablas después de muchas operaciones:

```sql
OPTIMIZE TABLE clientes, productos, pedidos, zonas;
```

## Ampliaciones futuras

La estructura actual permitiría las siguientes ampliaciones con mínimos cambios:

1. **Tabla de usuarios**: Para administrar diferentes niveles de acceso
2. **Tabla de proveedores**: Para relacionar productos con sus proveedores
3. **Estado de pedidos**: Añadir un campo de estado a la tabla de pedidos (pendiente, entregado, cancelado)
4. **Métodos de pago**: Añadir información sobre cómo se pagó cada pedido

---

*Esta documentación está actualizada a la versión 1.0.0 de DistriApp.*