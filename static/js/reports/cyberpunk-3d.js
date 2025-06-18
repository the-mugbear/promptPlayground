// static/js/reports/cyberpunk-3d.js
// Cyberpunk 3D Visualization Engine with Binary Aesthetics

class CyberpunkVisualization {
    constructor() {
        this.scenes = {};
        this.renderers = {};
        this.cameras = {};
        this.animationFrames = {};
        this.binaryRain = {};
        
        // Cyberpunk color palette
        this.colors = {
            neonGreen: 0x00ff41,
            neonBlue: 0x0099ff,
            neonPink: 0xff0099,
            neonYellow: 0xffff00,
            darkBackground: 0x0a0a0a,
            matrixGreen: 0x00ff00,
            warningRed: 0xff3030,
            errorRed: 0xff0000,
            gridBlue: 0x004455
        };
        
        this.init();
    }

    init() {
        // Initialize after a small delay to ensure Three.js is loaded
        setTimeout(() => {
            if (typeof THREE !== 'undefined') {
                console.log('Three.js loaded, initializing cyberpunk visualizations...');
                this.createBinaryRainBackground();
            } else {
                console.error('Three.js not loaded');
            }
        }, 200);
    }

    // Create a 3D holographic pie chart with binary particle effects
    create3DPieChart(containerId, data, options = {}) {
        console.log('Creating 3D pie chart for container:', containerId);
        console.log('Chart data:', data);
        console.log('Chart options:', options);
        
        const container = document.getElementById(containerId);
        if (!container) {
            console.error('Container not found:', containerId);
            return null;
        }

        console.log('Container found, dimensions:', container.clientWidth, 'x', container.clientHeight);

        // Clear existing content
        container.innerHTML = '';
        
        const width = container.clientWidth;
        const height = container.clientHeight || 400;

        console.log('Using dimensions:', width, 'x', height);

        // Create scene, camera, renderer
        console.log('Creating Three.js scene...');
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(this.colors.darkBackground);

        const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(width, height);
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        
        console.log('Appending renderer to container...');
        container.appendChild(renderer.domElement);
        console.log('Renderer appended successfully');

        // Store references
        this.scenes[containerId] = scene;
        this.cameras[containerId] = camera;
        this.renderers[containerId] = renderer;

        // Add a simple test cube first to verify Three.js is working
        console.log('Adding test cube...');
        const testGeometry = new THREE.BoxGeometry(1, 1, 1);
        const testMaterial = new THREE.MeshBasicMaterial({ color: this.colors.neonGreen });
        const testCube = new THREE.Mesh(testGeometry, testMaterial);
        testCube.position.set(0, 0, 0);
        scene.add(testCube);
        console.log('Test cube added');

        // Add atmospheric lighting
        this.addCyberpunkLighting(scene);

        // Create the 3D pie chart
        console.log('Creating holographic pie...');
        this.createHolographicPie(scene, data, options);

        // Add binary particle system
        console.log('Adding particle system...');
        this.addBinaryParticleSystem(scene);

        // Add grid background
        console.log('Adding cyber grid...');
        this.addCyberGrid(scene);

        // Position camera
        camera.position.set(0, 5, 10);
        camera.lookAt(0, 0, 0);
        console.log('Camera positioned');

        // Start animation loop
        console.log('Starting animation loop...');
        this.animate3DChart(containerId);

        // Add mouse interaction
        console.log('Adding mouse interaction...');
        this.addMouseInteraction(containerId, camera, renderer);

        console.log('3D pie chart creation completed successfully');
        return { scene, camera, renderer };
    }

    addCyberpunkLighting(scene) {
        // Ambient light for overall illumination
        const ambientLight = new THREE.AmbientLight(this.colors.neonBlue, 0.3);
        scene.add(ambientLight);

        // Neon rim light
        const rimLight = new THREE.DirectionalLight(this.colors.neonGreen, 0.8);
        rimLight.position.set(5, 5, 5);
        rimLight.castShadow = true;
        scene.add(rimLight);

        // Pink accent light
        const accentLight = new THREE.PointLight(this.colors.neonPink, 0.6, 20);
        accentLight.position.set(-5, 3, 5);
        scene.add(accentLight);

        // Dynamic rotating light
        const dynamicLight = new THREE.SpotLight(this.colors.neonYellow, 1, 30, Math.PI / 6);
        dynamicLight.position.set(0, 10, 0);
        dynamicLight.target.position.set(0, 0, 0);
        scene.add(dynamicLight);
        scene.add(dynamicLight.target);

        // Store for animation
        scene.userData.dynamicLight = dynamicLight;
    }

