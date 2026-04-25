import { create } from 'zustand';

export enum Scale {
  NANO = 'NANO',
  INFANT = 'INFANT',
  MESH = 'MESH',
  SWARM = 'SWARM',
}

export interface ScaleCount {
  scale: Scale;
  count: number;
  energy: number;
}

export interface EnergyDataPoint {
  timestamp: number;
  totalEnergy: number;
}

export interface MyceliumNode {
  id: string;
  position: [number, number, number];
  scale: Scale;
  energy: number;
  connections: string[];
}

export interface SystemState {
  scaleCounts: ScaleCount[];
  energyHistory: EnergyDataPoint[];
  myceliumNodes: MyceliumNode[];
  isConnected: boolean;
  lastUpdate: number;
  
  setScaleCounts: (counts: ScaleCount[]) => void;
  addEnergyDataPoint: (point: EnergyDataPoint) => void;
  setMyceliumNodes: (nodes: MyceliumNode[]) => void;
  setConnected: (connected: boolean) => void;
  updateFromApi: (data: {
    scale_counts?: ScaleCount[];
    energy?: number;
    nodes?: MyceliumNode[];
  }) => void;
}

const MAX_ENERGY_HISTORY = 60;

export const useSystemStore = create<SystemState>((set) => ({
  scaleCounts: [
    { scale: Scale.NANO, count: 0, energy: 0 },
    { scale: Scale.INFANT, count: 0, energy: 0 },
    { scale: Scale.MESH, count: 0, energy: 0 },
    { scale: Scale.SWARM, count: 0, energy: 0 },
  ],
  energyHistory: [],
  myceliumNodes: [],
  isConnected: false,
  lastUpdate: Date.now(),

  setScaleCounts: (counts) => set({ scaleCounts: counts, lastUpdate: Date.now() }),

  addEnergyDataPoint: (point) =>
    set((state) => ({
      energyHistory: [...state.energyHistory.slice(-MAX_ENERGY_HISTORY + 1), point],
      lastUpdate: Date.now(),
    })),

  setMyceliumNodes: (nodes) => set({ myceliumNodes: nodes, lastUpdate: Date.now() }),

  setConnected: (connected) => set({ isConnected: connected }),

  updateFromApi: (data) =>
    set((state) => {
      const newScaleCounts = data.scale_counts ?? state.scaleCounts;
      const newEnergy = data.energy ?? state.energyHistory.at(-1)?.totalEnergy ?? 0;
      const newNodes = data.nodes ?? state.myceliumNodes;

      return {
        scaleCounts: newScaleCounts,
        energyHistory: [
          ...state.energyHistory.slice(-MAX_ENERGY_HISTORY + 1),
          { timestamp: Date.now(), totalEnergy: newEnergy },
        ],
        myceliumNodes: newNodes,
        lastUpdate: Date.now(),
      };
    }),
}));

const API_BASE = '/api';

export async function fetchSystemStatus(): Promise<void> {
  try {
    const response = await fetch(`${API_BASE}/status`);
    if (!response.ok) throw new Error('Failed to fetch status');
    const data = await response.json();
    useSystemStore.getState().updateFromApi(data);
  } catch (error) {
    console.error('Failed to fetch system status:', error);
  }
}

let ws: WebSocket | null = null;

export function connectWebSocket(): void {
  if (ws?.readyState === WebSocket.OPEN) return;

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

  ws.onopen = () => {
    useSystemStore.getState().setConnected(true);
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      useSystemStore.getState().updateFromApi(data);
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  };

  ws.onclose = () => {
    useSystemStore.getState().setConnected(false);
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = () => {
    useSystemStore.getState().setConnected(false);
  };
}

export function disconnectWebSocket(): void {
  if (ws) {
    ws.close();
    ws = null;
  }
}