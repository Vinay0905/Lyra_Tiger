# Phase 2: Transparent UI Shell & The 3D WebGL Fluid Orb

In this phase, we build our visual interface. You will learn how to configure a borderless, transparent desktop window overlay using `pywebview`, write a dual-theme glassmorphic slide-out text banner in Vanilla CSS, import Three.js, and implement a liquid-metal 3D fluid orb using WebGL shaders.

---

## 1. Directory Structure

At the end of this phase, your project tree should look exactly like this:
```text
AI_Assistant/
├── .env
├── pyproject.toml
├── uv.lock
├── ui/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── src/
    ├── __init__.py
    ├── config.py
    ├── gui.py
    └── main.py
```

---

## 2. Dynamic Desktop Sizing & Positioning (`src/gui.py`)

To position our assistant in the bottom-right corner of the user's screen, we fetch system screen dimensions. When idle, we resize the window to a small `80px` x `80px` circle. When active, we expand it to `550px` x `380px` to show the caption banner.

Create `src/gui.py`:
```python
import os
import webview
from src.config import settings

# Global window references
app_window = None
is_expanded = False

class WindowAPI:
    """Python methods exposed to the frontend JavaScript runtime."""
    def toggle_expand(self, expand: bool):
        """Resizes the borderless pywebview window shell dynamically."""
        global app_window, is_expanded
        if not app_window:
            return
            
        screen = webview.screens[0]  # Get primary screen
        is_expanded = expand
        
        if expand:
            # Expand window to fit text captions and logs
            app_window.resize(550, 380)
            # Move to bottom right coordinates
            app_window.move(screen.width - 570, screen.height - 420)
        else:
            # Collapse back to small corner circle
            app_window.resize(80, 80)
            app_window.move(screen.width - 100, screen.height - 120)

    def send_command(self, text: str) -> dict:
        print(f"[GUI API] Received Text Command: {text}")
        return {
            "reply": f"Lyra: Processing resonance check for '{text}'",
            "route": "chat",
            "status": "success"
        }

    def close_app(self):
        os._exit(0)

def start_gui():
    global app_window
    api = WindowAPI()
    
    ui_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui"))
    html_path = os.path.join(ui_dir, "index.html")
    
    screen = webview.screens[0]
    
    app_window = webview.create_window(
        title="Lyra Assistant",
        url=f"file://{html_path}",
        js_api=api,
        width=80,
        height=80,
        x=screen.width - 100,
        y=screen.height - 120,
        resizable=False,
        frameless=True,
        background_color="#00000000",
        on_top=True
    )
    
    webview.start(debug=settings.debug)

if __name__ == "__main__":
    start_gui()
```

---

## 3. Designing the Frosted Slide-out Interface

### 3.1 The HTML Markup (`ui/index.html`)
This markup imports the Three.js library and outlines a layout consisting of a text banner sliding out to the left of the round orb container.
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Lyra Desktop Interface</title>
    <link rel="stylesheet" href="style.css">
    <!-- Import Three.js Core -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body class="theme-cosmic">
    <div class="app-container" id="main-container">
        <!-- Slide-out Glass Caption Banner -->
        <div class="caption-banner" id="banner">
            <div class="banner-header">
                <span class="status-indicator">
                    <span class="status-dot idle" id="status-dot"></span>
                    <span id="status-text">Resonator Idle</span>
                </span>
                <span class="ctrl-group">
                    <button class="theme-btn" onclick="toggleTheme()" title="Switch Theme">☼</button>
                    <button class="close-btn" onclick="closeWindow()">&times;</button>
                </span>
            </div>
            
            <div class="caption-body" id="output-box">
                "Resonance active. Speak to Lyra."
            </div>
            
            <div class="input-row">
                <input type="text" id="cmd-input" placeholder="Type coordinates..." onkeydown="handleInput(event)">
                <button class="send-btn" onclick="submitCommand()">Send</button>
            </div>
            
            <!-- Monospace Ticker drawer -->
            <div class="ticker-drawer" onclick="toggleDrawer()">
                <div class="ticker-label">Logs Trace</div>
                <div class="ticker-body" id="audit-log">
                    <p>[System] Interface active.</p>
                </div>
            </div>
        </div>

        <!-- The 3D WebGL Orb Anchor -->
        <div class="orb-anchor" onclick="triggerSummon()">
            <div id="canvas-container"></div>
        </div>
    </div>
    
    <script src="app.js"></script>