    createHolographicPie(scene, data, options = {}) {
        const radius = options.radius || 3;
        const height = options.height || 0.5;
        const segments = data.length;
        
        let currentAngle = 0;
        const total = data.reduce((sum, item) => sum + item.value, 0);

        data.forEach((item, index) => {
            const segmentAngle = (item.value / total) * Math.PI * 2;
            
            // Create holographic segment
            const segment = this.createHolographicSegment(
                radius, 
                height, 
                currentAngle, 
                segmentAngle, 
                this.getSegmentColor(index),
                item
            );
            
            scene.add(segment);
            currentAngle += segmentAngle;
        });

        // Add center hologram
        this.addCenterHologram(scene, total, options);
    }

    createHolographicSegment(radius, height, startAngle, segmentAngle, color, data) {
        const group = new THREE.Group();

        // Main segment geometry
        const geometry = new THREE.CylinderGeometry(radius, radius, height, 32, 1, false, startAngle, segmentAngle);
        
        // Holographic material with glow effect
        const material = new THREE.MeshPhongMaterial({
            color: color,
            transparent: true,
            opacity: 0.8,
            emissive: color,
            emissiveIntensity: 0.3,
            side: THREE.DoubleSide
        });

        const segment = new THREE.Mesh(geometry, material);
        segment.castShadow = true;
        segment.receiveShadow = true;
        group.add(segment);

        // Add glowing edges
        const edgeGeometry = new THREE.EdgesGeometry(geometry);
        const edgeMaterial = new THREE.LineBasicMaterial({
            color: color,
            transparent: true,
            opacity: 1,
            linewidth: 3
        });
        const edges = new THREE.LineSegments(edgeGeometry, edgeMaterial);
        group.add(edges);

        // Add floating binary data streams
        this.addBinaryStream(group, radius, startAngle, segmentAngle, color);

        // Add label hologram
        this.addDataLabel(group, radius, startAngle + segmentAngle/2, data);

        // Store data for interaction
        group.userData = { data, color, startAngle, segmentAngle };

        return group;
    }

    addBinaryStream(parent, radius, startAngle, segmentAngle, color) {
        const streamCount = Math.floor(segmentAngle * 5) + 1;
        
        for (let i = 0; i < streamCount; i++) {
            const angle = startAngle + (segmentAngle * i / streamCount);
            const x = Math.cos(angle) * (radius + 1);
            const z = Math.sin(angle) * (radius + 1);
            
            // Create binary text sprites
            const binaryString = this.generateBinaryString(8);
            const sprite = this.createTextSprite(binaryString, color, 0.3);
            sprite.position.set(x, Math.random() * 2 - 1, z);
            
            // Animate the binary stream
            sprite.userData.originalY = sprite.position.y;
            sprite.userData.speed = 0.02 + Math.random() * 0.03;
            
            parent.add(sprite);
        }
    }

    createTextSprite(text, color, scale = 1) {
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.width = 256;
        canvas.height = 64;
        
        context.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
        context.font = '20px "Courier New", monospace';
        context.textAlign = 'center';
        context.fillText(text, canvas.width / 2, canvas.height / 2);
        
        const texture = new THREE.CanvasTexture(canvas);
        const material = new THREE.SpriteMaterial({
            map: texture,
            transparent: true,
            opacity: 0.8
        });
        
        const sprite = new THREE.Sprite(material);
        sprite.scale.set(scale, scale * 0.25, 1);
        
        return sprite;
    }

    addDataLabel(parent, radius, angle, data) {
        const x = Math.cos(angle) * (radius + 2);
        const z = Math.sin(angle) * (radius + 2);
        
        const labelText = `${data.label}\n${data.value}`;
        const sprite = this.createTextSprite(labelText, this.colors.neonGreen, 0.5);
        sprite.position.set(x, 1, z);
        
        parent.add(sprite);
    }

