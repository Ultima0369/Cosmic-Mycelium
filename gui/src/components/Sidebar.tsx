import { NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';

const navItems = [
  { path: '/', label: 'Dashboard' },
  { path: '/infants', label: 'Infants' },
  { path: '/dialogue', label: 'Fractal Dialogue' },
  { path: '/physics', label: 'Physics Lab' },
];

export function Sidebar() {
  return (
    <motion.aside
      initial={{ x: -20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      className="w-56 h-screen bg-[var(--social-bg)] border-r border-[var(--border)] flex flex-col"
    >
      <div className="p-4 border-b border-[var(--border)]">
        <h1 className="text-xl font-semibold" style={{ color: 'var(--accent)' }}>
          Cosmic Mycelium
        </h1>
      </div>
      <nav className="flex-1 p-2">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `block px-3 py-2 rounded-lg mb-1 transition-colors ${
                isActive
                  ? 'bg-[var(--accent-bg)] text-[var(--accent)]'
                  : 'hover:bg-[var(--code-bg)]'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </motion.aside>
  );
}