import { useRef, useMemo, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Sphere, Line, Text } from '@react-three/drei';
import * as THREE from 'three';

interface PhysicsState {
  q: number;
  p: number;
  m: number;
  k: number;
  dt: number;
}

interface SpringMassSimProps {
  onStateChange?: (state: PhysicsState) => void;
  running?: boolean;
}

function Spring({ start, end }: { start: [number, number, number]; end: [number, number, number] }) {
  const points = useMemo(() => {
    const startVec = new THREE.Vector3(...start);
    const endVec = new THREE.Vector3(...end);
    const diff = endVec.clone().sub(startVec);
    const length = diff.length();
    const segments = 20;
    const positions: THREE.Vector3[] = [];
    
    for (let i = 0; i <= segments; i++) {
      const t = i / segments;
      const point = startVec.clone().add(diff.clone().multiplyScalar(t));
      const wave = Math.sin(t * Math.PI * 4) * 0.05 * (1 - Math.abs(t - 0.5) * 2);
      point.y += wave;
      positions.push(point);
    }
    
    return positions;
  }, [start, end]);

  return (
    <Line
      points={points}
      color="#22d3ee"
      lineWidth={2}
    />
  );
}

function Mass({ position, onClick }: { position: [number, number, number]; onClick?: () => void }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  useFrame(() => {
    if (meshRef.current) {
      const scale = hovered ? 1.2 : 1;
      meshRef.current.scale.lerp(new THREE.Vector3(scale, scale, scale), 0.1);
    }
  });

  return (
    <Sphere
      ref={meshRef}
      position={position}
      args={[0.3, 32, 32]}
      onClick={onClick}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
    >
      <meshStandardMaterial
        color={hovered ? '#f472b6' : '#c084fc'}
        emissive={hovered ? '#f472b6' : '#c084fc'}
        emissiveIntensity={0.5}
        roughness={0.2}
        metalness={0.8}
      />
    </Sphere>
  );
}

function Simulation({ onStateChange, running = true }: SpringMassSimProps) {
  const physicsRef = useRef<PhysicsState>({
    q: 2,
    p: 0,
    m: 1,
    k: 2,
    dt: 0.016,
  });

  const massRef = useRef<THREE.Group>(null);
  const [state, setState] = useState(physicsRef.current);

  useFrame((_, delta) => {
    if (!running || !massRef.current) return;

    const ps = physicsRef.current;
    const dt = Math.min(delta, 0.033);

    const q = ps.q;
    const p = ps.p;
    const m = ps.m;
    const k = ps.k;

    const dq_dt = p / m;
    const dp_dt = -k * q;

    ps.q += dq_dt * dt;
    ps.p += dp_dt * dt;

    ps.q = Math.max(-3, Math.min(3, ps.q));

    massRef.current.position.x = ps.q;

    const currentState = { ...ps };
    setState(currentState);
    onStateChange?.(currentState);
  });

  const anchorPos: [number, number, number] = [-3, 0, 0];
  const massPos: [number, number, number] = [state.q, 0, 0];

  return (
    <group>
      <Line
        points={[
          new THREE.Vector3(-4, 0, 0),
          new THREE.Vector3(-3, 0, 0),
        ]}
        color="#64748b"
        lineWidth={4}
      />
      <Sphere position={anchorPos} args={[0.1, 16, 16]}>
        <meshStandardMaterial color="#64748b" metalness={0.9} roughness={0.3} />
      </Sphere>
      <Spring start={anchorPos} end={massPos} />
      <group ref={massRef} position={massPos}>
        <Mass position={[0, 0, 0]} />
      </group>
    </group>
  );
}

export function SpringMassSim({ onStateChange, running = true }: SpringMassSimProps) {
  const [physicsState, setPhysicsState] = useState<PhysicsState | null>(null);

  const handleStateChange = (state: PhysicsState) => {
    setPhysicsState(state);
    onStateChange?.(state);
  };

  const T = physicsState ? (physicsState.p ** 2) / (2 * physicsState.m) : 0;
  const V = physicsState ? 0.5 * physicsState.k * (physicsState.q ** 2) : 0;
  const E = T + V;

  return (
    <div className="relative w-full h-full">
      <Canvas camera={{ position: [0, 2, 6], fov: 50 }}>
        <ambientLight intensity={0.4} />
        <pointLight position={[5, 5, 5]} intensity={1} />
        <pointLight position={[-5, 3, -5]} intensity={0.5} color="#22d3ee" />
        
        <Simulation onStateChange={handleStateChange} running={running} />
        
        <OrbitControls
          enableZoom
          enablePan={false}
          enableRotate
          minPolarAngle={Math.PI / 4}
          maxPolarAngle={Math.PI / 2}
        />
        
        <gridHelper args={[10, 20, '#334155', '#1e293b']} rotation={[Math.PI / 2, 0, 0]} />
      </Canvas>
      
      {physicsState && (
        <div className="absolute bottom-4 left-4 bg-black/60 backdrop-blur-sm rounded-lg p-3 text-xs space-y-1">
          <div className="text-cyan-400">
            <span className="text-gray-400">q = </span>
            {physicsState.q.toFixed(3)}
          </div>
          <div className="text-purple-400">
            <span className="text-gray-400">p = </span>
            {physicsState.p.toFixed(3)}
          </div>
          <div className="border-t border-gray-700 pt-1 mt-1">
            <div className="text-green-400">T = {T.toFixed(3)}</div>
            <div className="text-yellow-400">V = {V.toFixed(3)}</div>
            <div className="text-white font-semibold">E = {E.toFixed(3)}</div>
          </div>
        </div>
      )}
    </div>
  );
}