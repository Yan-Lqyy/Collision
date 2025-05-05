# physics.py
import math
import random
import time

# --- Vector3 Class (remains the same) ---
class Vector3:
    # ... (no changes needed here) ...
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
    def __add__(self, other): return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)
    def __sub__(self, other): return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)
    def __mul__(self, scalar): return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)
    def __truediv__(self, scalar): return Vector3(self.x / scalar, self.y / scalar, self.z / scalar) if scalar != 0 else Vector3()
    def magnitude_sq(self): return self.x*self.x + self.y*self.y + self.z*self.z
    def magnitude(self): return math.sqrt(self.magnitude_sq())
    def normalize(self): mag = self.magnitude(); return self / mag if mag != 0 else Vector3()
    def dot(self, other): return self.x * other.x + self.y * other.y + self.z * other.z
    def to_list(self): return [self.x, self.y, self.z]
    def __repr__(self): return f"Vector3({self.x:.2f}, {self.y:.2f}, {self.z:.2f})"


# --- Sphere Class (remains the same) ---
class Sphere:
    _id_counter = 0
    def __init__(self, position: Vector3, velocity: Vector3, radius: float, mass: float):
        self.id = Sphere._id_counter
        Sphere._id_counter += 1
        self.position = position
        self.velocity = velocity
        self.radius = max(0.1, float(radius))
        self.mass = max(0.1, float(mass))

    def update(self, dt: float):
        self.position += self.velocity * dt

    def get_state(self):
        return {
            "id": self.id,
            "position": self.position.to_list(),
            "radius": self.radius
        }

