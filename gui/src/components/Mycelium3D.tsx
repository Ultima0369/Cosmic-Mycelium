import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Sphere, Line } from '@react-three/drei';
import * as THREE from 'three';
import { Scale, type MyceliumNode } from '../stores/useSystemStore';

interface MyceliumNodeProps {
  node: MyceliumNode;
}

const scaleColors: Record<Scale, string> = {
  [Scale.NANO]: '#06b6d4',
  [Scale.INFANT]: '#4ade80',
  [Scale.MESH]: '#a855f7',
  [Scale.SWARM]: '#fb923c',
};

function Node({ node }: MyceliumNodeProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const color = scaleColors[node.scale] || '#c084fc';

  useFrame((_, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * 0.5;
      const scale = 1 + Math.sin(Date.now() * 0.003 + node.energy) * 0.1;
      meshRef.current.scale.setScalar(scale * (0.3 + node.energy * 0.001));
    }
  });

  return (
    <Sphere ref={meshRef} position={node.position}>
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={0.3 + node.energy * 0.001}
        roughness={0.3}
        metalness={0.7}
      />
    </Sphere>
  );
}

interface ConnectionProps {
  start: [number, number, number];
  end: [number, number, number];
}

function Connection({ start, end }: ConnectionProps) {
  const points = useMemo(() => [new THREE.Vector3(...start), new THREE.Vector3(...end)], [start, end]);
  
  return (
    <Line
      points={points}
      color="#c084fc"
      lineWidth={1}
      transparent
      opacity={0.3}
    />
  );
}

interface MyceliumNetworkProps {
  nodes: MyceliumNode[];
}

function MyceliumNetwork({ nodes }: MyceliumNetworkProps) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.05;
    }
  });

  const connections = useMemo(() => {
    const conns: ConnectionProps[] = [];
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    
    for (const node of nodes) {
      for (const connId of node.connections) {
        const target = nodeMap.get(connId);
        if (target) {
          conns.push({
            start: node.position,
            end: target.position,
          });
        }
      }
    }
    return conns;
  }, [nodes]);

  return (
    <group ref={groupRef}>
      {nodes.map((node) => (
        <Node key={node.id} node={node} />
      ))}
      {connections.map((conn, i) => (
        <Connection key={i} start={conn.start} end={conn.end} />
      ))}
    </group>
  );
}

interface Mycelium3DProps {
  nodes: MyceliumNode[];
}

function generateDemoNodes(): MyceliumNode[] {
  const scales = [Scale.INFANT, Scale.MESH, Scale.SWARM];
  const nodes: MyceliumNode[] = [];
  
  for (let i = 0; i < 30; i++) {
    const scale = scales[Math.floor(Math.random() * scales.length)];
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const radius = 2 + Math.random() * 3;
    
    nodes.push({
      id: `node-${i}`,
      position: [
        radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.sin(phi) * Math.sin(theta),
        radius * Math.cos(phi),
      ],
      scale,
      energy: Math.random() * 100,
      connections: [],
    });
  }

  for (const node of nodes) {
    const numConnections = Math.floor(Math.random() * 3) + 1;
    const otherNodes = nodes.filter((n) => n.id !== node.id);
    for (let i = 0; i < numConnections && i < otherNodes.length; i++) {
      const target = otherNodes[Math.floor(Math.random() * otherNodes.length)];
      if (!node.connections.includes(target.id)) {
        node.connections.push(target.id);
      }
    }
  }

  return nodes;
}

export function Mycelium3D({ nodes }: Mycelium3DProps) {
  const displayNodes = useMemo(() => {
    if (nodes.length > 0) return nodes;
    return generateDemoNodes();
  }, [nodes]);

  return (
    <div className="w-full h-[400px] rounded-xl bg-bg-secondary border border-border overflow-hidden">
      <Canvas camera={{ position: [0, 0, 10], fov: 60 }}>
        <ambientLight intensity={0.3} />
        <pointLight position={[10, 10, 10]} intensity={1} />
        <pointLight position={[-10, -10, -10]} intensity={0.5} color="#c084fc" />
        
        <MyceliumNetwork nodes={displayNodes} />
        
        <OrbitControls
          enableZoom
          enablePan
          enableRotate
          autoRotate
          autoRotateSpeed={0.5}
        />
      </Canvas>
      <div className="absolute bottom-4 left-4 text-xs text-text-secondary">
        Drag to rotate | Scroll to zoom
      </div>
    </div>
  );
}