    addCenterHologram(scene, total, options) {
        // Central holographic display
        const geometry = new THREE.CylinderGeometry(0.5, 0.5, 0.1, 16);
        const material = new THREE.MeshPhongMaterial({
            color: this.colors.neonBlue,
            transparent: true,
            opacity: 0.6,
            emissive: this.colors.neonBlue,
            emissiveIntensity: 0.5
        });
        
        const centerPlatform = new THREE.Mesh(geometry, material);
        centerPlatform.position.y = 0.3;
        scene.add(centerPlatform);

        // Total value display
        const totalSprite = this.createTextSprite(`TOTAL\n${total}`, this.colors.neonYellow, 0.6);
        totalSprite.position.set(0, 1, 0);
        scene.add(totalSprite);

        // Rotating rings
        this.addRotatingRings(scene);
    }

    addRotatingRings(scene) {
        for (let i = 0; i < 3; i++) {
            const ringGeometry = new THREE.RingGeometry(4 + i, 4.1 + i, 32);
            const ringMaterial = new THREE.MeshBasicMaterial({
                color: [this.colors.neonGreen, this.colors.neonBlue, this.colors.neonPink][i],
                transparent: true,
                opacity: 0.3,
                side: THREE.DoubleSide
            });
            
            const ring = new THREE.Mesh(ringGeometry, ringMaterial);
            ring.rotation.x = -Math.PI / 2;
            ring.userData.rotationSpeed = 0.01 * (i + 1);
            scene.add(ring);
            
            // Store for animation
            if (!scene.userData.rings) scene.userData.rings = [];
            scene.userData.rings.push(ring);
        }
    }

    addBinaryParticleSystem(scene) {
        const particleCount = 200;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        
        for (let i = 0; i < particleCount; i++) {
            positions[i * 3] = (Math.random() - 0.5) * 20;
            positions[i * 3 + 1] = Math.random() * 10;
            positions[i * 3 + 2] = (Math.random() - 0.5) * 20;
            
            const color = new THREE.Color(Math.random() > 0.5 ? this.colors.neonGreen : this.colors.neonBlue);
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;
        }
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        
        const material = new THREE.PointsMaterial({
            size: 0.1,
            vertexColors: true,
            transparent: true,
            opacity: 0.8
        });
        
        const particles = new THREE.Points(geometry, material);
        scene.add(particles);
        
        // Store for animation
        scene.userData.particles = particles;
    }

    addCyberGrid(scene) {
        const gridSize = 20;
        const gridDivisions = 20;
        
        const grid = new THREE.GridHelper(gridSize, gridDivisions, this.colors.gridBlue, this.colors.gridBlue);
        grid.material.transparent = true;
        grid.material.opacity = 0.3;
        grid.position.y = -2;
        scene.add(grid);
        
        // Add scanning line effect
        const scanlineGeometry = new THREE.PlaneGeometry(gridSize, 0.1);
        const scanlineMaterial = new THREE.MeshBasicMaterial({
            color: this.colors.neonGreen,
            transparent: true,
            opacity: 0.8,
            side: THREE.DoubleSide
        });
        
        const scanline = new THREE.Mesh(scanlineGeometry, scanlineMaterial);
        scanline.rotation.x = -Math.PI / 2;
        scanline.position.y = -1.9;
        scene.add(scanline);
        
        // Store for animation
        scene.userData.scanline = scanline;
    }

    animate3DChart(containerId) {
        const scene = this.scenes[containerId];
        const camera = this.cameras[containerId];
        const renderer = this.renderers[containerId];
        
        if (!scene || !camera || !renderer) {
            console.error('Missing required objects for animation:', {
                scene: !!scene,
                camera: !!camera, 
                renderer: !!renderer
            });
            return;
        }

        console.log('Starting animation loop for container:', containerId);
        let frameCount = 0;

        const animate = () => {
            this.animationFrames[containerId] = requestAnimationFrame(animate);
            
            frameCount++;
            if (frameCount % 60 === 0) { // Log every 60 frames (about once per second)
                console.log('Animation frame:', frameCount);
            }
            
            // Animate rotating rings
            if (scene.userData.rings) {
                scene.userData.rings.forEach(ring => {
                    ring.rotation.z += ring.userData.rotationSpeed;
                });
            }
            
            // Animate dynamic light
            if (scene.userData.dynamicLight) {
                const time = Date.now() * 0.001;
                scene.userData.dynamicLight.position.x = Math.cos(time) * 5;
                scene.userData.dynamicLight.position.z = Math.sin(time) * 5;
            }
            
            // Animate particles
            if (scene.userData.particles) {
                const positions = scene.userData.particles.geometry.attributes.position.array;
                for (let i = 1; i < positions.length; i += 3) {
                    positions[i] -= 0.02; // Fall down
                    if (positions[i] < -2) {
                        positions[i] = 10; // Reset to top
                    }
                }
                scene.userData.particles.geometry.attributes.position.needsUpdate = true;
            }
            
            // Animate scanline
            if (scene.userData.scanline) {
                const time = Date.now() * 0.002;
                scene.userData.scanline.position.z = Math.sin(time) * 8;
            }
            
            // Animate binary streams
            scene.traverse(child => {
                if (child.type === 'Sprite' && child.userData.speed) {
                    child.position.y += child.userData.speed;
                    child.material.opacity = 0.8 * Math.sin(Date.now() * 0.003 + child.position.x);
                    
                    if (child.position.y > 3) {
                        child.position.y = child.userData.originalY;
                    }
                }
            });
            
            // Render the scene
            renderer.render(scene, camera);
            
            if (frameCount === 1) {
                console.log('First render completed');
            }
        };
        
        animate();
    }

