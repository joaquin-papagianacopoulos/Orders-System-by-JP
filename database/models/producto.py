# database/models/producto.py
from database.db_connection import db
import logging

logger = logging.getLogger(__name__)

class Producto:
    """Modelo para gestionar productos en la base de datos."""
    
    def __init__(self, id=None, nombre=None, costo=0.0, precio_venta=0.0, stock=0, codigo=None):
        """
        Inicializa un nuevo producto.
        
        Args:
            id: ID del producto en la base de datos
            nombre: Nombre del producto
            costo: Costo de adquisición
            precio_venta: Precio de venta
            stock: Cantidad en inventario
            codigo: Código o referencia opcional
        """
        self.id = id
        self.nombre = nombre
        self.costo = float(costo) if costo is not None else 0.0
        self.precio_venta = float(precio_venta) if precio_venta is not None else 0.0
        self.stock = int(stock) if stock is not None else 0
        self.codigo = codigo
    
    def save(self):
        """
        Guarda el producto en la base de datos.
        Si ya existe (tiene ID), actualiza sus datos.
        Si no existe, crea un nuevo registro.
        
        Returns:
            El ID del producto
        """
        try:
            if self.id:
                # Actualizar producto existente
                query = """
                    UPDATE productos 
                    SET nombre = %s, costo = %s, precio_venta = %s, stock = %s, codigo = %s 
                    WHERE id = %s
                """
                db.execute_update(query, (
                    self.nombre, self.costo, self.precio_venta, self.stock, self.codigo, self.id
                ))
                return self.id
            else:
                # Insertar nuevo producto
                query = """
                    INSERT INTO productos (nombre, costo, precio_venta, stock, codigo) 
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)
                """
                self.id = db.insert(query, (
                    self.nombre, self.costo, self.precio_venta, self.stock, self.codigo
                ))
                return self.id
        except Exception as e:
            logger.error(f"Error al guardar producto {self.nombre}: {e}")
            raise
    
    def update_stock(self, cantidad):
        """
        Actualiza el stock del producto.
        
        Args:
            cantidad: Cantidad a sumar o restar al stock (negativo para restar)
            
        Returns:
            True si se actualizó correctamente, False en caso contrario
        """
        try:
            # Actualizar en la base de datos
            query = "UPDATE productos SET stock = stock + %s WHERE id = %s"
            result = db.execute_update(query, (cantidad, self.id))
            
            # Actualizar el objeto en memoria
            if result > 0:
                self.stock += cantidad
                return True
            return False
        except Exception as e:
            logger.error(f"Error al actualizar stock del producto {self.nombre}: {e}")
            return False
    
    @classmethod
    def get_all(cls):
        """
        Obtiene todos los productos de la base de datos.
        
        Returns:
            Lista de objetos Producto
        """
        try:
            query = "SELECT * FROM productos ORDER BY nombre"
            productos_data = db.execute_query(query)
            return [cls(**producto) for producto in productos_data]
        except Exception as e:
            logger.error(f"Error al obtener todos los productos: {e}")
            return []
    
    @classmethod
    def get_by_id(cls, producto_id):
        """
        Obtiene un producto por su ID.
        
        Args:
            producto_id: ID del producto a buscar
            
        Returns:
            Objeto Producto o None si no existe
        """
        try:
            query = "SELECT * FROM productos WHERE id = %s"
            producto_data = db.execute_one(query, (producto_id,))
            return cls(**producto_data) if producto_data else None
        except Exception as e:
            logger.error(f"Error al obtener producto con ID {producto_id}: {e}")
            return None
    
    @classmethod
    def get_by_name(cls, nombre):
        """
        Obtiene un producto por su nombre.
        
        Args:
            nombre: Nombre exacto del producto a buscar
            
        Returns:
            Objeto Producto o None si no existe
        """
        try:
            query = "SELECT * FROM productos WHERE nombre = %s"
            producto_data = db.execute_one(query, (nombre,))
            return cls(**producto_data) if producto_data else None
        except Exception as e:
            logger.error(f"Error al obtener producto con nombre '{nombre}': {e}")
            return None
    
    @classmethod
    def search_by_name(cls, nombre, limit=5):
        """
        Busca productos por nombre (búsqueda parcial).
        
        Args:
            nombre: Texto a buscar en el nombre
            limit: Número máximo de resultados
            
        Returns:
            Lista de objetos Producto que coinciden con la búsqueda
        """
        try:
            query = "SELECT * FROM productos WHERE nombre LIKE %s ORDER BY nombre LIMIT %s"
            productos_data = db.execute_query(query, (f"%{nombre}%", limit))
            return [cls(**producto) for producto in productos_data]
        except Exception as e:
            logger.error(f"Error al buscar productos por nombre '{nombre}': {e}")
            return []
    
    @classmethod
    def delete(cls, producto_id):
        """
        Elimina un producto de la base de datos.
        
        Args:
            producto_id: ID del producto a eliminar
            
        Returns:
            True si se eliminó correctamente, False en caso contrario
        """
        try:
            query = "DELETE FROM productos WHERE id = %s"
            result = db.execute_update(query, (producto_id,))
            return result > 0
        except Exception as e:
            logger.error(f"Error al eliminar producto con ID {producto_id}: {e}")
            return False
    
    def to_dict(self):
        """
        Convierte el producto a un diccionario.
        
        Returns:
            Diccionario con los datos del producto
        """
        return {
            'id': self.id,
            'nombre': self.nombre,
            'costo': self.costo,
            'precio_venta': self.precio_venta,
            'stock': self.stock,
            'codigo': self.codigo
        }
    
    @classmethod
    def from_dict(cls, data):
        """
        Crea un objeto Producto a partir de un diccionario.
        
        Args:
            data: Diccionario con los datos del producto
            
        Returns:
            Objeto Producto
        """
        return cls(
            id=data.get('id'),
            nombre=data.get('nombre'),
            costo=data.get('costo', 0.0),
            precio_venta=data.get('precio_venta', 0.0),
            stock=data.get('stock', 0),
            codigo=data.get('codigo')
        )
    
    @classmethod
    def bulk_update_from_csv(cls, productos_data):
        """
        Actualiza o crea múltiples productos desde datos CSV.
        
        Args:
            productos_data: Lista de diccionarios con datos de productos
            
        Returns:
            Tupla (actualizados, creados) con el número de registros procesados
        """
        actualizados = 0
        creados = 0
        
        try:
            for data in productos_data:
                try:
                    # Asegurarse de que todos los campos requeridos estén presentes
                    if not all(key in data for key in ['nombre', 'costo', 'precio_venta', 'stock']):
                        logger.warning(f"Datos de producto incompletos: {data}")
                        continue
                    
                    # Verificar si el producto ya existe
                    producto = cls.get_by_name(data['nombre'])
                    
                    # Convertir valores a tipos adecuados
                    costo = float(data['costo'])
                    precio_venta = float(data['precio_venta'])
                    stock = int(data['stock'])
                    codigo = data.get('codigo', None)
                    
                    if producto:
                        # Actualizar producto existente
                        producto.costo = costo
                        producto.precio_venta = precio_venta
                        producto.stock = stock
                        producto.codigo = codigo
                        producto.save()
                        actualizados += 1
                        logger.info(f"Producto actualizado: {data['nombre']}")
                    else:
                        # Crear nuevo producto
                        nuevo = cls(
                            nombre=data['nombre'],
                            costo=costo,
                            precio_venta=precio_venta,
                            stock=stock,
                            codigo=codigo
                        )
                        nuevo.save()
                        creados += 1
                        logger.info(f"Producto creado: {data['nombre']}")
                except Exception as e:
                    logger.error(f"Error al procesar producto {data.get('nombre', 'desconocido')}: {e}")
                    continue
            
            return actualizados, creados
        except Exception as e:
            logger.error(f"Error en bulk_update_from_csv: {e}")
            return actualizados, creados