// static/js/reports/cyberpunk-canvas.js
// Cyberpunk Canvas Visualization - Pure Canvas 2D with stunning effects

class CyberpunkCanvas {
    constructor() {
        this.animations = {};
        this.colors = {
            neonGreen: '#00ff41',
            neonBlue: '#0099ff', 
            neonPink: '#ff0099',
            neonYellow: '#ffff00',
            darkBg: '#0a0a0a',
            gridBlue: '#004455'
        };
        this.init();
    }

    init() {
        console.log('Initializing Cyberpunk Canvas visualizations...');
        this.createBinaryRain();
        this.setupGlobalEffects();
    }

    // Create animated holographic pie chart
    createHoloPieChart(containerId, data, options = {}) {
        console.log('Creating holographic pie chart for:', containerId);
        const container = document.getElementById(containerId);
        if (!container) return;

        // Clear container
        container.innerHTML = '';
        
        // Create canvas
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight || 400;
        container.appendChild(canvas);

        // Animation state
        const state = {
            rotation: 0,
            pulsePhase: 0,
            glitchPhase: 0,
            scanlinePos: 0,
            particleSystem: this.createParticleSystem(),
            data: data.filter(d => d.value > 0)
        };

        // Start animation
        this.animateHoloPie(canvas, ctx, state, options);
        
        // Store animation reference
        this.animations[containerId] = state;

        return canvas;
    }

    createParticleSystem() {
        const particles = [];
        for (let i = 0; i < 50; i++) {
            particles.push({
                x: Math.random() * 800,
                y: Math.random() * 600,
                vx: (Math.random() - 0.5) * 2,
                vy: (Math.random() - 0.5) * 2,
                life: Math.random(),
                size: Math.random() * 3 + 1,
                color: [this.colors.neonGreen, this.colors.neonBlue, this.colors.neonPink][Math.floor(Math.random() * 3)]
            });
        }
        return particles;
    }

    animateHoloPie(canvas, ctx, state, options) {
        const animate = () => {
            this.clearCanvas(ctx, canvas.width, canvas.height);
            
            // Update animation state
            state.rotation += 0.005;
            state.pulsePhase += 0.03;
            state.glitchPhase += 0.07;
            state.scanlinePos = (state.scanlinePos + 2) % canvas.height;

            // Draw background effects
            this.drawHoloBackground(ctx, canvas.width, canvas.height, state);
            
            // Draw particles
            this.updateAndDrawParticles(ctx, state.particleSystem, canvas.width, canvas.height);
            
            // Draw the pie chart
            this.drawHolographicPie(ctx, canvas.width, canvas.height, state);
            
            // Draw scanlines
            this.drawScanlines(ctx, canvas.width, canvas.height, state);
            
            // Draw data labels
            this.drawDataLabels(ctx, canvas.width, canvas.height, state);

            requestAnimationFrame(animate);
        };
        animate();
    }

    clearCanvas(ctx, width, height) {
        ctx.fillStyle = this.colors.darkBg;
        ctx.fillRect(0, 0, width, height);
    }

    drawHoloBackground(ctx, width, height, state) {
        // Grid background
        ctx.strokeStyle = this.colors.gridBlue;
        ctx.lineWidth = 0.5;
        ctx.globalAlpha = 0.3;
        
        const gridSize = 30;
        for (let x = 0; x < width; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.stroke();
        }
        for (let y = 0; y < height; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();
        }

        // Radial gradient overlay
        const centerX = width / 2;
        const centerY = height / 2;
        const gradient = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, Math.max(width, height) / 2);
        gradient.addColorStop(0, 'rgba(0, 255, 65, 0.1)');
        gradient.addColorStop(0.5, 'rgba(0, 153, 255, 0.05)');
        gradient.addColorStop(1, 'rgba(255, 0, 153, 0.02)');
        
