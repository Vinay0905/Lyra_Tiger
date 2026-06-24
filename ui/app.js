let container = document.getElementById('canvas-container');
let scene, camera, renderer, mesh, material;
let time = 0;
let orbState = 'idle';

// Vertex Shader: Simplex Noise math to ripple the sphere mesh
const vertexShader = `
    uniform float uTime;
    uniform float uAmplitude;
    varying vec3 vNormal;
    varying vec3 vPosition;

    // Simplex 3D Noise Generator by Ashima Arts
    vec4 permute(vec4 x){return mod(((x*34.0)+1.0)*x, 289.0);}
    vec4 taylorInvSqrt(vec4 r){return 1.79284291400159 - 0.85373472095314 * r;}
    float snoise(vec3 v){
      const vec2 C = vec2(1.0/6.0, 1.0/3.0);
      const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
      vec3 i  = floor(v + dot(v, C.yyy) );
      vec3 x0 =   v - i + dot(i, C.xxx) ;
      vec3 g = step(x0.yzx, x0.xyz);
      vec3 l = 1.0 - g;
      vec3 i1 = min( g.xyz, l.zxy );
      vec3 i2 = max( g.xyz, l.zxy );
      vec3 x1 = x0 - i1 + 1.0 * C.xxx;
      vec3 x2 = x0 - i2 + 2.0 * C.xxx;
      vec3 x3 = x0 - D.yyy;
      i = mod(i, 289.0 );
      vec4 p = permute( permute( permute(
                 i.z + vec4(0.0, i1.z, i2.z, 1.0 ))
               + i.y + vec4(0.0, i1.y, i2.y, 1.0 ))
               + i.x + vec4(0.0, i1.x, i2.x, 1.0 ));
      float n_ = 1.0/7.0;
      vec3  ns = n_ * D.wyz - D.xzx;
      vec4 j = p - 49.0 * floor(p * ns.z *ns.z);
      vec4 x_ = floor(j * ns.z);
      vec4 y_ = floor(j - 7.0 * x_ );
      vec4 x = x_ *ns.x + ns.yyyy;
      vec4 y = y_ *ns.x + ns.yyyy;
      vec4 h = 1.0 - abs(x) - abs(y);
      vec4 b0 = vec4( x.xy, y.xy );
      vec4 b1 = vec4( x.zw, y.zw );
      vec4 s0 = floor(b0)*2.0 + 1.0;
      vec4 s1 = floor(b1)*2.0 + 1.0;
      vec4 sh = -step(h, vec4(0.0));
      vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy ;
      vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww ;
      vec3 p0 = vec3(a0.xy,h.x);
      vec3 p1 = vec3(a0.zw,h.y);
      vec3 p2 = vec3(a1.xy,h.z);
      vec3 p3 = vec3(a1.zw,h.w);
      vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3)));
      p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
      vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
      m = m * m;
      return 42.0 * dot( m*m, vec4( dot(p0,x0), dot(p1,x1),
                                    dot(p2,x2), dot(p3,x3) ) );
    }

    void main() {
        vNormal = normal;
        vPosition = position;
        
        // Deform vertices along normal using time-based simplex noise
        float noise = snoise(position * 1.5 + uTime * 0.8) * uAmplitude;
        vec3 newPosition = position + normal * noise;
        
        gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
    }
`;

// Fragment Shader: Simplex color mixing based on Fresnel lighting curves
const fragmentShader = `
    varying vec3 vNormal;
    varying vec3 vPosition;
    uniform vec3 uColorCenter;
    uniform vec3 uColorRim;

    void main() {
        // Calculate standard rim-glow (Fresnel effect)
        vec3 normal = normalize(vNormal);
        vec3 eye = normalize(vec3(0.0, 0.0, 1.0));
        float fresnel = pow(1.0 - max(dot(normal, eye), 0.0), 2.5);
        
        // Mix colors dynamically based on surface normals
        vec3 color = mix(uColorCenter, uColorRim, fresnel);
        gl_FragColor = vec4(color, 1.0);
    }
`;

function initThree() {
    const width = container ? (container.clientWidth || 80) : 80;
    const height = container ? (container.clientHeight || 80) : 80;

    if (typeof THREE === 'undefined') {
        throw new Error("THREE is not defined in the global window namespace.");
    }

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.z = 5.2;

    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    if (container) {
        container.appendChild(renderer.domElement);
    }

    // High density geometry sphere
    const geometry = new THREE.IcosahedronGeometry(1.6, 64);
    
    // Shader Material Uniforms
    material = new THREE.ShaderMaterial({
        vertexShader,
        fragmentShader,
        uniforms: {
            uTime: { value: 0 },
            uAmplitude: { value: 0.12 },
            uColorCenter: { value: new THREE.Color('#4300a3') },
            uColorRim: { value: new THREE.Color('#ff7f50') } // Indigo to Rose-Gold Aurora
        },
        transparent: true
    });

    mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);
}

