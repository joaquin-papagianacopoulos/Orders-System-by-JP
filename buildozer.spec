[app]
# Título de la aplicación
title = DistribucionApp

# Paquete de la aplicación
package.name = distribucionapp
package.domain = org.distrisulpi

# Versión y metadatos
version = 0.1
author = Joaquin Papagianacopoulos
description = Aplicación de gestión de pedidos y distribución

# Configuración de código
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,db,json
source.exclude_dirs = tests, bin, venv, .git

# Requisitos (lista de dependencias)
requirements = python3,kivy,kivymd,pillow,fpdf,numpy

# Orientación de la pantalla
orientation = portrait
fullscreen = 0

# Icono de la aplicación
icon.filename = logoSulpi.png

# Permisos requeridos por la aplicación
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,ACCESS_NETWORK_STATE

# Configuración de Android
android.minapi = 21
android.api = 33
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.accept_sdk_license = True
android.logcat_filters = *:S python:D
android.ndk_api = 21

# Compilacion
log_level = 2

# Configuración adicional
android.presplash.filename = presplash.png
p4a.bootstrap = sdl2
p4a.port = 5000