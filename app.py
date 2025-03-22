import time
import random
import json
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import threading
import queue

app = Flask(__name__)
CORS(app)  # Esto permite solicitudes CORS

# Colas para cada servicio
cola_caja = queue.Queue()
cola_servicio_cliente = queue.Queue()

# Contadores para números de ticket
contador_caja = 1
contador_servicio = 1

# Semáforo para proteger acceso a contadores
contador_lock = threading.Lock()

# Estado de los cajeros
cajeros_disponibles = 2  # Puedes ajustar este número
servicio_cliente_disponibles = 1  # Puedes ajustar este número

cajeros_lock = threading.Lock()
servicio_lock = threading.Lock()

# Función para procesar cliente en caja
def procesar_caja(numero_ticket):
    tiempo_atencion = random.randint(5, 10)
    print(f"Procesando ticket {numero_ticket} en CAJA - tiempo estimado: {tiempo_atencion} segundos")
    time.sleep(tiempo_atencion)
    print(f"Ticket {numero_ticket} de CAJA ha sido atendido.")
    
    # Liberar cajero
    global cajeros_disponibles
    with cajeros_lock:
        cajeros_disponibles += 1

# Función para procesar cliente en servicio al cliente
def procesar_servicio(numero_ticket):
    tiempo_atencion = random.randint(7, 15)
    print(f"Procesando ticket {numero_ticket} en SERVICIO AL CLIENTE - tiempo estimado: {tiempo_atencion} segundos")
    time.sleep(tiempo_atencion)
    print(f"Ticket {numero_ticket} de SERVICIO AL CLIENTE ha sido atendido.")
    
    # Liberar servicio al cliente
    global servicio_cliente_disponibles
    with servicio_lock:
        servicio_cliente_disponibles += 1

# Hilo para monitorear la cola de caja
def monitor_cola_caja():
    while True:
        global cajeros_disponibles
        if not cola_caja.empty():
            with cajeros_lock:
                if cajeros_disponibles > 0:
                    cajeros_disponibles -= 1
                    ticket = cola_caja.get()
                    # Iniciar un hilo para atender este cliente
                    threading.Thread(target=procesar_caja, args=(ticket,)).start()
        time.sleep(1)  # Revisar cada segundo

# Hilo para monitorear la cola de servicio al cliente
def monitor_cola_servicio():
    while True:
        global servicio_cliente_disponibles
        if not cola_servicio_cliente.empty():
            with servicio_lock:
                if servicio_cliente_disponibles > 0:
                    servicio_cliente_disponibles -= 1
                    ticket = cola_servicio_cliente.get()
                    # Iniciar un hilo para atender este cliente
                    threading.Thread(target=procesar_servicio, args=(ticket,)).start()
        time.sleep(1)  # Revisar cada segundo

# Ruta principal
@app.route('/')
def index():
    return render_template('index.html')

# Endpoint para obtener un nuevo ticket
@app.route('/nuevo-ticket', methods=['POST'])
def nuevo_ticket():
    data = request.json
    tipo_servicio = data.get('tipo_servicio')
    
    global contador_caja, contador_servicio
    
    if tipo_servicio == 'caja':
        with contador_lock:
            numero_ticket = contador_caja
            contador_caja += 1
        cola_caja.put(numero_ticket)
        posicion = cola_caja.qsize()
        tiempo_estimado = posicion * 7.5  # Promedio entre 5 y 10 segundos
        prefijo = 'C'
    
    elif tipo_servicio == 'servicio_cliente':
        with contador_lock:
            numero_ticket = contador_servicio
            contador_servicio += 1
        cola_servicio_cliente.put(numero_ticket)
        posicion = cola_servicio_cliente.qsize()
        tiempo_estimado = posicion * 11  # Promedio entre 7 y 15 segundos
        prefijo = 'S'
    
    else:
        return jsonify({'error': 'Tipo de servicio no válido'}), 400
    
    # Formatear el número de ticket (por ejemplo, C001 o S001)
    ticket_formateado = f"{prefijo}{numero_ticket:03d}"
    
    return jsonify({
        'ticket': ticket_formateado,
        'posicion': posicion,
        'tiempo_estimado': int(tiempo_estimado)
    })

# Endpoint para verificar el estado de las colas
@app.route('/estado-colas', methods=['GET'])
def estado_colas():
    return jsonify({
        'caja': {
            'personas_esperando': cola_caja.qsize(),
            'cajeros_disponibles': cajeros_disponibles
        },
        'servicio_cliente': {
            'personas_esperando': cola_servicio_cliente.qsize(),
            'agentes_disponibles': servicio_cliente_disponibles
        }
    })

if __name__ == '__main__':
    # Iniciar hilos para monitorear colas
    threading.Thread(target=monitor_cola_caja, daemon=True).start()
    threading.Thread(target=monitor_cola_servicio, daemon=True).start()
    
    print("Sistema de colas iniciado!")
    app.run(debug=True, port=5000)