        ctx.globalAlpha = 0.8;
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, width, height);
    }

    drawHolographicPie(ctx, width, height, state) {
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(width, height) * 0.25;
        
        const total = state.data.reduce((sum, item) => sum + item.value, 0);
        let currentAngle = state.rotation;

        state.data.forEach((item, index) => {
            const sliceAngle = (item.value / total) * Math.PI * 2;
            const color = this.getSegmentColor(index);
            
            // Main pie slice with glow
            ctx.save();
            
            // Outer glow
            ctx.shadowColor = color;
            ctx.shadowBlur = 20;
            ctx.globalAlpha = 0.8;
            
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.arc(centerX, centerY, radius, currentAngle, currentAngle + sliceAngle);
            ctx.closePath();
            ctx.fillStyle = color;
            ctx.fill();
            
            // Inner glow ring
            ctx.globalAlpha = 0.4;
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius * 0.7, currentAngle, currentAngle + sliceAngle);
            ctx.arc(centerX, centerY, radius * 0.3, currentAngle + sliceAngle, currentAngle, true);
            ctx.closePath();
            ctx.fillStyle = '#ffffff';
            ctx.fill();
            
            // Holographic edge lines
            ctx.restore();
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.globalAlpha = 1;
            ctx.shadowColor = color;
            ctx.shadowBlur = 10;
            
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.lineTo(
                centerX + Math.cos(currentAngle) * radius,
                centerY + Math.sin(currentAngle) * radius
            );
            ctx.stroke();
            
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.lineTo(
                centerX + Math.cos(currentAngle + sliceAngle) * radius,
                centerY + Math.sin(currentAngle + sliceAngle) * radius
            );
            ctx.stroke();

            currentAngle += sliceAngle;
        });

        // Central hologram
        this.drawCentralHolo(ctx, centerX, centerY, radius * 0.3, state);
    }

    drawCentralHolo(ctx, x, y, radius, state) {
        const pulse = Math.sin(state.pulsePhase) * 0.3 + 0.7;
        
        // Central ring
        ctx.save();
        ctx.globalAlpha = pulse;
        ctx.strokeStyle = this.colors.neonGreen;
        ctx.lineWidth = 3;
        ctx.shadowColor = this.colors.neonGreen;
        ctx.shadowBlur = 15;
        
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.stroke();
        
        // Rotating inner elements
        const spokes = 8;
        for (let i = 0; i < spokes; i++) {
            const angle = (i / spokes) * Math.PI * 2 + state.rotation * 3;
            const innerRadius = radius * 0.3;
            const outerRadius = radius * 0.8;
            
            ctx.beginPath();
            ctx.moveTo(
                x + Math.cos(angle) * innerRadius,
                y + Math.sin(angle) * innerRadius
            );
            ctx.lineTo(
                x + Math.cos(angle) * outerRadius,
                y + Math.sin(angle) * outerRadius
            );
            ctx.stroke();
        }
        
        ctx.restore();
    }

    updateAndDrawParticles(ctx, particles, width, height) {
        particles.forEach(particle => {
            // Update position
            particle.x += particle.vx;
            particle.y += particle.vy;
            particle.life -= 0.01;
            
            // Wrap around screen
            if (particle.x < 0) particle.x = width;
            if (particle.x > width) particle.x = 0;
            if (particle.y < 0) particle.y = height;
            if (particle.y > height) particle.y = 0;
            
            // Reset if dead
            if (particle.life <= 0) {
                particle.life = 1;
                particle.x = Math.random() * width;
                particle.y = Math.random() * height;
            }
            
            // Draw particle
            ctx.save();
            ctx.globalAlpha = particle.life * 0.8;
            ctx.fillStyle = particle.color;
            ctx.shadowColor = particle.color;
            ctx.shadowBlur = 5;
            
            ctx.beginPath();
            ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
            ctx.fill();
            
            ctx.restore();
        });
    }

    drawScanlines(ctx, width, height, state) {
        // Moving scanline effect
        ctx.save();
        ctx.globalAlpha = 0.3;
        
        const gradient = ctx.createLinearGradient(0, state.scanlinePos - 50, 0, state.scanlinePos + 50);
        gradient.addColorStop(0, 'transparent');
        gradient.addColorStop(0.5, this.colors.neonGreen);
        gradient.addColorStop(1, 'transparent');
        
        ctx.fillStyle = gradient;
        ctx.fillRect(0, state.scanlinePos - 50, width, 100);
        
        ctx.restore();
    }

    drawDataLabels(ctx, width, height, state) {
        const centerX = width / 2;
        const centerY = height / 2;
        const labelRadius = Math.min(width, height) * 0.35;
        
        const total = state.data.reduce((sum, item) => sum + item.value, 0);
        let currentAngle = state.rotation;

        ctx.font = 'bold 14px "Courier New", monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        state.data.forEach((item, index) => {
            const sliceAngle = (item.value / total) * Math.PI * 2;
            const labelAngle = currentAngle + sliceAngle / 2;
            const color = this.getSegmentColor(index);
            
            const labelX = centerX + Math.cos(labelAngle) * labelRadius;
            const labelY = centerY + Math.sin(labelAngle) * labelRadius;
            
            // Label background
            ctx.save();
            ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
            ctx.fillRect(labelX - 40, labelY - 20, 80, 40);
            
            // Label text with glow
            ctx.shadowColor = color;
            ctx.shadowBlur = 10;
            ctx.fillStyle = color;
            ctx.fillText(item.label, labelX, labelY - 5);
            ctx.fillText(item.value.toString(), labelX, labelY + 10);
            
            ctx.restore();
            currentAngle += sliceAngle;
        });
    }

    getSegmentColor(index) {
        const colors = [this.colors.neonGreen, this.colors.neonBlue, this.colors.neonPink, this.colors.neonYellow];
        return colors[index % colors.length];
    }

    // Enhanced 2D bar chart with cyberpunk effects
    createCyberBarChart(containerId, data, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = '';
        
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight || 300;
        container.appendChild(canvas);

        const state = {
            animationProgress: 0,
            glitchPhase: 0,
            data: data
        };

        this.animateCyberBar(canvas, ctx, state, options);
        return canvas;
    }

    animateCyberBar(canvas, ctx, state, options) {
        const animate = () => {
            this.clearCanvas(ctx, canvas.width, canvas.height);
            
            state.animationProgress = Math.min(state.animationProgress + 0.02, 1);
            state.glitchPhase += 0.1;
            
            this.drawCyberBars(ctx, canvas.width, canvas.height, state, options);
            
            if (state.animationProgress < 1) {
                requestAnimationFrame(animate);
            }
        };
        animate();
    }

    drawCyberBars(ctx, width, height, state, options) {
        const margin = 60;
        const chartWidth = width - margin * 2;
        const chartHeight = height - margin * 2;
        
        if (!state.data.length) return;
        
        const maxValue = Math.max(...state.data.map(d => d.value));
        const barWidth = chartWidth / state.data.length * 0.8;
        const spacing = chartWidth / state.data.length * 0.2;

        state.data.forEach((item, index) => {
            const barHeight = (item.value / maxValue) * chartHeight * state.animationProgress;
            const x = margin + index * (barWidth + spacing);
            const y = height - margin - barHeight;
            const color = this.getSegmentColor(index);
            
            // Bar with glow effect
            ctx.save();
            ctx.fillStyle = color;
            ctx.shadowColor = color;
            ctx.shadowBlur = 15;
            ctx.globalAlpha = 0.8;
            
            ctx.fillRect(x, y, barWidth, barHeight);
            
            // Inner highlight
            ctx.globalAlpha = 0.3;
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(x + 2, y + 2, barWidth - 4, Math.max(0, barHeight - 4));
            
            // Label
            ctx.restore();
            ctx.fillStyle = color;
            ctx.font = 'bold 12px "Courier New", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(item.value.toString(), x + barWidth/2, y - 10);
            
            // X-axis label
            ctx.save();
            ctx.translate(x + barWidth/2, height - margin + 20);
            ctx.rotate(-Math.PI/4);
            ctx.fillStyle = this.colors.neonGreen;
            ctx.textAlign = 'right';
            ctx.fillText(item.label || `Item ${index + 1}`, 0, 0);
            ctx.restore();
        });
        
        // Grid lines
        ctx.strokeStyle = this.colors.gridBlue;
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.3;
        
        for (let i = 0; i <= 5; i++) {
            const y = height - margin - (i / 5) * chartHeight;
            ctx.beginPath();
            ctx.moveTo(margin, y);
            ctx.lineTo(width - margin, y);
            ctx.stroke();
        }
    }

    createBinaryRain() {
        const canvas = document.createElement('canvas');
        canvas.id = 'binary-rain-canvas';
        canvas.style.position = 'fixed';
        canvas.style.top = '0';
        canvas.style.left = '0';
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        canvas.style.pointerEvents = 'none';
        canvas.style.zIndex = '-1';
        canvas.style.opacity = '0.1';
        
        document.body.appendChild(canvas);
        
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        
        const columns = Math.floor(canvas.width / 20);
        const drops = Array(columns).fill(0);
        
        const drawRain = () => {
            ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            ctx.fillStyle = this.colors.neonGreen;
            ctx.font = '15px "Courier New", monospace';
            
            for (let i = 0; i < drops.length; i++) {
                const text = Math.random() > 0.5 ? '1' : '0';
                ctx.fillText(text, i * 20, drops[i] * 20);
                
                if (drops[i] * 20 > canvas.height && Math.random() > 0.975) {
                    drops[i] = 0;
                }
                drops[i]++;
            }
        };
        
        setInterval(drawRain, 50);
        
        window.addEventListener('resize', () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        });
    }

    setupGlobalEffects() {
        // Add CSS animations and effects
        const style = document.createElement('style');
        style.textContent = `
            @keyframes cyber-glow {
                0%, 100% { box-shadow: 0 0 5px currentColor; }
                50% { box-shadow: 0 0 20px currentColor, 0 0 30px currentColor; }
            }
            
            @keyframes data-stream {
                0% { transform: translateY(-100%); opacity: 0; }
                50% { opacity: 1; }
                100% { transform: translateY(100vh); opacity: 0; }
            }
            
            .cyber-glow {
                animation: cyber-glow 2s ease-in-out infinite;
            }
            
            .data-stream {
                animation: data-stream 3s linear infinite;
            }
            
            .glitch-text {
                position: relative;
            }
            
            .glitch-text::before,
            .glitch-text::after {
                content: attr(data-text);
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
            }
            
            .glitch-text::before {
                animation: glitch-1 0.5s infinite;
                color: #ff0099;
                z-index: -1;
            }
            
            .glitch-text::after {
                animation: glitch-2 0.5s infinite;
                color: #00ffff;
                z-index: -2;
            }
            
            @keyframes glitch-1 {
                0%, 14%, 15%, 49%, 50%, 99%, 100% { transform: translate(0); }
                15%, 49% { transform: translate(-2px, 1px); }
            }
            
            @keyframes glitch-2 {
                0%, 20%, 21%, 62%, 63%, 99%, 100% { transform: translate(0); }
                21%, 62% { transform: translate(2px, -1px); }
            }
        `;
        document.head.appendChild(style);
    }

    destroy(containerId) {
        if (this.animations[containerId]) {
            delete this.animations[containerId];
        }
    }
}

// Initialize global cyberpunk canvas manager
window.cyberpunkCanvas = new CyberpunkCanvas();