    addMouseInteraction(containerId, camera, renderer) {
        const container = document.getElementById(containerId);
        let isMouseDown = false;
        let mouseX = 0, mouseY = 0;
        
        container.addEventListener('mousedown', (event) => {
            isMouseDown = true;
            mouseX = event.clientX;
            mouseY = event.clientY;
        });
        
        container.addEventListener('mouseup', () => {
            isMouseDown = false;
        });
        
        container.addEventListener('mousemove', (event) => {
            if (!isMouseDown) return;
            
            const deltaX = event.clientX - mouseX;
            const deltaY = event.clientY - mouseY;
            
            // Rotate camera around the scene
            const spherical = new THREE.Spherical();
            spherical.setFromVector3(camera.position);
            spherical.theta -= deltaX * 0.01;
            spherical.phi += deltaY * 0.01;
            spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi));
            
            camera.position.setFromSpherical(spherical);
            camera.lookAt(0, 0, 0);
            
            mouseX = event.clientX;
            mouseY = event.clientY;
        });
        
        // Mouse wheel zoom
        container.addEventListener('wheel', (event) => {
            camera.position.multiplyScalar(1 + event.deltaY * 0.001);
            camera.position.clampLength(5, 20);
        });
    }

    createBinaryRainBackground() {
        // Create full-screen binary rain effect
        const body = document.body;
        const canvas = document.createElement('canvas');
        canvas.id = 'binary-rain';
        canvas.style.position = 'fixed';
        canvas.style.top = '0';
        canvas.style.left = '0';
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        canvas.style.pointerEvents = 'none';
        canvas.style.zIndex = '-1';
        canvas.style.opacity = '0.1';
        
        body.appendChild(canvas);
        
        this.initBinaryRain(canvas);
    }

    initBinaryRain(canvas) {
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        
        const columns = Math.floor(canvas.width / 20);
        const drops = Array(columns).fill(0);
        
        const drawBinaryRain = () => {
            ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            ctx.fillStyle = '#00ff41';
            ctx.font = '15px monospace';
            
            for (let i = 0; i < drops.length; i++) {
                const text = Math.random() > 0.5 ? '1' : '0';
                ctx.fillText(text, i * 20, drops[i] * 20);
                
                if (drops[i] * 20 > canvas.height && Math.random() > 0.975) {
                    drops[i] = 0;
                }
                drops[i]++;
            }
        };
        
        setInterval(drawBinaryRain, 100);
        
        // Resize handler
        window.addEventListener('resize', () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        });
    }

    getSegmentColor(index) {
        const colorArray = [
            this.colors.neonGreen,
            this.colors.neonBlue, 
            this.colors.neonPink,
            this.colors.neonYellow,
            this.colors.warningRed
        ];
        return colorArray[index % colorArray.length];
    }

    generateBinaryString(length) {
        let binary = '';
        for (let i = 0; i < length; i++) {
            binary += Math.random() > 0.5 ? '1' : '0';
        }
        return binary;
    }

    // Clean up function
    destroy(containerId) {
        if (this.animationFrames[containerId]) {
            cancelAnimationFrame(this.animationFrames[containerId]);
            delete this.animationFrames[containerId];
        }
        
        if (this.renderers[containerId]) {
            this.renderers[containerId].dispose();
            delete this.renderers[containerId];
        }
        
        delete this.scenes[containerId];
        delete this.cameras[containerId];
    }
}

// Initialize global cyberpunk visualization manager
window.cyberpunkViz = new CyberpunkVisualization();