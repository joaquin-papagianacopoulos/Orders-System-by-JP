#!/usr/bin/env python3
"""
Script de configuración inicial para DistriApp.
Este script ayuda a configurar el entorno de ejecución para DistriApp.
"""

import os
import sys
import subprocess
import platform
import getpass
import configparser
import shutil
from pathlib import Path

# Colores para los mensajes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_banner():
    """Muestra un banner de bienvenida."""
    print(Colors.HEADER + """
 ____  _     _        _    _                
|  _ \(_)___| |_ _ __(_)  / \   _ __  _ __  
| | | | / __| __| '__| | / _ \ | '_ \| '_ \ 
| |_| | \__ \ |_| |  | |/ ___ \| |_) | |_) |
|____/|_|___/\__|_|  |_/_/   \_\ .__/| .__/ 
                               |_|   |_|    
    """ + Colors.END)
    
    print(Colors.BOLD + "Sistema de Gestión de Distribución" + Colors.END)
    print("Script de instalación y configuración inicial\n")

def check_python_version():
    """Verifica que la versión de Python sea compatible."""
    print(Colors.BLUE + "Verificando versión de Python..." + Colors.END)
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(Colors.FAIL + f"Error: Se requiere Python 3.8 o superior. Versión actual: {sys.version.split()[0]}" + Colors.END)
        return False
    
    print(Colors.GREEN + f"✓ Python {sys.version.split()[0]} detectado." + Colors.END)
    return True

def check_virtual_env():
    """Verifica si estamos en un entorno virtual y sugiere crear uno si no."""
    print(Colors.BLUE + "Verificando entorno virtual..." + Colors.END)
    
    in_virtualenv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    
    if not in_virtualenv:
        print(Colors.WARNING + "No estás en un entorno virtual. Se recomienda usar uno." + Colors.END)
        create_env = input("¿Desea crear un entorno virtual ahora? (s/n): ")
        
        if create_env.lower() == 's':
            venv_name = input("Nombre del entorno (default: venv): ") or "venv"
            
            try:
                subprocess.run([sys.executable, "-m", "venv", venv_name], check=True)
                
                # Mostrar instrucciones para activar el entorno
                print(Colors.GREEN + f"✓ Entorno virtual '{venv_name}' creado." + Colors.END)
                
                if platform.system() == "Windows":
                    print(Colors.BOLD + f"\nPara activar el entorno virtual, ejecute:" + Colors.END)
                    print(f"{venv_name}\\Scripts\\activate")
                else:
                    print(Colors.BOLD + f"\nPara activar el entorno virtual, ejecute:" + Colors.END)
                    print(f"source {venv_name}/bin/activate")
                
                print(Colors.WARNING + "Por favor, active el entorno virtual y vuelva a ejecutar este script." + Colors.END)
                return False
            except subprocess.CalledProcessError as e:
                print(Colors.FAIL + f"Error al crear el entorno virtual: {e}" + Colors.END)
                return False
        else:
            print(Colors.WARNING + "Continuando sin entorno virtual..." + Colors.END)
    else:
        print(Colors.GREEN + "✓ Entorno virtual detectado." + Colors.END)
    
    return True

def install_dependencies():
    """Instala las dependencias de Python desde requirements.txt."""
    print(Colors.BLUE + "Instalando dependencias..." + Colors.END)
    
    if not os.path.exists("requirements.txt"):
        print(Colors.FAIL + "Error: Archivo requirements.txt no encontrado." + Colors.END)
        return False
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        print(Colors.GREEN + "✓ Dependencias instaladas correctamente." + Colors.END)
        return True
    except subprocess.CalledProcessError as e:
        print(Colors.FAIL + f"Error al instalar dependencias: {e}" + Colors.END)
        return False

