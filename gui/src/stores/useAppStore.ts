import { create } from 'zustand';

export interface Infant {
  id: string;
  name: string;
  energy: number;
  confidence: number;
  status: 'active' | 'suspended' | 'dead';
  age: number;
  breathPhase: 'CONTRACT' | 'DIFFUSE' | 'SUSPEND';
  position: { q: number[]; p: number[] };
  energyHistory: { timestamp: number; energy: number }[];
  confidenceHistory: { timestamp: number; confidence: number; surprise: number }[];
  myelinationPaths: { pathId: string; strength: number }[];
  traumaEvents: { timestamp: number; type: string; intensity: number }[];
}

interface AppState {
  infants: Infant[];
  selectedInfantId: string | null;
  setInfants: (infants: Infant[]) => void;
  addInfant: (infant: Infant) => void;
  removeInfant: (id: string) => void;
  updateInfant: (id: string, updates: Partial<Infant>) => void;
  selectInfant: (id: string | null) => void;
}

const generateMockInfant = (id: string, name: string): Infant => ({
  id,
  name,
  energy: 50 + Math.random() * 50,
  confidence: 40 + Math.random() * 40,
  status: 'active',
  age: Math.floor(Math.random() * 500),
  breathPhase: ['CONTRACT', 'DIFFUSE', 'SUSPEND'][Math.floor(Math.random() * 3)] as Infant['breathPhase'],
  position: {
    q: [Math.random() * 10, Math.random() * 10, Math.random() * 10],
    p: [Math.random() * 5, Math.random() * 5, Math.random() * 5],
  },
  energyHistory: Array.from({ length: 30 }, (_, i) => ({
    timestamp: Date.now() - (30 - i) * 1000,
    energy: 50 + Math.random() * 50,
  })),
  confidenceHistory: Array.from({ length: 30 }, (_, i) => ({
    timestamp: Date.now() - (30 - i) * 1000,
    confidence: 40 + Math.random() * 40,
    surprise: Math.random() * 20,
  })),
  myelinationPaths: [
    { pathId: 'path-alpha', strength: Math.random() },
    { pathId: 'path-beta', strength: Math.random() },
    { pathId: 'path-gamma', strength: Math.random() },
    { pathId: 'path-delta', strength: Math.random() },
  ],
  traumaEvents: Array.from({ length: Math.floor(Math.random() * 5) }, (_, i) => ({
    timestamp: Date.now() - Math.random() * 3600000,
    type: ['danger-zone', 'energy-depletion', 'collision'][Math.floor(Math.random() * 3)],
    intensity: Math.random(),
  })),
});

export const useAppStore = create<AppState>((set) => ({
  infants: [
    generateMockInfant('infant-alpha', 'Bee Alpha'),
    generateMockInfant('infant-beta', 'Bee Beta'),
    generateMockInfant('infant-gamma', 'Bee Gamma'),
    generateMockInfant('infant-delta', 'Bee Delta'),
    generateMockInfant('infant-epsilon', 'Bee Epsilon'),
  ],
  selectedInfantId: null,
  setInfants: (infants) => set({ infants }),
  addInfant: (infant) => set((state) => ({ infants: [...state.infants, infant] })),
  removeInfant: (id) => set((state) => ({ infants: state.infants.filter((i) => i.id !== id) })),
  updateInfant: (id, updates) =>
    set((state) => ({
      infants: state.infants.map((i) => (i.id === id ? { ...i, ...updates } : i)),
    })),
  selectInfant: (id) => set({ selectedInfantId: id }),
}));