import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { SpringMassSim } from '../components/SpringMassSim';
import { EnergyConservationChart } from '../components/EnergyConservationChart';

interface PhysicsData {
  q: number;
  p: number;
  m: number;
  k: number;
  T: number;
  V: number;
  E: number;
}

interface Fingerprint {
  timestamp: number;
  drift_rate: number;
  energy_initial: number;
  energy_current: number;
}

function Gauge({
  value,
  min = 0,
  max = 1,
  label,
  unit = '%',
  target,
}: {
  value: number;
  min?: number;
  max?: number;
  label: string;
  unit?: string;
  target?: number;
}) {
  const percentage = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
  const isGood = target === undefined || Math.abs(value - target) <= target * 2;
  const color = isGood ? '#4ade80' : percentage < 50 ? '#fbbf24' : '#f87171';

  return (
    <div className="bg-[#0f172a] rounded-xl p-4 border border-[#334155]">
      <div className="text-xs text-gray-400 mb-2">{label}</div>
      <div className="flex items-end gap-2">
        <span className="text-2xl font-bold" style={{ color }}>
          {value.toFixed(3)}
        </span>
        <span className="text-sm text-gray-500">{unit}</span>
      </div>
      <div className="mt-3 h-2 bg-[#1e293b] rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.5 }}
        />
      </div>
      {target !== undefined && (
        <div className="mt-2 text-xs text-gray-500">
          Target: {target}
          {unit}
        </div>
      )}
    </div>
  );
}

async function fetchFingerprint(): Promise<Fingerprint | null> {
  try {
    const response = await fetch('/api/physics/fingerprint');
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

export function PhysicsLab() {
  const [isRunning, setIsRunning] = useState(true);
  const [energyData, setEnergyData] = useState<{ timestamp: number; T: number; V: number; E: number }[]>([]);
  const [physicsState, setPhysicsState] = useState<PhysicsData | null>(null);
  const [fingerprint, setFingerprint] = useState<Fingerprint | null>(null);

  const handleStateChange = useCallback((state: { q: number; p: number; m: number; k: number }) => {
    const T = (state.p ** 2) / (2 * state.m);
    const V = 0.5 * state.k * (state.q ** 2);
    const E = T + V;
    
    setPhysicsState({ ...state, T, V, E });
    
    setEnergyData((prev) => {
      const newData = [...prev, { timestamp: Date.now(), T, V, E }];
      return newData.slice(-100);
    });
  }, []);

  useEffect(() => {
    fetchFingerprint().then(setFingerprint);
    const interval = setInterval(() => {
      fetchFingerprint().then(setFingerprint);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const currentDrift = physicsState
    ? Math.abs((physicsState.E - (physicsState.T + physicsState.V)) / physicsState.E) * 100
    : 0;

  const initialEnergy = energyData[0]?.E ?? physicsState?.E ?? 1;
  const currentEnergy = physicsState?.E ?? 1;
  const driftRate = initialEnergy > 0 
    ? ((currentEnergy - initialEnergy) / initialEnergy) * 100 
    : 0;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <motion.h1
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          className="text-2xl font-bold text-white"
        >
          Physics Lab - SympNet
        </motion.h1>
        <button
          onClick={() => setIsRunning(!isRunning)}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            isRunning
              ? 'bg-red-500/20 text-red-400 border border-red-500/50'
              : 'bg-green-500/20 text-green-400 border border-green-500/50'
          }`}
        >
          {isRunning ? 'Pause' : 'Start'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="lg:col-span-1 rounded-xl bg-[#0f172a] border border-[#334155] overflow-hidden"
        >
          <div className="p-4 border-b border-[#334155]">
            <h2 className="text-lg font-semibold text-white">Spring-Mass System</h2>
            <p className="text-xs text-gray-500">SympNet 辛积分器</p>
          </div>
          <div className="h-[350px]">
            <SpringMassSim onStateChange={handleStateChange} running={isRunning} />
          </div>
        </motion.div>

        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="lg:col-span-1"
        >
          <EnergyConservationChart data={energyData} />
          
          <div className="mt-4 space-y-4">
            <Gauge
              value={driftRate}
              label="Energy Drift Rate"
              unit="%"
              target={0.1}
            />
            <Gauge
              value={currentDrift}
              label="Current Drift"
              unit="%"
            />
          </div>
        </motion.div>

        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="lg:col-span-1 space-y-4"
        >
          <div className="bg-[#0f172a] rounded-xl p-4 border border-[#334155]">
            <h3 className="text-lg font-semibold text-white mb-4">漂移率仪表盘</h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">API 漂移率</span>
                <span className={`font-mono ${
                  (fingerprint?.drift_rate ?? 0) < 0.1 
                    ? 'text-green-400' 
                    : 'text-yellow-400'
                }`}>
                  {(fingerprint?.drift_rate ?? 0).toFixed(4)}%
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">初始能量</span>
                <span className="font-mono text-white">
                  {(fingerprint?.energy_initial ?? 0).toFixed(4)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">当前能量</span>
                <span className="font-mono text-white">
                  {(fingerprint?.energy_current ?? 0).toFixed(4)}
                </span>
              </div>
            </div>
          </div>

          <div className="bg-[#0f172a] rounded-xl p-4 border border-[#334155]">
            <h3 className="text-lg font-semibold text-white mb-4">物理参数</h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">质量 m</span>
                <span className="font-mono text-cyan-400">
                  {physicsState?.m ?? 1.0}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">刚度 k</span>
                <span className="font-mono text-cyan-400">
                  {physicsState?.k ?? 2.0}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">动能 T</span>
                <span className="font-mono text-green-400">
                  {(physicsState?.T ?? 0).toFixed(4)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">势能 V</span>
                <span className="font-mono text-yellow-400">
                  {(physicsState?.V ?? 0).toFixed(4)}
                </span>
              </div>
              <div className="flex justify-between items-center pt-2 border-t border-[#334155]">
                <span className="text-gray-400">总能量 E</span>
                <span className="font-mono text-purple-400 font-bold">
                  {(physicsState?.E ?? 0).toFixed(4)}
                </span>
              </div>
            </div>
          </div>

          <div className={`rounded-xl p-4 border ${
            Math.abs(driftRate) < 0.1
              ? 'bg-green-500/10 border-green-500/30'
              : 'bg-yellow-500/10 border-yellow-500/30'
          }`}>
            <div className="text-center">
              <div className={`text-2xl font-bold ${
                Math.abs(driftRate) < 0.1
                  ? 'text-green-400'
                  : 'text-yellow-400'
              }`}>
                {Math.abs(driftRate) < 0.1 ? '✓ PASS' : '⚠ WATCH'}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                目标: drift &lt; 0.1%
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}