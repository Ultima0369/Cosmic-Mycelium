import { useEffect } from 'react';
import { useSystemStore, fetchSystemStatus, connectWebSocket, disconnectWebSocket } from '../stores/useSystemStore';
import { ScaleCard } from '../components/ScaleCard';
import { EnergyChart } from '../components/EnergyChart';
import { Mycelium3D } from '../components/Mycelium3D';

export function Dashboard() {
  const { scaleCounts, energyHistory, myceliumNodes, isConnected, lastUpdate } = useSystemStore();

  useEffect(() => {
    fetchSystemStatus();
    connectWebSocket();

    const pollInterval = setInterval(fetchSystemStatus, 5000);

    return () => {
      clearInterval(pollInterval);
      disconnectWebSocket();
    };
  }, []);

  const formatLastUpdate = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  return (
    <div className="min-h-screen bg-bg-primary p-6">
      <header className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-text-primary">Cosmic Mycelium</h1>
            <p className="text-text-secondary mt-1">Silicon-based Life Form Dashboard</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  isConnected ? 'bg-success animate-pulse' : 'bg-danger'
                }`}
              />
              <span className="text-sm text-text-secondary">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
            <div className="text-xs text-text-secondary">
              Last update: {formatLastUpdate(lastUpdate)}
            </div>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-4 gap-4 mb-6">
        {scaleCounts.map((item) => (
          <ScaleCard key={item.scale} data={item} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div>
          <h2 className="text-lg font-semibold text-text-primary mb-4">Energy Flow</h2>
          <EnergyChart data={energyHistory} />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-text-primary mb-4">Network Status</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-xl bg-bg-secondary border border-border p-4">
              <div className="text-text-secondary text-sm">Total Nodes</div>
              <div className="text-2xl font-bold text-text-primary">
                {myceliumNodes.length || 30}
              </div>
            </div>
            <div className="rounded-xl bg-bg-secondary border border-border p-4">
              <div className="text-text-secondary text-sm">Active Scales</div>
              <div className="text-2xl font-bold text-text-primary">
                {new Set(myceliumNodes.map((n) => n.scale)).size || 3}
              </div>
            </div>
            <div className="rounded-xl bg-bg-secondary border border-border p-4">
              <div className="text-text-secondary text-sm">Total Energy</div>
              <div className="text-2xl font-bold text-accent">
                {(scaleCounts.reduce((sum, s) => sum + s.energy, 0) || 0).toFixed(1)}
              </div>
            </div>
            <div className="rounded-xl bg-bg-secondary border border-border p-4">
              <div className="text-text-secondary text-sm">Connections</div>
              <div className="text-2xl font-bold text-text-primary">
                {myceliumNodes.reduce((sum, n) => sum + n.connections.length, 0) / 2 || 45}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-text-primary mb-4">3D Mycelium Network</h2>
        <Mycelium3D nodes={myceliumNodes} />
      </div>
    </div>
  );
}

export default Dashboard;