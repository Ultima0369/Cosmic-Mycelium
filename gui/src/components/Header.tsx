import { motion } from 'framer-motion';
import { useLocation } from 'react-router-dom';

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/infants': 'Infant List',
  '/dialogue': 'Fractal Dialogue',
  '/physics': 'Physics Lab',
};

export function Header() {
  const location = useLocation();
  const title = pageTitles[location.pathname] || 'Cosmic Mycelium';

  return (
    <motion.header
      initial={{ y: -10, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="h-14 border-b border-[var(--border)] flex items-center justify-between px-6 bg-[var(--bg)]"
    >
      <h2 className="text-lg font-medium">{title}</h2>
      <div className="flex items-center gap-4">
        <span className="text-sm" style={{ color: 'var(--text)' }}>
          Status: Active
        </span>
      </div>
    </motion.header>
  );
}