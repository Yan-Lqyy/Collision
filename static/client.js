// static/client.js
import * as THREE from 'three';
// Optional: Import OrbitControls
// import { OrbitControls } from 'OrbitControls'; // Adjust path if needed

// --- Configuration ---
const POLLING_INTERVAL_MS = 30;

// --- Global Variables ---
let scene, camera, renderer, controls;
let sphereMeshes = {}; // Map sphere ID to Three.js Mesh { id: mesh }
let boundsBoxMesh = null;
let lastState = null;
const raycaster = new THREE.Raycaster(); // For clicking spheres
const mouse = new THREE.Vector2(); // To store normalized mouse coords

// --- Initialization ---
function init() {
    // ... (Scene, Camera, Renderer, Lighting setup remains the same) ...
    scene = new THREE.Scene();
    const container = document.getElementById('simulationCanvasContainer');
    const aspect = container.clientWidth / container.clientHeight;
    camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 1000);
    camera.position.set(0, 5, 30);
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);
    const ambientLight = new THREE.AmbientLight(0xcccccc, 0.6);
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 10, 7.5);
    scene.add(directionalLight);


    // Controls (Optional but highly recommended)
    // controls = new OrbitControls(camera, renderer.domElement);
    // controls.enableDamping = true;
    // controls.dampingFactor = 0.05;

    // --- Event Listeners ---
    window.addEventListener('resize', onWindowResize, false);
    document.getElementById('resetButton').addEventListener('click', handleResetSimulation);
    document.getElementById('addSphereButton').addEventListener('click', handleAddSphere);
    renderer.domElement.addEventListener('click', handleCanvasClick, false); // Listener for sphere deletion

    // Start fetching state and the animation loop
    fetchState();
    setInterval(fetchState, POLLING_INTERVAL_MS);
    animate();
}

// --- State Update and Rendering ---

function fetchState() {
    // ... (fetchState remains the same, fetching from /api/state) ...
    fetch('/api/state')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            lastState = data;
            if (data.bounds && (!boundsBoxMesh || !boundsAreEqual(boundsBoxMesh.userData.bounds, data.bounds))) {
                 updateBoundsVisual(data.bounds);
            }
        })
        .catch(error => {
            console.error('Error fetching simulation state:', error);
        });
}


function updateScene() {
    // ... (updateScene remains largely the same, creating/updating/removing meshes) ...
     if (!lastState || !lastState.spheres) return;

    const receivedSphereIds = new Set();

    lastState.spheres.forEach(sphereData => {
        receivedSphereIds.add(sphereData.id);
        let mesh = sphereMeshes[sphereData.id];

        if (!mesh) {
            const geometry = new THREE.SphereGeometry(sphereData.radius, 16, 12);
            const color = new THREE.Color().setHSL((sphereData.id * 0.1) % 1.0, 0.7, 0.6);
            const material = new THREE.MeshStandardMaterial({
                 color: color,
                 metalness: 0.3,
                 roughness: 0.6
            });
            mesh = new THREE.Mesh(geometry, material);
            mesh.userData = { id: sphereData.id }; // Store ID in userData
            scene.add(mesh);
            sphereMeshes[sphereData.id] = mesh;
        } else {
             if (mesh.geometry.parameters.radius !== sphereData.radius) {
                  mesh.geometry.dispose();
                  mesh.geometry = new THREE.SphereGeometry(sphereData.radius, 16, 12);
             }
        }
        mesh.position.fromArray(sphereData.position);
    });

    // Remove meshes for spheres no longer present in backend state
    for (const id in sphereMeshes) {
        if (!receivedSphereIds.has(parseInt(id))) {
            removeMesh(id); // Use helper function
        }
    }
}

function updateBoundsVisual(boundsData) {
    // ... (updateBoundsVisual remains the same) ...
    if (!boundsData || !boundsData.min || !boundsData.max) return;
    if (boundsBoxMesh) {
        scene.remove(boundsBoxMesh);
        boundsBoxMesh.geometry.dispose();
        boundsBoxMesh.material.dispose();
    }
    const min = new THREE.Vector3().fromArray(boundsData.min);
    const max = new THREE.Vector3().fromArray(boundsData.max);
    const size = max.clone().sub(min);
    const center = min.clone().add(size.clone().multiplyScalar(0.5));
    const boxGeometry = new THREE.BoxGeometry(size.x, size.y, size.z);
    const edgesGeometry = new THREE.EdgesGeometry(boxGeometry);
    const material = new THREE.LineBasicMaterial({ color: 0x555555 });
    boundsBoxMesh = new THREE.LineSegments(edgesGeometry, material);
    boundsBoxMesh.position.copy(center);
    boundsBoxMesh.userData.bounds = boundsData;
    scene.add(boundsBoxMesh);
}

