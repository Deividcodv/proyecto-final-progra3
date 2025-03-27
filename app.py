import time
import random
import json
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import threading
import queue
from datetime import datetime
from flask_socketio import SocketIO

app = Flask(__name__, template_folder='templetes')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Database for tracking clients
clients_db = {}
db_lock = threading.Lock()

# Queue and counter setup
cola_caja = queue.Queue()
cola_servicio_cliente = queue.Queue()
contador_caja = 1
contador_servicio = 1
contador_lock = threading.Lock()
cajeros_disponibles = 2
servicio_cliente_disponibles = 1
cajeros_lock = threading.Lock()
servicio_lock = threading.Lock()

def generate_ticket(tipo_servicio):
    global contador_caja, contador_servicio
    with contador_lock:
        if tipo_servicio == 'caja':
            numero_ticket = contador_caja
            contador_caja += 1
            cola_caja.put(numero_ticket)
            posicion = cola_caja.qsize()
            tiempo_estimado = posicion * 7.5
            prefijo = 'C'
        else:  # servicio_cliente
            numero_ticket = contador_servicio
            contador_servicio += 1
            cola_servicio_cliente.put(numero_ticket)
            posicion = cola_servicio_cliente.qsize()
            tiempo_estimado = posicion * 11
            prefijo = 'S'
    
    ticket_formateado = f"{prefijo}{numero_ticket:03d}"
    return ticket_formateado, posicion, int(tiempo_estimado)

# Existing processing functions (procesar_caja, procesar_servicio)
def procesar_caja(numero_ticket):
    tiempo_atencion = random.randint(5, 10)
    print(f"Procesando ticket {numero_ticket} en CAJA - tiempo estimado: {tiempo_atencion} segundos")
    time.sleep(tiempo_atencion)
    print(f"Ticket {numero_ticket} de CAJA ha sido atendido.")
    global cajeros_disponibles
    with cajeros_lock:
        cajeros_disponibles += 1
    socketio.emit('queue_update', get_queue_status())

def procesar_servicio(numero_ticket):
    tiempo_atencion = random.randint(7, 15)
    print(f"Procesando ticket {numero_ticket} en SERVICIO AL CLIENTE - tiempo estimado: {tiempo_atencion} segundos")
    time.sleep(tiempo_atencion)
    print(f"Ticket {numero_ticket} de SERVICIO AL CLIENTE ha sido atendido.")
    global servicio_cliente_disponibles
    with servicio_lock:
        servicio_cliente_disponibles += 1
    socketio.emit('queue_update', get_queue_status())

# Queue monitoring threads
def monitor_cola_caja():
    while True:
        global cajeros_disponibles
        if not cola_caja.empty():
            with cajeros_lock:
                if cajeros_disponibles > 0:
                    cajeros_disponibles -= 1
                    ticket = cola_caja.get()
                    threading.Thread(target=procesar_caja, args=(ticket,)).start()
        time.sleep(1)

def monitor_cola_servicio():
    while True:
        global servicio_cliente_disponibles
        if not cola_servicio_cliente.empty():
            with servicio_lock:
                if servicio_cliente_disponibles > 0:
                    servicio_cliente_disponibles -= 1
                    ticket = cola_servicio_cliente.get()
                    threading.Thread(target=procesar_servicio, args=(ticket,)).start()
        time.sleep(1)

# API Endpoints
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/ticket', methods=['POST'])
def external_ticket():
    data = request.json
    if not data or 'tipo_servicio' not in data:
        return jsonify({'error': 'Invalid request'}), 400
    
    client_id = data.get('client_id', f"EXT-{random.randint(1000,9999)}")
    ticket, pos, wait = generate_ticket(data['tipo_servicio'])
    
    with db_lock:
        clients_db[client_id] = {
            'ticket': ticket,
            'status': 'waiting',
            'timestamp': datetime.now().isoformat(),
            'service': data['tipo_servicio']
        }
    
    socketio.emit('queue_update', get_queue_status())
    return jsonify({
        'ticket': ticket,
        'position': pos,
        'wait_time': wait,
        'client_id': client_id
    })

@app.route('/api/attended/<client_id>', methods=['POST'])
def mark_attended(client_id):
    with db_lock:
        if client_id in clients_db:
            clients_db[client_id]['status'] = 'attended'
            clients_db[client_id]['attended_at'] = datetime.now().isoformat()
            socketio.emit('attended_update', {'client_id': client_id})
            return jsonify({'status': 'success'})
    return jsonify({'error': 'Client not found'}), 404

@app.route('/api/status/<client_id>', methods=['GET'])
def client_status(client_id):
    with db_lock:
        if client_id in clients_db:
            return jsonify(clients_db[client_id])
    return jsonify({'error': 'Client not found'}), 404

def get_queue_status():
    return {
        'caja': {
            'waiting': cola_caja.qsize(),
            'available': cajeros_disponibles
        },
        'servicio_cliente': {
            'waiting': cola_servicio_cliente.qsize(),
            'available': servicio_cliente_disponibles
        }
    }

if __name__ == '__main__':
    threading.Thread(target=monitor_cola_caja, daemon=True).start()
    threading.Thread(target=monitor_cola_servicio, daemon=True).start()
    socketio.run(app, debug=True, port=5000)
