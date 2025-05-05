# Interactive 3D Sphere Collision Simulation

This project simulates the physical collisions between multiple spheres within a bounding box using Python for the physics backend and Flask/Three.js for a web-based 3D visualization. Users can interactively add new spheres with custom properties and delete existing spheres by clicking on them.

## Core Physics Concepts & Implementation

The simulation models the motion and interaction of spheres based on classical mechanics principles, simplified for this implementation.

### 1. Sphere Representation (`physics.py: Sphere` class)

Each sphere is represented by its physical state:

*   **`position` (Vector3):** The 3D coordinates (x, y, z) of the sphere's center.
*   **`velocity` (Vector3):** The rate of change of the position (linear velocity).
*   **`radius` (float):** The sphere's radius.
*   **`mass` (float):** The sphere's mass. Currently calculated based on volume (assuming constant density) when adding spheres, ensuring a minimum mass.
*   **`id` (int):** A unique identifier for tracking and managing spheres across the backend and frontend.

*(Note: Angular velocity and moment of inertia are **not** currently implemented, so rotational dynamics are ignored.)*

### 2. Motion Between Collisions (`physics.py: Sphere.update`, `Simulation.step`)

When spheres are not colliding, their motion is updated using **Euler integration** over small time steps (`dt`):

*   `new_position = old_position + velocity * dt`
*   `velocity` remains constant between collisions (assuming no external forces like gravity or friction are currently implemented).

To improve stability and accuracy compared to a single large step, the `Simulation.step` method implements **sub-stepping**:
*   The total time delta (`dt`) since the last frame is calculated.
*   This `dt` is divided into several smaller `sub_dt` intervals.
*   The position updates and collision checks/resolutions are performed multiple times within a single `step` call, using `sub_dt`. This reduces the chance of spheres passing through each other (tunneling) between checks.

```python
# physics.py - Simulation.step() excerpt
def step(self):
    # ... calculate dt ...
    num_sub_steps = 5 # Perform multiple smaller steps
    sub_dt = dt / num_sub_steps

    for _ in range(num_sub_steps):
        # 1. Update positions using sub_dt
        for sphere in self.spheres:
            sphere.update(sub_dt)

        # 2. Handle Collisions (Walls and Sphere-Sphere) using updated positions
        # ... collision handling calls ...
```

### 3. Collision Detection

Collisions are checked during each sub-step:

*   **Sphere-Wall Collision (`physics.py: Simulation._handle_wall_collisions`)**:
    *   Checks if a sphere's boundary (`position +/- radius`) exceeds the simulation's Axis-Aligned Bounding Box (AABB) defined by `bounds_min` and `bounds_max`.
    *   Implemented by simple coordinate comparison.

*   **Sphere-Sphere Collision (`physics.py: Simulation._resolve_sphere_collision`)**:
    *   For every unique pair of spheres (i, j), the distance between their centers is calculated: `distance = ||pos_i - pos_j||`.
    *   A collision is detected if `distance <= radius_i + radius_j`.
    *   This is currently an O(N^2) check, which can become slow with many spheres.

```python
# physics.py - _resolve_sphere_collision() excerpt (Detection part)
def _resolve_sphere_collision(self, s1: Sphere, s2: Sphere):
    collision_normal = s1.position - s2.position
    distance_sq = collision_normal.magnitude_sq()
    min_dist = s1.radius + s2.radius
    min_dist_sq = min_dist * min_dist

    # Check if distance squared is less than minimum distance squared
    if distance_sq <= 1e-9 or distance_sq >= min_dist_sq:
        return # No collision or already separated
    # ... collision resolution follows ...
```

### 4. Collision Resolution

When a collision is detected, the simulation needs to adjust the spheres' states.

