import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { useFractalStore, fetchFractalMessages, fetchEchoPatterns } from '../stores/useFractalStore';
import { TranslationFlow } from '../components/TranslationFlow';
import { EchoHeatmap } from '../components/EchoHeatmap';

function formatTimeAgo(ts: number): string {
  const diff = Date.now() - ts;
  if (diff < 60000) return `${Math.floor(diff / 1000)}s`;
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m`;
  return `${Math.floor(diff / 3600000)}h`;
}

const SCALE_LABELS: Record<string, string> = {
  NANO: 'Nano',
  INFANT: 'Infant',
  MESH: 'Mesh',
  SWARM: 'Swarm',
};

function getFidelityColor(fidelity: number): string {
  if (fidelity > 0.7) return 'text-success';
  if (fidelity > 0.4) return 'text-warning';
  return 'text-danger';
}

function getFidelityLabel(fidelity: number): string {
  if (fidelity > 0.7) return '高';
  if (fidelity > 0.4) return '中';
  return '低';
}

export function FractalDialogue() {
  const { messages, echoPatterns, heatmapData, isLoading, selectedMessage, setSelectedMessage } = useFractalStore();

  useEffect(() => {
    fetchFractalMessages();
    fetchEchoPatterns();
    
    const interval = setInterval(() => {
      fetchFractalMessages();
      fetchEchoPatterns();
    }, 3000);
    
    return () => clearInterval(interval);
  }, []);

  const sortedMessages = [...messages].sort((a, b) => b.timestamp - a.timestamp);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-[var(--text-primary)]">分形对话</h2>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-[var(--text-secondary)]">
            消息: {messages.length}
          </span>
          <span className="text-[var(--text-secondary)]">
            模式: {echoPatterns.length}
          </span>
        </div>
      </div>

      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="h-[600px] flex gap-4"
      >
        <div className="w-64 rounded-xl bg-[var(--code-bg)] border border-[var(--border)] p-4 flex flex-col">
          <h3 className="font-medium mb-3 text-[var(--text-primary)]">消息信封</h3>
          
          {isLoading && messages.length === 0 ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="w-6 h-6 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <div className="flex-1 space-y-2 overflow-auto">
              {sortedMessages.map((msg) => (
                <motion.button
                  key={msg.id}
                  onClick={() => setSelectedMessage(msg.id)}
                  className={`w-full p-3 rounded text-left transition-colors ${
                    selectedMessage === msg.id
                      ? 'bg-[var(--accent-bg)] border border-[var(--accent)]'
                      : 'bg-[var(--bg)] hover:bg-[var(--bg-tertiary)] border border-transparent'
                  }`}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[var(--text-secondary)]">
                      {formatTimeAgo(msg.timestamp)}
                    </span>
                    <span className={getFidelityColor(msg.fidelity)}>
                      {getFidelityLabel(msg.fidelity)}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-[var(--text-secondary)]">
                    {SCALE_LABELS[msg.from_scale] || msg.from_scale} → {SCALE_LABELS[msg.to_scale] || msg.to_scale}
                  </div>
                  <div className="mt-1 text-sm truncate text-[var(--text-primary)]">
                    {msg.content}
                  </div>
                </motion.button>
              ))}
              
              {messages.length === 0 && (
                <div className="flex-1 flex items-center justify-center text-[var(--text-secondary)] text-sm">
                  暂无消息
                </div>
              )}
            </div>
          )}
        </div>

        <TranslationFlow 
          messages={messages} 
          activeMessageId={selectedMessage}
        />

        <EchoHeatmap 
          heatmapData={heatmapData}
          patterns={echoPatterns}
        />
      </motion.div>
    </div>
  );
}

export default FractalDialogue;