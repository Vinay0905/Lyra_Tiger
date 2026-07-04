import React, { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { useAppStore } from '../store/useAppStore'
import type { OrbState } from '../store/useAppStore'

// ─── VERTEX SHADER ────────────────────────────────────────────────────────────
// Multi-layered low-frequency simplex noise drives soft, organic liquid deformation.
const vertexShader = `
  uniform float uTime;
  uniform float uAudioLevel;
  uniform float uNoiseFreq;
  uniform float uWarpStrength;
  varying vec3 vNormal;
  varying vec3 vPosition;
  varying float vNoise;

  // Simplex 3D Noise (Ashima Arts)
  vec4 permute(vec4 x){return mod(((x*34.0)+1.0)*x, 289.0);}
  vec4 taylorInvSqrt(vec4 r){return 1.79284291400159 - 0.85373472095314 * r;}
  float snoise(vec3 v){
    const vec2 C = vec2(1.0/6.0, 1.0/3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i  = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + 2.0 * C.xxx;
    vec3 x3 = x0 - D.yyy;
    i = mod(i, 289.0);
    vec4 p = permute(permute(permute(
        i.z + vec4(0.0, i1.z, i2.z, 1.0))
      + i.y + vec4(0.0, i1.y, i2.y, 1.0))
      + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 1.0/7.0;
    vec3 ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ * ns.x + ns.yyyy;
    vec4 y = y_ * ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    vec4 s0 = floor(b0)*2.0 + 1.0;
    vec4 s1 = floor(b1)*2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
    vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
    m = m * m;
    return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
  }

  void main() {
    vNormal = normal;
    vPosition = position;

    // Primary slow wave — the liquid "breathing" base layer
    float baseWave = snoise(position * uNoiseFreq + uTime * 0.45);
    // Secondary high-frequency ripple — audio-reactive fine detail
    float ripple   = snoise(position * uNoiseFreq * 2.8 + uTime * 1.1) * uAudioLevel;
    // Domain-warp offset — samples noise displaced by a secondary noise field
    vec3 warpOffset = vec3(
      snoise(position * 0.9 + uTime * 0.3),
      snoise(position * 0.9 + uTime * 0.3 + 3.14),
      snoise(position * 0.9 + uTime * 0.3 + 6.28)
    ) * uWarpStrength;

    float displacement = baseWave * 0.14 + ripple * 0.18;
    vec3 newPosition = position + normal * displacement + warpOffset * 0.06;

    vNoise = displacement;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
  }
`

// ─── FRAGMENT SHADER ──────────────────────────────────────────────────────────
// Domain-warped color blending creates flowing marble/liquid texture.
// Tight palette: ocean blue + electric cyan + restrained violet.
const fragmentShader = `
  varying vec3 vNormal;
  varying vec3 vPosition;
  varying float vNoise;
  uniform vec3  uColorA;
  uniform vec3  uColorB;
  uniform vec3  uColorRim;
  uniform float uTime;
  uniform float uGlow;

  void main() {
    vec3 n  = normalize(vNormal);
    vec3 eye = normalize(vec3(0.0, 0.0, 1.0));

    // Fresnel glow — luminous edge falloff
    float fresnel = pow(1.0 - max(dot(n, eye), 0.0), 2.0);

    // Noise-warped texture coordinate for fluid color banding
    float band = sin(vPosition.y * 3.0 + vNoise * 6.0 + uTime * 0.5) * 0.5 + 0.5;

    vec3 baseColor  = mix(uColorA, uColorB, band);
    vec3 finalColor = mix(baseColor, uColorRim, fresnel * uGlow);

    // Soft specular hotspot
    float spec = pow(max(dot(n, normalize(vec3(0.6, 0.8, 1.0))), 0.0), 18.0);
    finalColor += vec3(0.12, 0.20, 0.30) * spec;

    // Opacity: pearlescent center, luminous rim
    float alpha = 0.18 + smoothstep(0.1, 0.8, fresnel) * 0.75;

    gl_FragColor = vec4(finalColor, alpha);
  }
`

// ─── Types ────────────────────────────────────────────────────────────────────
interface OrbVisualizerProps {
  width: number
  height: number
}

// ─── State config (colour palette per state) ─────────────────────────────────
const STATE_CONFIG: Record<OrbState, {
  colorA: string
  colorB: string
  colorRim: string
  glow: number
  noiseFreq: number
  warpStrength: number
  amplitudeBase: number
  speed: number
}> = {
  idle: {
    colorA: '#001433', colorB: '#002a5c', colorRim: '#00c8ff',
    glow: 0.9, noiseFreq: 1.1, warpStrength: 0.8,
    amplitudeBase: 0.0, speed: 0.45,
  },
  listening: {
    colorA: '#00112b', colorB: '#003366', colorRim: '#00eaff',
    glow: 1.1, noiseFreq: 1.4, warpStrength: 1.2,
    amplitudeBase: 0.0, speed: 0.9,
  },
  thinking: {
    // Restrained internal turbulence — NOT a cosmic vortex.
    // Slightly higher noise frequency + subtle warp gives internal liquid flow feel.
    colorA: '#050525', colorB: '#0a0a4a', colorRim: '#6070ff',
    glow: 0.85, noiseFreq: 1.8, warpStrength: 1.5,
    amplitudeBase: 0.18, speed: 0.6,
  },
  speaking: {
    colorA: '#000e2e', colorB: '#001a55', colorRim: '#4488ff',
    glow: 1.05, noiseFreq: 1.3, warpStrength: 1.0,
    amplitudeBase: 0.0, speed: 0.7,
  },
  error: {
    colorA: '#1a0000', colorB: '#2a0000', colorRim: '#cc2200',
    glow: 0.6, noiseFreq: 0.8, warpStrength: 0.4,
    amplitudeBase: 0.06, speed: 0.25,
  },
}

// ─── Component ────────────────────────────────────────────────────────────────
export const OrbVisualizer: React.FC<OrbVisualizerProps> = ({ width, height }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const webglFailedRef = useRef(false)

  const orbState  = useAppStore((s) => s.orbState)
  const volume    = useAppStore((s) => s.volumeLevel)

  // Respect the OS "Reduce Motion" accessibility setting (U3)
  const prefersReducedMotion =
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  // Keep refs so the animation loop always reads latest values without re-mounting
  const stateRef  = useRef<OrbState>(orbState)
  const volumeRef = useRef<number>(volume)

  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const cameraRef   = useRef<THREE.PerspectiveCamera | null>(null)
  const materialRef = useRef<THREE.ShaderMaterial | null>(null)

  useEffect(() => { stateRef.current = orbState }, [orbState])
  useEffect(() => { volumeRef.current = volume  }, [volume])

  // Resize renderer when prop dimensions change
  useEffect(() => {
    if (rendererRef.current && cameraRef.current) {
      rendererRef.current.setSize(width, height)
      cameraRef.current.aspect = width / height
      cameraRef.current.updateProjectionMatrix()
    }
  }, [width, height])

  // Main Three.js setup — runs once on mount
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    // ── WebGL capability check ──────────────────────────────────────────────
    try {
      const testCanvas = document.createElement('canvas')
      const gl = testCanvas.getContext('webgl') || testCanvas.getContext('experimental-webgl')
      if (!gl) throw new Error('WebGL not supported')
    } catch {
      webglFailedRef.current = true
      return  // Fallback CSS orb will render instead
    }

    // ── Scene & Camera ──────────────────────────────────────────────────────
    const scene  = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100)
    camera.position.z = 4.5
    cameraRef.current = camera

    // ── Renderer ────────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    container.appendChild(renderer.domElement)
    rendererRef.current = renderer

    // ── Geometry — smooth subdivision sphere ────────────────────────────────
    const geometry = new THREE.IcosahedronGeometry(1.4, 64)

    // ── Shader Material ─────────────────────────────────────────────────────
    const cfg = STATE_CONFIG.idle
    const material = new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: {
        uTime:         { value: 0 },
        uAudioLevel:   { value: 0 },
        uNoiseFreq:    { value: cfg.noiseFreq },
        uWarpStrength: { value: cfg.warpStrength },
        uColorA:       { value: new THREE.Color(cfg.colorA) },
        uColorB:       { value: new THREE.Color(cfg.colorB) },
        uColorRim:     { value: new THREE.Color(cfg.colorRim) },
        uGlow:         { value: cfg.glow },
      },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
    materialRef.current = material

    const mesh = new THREE.Mesh(geometry, material)
    scene.add(mesh)

    // ── LERP helpers ────────────────────────────────────────────────────────
    let time           = 0
    let smoothedAudio  = 0
    let currentFreq    = cfg.noiseFreq
    let currentWarp    = cfg.warpStrength
    let currentGlow    = cfg.glow

    const targetColorA   = new THREE.Color(cfg.colorA)
    const targetColorB   = new THREE.Color(cfg.colorB)
    const targetColorRim = new THREE.Color(cfg.colorRim)

    let rafId = 0

    // ── Render loop — samples values frame by frame ─────────────────────────
    const animate = () => {
      rafId = requestAnimationFrame(animate)

      // Battery/visibility-aware throttle: skip GPU work while the popover is
      // hidden (blur/tray-toggle) — the render is pure overhead then. (U3)
      if (typeof document !== 'undefined' && document.hidden) return

      const state = stateRef.current
      const rawVolume = volumeRef.current
      const stateCfg  = STATE_CONFIG[state]

      // Time advances at state-specific speed (slowed under Reduce Motion)
      const motionScale = prefersReducedMotion ? 0.15 : 1.0
      time += 0.01 * stateCfg.speed * 1.5 * motionScale

      // Smoothed audio: layered on top of AnalyserNode's own smoothingTimeConstant.
      // Fast attack (0.25), slow decay (0.08) — different per state.
      const attackRate = state === 'listening' ? 0.35 : 0.25
      const decayRate  = state === 'speaking'  ? 0.12 : 0.08
      const alpha = rawVolume > smoothedAudio ? attackRate : decayRate
      smoothedAudio = smoothedAudio + (rawVolume - smoothedAudio) * alpha

      // Compute total audio level fed into shader
      const audioLevel = stateCfg.amplitudeBase + smoothedAudio * (
        state === 'listening' ? 1.2 : state === 'speaking' ? 1.0 : 0.5
      )

      // LERP structural uniforms toward state targets
      const lerpRate = 0.06
      currentFreq = currentFreq + (stateCfg.noiseFreq    - currentFreq) * lerpRate
      currentWarp = currentWarp + (stateCfg.warpStrength  - currentWarp) * lerpRate
      currentGlow = currentGlow + (stateCfg.glow          - currentGlow) * lerpRate

      targetColorA.set(stateCfg.colorA)
      targetColorB.set(stateCfg.colorB)
      targetColorRim.set(stateCfg.colorRim)
      material.uniforms.uColorA.value.lerp(targetColorA,   lerpRate * 1.2)
      material.uniforms.uColorB.value.lerp(targetColorB,   lerpRate * 1.2)
      material.uniforms.uColorRim.value.lerp(targetColorRim, lerpRate * 1.2)

      // Write uniforms for GPU
      material.uniforms.uTime.value       = time
      material.uniforms.uAudioLevel.value = audioLevel
      material.uniforms.uNoiseFreq.value  = currentFreq
      material.uniforms.uWarpStrength.value = currentWarp
      material.uniforms.uGlow.value       = currentGlow

      // Thinking: slow, restrained internal rotation — NOT a cosmic spin
      if (!prefersReducedMotion) {
        if (state === 'thinking') {
          mesh.rotation.y += 0.004
          mesh.rotation.x += 0.0015
        } else {
          // Gentle orbit drift for other states
          mesh.rotation.y += 0.0025
          mesh.rotation.z += 0.001
        }
      }

      renderer.render(scene, camera)
    }

    animate()

    return () => {
      cancelAnimationFrame(rafId)
      geometry.dispose()
      material.dispose()
      renderer.dispose()
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement)
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Graceful CSS fallback if WebGL fails ────────────────────────────────────
  if (webglFailedRef.current) {
    return (
      <div
        style={{ width, height }}
        className="rounded-full bg-radial from-blue-900/60 to-cyan-500/20 animate-pulse border border-cyan-500/30"
      />
    )
  }

  return (
    <div
      ref={containerRef}
      style={{ width, height }}
      className="relative overflow-hidden select-none"
    />
  )
}
