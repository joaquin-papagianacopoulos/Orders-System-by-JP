import requests

# URL base de tu API Flask
base_url = "http://localhost:5000"

# Probar una función simple como obtener clientes
try:
    response = requests.get(f"{base_url}/api/clientes", params={"buscar": ""})
    if response.status_code == 200:
        print("Conexión exitosa!")
        print("Respuesta:", response.json())
    else:
        print(f"Error: Status code {response.status_code}")
        print("Respuesta:", response.text)
except requests.exceptions.ConnectionError:
    print("Error de conexión: No se pudo conectar al servidor")
except Exception as e:
    print(f"Error inesperado: {str(e)}")