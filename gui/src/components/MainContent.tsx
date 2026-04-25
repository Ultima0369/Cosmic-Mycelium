import { type ReactNode } from 'react';
import { motion } from 'framer-motion';

interface MainContentProps {
  children: ReactNode;
}

export function MainContent({ children }: MainContentProps) {
  return (
    <motion.main
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="flex-1 overflow-auto"
    >
      {children}
    </motion.main>
  );
}