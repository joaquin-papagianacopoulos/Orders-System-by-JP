# utils/pdf_generator.py
import os
from datetime import datetime
from fpdf import FPDF
import logging
from database.models.pedido import Pedido
from database.models.producto import Producto

logger = logging.getLogger(__name__)

class PDF(FPDF):
    """Clase personalizada que extiende FPDF para añadir encabezados y pies de página."""
    
    def __init__(self, title="Reporte", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        self.set_auto_page_break(auto=True, margin=15)
    
    def header(self):
        # Logo
        # self.image('logo.png', 10, 8, 33)
        
        # Título
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, self.title, 0, 1, 'C')
        
        # Fecha
        self.set_font('Arial', '', 10)
        self.cell(0, 5, f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1, 'R')
        
        # Línea
        self.ln(5)
        self.line(10, self.get_y(), self.w - 10, self.get_y())
        self.ln(5)
    
    def footer(self):
        # Posicionarse a 1.5 cm del final
        self.set_y(-15)
        # Arial italic 8
        self.set_font('Arial', 'I', 8)
        # Número de página
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', 0, 0, 'C')


class PDFGenerator:
    """Clase para generar diferentes tipos de informes PDF."""
    
    @staticmethod
    def _get_pdf_dir():
        """Obtiene el directorio para guardar los PDF."""
        pdf_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'pdfs')
        if not os.path.exists(pdf_dir):
            os.makedirs(pdf_dir)
        return pdf_dir
    
    @staticmethod
    def generar_pedido_cliente(cliente, fecha=None):
        """
        Genera un PDF con los pedidos de un cliente en una fecha específica.
        
        Args:
            cliente: Nombre del cliente
            fecha: Fecha para filtrar pedidos (opcional)
            
        Returns:
            Ruta al archivo PDF generado
        """
        try:
            # Obtener los pedidos del cliente
            pedidos = Pedido.get_by_cliente(cliente, fecha)
            
            if not pedidos:
                logger.warning(f"No hay pedidos para el cliente {cliente} en la fecha indicada")
                return None
            
            # Crear PDF
            pdf = PDF(title=f"Pedido de {cliente}")
            pdf.add_page()
            pdf.alias_nb_pages()
            
            # Configurar fuentes
            pdf.set_font('Arial', 'B', 12)
            
            # Fecha del pedido
            fecha_str = pedidos[0].fecha.strftime('%d/%m/%Y') if hasattr(pedidos[0].fecha, 'strftime') else str(pedidos[0].fecha)
            pdf.cell(0, 10, f"Fecha: {fecha_str}", 0, 1)
            pdf.ln(5)
            
            # Encabezados de la tabla
            pdf.set_fill_color(200, 200, 200)
            col_widths = [60, 25, 30, 30, 35]
            
            pdf.cell(col_widths[0], 10, 'Producto', 1, 0, 'C', 1)
            pdf.cell(col_widths[1], 10, 'Cantidad', 1, 0, 'C', 1)
            pdf.cell(col_widths[2], 10, 'Costo Unit.', 1, 0, 'C', 1)
            pdf.cell(col_widths[3], 10, 'Total', 1, 0, 'C', 1)
            pdf.cell(col_widths[4], 10, 'Zona', 1, 1, 'C', 1)
            
            # Datos de los pedidos
            pdf.set_font('Arial', '', 10)
            total_cliente = 0
            
            for pedido in pedidos:
                total = pedido.cantidad * pedido.costo
                total_cliente += total
                
                pdf.cell(col_widths[0], 10, pedido.producto, 1, 0, 'L')
                pdf.cell(col_widths[1], 10, str(pedido.cantidad), 1, 0, 'C')
                pdf.cell(col_widths[2], 10, f"${pedido.costo:.2f}", 1, 0, 'C')
                pdf.cell(col_widths[3], 10, f"${total:.2f}", 1, 0, 'C')
                pdf.cell(col_widths[4], 10, pedido.zona, 1, 1, 'C')
            
            # Fila de total
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(col_widths[0], 10, "TOTAL", 1, 0, 'R')
            pdf.cell(col_widths[1] + col_widths[2], 10, "", 1, 0, 'C')
            pdf.cell(col_widths[3], 10, f"${total_cliente:.2f}", 1, 0, 'C')
            pdf.cell(col_widths[4], 10, "", 1, 1, 'C')
            
            # Guardar PDF
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(PDFGenerator._get_pdf_dir(), f"Pedido_{cliente}_{timestamp}.pdf")
            pdf.output(filename)
            
            return filename
        
        except Exception as e:
            logger.error(f"Error al generar PDF de pedido para {cliente}: {e}")
            raise
    
    @staticmethod
    def generar_productos_por_dia(fecha=None):
        """
        Genera un PDF con los productos vendidos en un día específico.
        
        Args:
            fecha: Fecha para filtrar pedidos (opcional)
            
        Returns:
            Ruta al archivo PDF generado
        """
        try:
            # Obtener los productos vendidos en la fecha
            productos_vendidos = Pedido.get_productos_by_date(fecha)
            
            if not productos_vendidos:
                logger.warning(f"No hay productos vendidos en la fecha indicada")
                return None
            
            # Si la fecha es None, se usa la fecha actual
            if fecha is None:
                fecha = datetime.now().date()
            elif isinstance(fecha, str):
                fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
            
            # Crear PDF
            pdf = PDF(title='Reporte de Productos por Día')
            pdf.add_page()
            pdf.alias_nb_pages()
            
            # Fecha
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, f"Fecha: {fecha.strftime('%d/%m/%Y')}", 0, 1)
            pdf.ln(5)
            
            # Encabezados de la tabla
            pdf.set_fill_color(200, 200, 200)
            pdf.set_font('Arial', 'B', 11)
            
            # Definir anchos de columnas
            ancho_producto = 120
            ancho_cantidad = 60
            altura_celda = 10
            
            # Dibujar encabezados
            pdf.cell(ancho_producto, altura_celda, 'Producto', 1, 0, 'C', 1)
            pdf.cell(ancho_cantidad, altura_celda, 'Cantidad', 1, 1, 'C', 1)
            
            # Dibujar filas de datos
            pdf.set_font('Arial', '', 10)
            for producto in productos_vendidos:
                pdf.cell(ancho_producto, altura_celda, producto['producto'], 1, 0, 'L')
                pdf.cell(ancho_cantidad, altura_celda, str(producto['cantidad_total']), 1, 1, 'C')
            
            # Guardar PDF
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(PDFGenerator._get_pdf_dir(), f"Productos_por_dia_{timestamp}.pdf")
            pdf.output(filename)
            
            return filename
        
        except Exception as e:
            logger.error(f"Error al generar PDF de productos por día: {e}")
            raise
    
    @staticmethod
    def generar_estadisticas():
        """
        Genera un PDF con estadísticas generales de ventas.
        
        Returns:
            Ruta al archivo PDF generado
        """
        try:
            # Obtener datos para estadísticas
            ventas_diarias = Pedido.get_ventas_diarias(30)
            
            # Crear PDF
            pdf = PDF(title='Informe de Estadísticas de Ventas')
            pdf.add_page()
            pdf.alias_nb_pages()
            
            # 1. Resumen de ventas
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, "Resumen de Ventas", 0, 1, 'L')
            pdf.ln(2)
            
            # Calcular total de ventas
            total_ventas = sum(venta['total'] for venta in ventas_diarias) if ventas_diarias else 0
            
            # Tabla de resumen
            pdf.set_fill_color(150, 150, 150)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'B', 10)
            col_widths = [90, 90]
            pdf.cell(col_widths[0], 10, "Total Facturado (30 días)", 1, 0, 'C', 1)
            pdf.cell(col_widths[1], 10, f"${total_ventas:.2f}", 1, 1, 'C', 1)
            
            pdf.ln(10)
            
            # 2. Ventas por día
            pdf.set_font('Arial', 'B', 14)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 10, "Ventas de los Últimos Días", 0, 1, 'L')
            pdf.ln(2)
            
            # Tabla de ventas por día
            pdf.set_fill_color(150, 150, 150)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'B', 10)
            col_widths = [90, 90]
            pdf.cell(col_widths[0], 10, "Fecha", 1, 0, 'C', 1)
            pdf.cell(col_widths[1], 10, "Total", 1, 1, 'C', 1)
            
            pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Arial', '', 10)
            
            for venta in ventas_diarias[:15]:  # Mostrar solo los últimos 15 días
                fecha_str = venta['dia']
                if isinstance(fecha_str, datetime) or hasattr(fecha_str, 'strftime'):
                    fecha_str = fecha_str.strftime('%d/%m/%Y')
                
                pdf.cell(col_widths[0], 10, str(fecha_str), 1, 0, 'C')
                pdf.cell(col_widths[1], 10, f"${venta['total']:.2f}", 1, 1, 'C')
            
            # Guardar PDF
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(PDFGenerator._get_pdf_dir(), f"Estadisticas_{timestamp}.pdf")
            pdf.output(filename)
            
            return filename
        
        except Exception as e:
            logger.error(f"Error al generar PDF de estadísticas: {e}")
            raise