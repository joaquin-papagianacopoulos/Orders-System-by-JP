-- Crear la base de datos si no existe
CREATE DATABASE IF NOT EXISTS distriapp;
USE distriapp;

-- Tabla de productos
CREATE TABLE IF NOT EXISTS productos (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  nombre VARCHAR(100) NOT NULL UNIQUE,
  costo DECIMAL(10, 2) NOT NULL,
  precio_venta DECIMAL(10, 2) NOT NULL,
  stock INTEGER DEFAULT 0,
  codigo VARCHAR(50) DEFAULT NULL
);

-- Tabla de clientes
CREATE TABLE IF NOT EXISTS clientes (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  nombre VARCHAR(100) NOT NULL UNIQUE
);

-- Tabla de pedidos
CREATE TABLE IF NOT EXISTS pedidos (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  cliente VARCHAR(100) NOT NULL,
  producto VARCHAR(100) NOT NULL,
  cantidad INTEGER NOT NULL,
  costo DECIMAL(10, 2) NOT NULL,
  zona VARCHAR(50) NOT NULL,
  fecha DATE DEFAULT (CURRENT_DATE)
);

-- Insertar algunas zonas predefinidas para usar en la aplicación
CREATE TABLE IF NOT EXISTS zonas (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  nombre VARCHAR(50) NOT NULL UNIQUE
);

-- Insertar zonas predefinidas
INSERT IGNORE INTO zonas (nombre) VALUES
  ('Bernal'),
  ('Avellaneda #1'),
  ('Avellaneda #2'),
  ('Quilmes Centro'),
  ('Solano');