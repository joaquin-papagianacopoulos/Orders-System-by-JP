[app]
# Título de la aplicación
title = DistriSulpiAPP

# Nombre del paquete
package.name = sulpiapp

# Dominio de la aplicación (generalmente en formato inverso)
package.domain = com.tuempresa

# Versión de la aplicación
version = 0.1

# Requisitos (asegúrate de incluir todas las bibliotecas que usas)
requirements = python3,kivy,kivymd,sqlite3,pillow,fpdf

# Orientación (portrait, landscape, etc.)
orientation = portrait

# Directorio fuente (donde está tu código)
source.dir = .

# Archivo principal (generalmente app.py o main.py)
source.include_exts = py,png,jpg,kv,atlas,db

# Archivos de recursos a incluir
source.include_patterns = assets/*,images/*,fonts/*,data/*,*.db

# Android específico
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 31
android.minapi = 21
android.ndk = 23b
android.sdk = 31
android.accept_sdk_license = True
android.sdk_path = /home/joacomamoliti/.buildozer/android/platform/android-sdk
android.archs = arm64-v8a, armeabi-v7a

# Configuración opcional para firmado
#android.keystore = 
#android.keyalias = 
#android.keystore_password = 
#android.keyalias_password = 

# Icono de la aplicación
#icon.filename = %(source.dir)s/data/icon.png