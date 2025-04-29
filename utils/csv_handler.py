# utils/csv_handler.py
import pandas as pd
import io
import logging
from database.models.producto import Producto

logger = logging.getLogger(__name__)

class CSVHandler:
    """Clase para manejar la importación y exportación de archivos CSV."""
    
    @staticmethod
    def procesar_csv_productos(contenido_csv):
        """
        Procesa un archivo CSV de productos y actualiza la base de datos.
        
        Args:
            contenido_csv: Contenido del archivo CSV como string o bytes
            
        Returns:
            Tupla (exito, mensaje, actualizados, creados)
        """
        try:
            # Si el contenido es bytes, convertirlo a string
            if isinstance(contenido_csv, bytes):
                contenido_csv = contenido_csv.decode('utf-8-sig')
            
            # Crear un DataFrame desde el contenido
            df = pd.read_csv(io.StringIO(contenido_csv))
            
            # Verificar encabezados requeridos
            required_columns = {'nombre', 'costo', 'precio_venta', 'stock'}
            if not required_columns.issubset(set(df.columns)):
                missing = required_columns - set(df.columns)
                return (False, f"Faltan columnas requeridas: {', '.join(missing)}", 0, 0)
            
            # Convertir DataFrame a lista de diccionarios
            productos_data = df.to_dict('records')
            
            # Procesar los productos
            actualizados, creados = Producto.bulk_update_from_csv(productos_data)
            
            mensaje = f"CSV procesado exitosamente. {actualizados} productos actualizados, {creados} productos nuevos."
            return (True, mensaje, actualizados, creados)
            
        except Exception as e:
            logger.error(f"Error al procesar CSV: {e}")
            return (False, f"Error al procesar el archivo: {str(e)}", 0, 0)
    
    @staticmethod
    def crear_csv_productos(productos=None):
        """
        Crea un archivo CSV con todos los productos o una lista específica.
        
        Args:
            productos: Lista de objetos Producto o None para todos los productos
            
        Returns:
            String con contenido CSV
        """
        try:
            if productos is None:
                productos = Producto.get_all()
            
            # Convertir lista de objetos a diccionarios
            productos_dict = [p.to_dict() for p in productos]
            
            # Crear DataFrame
            df = pd.DataFrame(productos_dict)
            
            # Seleccionar y ordenar columnas
            columnas = ['nombre', 'costo', 'precio_venta', 'stock', 'codigo']
            df = df[columnas]
            
            # Convertir a CSV
            csv_data = df.to_csv(index=False)
            return csv_data
            
        except Exception as e:
            logger.error(f"Error al crear CSV de productos: {e}")
            raise
    
    @staticmethod
    def crear_csv_pedidos(pedidos=None, fecha=None):
        """
        Crea un archivo CSV con los pedidos, opcionalmente filtrando por fecha.
        
        Args:
            pedidos: Lista de objetos Pedido o None para filtrar por fecha
            fecha: Fecha para filtrar los pedidos (si pedidos es None)
            
        Returns:
            String con contenido CSV
        """
        try:
            from database.models.pedido import Pedido
            
            if pedidos is None:
                if fecha is not None:
                    pedidos = Pedido.get_by_date(fecha)
                else:
                    pedidos = Pedido.get_all()
            
            # Convertir lista de objetos a diccionarios
            pedidos_dict = [p.to_dict() for p in pedidos]
            
            # Crear DataFrame
            df = pd.DataFrame(pedidos_dict)
            
            if df.empty:
                return "No hay datos para exportar"
            
            # Seleccionar y ordenar columnas
            columnas = ['fecha', 'cliente', 'producto', 'cantidad', 'costo', 'total', 'zona']
            df = df[columnas]
            
            # Convertir a CSV
            csv_data = df.to_csv(index=False)
            return csv_data
            
        except Exception as e:
            logger.error(f"Error al crear CSV de pedidos: {e}")
            raise