import { create } from 'zustand';

export enum Scale {
  NANO = 'NANO',
  INFANT = 'INFANT',
  MESH = 'MESH',
  SWARM = 'SWARM',
}

export interface FractalMessage {
  id: string;
  from_scale: Scale;
  to_scale: Scale;
  content: string;
  fidelity: number;
  timestamp: number;
}

export interface EchoPattern {
  id: string;
  signature: string;
  source_scale: Scale;
  count: number;
  last_activated: number;
  severity: 'low' | 'medium' | 'high';
}

export interface HeatmapCell {
  fromScale: Scale;
  toScale: Scale;
  intensity: number;
}

interface FractalState {
  messages: FractalMessage[];
  echoPatterns: EchoPattern[];
  heatmapData: HeatmapCell[];
  isLoading: boolean;
  selectedMessage: string | null;
  
  setMessages: (messages: FractalMessage[]) => void;
  setEchoPatterns: (patterns: EchoPattern[]) => void;
  setHeatmapData: (data: HeatmapCell[]) => void;
  setLoading: (loading: boolean) => void;
  setSelectedMessage: (id: string | null) => void;
}

export const useFractalStore = create<FractalState>((set) => ({
  messages: [],
  echoPatterns: [],
  heatmapData: [],
  isLoading: false,
  selectedMessage: null,

  setMessages: (messages) => set({ messages }),
  setEchoPatterns: (patterns) => set({ echoPatterns: patterns }),
  setHeatmapData: (data) => set({ heatmapData: data }),
  setLoading: (loading) => set({ isLoading: loading }),
  setSelectedMessage: (id) => set({ selectedMessage: id }),
}));

const API_BASE = '/api';

export async function fetchFractalMessages(): Promise<void> {
  useFractalStore.getState().setLoading(true);
  try {
    const response = await fetch(`${API_BASE}/fractal/messages?limit=50`);
    if (!response.ok) throw new Error('Failed to fetch messages');
    const data = await response.json();
    useFractalStore.getState().setMessages(data);
    
    const heatmapData = computeHeatmap(data);
    useFractalStore.getState().setHeatmapData(heatmapData);
  } catch (error) {
    console.error('Failed to fetch fractal messages:', error);
  } finally {
    useFractalStore.getState().setLoading(false);
  }
}

export async function fetchEchoPatterns(): Promise<void> {
  try {
    const response = await fetch(`${API_BASE}/fractal/echoes`);
    if (!response.ok) throw new Error('Failed to fetch echoes');
    const data = await response.json();
    useFractalStore.getState().setEchoPatterns(data);
  } catch (error) {
    console.error('Failed to fetch echo patterns:', error);
  }
}

function computeHeatmap(messages: FractalMessage[]): HeatmapCell[] {
  const scales = [Scale.NANO, Scale.INFANT, Scale.MESH, Scale.SWARM];
  const matrix: Record<string, number> = {};
  
  for (const msg of messages) {
    const key = `${msg.from_scale}->${msg.to_scale}`;
    matrix[key] = (matrix[key] || 0) + msg.fidelity;
  }
  
  const cells: HeatmapCell[] = [];
  for (const from of scales) {
    for (const to of scales) {
      const key = `${from}->${to}`;
      cells.push({
        fromScale: from,
        toScale: to,
        intensity: matrix[key] || 0,
      });
    }
  }
  
  return cells;
}