</body>
</html>
```

### 3.2 Premium CSS Theme Configurations (`ui/style.css`)
Here we configure the **Celestial Aurora** and **Solar Frost** themes using CSS variables, and design banner width transition physics.
```css
:root {
    /* Cosmic Theme Variables */
    --bg-glass: rgba(8, 8, 14, 0.85);
    --border-glass: rgba(138, 43, 226, 0.2);
    --text-starlight: #f8fafc;
    --text-cosmic: #94a3b8;
    --glow-shadow: rgba(138, 43, 226, 0.35);
    --btn-grad: linear-gradient(135deg, #8a2be2 0%, #00fff4 100%);
    --dot-color: #10b981;
}

body.theme-frost {
    /* Frost Theme Variables */
    --bg-glass: rgba(255, 255, 255, 0.72);
    --border-glass: rgba(0, 0, 0, 0.08);
    --text-starlight: #0f172a;
    --text-cosmic: #475569;
    --glow-shadow: rgba(0, 0, 0, 0.05);
    --btn-grad: linear-gradient(135deg, #f43f5e 0%, #fb923c 100%);
}

body {
    margin: 0;
    padding: 0;
    background: transparent;
    font-family: 'Outfit', sans-serif;
    overflow: hidden;
    color: var(--text-starlight);
}

.app-container {
    width: 80px;
    height: 80px;
    position: absolute;
    bottom: 0;
    right: 0;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    transition: width 0.6s cubic-bezier(0.16, 1, 0.3, 1),
                height 0.6s cubic-bezier(0.16, 1, 0.3, 1);
    overflow: hidden;
}

.app-container.expanded {
    width: 550px;
    height: 380px;
}

/* Horizontal slide out panel */
.caption-banner {
    width: 440px;
    height: 350px;
    background: var(--bg-glass);
    backdrop-filter: blur(28px);
    -webkit-backdrop-filter: blur(28px);
    border: 1px solid var(--border-glass);
    border-radius: 16px;
    margin-right: 12px;
    padding: 16px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    box-shadow: 0 12px 40px var(--glow-shadow);
    opacity: 0;
    transform: translateX(30px);
    transition: opacity 0.5s ease, transform 0.5s ease;
    pointer-events: none;
}

.app-container.expanded .caption-banner {
    opacity: 1;
    transform: translateX(0);
    pointer-events: auto;
}

.banner-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-cosmic);
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 6px;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--dot-color);
}
.status-dot.listening { background: #f43f5e; }
.status-dot.thinking { background: #3b82f6; }
.status-dot.speaking { background: #a855f7; }

.ctrl-group {
    display: flex;
    gap: 8px;
}

.theme-btn, .close-btn {
    background: transparent;
    border: none;
    color: var(--text-cosmic);
    cursor: pointer;
    font-size: 14px;
}
.close-btn { font-size: 18px; }
.close-btn:hover { color: #f43f5e; }

.caption-body {
    flex: 1;
    font-size: 15px;
    line-height: 1.6;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    font-weight: 300;
}

.input-row {
    display: flex;
    gap: 8px;
    margin-top: 8px;
}

input[type="text"] {
    flex: 1;
    background: rgba(0, 0, 0, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 8px 12px;
    color: var(--text-starlight);
    outline: none;
    font-size: 13px;
}

.send-btn {
    background: var(--btn-grad);
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    color: #08080e;
    font-weight: bold;
    cursor: pointer;
}

/* Monospace Ticker drawer styles */
.ticker-drawer {
    margin-top: 8px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    padding-top: 6px;
    font-family: monospace;
    font-size: 9px;
    color: var(--text-cosmic);
    cursor: pointer;
}

.ticker-body {
    max-height: 0px;
    overflow: hidden;
    transition: max-height 0.4s ease;
}

.ticker-drawer:hover .ticker-body {
    max-height: 50px;
    overflow-y: auto;
}

/* 3D Orb Circular Container */
.orb-anchor {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 20px rgba(0, 0, 0, 0.4);
    overflow: hidden;
    z-index: 100;
}

#canvas-container {
    width: 100%;
    height: 100%;
}
```

---

## 4. The 3D WebGL Fluid Orb Controller (`ui/app.js`)

We initialize the WebGL rendering space using Three.js and write custom shaders to deform the sphere in an organic liquid pattern.

Create `ui/app.js`:
```javascript
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
    const width = container.clientWidth || 80;
    const height = container.clientHeight || 80;

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.z = 5.2;

    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

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
            uColorRim: { value: new THREE.Color('#ff7f50') } # Indigo to Rose-Gold Aurora
        },
        transparent: true
    });

    mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);
}

