# Google Stitch Prompt: Lyra Desktop Assistant UI (WebGL 3D Orb & Corner Resonator)

Copy the text block below and paste it directly into Google Stitch or your preferred AI code generator to build the premium, custom frontend assets for Lyra.

***

### Google Stitch System Input & UI Prompt

Generate a single, premium, self-contained desktop assistant UI file (`index.html` with inline CSS/JS) for a macOS system-level utility named **Lyra**. The interface must feel organic, highly polished, and premium, completely avoiding flat vectors or generic layouts.

---

## 1. Subsystem Architecture (Floating Corner Resonator)
Instead of a centered card, the window wrapper is a borderless container placed in the **bottom-right corner of the desktop**.
-   **Default Collapse State:** A compact, floating circular bubble (`80px` x `80px`) holding only the **3D Resonance Orb**.
-   **Expanded Active State:** When summoned or responding, the window expands horizontally to `550px` wide. The **3D Resonance Orb** acts as the anchor on the right, and a sleek, narrow, glassmorphic caption banner slides out horizontally to the left.
-   **Layout Elements inside the Slide-out Banner:**
    *   **Header Control strip:** Sits at the top of the text banner, housing a tiny status indicator (`Vega Resonator (Active)`), a miniature Cosmic-to-Frost theme switch button, and an exit button (`&times;`).
    *   **Caption Area:** Displays Lyra's output in large, elegant, high-readability typography (`"Outfit"` or `"Inter"` Google Fonts), fading in sentence-by-sentence.
    *   **Input Row:** A minimalist text input field and a gradient-glow "Send" button that slide out when text-mode is activated.
    *   **Single-line Activity Log Ticker:** Sits at the very bottom of the banner, showing monospace events (e.g., `[18:32:01] WebBridge Connected`). When hovered over, it expands smoothly into a compact list.

---

## 2. Premium Color Palettes (Theme Switcher)
Implement a theme toggle supporting two high-end styles:
1.  **Cosmic Obsidian (Default):**
    -   Banner Background: Semi-transparent obsidian-black glass (`background: rgba(8, 8, 14, 0.85)`), backdrop blur (`30px`), and a 1px border styled with a subtle indigo-to-violet gradient.
    -   Lighting Accents: Soft, warm solar rose-gold (`rgba(255, 127, 80, 0.35)`) and cosmic purple shadows.
2.  **Solar Frost:**
    -   Banner Background: Frosted white glass (`background: rgba(255, 255, 255, 0.7)`), backdrop blur (`25px`), ultra-thin light-gray borders (`rgba(0, 0, 0, 0.08)`).
    -   Lighting Accents: Warm gold shadows and pearl-like gradients.

---

## 3. The 3D Resonance Orb (WebGL / Three.js Shader)
Inject the Three.js library (`https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js`) to render an organic, morphing **3D Fluid Orb** inside the circular container.
-   **Geometry:** A high-density sphere (`Three.IcosahedronGeometry(2, 64)`).
-   **Material:** A custom `ShaderMaterial` with Simplex Noise distortion calculations in the vertex shader.
    -   *Vertex Shader:* Distort sphere vertices along their normals using 3D Simplex Noise, controlled by a `uTime` float and a `uAudioAmplitude` uniform to create a fluid, liquid-mercury deformation.
    -   *Fragment Shader:* Calculate lighting and color blends using Fresnel reflections. The colors must dynamically shift from deep, dark midnight violet at the center to glowing indigo and warm solar rose-gold highlights on the deformed rim.
-   **Dynamic Animation States:**
    1.  **Idle State (`.idle`):** Low noise frequency and low amplitude. The orb deforms in a slow, breathing pattern with deep violet-blue tones.
    2.  **Listening State (`.listening`):** The `uAudioAmplitude` is linked to simulated microphone values. The orb deforms into highly organic, fluid, liquid blobs that ripple and stretch, shifting colors to include warm rose-gold and bright cyan Highlights.
    3.  **Thinking State (`.thinking`):** The noise frequency increases and the rotation speed spins rapidly, creating a swirling cosmic vortex effect.
    4.  **Speaking State (`.speaking`):** The orb deforms in rhythmic, pulsating wave patterns synced with the tempo of the output captions.

---

## 4. UI Transition & Simulation Logic (JavaScript)
Provide complete JavaScript logic supporting interactive testing:
1.  **State Tester Panel:** Include a floating, collapsible button array to simulate states (`idle`, `listening`, `thinking`, `speaking`) to verify shader morphs.
2.  **Banner Slide Transition:** When state changes to `listening`, `thinking`, or `speaking`, add a `.expanded` class to the main container. Use CSS transition rules (`transition: width 0.6s cubic-bezier(0.16, 1, 0.3, 1)`) to slide the text banner out smoothly.
3.  **Mock Command Loop:** Typing a request and hitting Send should expand the banner, transition the 3D orb to `thinking`, append log actions, display speech captions in `speaking` mode, and collapse the banner back to the corner circle after a timeout.
4.  **PyWebview Hooks:** Expose the state-manipulation functions (e.g. `setOrbState(state)`) globally so the Python `gui.py` can invoke them directly.