*   **Overlap Resolution (`physics.py: Simulation._resolve_sphere_collision`)**:
    *   Because discrete time steps are used, spheres might slightly overlap when a collision is detected.
    *   To fix this and prevent instability, the spheres are pushed apart along the collision normal (`n = normalize(pos1 - pos2)`).
    *   The amount each sphere moves is proportional to its inverse mass (lighter spheres move more), ensuring the center of mass is not affected by the separation.
    *   `overlap = (radius1 + radius2) - distance`
    *   `correction1 = n * overlap * (inv_mass1 / (inv_mass1 + inv_mass2))`
    *   `correction2 = -n * overlap * (inv_mass2 / (inv_mass1 + inv_mass2))`
    *   `s1.position += correction1`
    *   `s2.position += correction2`

*   **Velocity Resolution (Sphere-Sphere) (`physics.py: Simulation._resolve_sphere_collision`)**:
    *   This implementation uses a simplified model for **perfectly elastic collisions (coefficient of restitution `e = 1`)** and ignores friction and rotation.
    *   The goal is to calculate the change in velocity (impulse) along the collision normal.
    *   **Steps:**
        1.  Calculate the relative velocity: `v_rel = v1 - v2`.
        2.  Calculate the component of relative velocity along the collision normal: `vel_along_normal = v_rel.dot(n)`.
        3.  If `vel_along_normal > 0`, the spheres are already moving apart, so do nothing.
        4.  Calculate the impulse magnitude (`j`) needed to reverse the relative velocity along the normal according to the restitution `e`:
            `j = -(1 + e) * vel_along_normal / (inv_mass1 + inv_mass2)`
        5.  Calculate the impulse vector: `impulse_vec = n * j`.
        6.  Apply the impulse to each sphere's velocity based on its mass:
            `v1_new = v1 + impulse_vec / mass1`
            `v2_new = v2 - impulse_vec / mass2`

*   **Velocity Resolution (Sphere-Wall) (`physics.py: Simulation._handle_wall_collisions`)**:
    *   Very simple: The velocity component perpendicular to the wall is reversed and slightly dampened (multiplied by `-0.9`) to simulate some energy loss.
    *   The sphere's position is also clamped to the boundary edge to resolve overlap.

## Web Application Architecture & Implementation

The simulation is presented through a web interface using a client-server architecture.

### 1. Backend (`app.py`, `physics.py`)

