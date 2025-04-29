# database/models/cliente.py
from database.db_connection import db
import logging

logger = logging.getLogger(__name__)

class Cliente:
    """Modelo para gestionar clientes en la base de datos."""
    
    def __init__(self, id=None, nombre=None):
        """
        Inicializa un nuevo cliente.
        
        Args:
            id: ID del cliente en la base de datos
            nombre: Nombre del cliente
        """
        self.id = id
        self.nombre = nombre
    
    def save(self):
        """
        Guarda el cliente en la base de datos.
        Si ya existe (tiene ID), actualiza sus datos.
        Si no existe, crea un nuevo registro.
        
        Returns:
            El ID del cliente
        """
        try:
            if self.id:
                # Actualizar cliente existente
                query = "UPDATE clientes SET nombre = %s WHERE id = %s"
                db.execute_update(query, (self.nombre, self.id))
                return self.id
            else:
                # Insertar nuevo cliente
                query = """
                    INSERT INTO clientes (nombre) 
                    VALUES (%s)
                    ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)
                """
                self.id = db.insert(query, (self.nombre,))
                return self.id
        except Exception as e:
            logger.error(f"Error al guardar cliente {self.nombre}: {e}")
            raise
    
    @classmethod
    def get_all(cls):
        """
        Obtiene todos los clientes de la base de datos.
        
        Returns:
            Lista de objetos Cliente
        """
        try:
            query = "SELECT * FROM clientes ORDER BY nombre"
            clientes_data = db.execute_query(query)
            return [cls(**cliente) for cliente in clientes_data]
        except Exception as e:
            logger.error(f"Error al obtener todos los clientes: {e}")
            return []
    
    @classmethod
    def get_by_id(cls, cliente_id):
        """
        Obtiene un cliente por su ID.
        
        Args:
            cliente_id: ID del cliente a buscar
            
        Returns:
            Objeto Cliente o None si no existe
        """
        try:
            query = "SELECT * FROM clientes WHERE id = %s"
            cliente_data = db.execute_one(query, (cliente_id,))
            return cls(**cliente_data) if cliente_data else None
        except Exception as e:
            logger.error(f"Error al obtener cliente con ID {cliente_id}: {e}")
            return None
    
    @classmethod
    def search_by_name(cls, nombre, limit=5):
        """
        Busca clientes por nombre (búsqueda parcial).
        
        Args:
            nombre: Texto a buscar en el nombre
            limit: Número máximo de resultados
            
        Returns:
            Lista de objetos Cliente que coinciden con la búsqueda
        """
        try:
            query = "SELECT * FROM clientes WHERE nombre LIKE %s ORDER BY nombre LIMIT %s"
            clientes_data = db.execute_query(query, (f"%{nombre}%", limit))
            return [cls(**cliente) for cliente in clientes_data]
        except Exception as e:
            logger.error(f"Error al buscar clientes por nombre '{nombre}': {e}")
            return []
    
    @classmethod
    def delete(cls, cliente_id):
        """
        Elimina un cliente de la base de datos.
        
        Args:
            cliente_id: ID del cliente a eliminar
            
        Returns:
            True si se eliminó correctamente, False en caso contrario
        """
        try:
            query = "DELETE FROM clientes WHERE id = %s"
            result = db.execute_update(query, (cliente_id,))
            return result > 0
        except Exception as e:
            logger.error(f"Error al eliminar cliente con ID {cliente_id}: {e}")
            return False
    
    def to_dict(self):
        """
        Convierte el cliente a un diccionario.
        
        Returns:
            Diccionario con los datos del cliente
        """
        return {
            'id': self.id,
            'nombre': self.nombre
        }
    
    @classmethod
    def from_dict(cls, data):
        """
        Crea un objeto Cliente a partir de un diccionario.
        
        Args:
            data: Diccionario con los datos del cliente
            
        Returns:
            Objeto Cliente
        """
        return cls(
            id=data.get('id'),
            nombre=data.get('nombre')
        )