# --- Simulation Class ---
class Simulation:
    def __init__(self, bounds_min: Vector3, bounds_max: Vector3):
        self.spheres = []
        self.bounds_min = bounds_min
        self.bounds_max = bounds_max
        self.last_step_time = time.monotonic()

    def add_sphere(self, sphere: Sphere):
        """Adds a pre-created sphere object to the simulation."""
        # Note: Assumes this is called within a lock in app.py
        self.spheres.append(sphere)
        print(f"Physics: Added sphere {sphere.id}. Total spheres: {len(self.spheres)}")


    def remove_sphere_by_id(self, sphere_id: int) -> bool:
        """Removes a sphere by its ID. Returns True if found and removed, False otherwise."""
        # Note: Assumes this is called within a lock in app.py
        initial_length = len(self.spheres)
        # Use list comprehension for safe removal while iterating conceptually
        self.spheres = [s for s in self.spheres if s.id != sphere_id]
        removed = len(self.spheres) < initial_length
        if removed:
             print(f"Physics: Removed sphere {sphere_id}. Total spheres: {len(self.spheres)}")
        return removed

    def _handle_wall_collisions(self, sphere: Sphere, dt: float):
        # ... (remains the same) ...
        min_pos = self.bounds_min + Vector3(sphere.radius, sphere.radius, sphere.radius)
        max_pos = self.bounds_max - Vector3(sphere.radius, sphere.radius, sphere.radius)
        damp = 0.9 # Damping factor on wall collision

        if sphere.position.x < min_pos.x:
            sphere.position.x = min_pos.x
            sphere.velocity.x *= -damp
        elif sphere.position.x > max_pos.x:
            sphere.position.x = max_pos.x
            sphere.velocity.x *= -damp

        if sphere.position.y < min_pos.y:
            sphere.position.y = min_pos.y
            sphere.velocity.y *= -damp
        elif sphere.position.y > max_pos.y:
            sphere.position.y = max_pos.y
            sphere.velocity.y *= -damp

        if sphere.position.z < min_pos.z:
            sphere.position.z = min_pos.z
            sphere.velocity.z *= -damp
        elif sphere.position.z > max_pos.z:
            sphere.position.z = max_pos.z
            sphere.velocity.z *= -damp


    def _resolve_sphere_collision(self, s1: Sphere, s2: Sphere):
        # ... (remains the same - basic elastic collision) ...
         collision_normal = s1.position - s2.position
         distance_sq = collision_normal.magnitude_sq()
         min_dist = s1.radius + s2.radius
         min_dist_sq = min_dist * min_dist

         if distance_sq <= 1e-9 or distance_sq >= min_dist_sq: # Added epsilon for near-zero dist
             return

         distance = math.sqrt(distance_sq)
         collision_normal /= distance # Normalize

         # Resolve Overlap
         overlap = min_dist - distance
         inv_mass1 = 1.0 / s1.mass
         inv_mass2 = 1.0 / s2.mass
         inv_mass_sum = inv_mass1 + inv_mass2
         if inv_mass_sum > 1e-9:
             correction_ratio1 = inv_mass1 / inv_mass_sum
             correction_ratio2 = inv_mass2 / inv_mass_sum
             s1.position += collision_normal * (overlap * correction_ratio1)
             s2.position -= collision_normal * (overlap * correction_ratio2)
         else: # Handle case of effectively infinite masses
              s1.position += collision_normal * (overlap * 0.5)
              s2.position -= collision_normal * (overlap * 0.5)

         # Resolve Velocity
         relative_velocity = s1.velocity - s2.velocity
         vel_along_normal = relative_velocity.dot(collision_normal)
         if vel_along_normal > 0:
             return
         e = 1.0 # Elastic
         j = -(1 + e) * vel_along_normal
         if inv_mass_sum > 1e-9:
             j /= inv_mass_sum
         else:
             j = 0 # No impulse if total mass is infinite

         impulse = collision_normal * j
         s1.velocity += impulse * inv_mass1
         s2.velocity -= impulse * inv_mass2


    def step(self):
        """Advances the simulation by one time step."""
        # Note: Assumes this is called within a lock in app.py
        current_time = time.monotonic()
        dt = current_time - self.last_step_time
        self.last_step_time = current_time
        dt = min(dt, 1.0 / 30.0)

        if dt <= 0: return

        num_sub_steps = 5
        sub_dt = dt / num_sub_steps

        for _ in range(num_sub_steps):
            for sphere in self.spheres:
                sphere.update(sub_dt) # Update position first

            for sphere in self.spheres:
                self._handle_wall_collisions(sphere, sub_dt) # Handle wall bounds

            num_spheres = len(self.spheres) # Check collisions
            for i in range(num_spheres):
                for j in range(i + 1, num_spheres):
                     # Ensure spheres still exist (might have been removed between API calls)
                     # This check is less critical now with locking, but doesn't hurt
                     if self.spheres[i] and self.spheres[j]:
                          self._resolve_sphere_collision(self.spheres[i], self.spheres[j])


    def get_state(self):
        """Returns the state of all spheres."""
        # Note: Assumes this is called within a lock in app.py
        return [s.get_state() for s in self.spheres]

    def reset(self):
        """Resets the simulation to an initial state."""
        # Note: Assumes this is called within a lock in app.py
        Sphere._id_counter = 0
        self.spheres = []
        self.last_step_time = time.monotonic()
        # Add initial spheres
        self.add_sphere(Sphere(Vector3(-5, 0, 0), Vector3(15, 5, 2), 1.0, 1.0))
        self.add_sphere(Sphere(Vector3(5, 1, -1), Vector3(-10, 2, -3), 1.5, 3.375)) # Mass ~ R^3
        self.add_sphere(Sphere(Vector3(0, -6, 2), Vector3(2, 10, 0), 0.8, 0.512))
        self.add_sphere(Sphere(Vector3(0, 6, -2), Vector3(-3, -12, 5), 1.2, 1.728))
        for _ in range(6):
             pos = Vector3(random.uniform(self.bounds_min.x+1, self.bounds_max.x-1),
                           random.uniform(self.bounds_min.y+1, self.bounds_max.y-1),
                           random.uniform(self.bounds_min.z+1, self.bounds_max.z-1))
             vel = Vector3(random.uniform(-8, 8), random.uniform(-8, 8), random.uniform(-8, 8))
             radius = random.uniform(0.3, 0.8)
             mass = max(0.1, (4/3) * math.pi * (radius**3))
             self.add_sphere(Sphere(pos, vel, radius, mass))

# --- Simulation Singleton ---
BOUNDS_MIN = Vector3(-15, -10, -15)
BOUNDS_MAX = Vector3(15, 10, 15)
simulation_instance = Simulation(BOUNDS_MIN, BOUNDS_MAX)
# No initial reset here, let the reset route handle it or do it after thread start if needed.
# Initial state will be empty until first reset or add.