*   **Framework:** Flask is used as the web server framework.
*   **Role:**
    *   Runs the core physics simulation (`Simulation` instance from `physics.py`) in a **background thread** (`run_simulation_background`). This allows the simulation to advance independently of user requests.
    *   Serves the static frontend files (HTML, CSS, JavaScript).
    *   Provides a RESTful API for the frontend to interact with the simulation.
    *   Manages **thread safety** using a `threading.Lock` (`simulation_lock`) when accessing or modifying the shared `simulation_instance.spheres` list from different threads (the simulation thread and Flask's request handler threads).

*   **API Endpoints:**
    *   `GET /`: Serves the main `index.html` page.
    *   `GET /static/<path>`: Serves static files (CSS, JS).
    *   `GET /api/state`: Returns the current state (ID, position, radius) of all spheres and the simulation bounds as JSON. Called periodically by the frontend.
    *   `POST /api/reset`: Resets the simulation to its initial state by calling `simulation_instance.reset()`.
    *   `POST /api/add_sphere`: Receives JSON data (position, velocity, radius) from the frontend, creates a new `Sphere` object, and adds it to the simulation via `simulation_instance.add_sphere()`.
    *   `POST /api/delete_sphere`: Receives a sphere ID as JSON, removes the corresponding sphere from the simulation via `simulation_instance.remove_sphere_by_id()`.

### 2. Frontend (`templates/index.html`, `static/client.js`, `static/style.css`)

*   **Technology:** Standard HTML, CSS, and JavaScript, utilizing the **Three.js** library for WebGL-based 3D rendering.
*   **Role:**
    *   Displays the 3D visualization of the spheres and bounding box.
    *   Provides UI controls (forms, buttons) for user interaction.
    *   Communicates with the backend API to get simulation state and send user commands.

*   **Key Components (`static/client.js`):**
    *   **Three.js Setup:** Initializes the `Scene`, `PerspectiveCamera`, `WebGLRenderer`, and basic lighting (`AmbientLight`, `DirectionalLight`).
    *   **State Synchronization:**
        *   Uses `setInterval` to call `fetchState()` periodically (e.g., every 30ms).
        *   `fetchState()` sends a GET request to `/api/state`.
        *   The received sphere data (`lastState`) is stored locally.
    *   **Rendering Loop (`animate`):**
        *   Uses `requestAnimationFrame` for smooth animation.
        *   Calls `updateScene()` in each frame.
        *   Calls `renderer.render(scene, camera)`.
    *   **Scene Management (`updateScene`):**
        *   Compares the `lastState` received from the backend with the current Three.js meshes stored in the `sphereMeshes` map (using sphere IDs as keys).
        *   **Creates** new `THREE.Mesh` objects (with `SphereGeometry` and `MeshStandardMaterial`) for spheres present in the backend state but not in the frontend map.
        *   **Updates** the `position` (and potentially `scale` if radius changed) of existing meshes.
        *   **Removes** meshes from the scene (and disposes of their geometry/material) if their corresponding sphere ID is no longer present in the backend state. This handles deletions initiated by other clients or the reset action.
        *   Updates the bounding box visualization (`boundsBoxMesh`).
    *   **User Interaction:**
        *   `handleAddSphere`: Reads values from the input form, packages them as JSON, and sends a POST request to `/api/add_sphere`.
        *   `handleCanvasClick`: Calculates normalized mouse coordinates. Uses `THREE.Raycaster` to determine which sphere (if any) was clicked in the 3D scene.
        *   `handleDeleteSphere`: If a sphere is clicked, this function is called with the sphere's ID. It performs an **optimistic UI update** (removes the mesh immediately using `removeMesh`) and sends a POST request to `/api/delete_sphere`.
        *   `handleResetSimulation`: Sends a POST request to `/api/reset` and clears all local meshes (`clearAllMeshes`).

*   **HTML (`templates/index.html`):**
    *   Contains the basic page structure, including the `<div>` container for the Three.js canvas.
    *   Includes the UI controls (reset button, add sphere form, delete instructions).
    *   Uses an **import map** (`<script type="importmap">`) to tell the browser how to resolve the `import * as THREE from 'three';` statement in `client.js`, mapping the specifier `"three"` to the actual path of the library file served by Flask (`/static/three.module.min.js`).

## Running the Application

1.  Ensure Python and Flask (`pip install Flask`) are installed.
2.  Place the `three.module.js` library file inside the `static/` directory.
3.  Run the Flask server from the project's root directory: `python app.py`
4.  Open a web browser and navigate to `http://127.0.0.1:5000` (or the appropriate host/port).

## Potential Improvements & Future Work

*   **Physics:**
    *   Implement more accurate integration methods (Verlet, RK4) to reduce energy drift.
    *   Add rotational dynamics (angular velocity, moment of inertia, torque).
    *   Implement friction (static and kinetic) during collisions.
    *   Implement inelastic collisions (coefficient of restitution `e < 1`).
    *   Add external forces (e.g., gravity).
    *   Optimize collision detection (e.g., spatial hashing or BVH trees) for large numbers of spheres.
*   **Web Application:**
    *   Replace polling with WebSockets for lower latency, real-time updates.
    *   Add more sophisticated UI controls (e.g., pausing, adjusting simulation parameters like restitution or timescale).
    *   Improve visual feedback (e.g., highlighting clicked sphere before deletion).
    *   Implement camera controls (like `OrbitControls` from Three.js examples) for better navigation.
    *   Add error handling and user feedback on the frontend.