function animate() {
    time += 0.025;
    
    if (material && material.uniforms) {
        material.uniforms.uTime.value = time;
        
        // State updates
        if (orbState === 'idle') {
            material.uniforms.uAmplitude.value = 0.08 + Math.sin(time * 0.5) * 0.02;
        } else if (orbState === 'thinking') {
            material.uniforms.uAmplitude.value = 0.25;
            if (mesh) mesh.rotation.y += 0.05;
        } else if (orbState === 'speaking') {
            material.uniforms.uAmplitude.value = 0.12 + Math.abs(Math.sin(time * 3.0)) * 0.1;
        }
    }
    
    if (renderer && scene && camera) {
        renderer.render(scene, camera);
    }
    requestAnimationFrame(animate);
}

function setOrbState(state) {
    orbState = state;
    const dot = document.getElementById('status-dot');
    if (dot) dot.className = `status-dot ${state}`;
    const statusText = document.getElementById('status-text');
    if (statusText) statusText.innerText = `Resonator ${state.toUpperCase()}`;
    
    // Fallback animation classes toggle
    const orbAnchor = document.querySelector('.orb-anchor');
    if (orbAnchor && orbAnchor.classList.contains('fallback-mode')) {
        orbAnchor.classList.remove('listening', 'thinking', 'speaking');
        if (state !== 'idle') {
            orbAnchor.classList.add(state);
        }
    }
    
    // Color states shifts
    if (material && material.uniforms) {
        if (state === 'listening') {
            material.uniforms.uColorCenter.value.set('#ef4444');
            material.uniforms.uColorRim.value.set('#ff8c00');
            material.uniforms.uAmplitude.value = 0.18;
        } else if (state === 'thinking') {
            material.uniforms.uColorCenter.value.set('#1e3a8a');
            material.uniforms.uColorRim.value.set('#00fff4');
        } else if (state === 'speaking') {
            material.uniforms.uColorCenter.value.set('#6366f1');
            material.uniforms.uColorRim.value.set('#a855f7');
        } else { //Idle
            material.uniforms.uColorCenter.value.set('#4300a3');
            material.uniforms.uColorRim.value.set('#ff7f50');
        }
    }
}

// GUI Banner Expanding Toggles
function triggerSummon() {
    const containerEl = document.getElementById('main-container');
    if (!containerEl) return;
    
    const isCurrentlyExpanded = containerEl.classList.contains('expanded');
    
    if (isCurrentlyExpanded) {
        containerEl.classList.remove('expanded');
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.toggle_expand(false);
        }
        setOrbState('idle');
    } else {
        containerEl.classList.add('expanded');
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.toggle_expand(true);
            window.pywebview.api.start_voice_capture();
        }
    }
}

function toggleTheme() {
    const body = document.body;
    if (body.classList.contains('theme-cosmic')) {
        body.classList.replace('theme-cosmic', 'theme-frost');
        addAuditLog("Theme swapped: Solar Frost.");
    } else {
        body.classList.replace('theme-frost', 'theme-cosmic');
        addAuditLog("Theme swapped: Cosmic Obsidian.");
    }
}

function submitCommand() {
    const input = document.getElementById('cmd-input');
    if (!input) return;
    const query = input.value.trim();
    if (!query) return;

    input.value = '';
    const output = document.getElementById('output-box');
    if (output) output.innerText = `"${query}"`;
    
    setOrbState('thinking');
    addAuditLog(`Sent command: "${query}"`);

    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.send_command(query).then(res => {
            if (output && res) output.innerText = res.reply;
            setOrbState('speaking');
            if (res) addAuditLog(`Output: [${res.route}] processed.`);
            
            // Revert state back to idle after speaking completes (approx 6 seconds)
            setTimeout(() => {
                setOrbState('idle');
            }, 6000);
        });
    }
}

function triggerVoice() {
    setOrbState('listening');
    const output = document.getElementById('output-box');
    if (output) output.innerText = 'Listening to your voice...';
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.start_voice_capture();
    }
}

function handleInput(e) {
    if (e.key === 'Enter') submitCommand();
}

function closeWindow() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.close_app();
    }
}

function toggleDrawer() {
    const body = document.getElementById('audit-log');
    if (body) {
        body.style.maxHeight = body.style.maxHeight === '50px' ? '0px' : '50px';
    }
}

function addAuditLog(text) {
    const logBox = document.getElementById('audit-log');
    if (logBox) {
        const entry = document.createElement('p');
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
        logBox.appendChild(entry);
        logBox.scrollTop = logBox.scrollHeight;
    }
}

// Window sizing resize event handler
window.addEventListener('resize', () => {
    if (renderer && container) {
        const width = container.clientWidth;
        const height = container.clientHeight;
        renderer.setSize(width, height);
        if (camera) {
            camera.aspect = width / height;
            camera.updateProjectionMatrix();
        }
    }
});

// Boot WebGL Canvas defensively
try {
    if (typeof THREE === 'undefined') {
        throw new Error("THREE namespace is undefined.");
    }
    initThree();
    animate();
    setOrbState('idle');
    addAuditLog("System boot complete with WebGL 3D orb.");
} catch (e) {
    console.error("Three.js/WebGL initialization failed:", e);
    
    // Set fallback classes on the orb anchor
    const orbAnchor = document.querySelector('.orb-anchor');
    if (orbAnchor) {
        orbAnchor.classList.add('fallback-mode');
    }
    
    // Call setOrbState to initialize fallback states safely
    setOrbState('idle');
    addAuditLog("WebGL failed; loaded CSS fallback orb.");
}