def configure_database():
    """Configura la conexión a la base de datos MySQL."""
    print(Colors.BLUE + "Configurando conexión a la base de datos..." + Colors.END)
    
    # Verificar si ya existe el archivo .env
    if os.path.exists(".env"):
        overwrite = input("Archivo .env ya existe. ¿Desea sobreescribirlo? (s/n): ")
        if overwrite.lower() != 's':
            print(Colors.WARNING + "Manteniendo configuración existente." + Colors.END)
            return True
    
    # Crear el archivo .env con configuración de base de datos
    print("Por favor, ingrese los datos de conexión a MySQL:")
    
    db_config = {
        'DB_HOST': input("Host (default: localhost): ") or "localhost",
        'DB_USER': input("Usuario (default: root): ") or "root",
        'DB_PASSWORD': getpass.getpass("Contraseña: "),
        'DB_NAME': input("Nombre de la base de datos (default: distriapp): ") or "distriapp",
        'DB_PORT': input("Puerto (default: 3306): ") or "3306"
    }
    
    # Escribir el archivo .env
    with open(".env", "w") as env_file:
        for key, value in db_config.items():
            env_file.write(f"{key}={value}\n")
    
    print(Colors.GREEN + "✓ Archivo .env creado con la configuración de base de datos." + Colors.END)
    
    # Preguntar si desea crear la base de datos
    create_db = input("¿Desea crear la base de datos ahora? (s/n): ")
    if create_db.lower() == 's':
        try:
            # Intenta importar PyMySQL para verificar la conexión
            import pymysql
            
            # Intentar conectar sin la base de datos
            conn = pymysql.connect(
                host=db_config['DB_HOST'],
                user=db_config['DB_USER'],
                password=db_config['DB_PASSWORD'],
                port=int(db_config['DB_PORT'])
            )
            
            cursor = conn.cursor()
            
            # Crear la base de datos
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['DB_NAME']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            
            # Crear usuario si no es root
            if db_config['DB_USER'] != 'root':
                try:
                    cursor.execute(f"CREATE USER IF NOT EXISTS '{db_config['DB_USER']}'@'{db_config['DB_HOST']}' IDENTIFIED BY '{db_config['DB_PASSWORD']}'")
                    cursor.execute(f"GRANT ALL PRIVILEGES ON {db_config['DB_NAME']}.* TO '{db_config['DB_USER']}'@'{db_config['DB_HOST']}'")
                    cursor.execute("FLUSH PRIVILEGES")
                except pymysql.Error:
                    print(Colors.WARNING + "No se pudo crear el usuario. Es posible que ya exista o no tenga permisos." + Colors.END)
            
            cursor.close()
            conn.close()
            
            print(Colors.GREEN + f"✓ Base de datos '{db_config['DB_NAME']}' creada exitosamente." + Colors.END)
        
        except ImportError:
            print(Colors.WARNING + "No se pudo importar PyMySQL. Instale las dependencias primero." + Colors.END)
        except pymysql.Error as e:
            print(Colors.FAIL + f"Error al crear la base de datos: {e}" + Colors.END)
    
    return True

def create_directories():
    """Crea los directorios necesarios para la aplicación."""
    print(Colors.BLUE + "Creando directorios de la aplicación..." + Colors.END)
    
    dirs = ["pdfs", "logs"]
    
    for dir_name in dirs:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            print(f"  - Directorio '{dir_name}' creado.")
    
    print(Colors.GREEN + "✓ Directorios creados correctamente." + Colors.END)
    return True

def verify_installation():
    """Verifica que la instalación esté completa y correcta."""
    print(Colors.BLUE + "Verificando instalación..." + Colors.END)
    
    # Verificar archivos y directorios críticos
    critical_files = [
        "main.py", 
        "requirements.txt", 
        ".env"
    ]
    
    critical_dirs = [
        "database",
        "utils",
        "pdfs"
    ]
    
    missing = []
    
    for file in critical_files:
        if not os.path.isfile(file):
            missing.append(f"Archivo: {file}")
    
    for dir_name in critical_dirs:
        if not os.path.isdir(dir_name):
            missing.append(f"Directorio: {dir_name}")
    
    if missing:
        print(Colors.FAIL + "Error: Faltan los siguientes archivos o directorios:" + Colors.END)
        for item in missing:
            print(f"  - {item}")
        return False
    
    # Todo está correcto
    print(Colors.GREEN + "✓ Todos los archivos y directorios necesarios están presentes." + Colors.END)
    return True

def final_instructions():
    """Muestra instrucciones finales al usuario."""
    print(Colors.HEADER + "\n=== Instalación completada ===" + Colors.END)
    print("\nPara iniciar DistriApp, ejecute el siguiente comando:")
    print(Colors.BOLD + "    python main.py" + Colors.END)
    
    print("\nSi encuentra algún problema, consulte la documentación en README.md")
    print("o revise los archivos de registro en el directorio 'logs'.")
    
    print(Colors.GREEN + "\n¡Gracias por instalar DistriApp!\n" + Colors.END)

def main():
    print_banner()
    
    steps = [
        ("Verificar versión de Python", check_python_version),
        ("Verificar entorno virtual", check_virtual_env),
        ("Instalar dependencias", install_dependencies),
        ("Configurar base de datos", configure_database),
        ("Crear directorios", create_directories),
        ("Verificar instalación", verify_installation)
    ]
    
    for step_name, step_func in steps:
        print(f"\n{Colors.BOLD}>>> {step_name}{Colors.END}")
        if not step_func():
            print(Colors.FAIL + f"\nInstalación detenida en: {step_name}" + Colors.END)
            return
    
    final_instructions()

if __name__ == "__main__":
    main()