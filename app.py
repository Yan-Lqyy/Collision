# app.py
from flask import Flask, jsonify, render_template, send_from_directory, request # Added 'request'
import threading
import time
import math # Added for mass calculation if needed

# Import the simulation instance and classes from physics.py
from physics import simulation_instance, BOUNDS_MIN, BOUNDS_MAX, Sphere, Vector3 # Added Sphere, Vector3

app = Flask(__name__, static_folder='static', template_folder='templates')

# --- Simulation Runner ---
simulation_active = True
simulation_thread = None
# Use a lock for modifications to the spheres list to improve thread safety
simulation_lock = threading.Lock()

def run_simulation_background():
    """Function to run the simulation loop in a separate thread."""
    print("Simulation thread started.")
    while simulation_active:
        start_time = time.monotonic()
        # Acquire lock before stepping (which reads/modifies sphere list)
        with simulation_lock:
             simulation_instance.step() # Step modifies sphere positions/velocities
        # Release lock happens automatically exiting 'with' block

        end_time = time.monotonic()
        sleep_time = (1.0 / 60.0) - (end_time - start_time)
        if sleep_time > 0:
            time.sleep(sleep_time)
    print("Simulation thread stopped.")

# --- Flask Routes ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    """Serves static files."""
    return send_from_directory('static', path)

@app.route('/api/state')
def get_state():
    """API endpoint to get the current state of all spheres."""
    # Acquire lock briefly to safely get the current state
    with simulation_lock:
        sphere_state = simulation_instance.get_state() # get_state reads sphere list

    bounds = {
        'min': BOUNDS_MIN.to_list(),
        'max': BOUNDS_MAX.to_list()
    }
    return jsonify({"spheres": sphere_state, "bounds": bounds})

@app.route('/api/reset', methods=['POST'])
def reset_simulation():
    """API endpoint to reset the simulation."""
    print("Resetting simulation...")
    # Acquire lock before modifying the simulation state
    with simulation_lock:
        simulation_instance.reset()
    return jsonify({"message": "Simulation reset successfully."})

@app.route('/api/add_sphere', methods=['POST'])
def add_sphere():
    """API endpoint to add a new sphere."""
    data = request.get_json()
    print(f"Received request to add sphere: {data}")

    try:
        # Basic validation
        if not all(k in data for k in ('position', 'velocity', 'radius')):
             raise ValueError("Missing required fields in request data.")
        if not (isinstance(data['position'], list) and len(data['position']) == 3 and
                isinstance(data['velocity'], list) and len(data['velocity']) == 3 and
                isinstance(data['radius'], (int, float))):
            raise ValueError("Invalid data types or list lengths.")

        pos_list = data['position']
        vel_list = data['velocity']
        radius = float(data['radius'])

        if radius <= 0:
            raise ValueError("Radius must be positive.")

        position = Vector3(pos_list[0], pos_list[1], pos_list[2])
        velocity = Vector3(vel_list[0], vel_list[1], vel_list[2])

        # Simple mass calculation (e.g., proportional to volume)
        mass = (4/3) * math.pi * (radius ** 3) # Assuming density = 1
        mass = max(0.1, mass) # Ensure minimum mass

        new_sphere = Sphere(position, velocity, radius, mass)

        # Acquire lock before adding to the simulation's sphere list
        with simulation_lock:
            simulation_instance.add_sphere(new_sphere) # Use the existing add_sphere method

        print(f"Added sphere with ID: {new_sphere.id}")
        return jsonify({"message": "Sphere added successfully", "id": new_sphere.id}), 200

    except (ValueError, TypeError, KeyError) as e:
        print(f"Error adding sphere: {e}")
        return jsonify({"error": str(e)}), 400 # Bad Request
    except Exception as e:
         print(f"Unexpected error adding sphere: {e}")
         return jsonify({"error": "An internal error occurred"}), 500


@app.route('/api/delete_sphere', methods=['POST']) # Using POST for simplicity
def delete_sphere():
    """API endpoint to delete a sphere by its ID."""
    data = request.get_json()
    print(f"Received request to delete sphere: {data}")

    try:
        if 'id' not in data or not isinstance(data['id'], int):
             raise ValueError("Missing or invalid 'id' field.")

        sphere_id_to_delete = data['id']

        # Acquire lock before removing from the simulation's sphere list
        with simulation_lock:
            removed = simulation_instance.remove_sphere_by_id(sphere_id_to_delete)

        if removed:
            print(f"Deleted sphere with ID: {sphere_id_to_delete}")
            return jsonify({"message": f"Sphere {sphere_id_to_delete} deleted successfully."}), 200
        else:
            print(f"Sphere with ID {sphere_id_to_delete} not found for deletion.")
            return jsonify({"error": f"Sphere with ID {sphere_id_to_delete} not found."}), 404 # Not Found

    except (ValueError, TypeError, KeyError) as e:
         print(f"Error deleting sphere: {e}")
         return jsonify({"error": str(e)}), 400 # Bad Request
    except Exception as e:
         print(f"Unexpected error deleting sphere: {e}")
         return jsonify({"error": "An internal error occurred"}), 500


# --- Main Execution ---
if __name__ == '__main__':
    simulation_active = True
    simulation_thread = threading.Thread(target=run_simulation_background, daemon=True)
    simulation_thread.start()

    print("Starting Flask server...")
    app.run(debug=True, host='0.0.0.0', use_reloader=False)

    simulation_active = False
    if simulation_thread:
        simulation_thread.join(timeout=1.0)
    print("Flask server stopped.")