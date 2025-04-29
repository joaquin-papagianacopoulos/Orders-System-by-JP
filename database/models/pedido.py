# database/models/pedido.py
from database.db_connection import db
from database.models.producto import Producto
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)

class Pedido:
    """Modelo para gestionar pedidos en la base de datos."""
    
    def __init__(self, id=None, cliente=None, producto=None, cantidad=0, 
                 costo=0.0, zona=None, fecha=None):
        """
        Inicializa un nuevo pedido.
        
        Args:
            id: ID del pedido en la base de datos
            cliente: Nombre del cliente
            producto: Nombre del producto
            cantidad: Cantidad de productos
            costo: Costo por unidad
            zona: Zona de entrega
            fecha: Fecha del pedido (si no se proporciona, se usa la fecha actual)
        """
        self.id = id
        self.cliente = cliente
        self.producto = producto
        self.cantidad = int(cantidad) if cantidad is not None else 0
        self.costo = float(costo) if costo is not None else 0.0
        self.zona = zona
        
        # Manejo de fecha
        if fecha is None:
            self.fecha = date.today()
        elif isinstance(fecha, str):
            try:
                self.fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
            except ValueError:
                logger.warning(f"Formato de fecha incorrecto: {fecha}, usando fecha actual")
                self.fecha = date.today()
        else:
            self.fecha = fecha
    
    def save(self):
        """
        Guarda el pedido en la base de datos.
        Si ya existe (tiene ID), actualiza sus datos.
        Si no existe, crea un nuevo registro.
        
        Returns:
            El ID del pedido
        """
        try:
            if self.id:
                # Actualizar pedido existente
                query = """
                    UPDATE pedidos 
                    SET cliente = %s, producto = %s, cantidad = %s, 
                        costo = %s, zona = %s, fecha = %s
                    WHERE id = %s
                """
                db.execute_update(query, (
                    self.cliente, self.producto, self.cantidad,
                    self.costo, self.zona, self.fecha, self.id
                ))
                return self.id
            else:
                # Insertar nuevo pedido
                query = """
                    INSERT INTO pedidos (cliente, producto, cantidad, costo, zona, fecha) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                self.id = db.insert(query, (
                    self.cliente, self.producto, self.cantidad,
                    self.costo, self.zona, self.fecha
                ))
                
                # Actualizar el stock del producto
                producto_obj = Producto.get_by_name(self.producto)
                if producto_obj:
                    producto_obj.update_stock(-self.cantidad)
                
                return self.id
        except Exception as e:
            logger.error(f"Error al guardar pedido: {e}")
            raise
    
    @classmethod
    def get_all(cls, limit=100):
        """
        Obtiene todos los pedidos de la base de datos.
        
        Args:
            limit: Número máximo de resultados
            
        Returns:
            Lista de objetos Pedido
        """
        try:
            query = "SELECT * FROM pedidos ORDER BY fecha DESC, id DESC LIMIT %s"
            pedidos_data = db.execute_query(query, (limit,))
            return [cls(**pedido) for pedido in pedidos_data]
        except Exception as e:
            logger.error(f"Error al obtener todos los pedidos: {e}")
            return []
    
    @classmethod
    def get_by_id(cls, pedido_id):
        """
        Obtiene un pedido por su ID.
        
        Args:
            pedido_id: ID del pedido a buscar
            
        Returns:
            Objeto Pedido o None si no existe
        """
        try:
            query = "SELECT * FROM pedidos WHERE id = %s"
            pedido_data = db.execute_one(query, (pedido_id,))
            return cls(**pedido_data) if pedido_data else None
        except Exception as e:
            logger.error(f"Error al obtener pedido con ID {pedido_id}: {e}")
            return None
    
    @classmethod
    def get_by_date(cls, fecha=None):
        """
        Obtiene los pedidos de una fecha específica.
        Si no se proporciona fecha, se usa la fecha actual.
        
        Args:
            fecha: Fecha para filtrar pedidos (objeto date, string YYYY-MM-DD o None)
            
        Returns:
            Lista de objetos Pedido
        """
        try:
            if fecha is None:
                fecha = date.today()
            elif isinstance(fecha, str):
                fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
            
            query = "SELECT * FROM pedidos WHERE fecha = %s ORDER BY id DESC"
            pedidos_data = db.execute_query(query, (fecha,))
            return [cls(**pedido) for pedido in pedidos_data]
        except Exception as e:
            logger.error(f"Error al obtener pedidos por fecha {fecha}: {e}")
            return []
    
    @classmethod
    def get_by_cliente(cls, cliente, fecha=None):
        """
        Obtiene los pedidos de un cliente específico, opcionalmente filtrando por fecha.
        
        Args:
            cliente: Nombre del cliente
            fecha: Fecha para filtrar pedidos (opcional)
            
        Returns:
            Lista de objetos Pedido
        """
        try:
            if fecha is None:
                query = "SELECT * FROM pedidos WHERE cliente = %s ORDER BY fecha DESC, id DESC"
                pedidos_data = db.execute_query(query, (cliente,))
            else:
                if isinstance(fecha, str):
                    fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
                
                query = "SELECT * FROM pedidos WHERE cliente = %s AND fecha = %s ORDER BY id DESC"
                pedidos_data = db.execute_query(query, (cliente, fecha))
            
            return [cls(**pedido) for pedido in pedidos_data]
        except Exception as e:
            logger.error(f"Error al obtener pedidos del cliente {cliente}: {e}")
            return []
    
    @classmethod
    def get_clientes_by_date(cls, fecha=None):
        """
        Obtiene la lista de clientes que tienen pedidos en una fecha específica.
        
        Args:
            fecha: Fecha para filtrar (objeto date, string YYYY-MM-DD o None para hoy)
            
        Returns:
            Lista de nombres de clientes
        """
        try:
            if fecha is None:
                fecha = date.today()
            elif isinstance(fecha, str):
                fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
            
            query = "SELECT DISTINCT cliente FROM pedidos WHERE fecha = %s ORDER BY cliente"
            result = db.execute_query(query, (fecha,))
            return [row['cliente'] for row in result]
        except Exception as e:
            logger.error(f"Error al obtener clientes por fecha {fecha}: {e}")
            return []
    
    @classmethod
    def get_productos_by_date(cls, fecha=None):
        """
        Obtiene los productos y cantidades vendidos en una fecha específica.
        
        Args:
            fecha: Fecha para filtrar (objeto date, string YYYY-MM-DD o None para hoy)
            
        Returns:
            Lista de diccionarios con producto y cantidad_total
        """
        try:
            if fecha is None:
                fecha = date.today()
            elif isinstance(fecha, str):
                fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
            
            query = """
                SELECT producto, SUM(cantidad) as cantidad_total
                FROM pedidos
                WHERE fecha = %s
                GROUP BY producto
                ORDER BY producto
            """
            return db.execute_query(query, (fecha,))
        except Exception as e:
            logger.error(f"Error al obtener productos por fecha {fecha}: {e}")
            return []
    
    @classmethod
    def get_ventas_diarias(cls, dias=30):
        """
        Obtiene las ventas totales por día de los últimos X días.
        
        Args:
            dias: Número de días para obtener
            
        Returns:
            Lista de diccionarios con dia y total
        """
        try:
            query = """
                SELECT fecha as dia, SUM(cantidad * costo) as total
                FROM pedidos
                GROUP BY fecha
                ORDER BY fecha DESC
                LIMIT %s
            """
            return db.execute_query(query, (dias,))
        except Exception as e:
            logger.error(f"Error al obtener ventas diarias: {e}")
            return []
    
    @classmethod
    def delete(cls, pedido_id):
        """
        Elimina un pedido de la base de datos y actualiza el stock.
        
        Args:
            pedido_id: ID del pedido a eliminar
            
        Returns:
            True si se eliminó correctamente, False en caso contrario
        """
        try:
            # Primero obtener el pedido para saber qué producto y cantidad restaurar
            pedido = cls.get_by_id(pedido_id)
            if not pedido:
                return False
            
            # Eliminar el pedido
            query = "DELETE FROM pedidos WHERE id = %s"
            result = db.execute_update(query, (pedido_id,))
            
            # Restaurar el stock si se eliminó correctamente
            if result > 0:
                producto_obj = Producto.get_by_name(pedido.producto)
                if producto_obj:
                    producto_obj.update_stock(pedido.cantidad)  # Sumar la cantidad de vuelta al stock
                return True
            return False
        except Exception as e:
            logger.error(f"Error al eliminar pedido con ID {pedido_id}: {e}")
            return False
    
    def to_dict(self):
        """
        Convierte el pedido a un diccionario.
        
        Returns:
            Diccionario con los datos del pedido
        """
        return {
            'id': self.id,
            'cliente': self.cliente,
            'producto': self.producto,
            'cantidad': self.cantidad,
            'costo': self.costo,
            'zona': self.zona,
            'fecha': self.fecha.isoformat() if hasattr(self.fecha, 'isoformat') else self.fecha,
            'total': round(self.cantidad * self.costo, 2)
        }
    
    @classmethod
    def from_dict(cls, data):
        """
        Crea un objeto Pedido a partir de un diccionario.
        
        Args:
            data: Diccionario con los datos del pedido
            
        Returns:
            Objeto Pedido
        """
        # Eliminar campos calculados que no están en el modelo
        if 'total' in data:
            del data['total']
            
        return cls(
            id=data.get('id'),
            cliente=data.get('cliente'),
            producto=data.get('producto'),
            cantidad=data.get('cantidad', 0),
            costo=data.get('costo', 0),
            zona=data.get('zona'),
            fecha=data.get('fecha')
        )