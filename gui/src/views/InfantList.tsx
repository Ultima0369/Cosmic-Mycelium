import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore, type Infant } from '../stores/useAppStore';

function generateId(): string {
  return `infant-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

function createDefaultInfant(id: string, name: string): Infant {
  return {
    id,
    name,
    energy: 100,
    confidence: 50 + Math.random() * 30,
    status: 'active',
    age: 0,
    breathPhase: 'DIFFUSE',
    position: {
      q: [Math.random() * 10, Math.random() * 10, Math.random() * 10],
      p: [Math.random() * 5, Math.random() * 5, Math.random() * 5],
    },
    energyHistory: Array.from({ length: 30 }, (_, i) => ({
      timestamp: Date.now() - (30 - i) * 1000,
      energy: 80 + Math.random() * 20,
    })),
    confidenceHistory: Array.from({ length: 30 }, (_, i) => ({
      timestamp: Date.now() - (30 - i) * 1000,
      confidence: 50 + Math.random() * 30,
      surprise: Math.random() * 10,
    })),
    myelinationPaths: [
      { pathId: 'path-alpha', strength: Math.random() * 0.8 },
      { pathId: 'path-beta', strength: Math.random() * 0.8 },
      { pathId: 'path-gamma', strength: Math.random() * 0.8 },
    ],
    traumaEvents: [],
  };
}

export function InfantList() {
  const navigate = useNavigate();
  const { infants, addInfant, removeInfant } = useAppStore();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');

  const handleCreate = () => {
    if (!newName.trim()) return;
    const newInfant = createDefaultInfant(generateId(), newName.trim());
    addInfant(newInfant);
    setNewName('');
    setShowCreate(false);
  };

  const handleDelete = (id: string) => {
    if (confirm('Delete this infant?')) {
      removeInfant(id);
    }
  };

  const getEnergyColor = (energy: number) => {
    if (energy > 70) return 'bg-success';
    if (energy > 30) return 'bg-warning';
    return 'bg-danger';
  };

  const getStatusBadge = (status: Infant['status']) => {
    const styles = {
      active: 'bg-success/20 text-success',
      suspended: 'bg-warning/20 text-warning',
      dead: 'bg-danger/20 text-danger',
    };
    return styles[status];
  };

  return (
    <div className="min-h-screen bg-bg-primary p-6">
      <header className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-text-primary">Infants</h1>
            <p className="text-text-secondary mt-1">
              MiniInfant Colony Management
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 rounded-lg bg-accent text-white font-medium hover:bg-accent/80 transition-colors"
          >
            + Create Infant
          </button>
        </div>
      </header>

      <AnimatePresence>
        {showCreate && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="mb-6 p-4 rounded-xl bg-bg-secondary border border-border"
          >
            <div className="flex items-center gap-4">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Infant name..."
                className="flex-1 px-4 py-2 rounded-lg bg-bg-tertiary border border-border text-text-primary placeholder:text-text-secondary focus:outline-none focus:border-accent"
                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              />
              <button
                onClick={handleCreate}
                className="px-4 py-2 rounded-lg bg-success text-white font-medium hover:bg-success/80 transition-colors"
              >
                Create
              </button>
              <button
                onClick={() => {
                  setShowCreate(false);
                  setNewName('');
                }}
                className="px-4 py-2 rounded-lg bg-bg-tertiary text-text-secondary font-medium hover:bg-border transition-colors"
              >
                Cancel
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="rounded-xl bg-bg-secondary border border-border overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="px-4 py-3 text-left text-sm font-medium text-text-secondary">
                ID
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-text-secondary">
                Name
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-text-secondary">
                Energy
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-text-secondary">
                Confidence
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-text-secondary">
                Status
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-text-secondary">
                Age
              </th>
              <th className="px-4 py-3 text-right text-sm font-medium text-text-secondary">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {infants.map((infant) => (
              <motion.tr
                key={infant.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="border-b border-border hover:bg-bg-tertiary/50 cursor-pointer transition-colors"
                onClick={() => navigate(`/infants/${infant.id}`)}
              >
                <td className="px-4 py-3 text-sm text-text-secondary font-mono">
                  {infant.id}
                </td>
                <td className="px-4 py-3 text-sm text-text-primary font-medium">
                  {infant.name}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-2 rounded-full bg-bg-tertiary overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${getEnergyColor(infant.energy)}`}
                        style={{ width: `${infant.energy}%` }}
                      />
                    </div>
                    <span className="text-sm text-text-secondary">
                      {infant.energy}%
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm text-text-secondary">
                  {(infant.confidence ?? (infant.energy * 0.8 + 10)).toFixed(1)}%
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`px-2 py-1 rounded text-xs font-medium ${getStatusBadge(infant.status)}`}
                  >
                    {infant.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-text-secondary">
                  {infant.age ?? 0} cycles
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(infant.id);
                    }}
                    className="px-2 py-1 text-sm text-danger hover:bg-danger/20 rounded transition-colors"
                  >
                    Delete
                  </button>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
        {infants.length === 0 && (
          <div className="p-8 text-center text-text-secondary">
            No infants found. Create one to get started.
          </div>
        )}
      </div>
    </div>
  );
}

export default InfantList;