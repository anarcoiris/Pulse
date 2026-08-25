import React, { useRef, useEffect, useState } from 'react';
import * as THREE from 'three';
import { Mesh3DData, PCBVectors2D } from '../types';
import { RotateCw, RefreshCcw, Box, Sun } from 'lucide-react';

interface PCBViewer3DProps {
  meshData: Mesh3DData | null;
  vectors: PCBVectors2D | null;
  boardWidth: number;
  boardHeight: number;
}

export const PCBViewer3D: React.FC<PCBViewer3DProps> = ({
  meshData,
  vectors,
  boardWidth,
  boardHeight,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [autoRotate, setAutoRotate] = useState(true);
  const [lightingMode, setLightingMode] = useState<'studio' | 'gold'>('studio');

  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const boardGroupRef = useRef<THREE.Group | null>(null);

  useEffect(() => {
    if (!containerRef.current || !meshData) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    // 1. Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#0a0c10');
    sceneRef.current = scene;

    // 2. Camera
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, -boardHeight * 1.3, boardHeight * 1.5);
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    // 3. Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    rendererRef.current = renderer;

    containerRef.current.innerHTML = '';
    containerRef.current.appendChild(renderer.domElement);

    // 4. Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 1.8);
    dirLight1.position.set(50, -50, 100);
    dirLight1.castShadow = true;
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x38bdf8, 0.9);
    dirLight2.position.set(-60, 60, 40);
    scene.add(dirLight2);

    const pointLight = new THREE.PointLight(0xf59e0b, 1.2, 150);
    pointLight.position.set(0, 0, 30);
    scene.add(pointLight);

    // 5. Board Object Group
    const boardGroup = new THREE.Group();
    boardGroupRef.current = boardGroup;
    scene.add(boardGroup);

    // 5a. FR4 PCB Substrate
    const pcbThick = 1.6;
    const boardGeo = new THREE.BoxGeometry(boardWidth, boardHeight, pcbThick);
    const boardMat = new THREE.MeshPhysicalMaterial({
      color: lightingMode === 'studio' ? 0x0f172a : 0x064e3b, // Dark obsidian or British racing green
      roughness: 0.35,
      metalness: 0.1,
      clearcoat: 0.3,
      clearcoatRoughness: 0.1,
    });
    const boardMesh = new THREE.Mesh(boardGeo, boardMat);
    boardMesh.receiveShadow = true;
    boardMesh.castShadow = true;
    boardGroup.add(boardMesh);

    // 5b. Mounting Holes (Centered)
    if (vectors?.mounting_holes) {
      vectors.mounting_holes.forEach((mh) => {
        const mhX = mh.x;
        const mhY = -mh.y;
        // Golden annular ring
        const ringGeo = new THREE.CylinderGeometry(mh.pad_dia / 2, mh.pad_dia / 2, 0.05, 32);
        const ringMat = new THREE.MeshStandardMaterial({ color: 0xd4af37, roughness: 0.2, metalness: 0.85 });
        const ringMesh = new THREE.Mesh(ringGeo, ringMat);
        ringMesh.rotation.x = Math.PI / 2;
        ringMesh.position.set(mhX, mhY, pcbThick / 2 + 0.03);
        boardGroup.add(ringMesh);

        // Through hole
        const holeGeo = new THREE.CylinderGeometry(mh.drill / 2, mh.drill / 2, pcbThick + 0.2, 32);
        const holeMat = new THREE.MeshBasicMaterial({ color: 0x090a0f });
        const holeMesh = new THREE.Mesh(holeGeo, holeMat);
        holeMesh.rotation.x = Math.PI / 2;
        holeMesh.position.set(mhX, mhY, 0);
        boardGroup.add(holeMesh);
      });
    }

    // 5c. Copper Traces (Centered)
    if (vectors?.traces) {
      const traceMat = new THREE.MeshStandardMaterial({
        color: 0xf59e0b,
        metalness: 0.8,
        roughness: 0.3,
      });

      vectors.traces.forEach((tr) => {
        const x1 = tr.start[0];
        const y1 = -tr.start[1];
        const x2 = tr.end[0];
        const y2 = -tr.end[1];

        const dx = x2 - x1;
        const dy = y2 - y1;
        const len = Math.sqrt(dx * dx + dy * dy);
        if (len < 0.1) return;

        const traceGeo = new THREE.BoxGeometry(tr.width, len, 0.04);
        const traceMesh = new THREE.Mesh(traceGeo, traceMat);
        const angle = Math.atan2(dy, dx) - Math.PI / 2;
        traceMesh.position.set((x1 + x2) / 2, (y1 + y2) / 2, pcbThick / 2 + 0.02);
        traceMesh.rotation.z = angle;
        boardGroup.add(traceMesh);
      });
    }

    // 5d. Vias (Centered)
    if (vectors?.vias) {
      const viaMat = new THREE.MeshStandardMaterial({ color: 0x10b981, metalness: 0.7, roughness: 0.3 });
      vectors.vias.forEach((v) => {
        const vx = v.x;
        const vy = -v.y;
        const vGeo = new THREE.CylinderGeometry(v.diameter / 2, v.diameter / 2, 0.06, 16);
        const vMesh = new THREE.Mesh(vGeo, viaMat);
        vMesh.rotation.x = Math.PI / 2;
        vMesh.position.set(vx, vy, pcbThick / 2 + 0.03);
        boardGroup.add(vMesh);
      });
    }

    // 5e. Components & 3D Packages
    meshData.components.forEach((comp) => {
      const refUpper = comp.ref.toUpperCase();
      const valUpper = (comp.value || '').toUpperCase();
      const pkgType = comp.package_type || 'GENERIC';
      const rotZ = THREE.MathUtils.degToRad(-comp.rotation);

      const compGroup = new THREE.Group();
      compGroup.position.set(comp.x, comp.y, pcbThick / 2);
      compGroup.rotation.z = rotZ;

      if (pkgType === 'MCU' || valUpper.includes('ESP') || valUpper.includes('MCU')) {
        // ESP32 Module (Substrate + Silver Metal Shield)
        const subGeo = new THREE.BoxGeometry(comp.width || 18, comp.length || 25.5, 0.8);
        const subMat = new THREE.MeshStandardMaterial({ color: 0x18181b, roughness: 0.5 });
        const subMesh = new THREE.Mesh(subGeo, subMat);
        subMesh.position.set(0, 0, 0.4);

        // Metallic RF Shield
        const shieldGeo = new THREE.BoxGeometry((comp.width || 18) - 2.0, 16, 2.2);
        const shieldMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, metalness: 0.95, roughness: 0.15 });
        const shieldMesh = new THREE.Mesh(shieldGeo, shieldMat);
        shieldMesh.position.set(0, 2.0, 1.5);

        compGroup.add(subMesh);
        compGroup.add(shieldMesh);
      } else if (pkgType === 'CONNECTOR' || valUpper.includes('USB')) {
        // USB-C Metallic Receptacle Shell
        const usbGeo = new THREE.BoxGeometry(comp.width || 8.9, comp.length || 7.3, comp.height || 3.2);
        const usbMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.9, roughness: 0.2 });
        const usbMesh = new THREE.Mesh(usbGeo, usbMat);
        usbMesh.position.set(0, 0, (comp.height || 3.2) / 2);
        compGroup.add(usbMesh);
      } else if (pkgType === 'HEADER') {
        // Pin Header (Black Insulator + Golden Pins)
        const baseGeo = new THREE.BoxGeometry(comp.width || 2.54, comp.length || 5.0, 2.5);
        const baseMat = new THREE.MeshStandardMaterial({ color: 0x09090b, roughness: 0.6 });
        const baseMesh = new THREE.Mesh(baseGeo, baseMat);
        baseMesh.position.set(0, 0, 1.25);
        compGroup.add(baseMesh);

        // Gold pin
        const pinGeo = new THREE.BoxGeometry(0.64, 0.64, 8.5);
        const pinMat = new THREE.MeshStandardMaterial({ color: 0xd4af37, metalness: 0.9, roughness: 0.15 });
        const pinMesh = new THREE.Mesh(pinGeo, pinMat);
        pinMesh.position.set(0, 0, 4.25);
        compGroup.add(pinMesh);
      } else if (pkgType === 'REGULATOR') {
        // SOT-223 Power Regulator with Tab
        const bodyGeo = new THREE.BoxGeometry(6.5, 3.5, 1.6);
        const bodyMat = new THREE.MeshStandardMaterial({ color: 0x18181b, roughness: 0.3 });
        const bodyMesh = new THREE.Mesh(bodyGeo, bodyMat);
        bodyMesh.position.set(0, 0, 0.8);

        const tabGeo = new THREE.BoxGeometry(3.0, 3.5, 0.3);
        const tabMat = new THREE.MeshStandardMaterial({ color: 0xd4d4d8, metalness: 0.9, roughness: 0.2 });
        const tabMesh = new THREE.Mesh(tabGeo, tabMat);
        tabMesh.position.set(0, 1.8, 0.15);

        compGroup.add(bodyMesh);
        compGroup.add(tabMesh);
      } else if (pkgType === 'BUTTON') {
        // Tactile Switch Button
        const swBaseGeo = new THREE.BoxGeometry(6.0, 6.0, 3.0);
        const swBaseMat = new THREE.MeshStandardMaterial({ color: 0x27272a, roughness: 0.4 });
        const swBaseMesh = new THREE.Mesh(swBaseGeo, swBaseMat);
        swBaseMesh.position.set(0, 0, 1.5);

        const stemGeo = new THREE.CylinderGeometry(1.5, 1.5, 1.5, 16);
        const stemMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.3 });
        const stemMesh = new THREE.Mesh(stemGeo, stemMat);
        stemMesh.rotation.x = Math.PI / 2;
        stemMesh.position.set(0, 0, 3.5);

        compGroup.add(swBaseMesh);
        compGroup.add(stemMesh);
      } else if (pkgType === 'LED' || refUpper.startsWith('LED')) {
        // LED Lens
        const ledGeo = new THREE.BoxGeometry(comp.width || 1.6, comp.length || 0.8, comp.height || 0.7);
        const isRed = valUpper.includes('RED');
        const isBlue = valUpper.includes('BLUE');
        const ledColor = isRed ? 0xef4444 : isBlue ? 0x3b82f6 : 0x22c55e;
        const ledMat = new THREE.MeshStandardMaterial({
          color: ledColor,
          emissive: ledColor,
          emissiveIntensity: 0.65,
          roughness: 0.2,
        });
        const ledMesh = new THREE.Mesh(ledGeo, ledMat);
        ledMesh.position.set(0, 0, (comp.height || 0.7) / 2);
        compGroup.add(ledMesh);
      } else if (pkgType === 'CAPACITOR' || pkgType === 'RESISTOR' || refUpper.startsWith('R') || refUpper.startsWith('C')) {
        // SMD Resistor / Capacitor (Ceramic Body + Silver Terminals)
        const isCap = pkgType === 'CAPACITOR' || refUpper.startsWith('C');
        const bodyGeo = new THREE.BoxGeometry((comp.width || 2.0) * 0.6, comp.length || 1.25, comp.height || 0.8);
        const bodyMat = new THREE.MeshStandardMaterial({
          color: isCap ? 0xb45309 : 0x334155, // Ochre capacitor / navy resistor
          roughness: 0.4,
        });
        const bodyMesh = new THREE.Mesh(bodyGeo, bodyMat);
        bodyMesh.position.set(0, 0, (comp.height || 0.8) / 2);

        const termGeo = new THREE.BoxGeometry((comp.width || 2.0) * 0.22, (comp.length || 1.25) * 1.02, (comp.height || 0.8) * 1.02);
        const termMat = new THREE.MeshStandardMaterial({ color: 0xd4d4d8, metalness: 0.9, roughness: 0.2 });
        const term1 = new THREE.Mesh(termGeo, termMat);
        term1.position.set(-((comp.width || 2.0) * 0.38), 0, (comp.height || 0.8) / 2);
        const term2 = new THREE.Mesh(termGeo, termMat);
        term2.position.set((comp.width || 2.0) * 0.38, 0, (comp.height || 0.8) / 2);

        compGroup.add(bodyMesh);
        compGroup.add(term1);
        compGroup.add(term2);
      } else {
        // Generic IC Package
        const icGeo = new THREE.BoxGeometry(comp.width || 4.0, comp.length || 4.0, comp.height || 1.2);
        const icMat = new THREE.MeshStandardMaterial({ color: 0x18181b, roughness: 0.3 });
        const icMesh = new THREE.Mesh(icGeo, icMat);
        icMesh.position.set(0, 0, (comp.height || 1.2) / 2);
        compGroup.add(icMesh);
      }

      boardGroup.add(compGroup);
    });

    // 6. Orbit & Mouse Drag Controls
    let isMouseDown = false;
    let prevMouseX = 0;
    let prevMouseY = 0;

    const handleMouseDown = (e: MouseEvent) => {
      isMouseDown = true;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!isMouseDown || !boardGroupRef.current) return;
      const deltaX = e.clientX - prevMouseX;
      const deltaY = e.clientY - prevMouseY;
      boardGroupRef.current.rotation.z += deltaX * 0.01;
      boardGroupRef.current.rotation.x += deltaY * 0.01;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    };

    const handleMouseUp = () => {
      isMouseDown = false;
    };

    const domElement = renderer.domElement;
    domElement.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    // 7. Animation Loop
    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      if (autoRotate && boardGroupRef.current && !isMouseDown) {
        boardGroupRef.current.rotation.z += 0.005;
      }
      renderer.render(scene, camera);
    };
    animate();

    // Resize Handler
    const handleResize = () => {
      if (!containerRef.current || !renderer || !camera) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', handleResize);
      domElement.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      renderer.dispose();
    };
  }, [meshData, vectors, boardWidth, boardHeight, lightingMode, autoRotate]);

  return (
    <div className="relative w-full h-full bg-[#08090d] rounded-xl overflow-hidden border border-zinc-800 shadow-2xl flex flex-col select-none">
      {/* 3D Viewport Controls */}
      <div className="absolute top-4 left-4 z-20 flex items-center gap-2 bg-zinc-900/90 backdrop-blur-md px-3 py-2 rounded-lg border border-zinc-800 text-xs shadow-lg">
        <button
          onClick={() => setAutoRotate((r) => !r)}
          className={`flex items-center gap-1.5 px-2 py-1 rounded transition-colors ${
            autoRotate ? 'bg-indigo-600 text-white font-semibold' : 'text-zinc-400 hover:text-white bg-zinc-800'
          }`}
          title="Toggle Auto Rotation"
        >
          <RotateCw className={`w-3.5 h-3.5 ${autoRotate ? 'animate-spin' : ''}`} />
          <span>Rotate</span>
        </button>

        <button
          onClick={() => {
            if (boardGroupRef.current) {
              boardGroupRef.current.rotation.set(0, 0, 0);
            }
          }}
          className="flex items-center gap-1.5 px-2 py-1 rounded transition-colors text-zinc-400 hover:text-white bg-zinc-800"
          title="Reset Camera Orientation"
        >
          <RefreshCcw className="w-3.5 h-3.5" />
          <span>Reset</span>
        </button>

        <div className="h-4 w-px bg-zinc-700 mx-1" />

        <button
          onClick={() => setLightingMode((m) => (m === 'studio' ? 'gold' : 'studio'))}
          className="flex items-center gap-1.5 px-2 py-1 rounded transition-colors text-zinc-300 hover:text-white bg-zinc-800"
          title="Toggle Soldermask Style"
        >
          <Sun className="w-3.5 h-3.5 text-amber-400" />
          <span>{lightingMode === 'studio' ? 'Obsidian Mask' : 'Classic Green'}</span>
        </button>
      </div>

      <div className="absolute bottom-4 right-4 z-20 bg-zinc-900/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-zinc-800 text-[11px] text-zinc-400 font-mono pointer-events-none">
        Click & Drag to Orbit | Scroll to Zoom
      </div>

      {/* Canvas Container */}
      <div ref={containerRef} className="w-full h-full flex-1 cursor-grab active:cursor-grabbing" />
    </div>
  );
};