function boundsAreEqual(b1, b2) {
    // ... (boundsAreEqual remains the same) ...
     if (!b1 || !b2) return false;
    return (
        b1.min[0] === b2.min[0] && b1.min[1] === b2.min[1] && b1.min[2] === b2.min[2] &&
        b1.max[0] === b2.max[0] && b1.max[1] === b2.max[1] && b1.max[2] === b2.max[2]
    );
}


// --- Animation Loop ---
function animate() {
    requestAnimationFrame(animate);
    // if (controls) controls.update();
    updateScene(); // Update based on fetched state
    renderer.render(scene, camera);
}

// --- Event Handlers ---
function onWindowResize() {
    // ... (onWindowResize remains the same) ...
    const container = document.getElementById('simulationCanvasContainer');
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
}


function handleResetSimulation() {
    // ... (handleResetSimulation remains the same, calls /api/reset) ...
     console.log("Requesting simulation reset...");
    fetch('/api/reset', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log(data.message);
            // Clear existing meshes immediately
            clearAllMeshes();
            lastState = null; // Clear local state
        })
        .catch(error => {
            console.error('Error resetting simulation:', error);
        });
}

function handleAddSphere() {
    console.log("Attempting to add sphere...");
    // Gather data from form
    const position = [
        parseFloat(document.getElementById('posX').value) || 0,
        parseFloat(document.getElementById('posY').value) || 0,
        parseFloat(document.getElementById('posZ').value) || 0
    ];
    const velocity = [
        parseFloat(document.getElementById('velX').value) || 0,
        parseFloat(document.getElementById('velY').value) || 0,
        parseFloat(document.getElementById('velZ').value) || 0
    ];
    const radius = Math.max(0.1, parseFloat(document.getElementById('radius').value) || 1.0); // Ensure minimum radius

    const sphereData = { position, velocity, radius };

    // Send data to backend
    fetch('/api/add_sphere', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(sphereData),
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log(data.message, "New sphere ID:", data.id);
        // No need to add mesh here, the regular updateScene will handle it
        // when the next /api/state call includes the new sphere.
    })
    .catch(error => {
        console.error('Error adding sphere:', error);
        alert("Failed to add sphere. Check console for details."); // User feedback
    });
}

function handleCanvasClick(event) {
    // Calculate mouse position in normalized device coordinates (-1 to +1)
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    // Update the picking ray with the camera and mouse position
    raycaster.setFromCamera(mouse, camera);

    // Calculate objects intersecting the picking ray
    const intersects = raycaster.intersectObjects(Object.values(sphereMeshes)); // Check against current sphere meshes

    if (intersects.length > 0) {
        // Find the closest intersected sphere mesh
        const clickedMesh = intersects[0].object;
        const sphereId = clickedMesh.userData.id;

        if (sphereId !== undefined) {
            console.log(`Clicked sphere ID: ${sphereId}`);
            handleDeleteSphere(sphereId);
        } else {
             console.warn("Clicked mesh does not have a sphere ID.", clickedMesh);
        }
    }
}

function handleDeleteSphere(sphereId) {
    console.log(`Requesting deletion of sphere ID: ${sphereId}`);

    // Optimistic UI update: Remove the mesh immediately for responsiveness
    removeMesh(sphereId);

    // Send request to backend
    fetch('/api/delete_sphere', {
        method: 'POST', // Or 'DELETE' if you configure the backend route for it
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id: sphereId }),
    })
    .then(response => {
        if (!response.ok) {
             // If backend fails, maybe add the mesh back? Or just log error.
            console.error(`Backend failed to delete sphere ${sphereId}. Status: ${response.status}`);
            // Re-fetching state should eventually correct the UI, but could cause flicker.
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log(data.message);
        // No need to remove mesh again, already done optimistically.
    })
    .catch(error => {
        console.error('Error deleting sphere:', error);
        // Consider adding the mesh back here if optimistic update failed verification
    });
}

// --- Helper Functions ---
function removeMesh(sphereId) {
    const meshToRemove = sphereMeshes[sphereId];
    if (meshToRemove) {
        scene.remove(meshToRemove);
        // Important: Dispose of geometry and material to free up GPU memory
        if (meshToRemove.geometry) meshToRemove.geometry.dispose();
        if (meshToRemove.material) meshToRemove.material.dispose();
        delete sphereMeshes[sphereId]; // Remove from our map
        console.log(`Removed mesh for sphere ${sphereId} from scene.`);
    }
}

function clearAllMeshes() {
     for (const id in sphereMeshes) {
        removeMesh(id);
    }
    sphereMeshes = {}; // Ensure the map is empty
}


// --- Start ---
init();