function animate() {
    time += 0.025;
    
    if (material) {
        material.uniforms.uTime.value = time;
        
        // State updates
        if (orbState === 'idle') {
            material.uniforms.uAmplitude.value = 0.08 + Math.sin(time * 0.5) * 0.02;
        } else if (orbState === 'thinking') {
            material.uniforms.uAmplitude.value = 0.25;
            mesh.rotation.y += 0.05;
        } else if (orbState === 'speaking') {
            material.uniforms.uAmplitude.value = 0.12 + Math.abs(Math.sin(time * 3.0)) * 0.1;
        }
    }
    
    if (renderer) {
        renderer.render(scene, camera);
    }
    requestAnimationFrame(animate);
}

function setOrbState(state) {
    orbState = state;
    const dot = document.getElementById('status-dot');
    dot.className = `status-dot ${state}`;
    document.getElementById('status-text').innerText = `Resonator ${state.toUpperCase()}`;
    
    // Color states shifts
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
    } else { # Idle
        material.uniforms.uColorCenter.value.set('#4300a3');
        material.uniforms.uColorRim.value.set('#ff7f50');
    }
}

// GUI Banner Expanding Toggles
function triggerSummon() {
    const container = document.getElementById('main-container');
    const isExpanded = container.classList.toggle('expanded');
    
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.toggle_expand(isExpanded);
    }
    
    if (isExpanded) {
        setOrbState('idle');
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
    const query = input.value.trim();
    if (!query) return;

    input.value = '';
    const output = document.getElementById('output-box');
    output.innerText = `"${query}"`;
    
    setOrbState('thinking');
    addAuditLog(`Sent command: "${query}"`);

    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.send_command(query).then(res => {
            output.innerText = res.reply;
            setOrbState('speaking');
            addAuditLog(`Output: [${res.route}] processed.`);
        });
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
    body.style.maxHeight = body.style.maxHeight === '50px' ? '0px' : '50px';
}

function addAuditLog(text) {
    const logBox = document.getElementById('audit-log');
    const entry = document.createElement('p');
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
    logBox.appendChild(entry);
    logBox.scrollTop = logBox.scrollHeight;
}

// Window sizing resize event handler
window.addEventListener('resize', () => {
    if (renderer && container) {
        const width = container.clientWidth;
        const height = container.clientHeight;
        renderer.setSize(width, height);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
    }
});

// Boot WebGL Canvas
initThree();
animate();
setOrbState('idle');
addAuditLog("System boot complete.");
```

---

## 5. Compiling and Verifying the UI
Boot the native window shell:
```bash
uv run python -m src.gui
```
- A small borderless circle containing the glowing, liquid 3D orb will float in the bottom-right corner of your screen.
- Click on the orb: it expands into a horizontal glassmorphic panel. In Python, the window expands to `550x380` and relocates itself to offset the expanded banner.
- Click the `☼` theme toggle icon to watch it transition smoothly between Cosmic Obsidian and Solar Frost.
