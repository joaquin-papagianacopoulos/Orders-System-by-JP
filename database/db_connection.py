# database/db_connection.py
import os
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv
import logging

# Configuración del logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

class DatabaseConnection:
    """Clase para manejar la conexión a la base de datos MySQL."""
    
    _instance = None
    
    def __new__(cls):
        """Patrón Singleton para asegurar una única instancia."""
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Inicializa la conexión con los parámetros desde variables de entorno."""
        self.config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', 'joacoelmascapo'),
            'database': os.getenv('DB_NAME', 'distriapp'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'charset': 'utf8mb4',
            'cursorclass': DictCursor,
            'autocommit': True
        }
        self.connection = None
        self._connect()
    
    def _connect(self):
        """Establece la conexión a la base de datos."""
        try:
            self.connection = pymysql.connect(**self.config)
            logger.info("Conexión a la base de datos establecida con éxito")
        except pymysql.MySQLError as e:
            logger.error(f"Error al conectar a la base de datos: {e}")
            raise
    
    def get_connection(self):
        """Retorna la conexión actual, reconectando si es necesario."""
        if self.connection is None or not self.connection.open:
            self._connect()
        return self.connection
    
    def execute_query(self, query, params=None):
        """
        Ejecuta una consulta SELECT y retorna los resultados.
        
        Args:
            query: Consulta SQL a ejecutar
            params: Parámetros para la consulta (opcional)
            
        Returns:
            Lista de diccionarios con los resultados
        """
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchall()
        except pymysql.MySQLError as e:
            logger.error(f"Error al ejecutar la consulta: {e}")
            logger.error(f"Query: {query}, Params: {params}")
            # Intentar reconectar para la próxima vez
            self._connect()
            raise
    
    def execute_one(self, query, params=None):
        """
        Ejecuta una consulta SELECT y retorna un solo resultado.
        
        Args:
            query: Consulta SQL a ejecutar
            params: Parámetros para la consulta (opcional)
            
        Returns:
            Diccionario con el primer resultado o None
        """
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchone()
        except pymysql.MySQLError as e:
            logger.error(f"Error al ejecutar la consulta: {e}")
            self._connect()
            raise
    
    def execute_update(self, query, params=None):
        """
        Ejecuta una consulta INSERT, UPDATE o DELETE.
        
        Args:
            query: Consulta SQL a ejecutar
            params: Parámetros para la consulta (opcional)
            
        Returns:
            Número de filas afectadas
        """
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(query, params or ())
                return cursor.rowcount
        except pymysql.MySQLError as e:
            logger.error(f"Error al ejecutar la actualización: {e}")
            self._connect()
            raise
    
    def insert(self, query, params=None):
        """
        Ejecuta una consulta INSERT y retorna el ID generado.
        
        Args:
            query: Consulta SQL a ejecutar
            params: Parámetros para la consulta (opcional)
            
        Returns:
            ID de la última fila insertada
        """
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(query, params or ())
                return cursor.lastrowid
        except pymysql.MySQLError as e:
            logger.error(f"Error al ejecutar la inserción: {e}")
            self._connect()
            raise
    
    def close(self):
        """Cierra la conexión a la base de datos."""
        if self.connection and self.connection.open:
            self.connection.close()
            logger.info("Conexión a la base de datos cerrada")

# Instancia global para usar en toda la aplicación
db = DatabaseConnection()

# Función para inicializar la base de datos con el esquema
def initialize_database():
    """
    Inicializa la base de datos con el esquema definido en schema.sql.
    Se debe ejecutar al inicio de la aplicación.
    """
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.join(script_dir, 'schema.sql')
        
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Dividir por ';' para ejecutar cada declaración por separado
        statements = schema_sql.split(';')
        
        conn = db.get_connection()
        with conn.cursor() as cursor:
            for statement in statements:
                if statement.strip():
                    cursor.execute(statement)
        
        logger.info("Base de datos inicializada correctamente")
    except Exception as e:
        logger.error(f"Error al inicializar la base de datos: {e}")
        raise