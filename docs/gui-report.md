# Cosmic Mycelium GUI Project Report

## Project Overview

This document describes the GUI implementation for the Cosmic Mycelium project - a silicon-based lifeform simulation platform.

## Architecture

### Tech Stack
- **Frontend**: React 18 + TypeScript + Vite
- **State Management**: Zustand
- **3D Graphics**: Three.js + @react-three/fiber + @react-three/drei
- **Charts**: D3.js
- **Animation**: Framer Motion
- **Styling**: Tailwind CSS + Radix UI
- **Backend**: FastAPI + WebSocket

### Project Structure
```
gui/
├── src/
│   ├── components/      # Reusable UI components
│   ├── views/          # Page-level components
│   ├── stores/         # Zustand state stores
│   ├── hooks/          # Custom React hooks
│   └── api/            # API clients
├── public/             # Static assets
└── package.json
```

## Views

### 1. Dashboard (`/`)
- 3D Mycelium Network visualization
- Real-time energy flow chart
- Scale cards (NANO/INFANT/MESH/SWARM counts)
- WebSocket live connection status

### 2. Infant List (`/infants`)
- Table of all MiniInfant instances
- Create/delete infants
- Quick status overview

### 3. Infant Detail (`/infants/:id`)
- Physical state panel (position q, momentum p)
- Energy curve chart
- Confidence + Surprise real-time charts
- Memory path visualization (myelination strength)
- Trauma event timeline
- Breath state indicator (CONTRACT/DIFFUSE/SUSPEND)

### 4. Fractal Dialogue (`/fractal`)
- Message envelope list
- Translation flow animation (D3 particles)
- Echo detector heatmap
- Cross-scale echo visualization

### 5. Physics Lab (`/physics`)
- Spring-Mass 3D simulation
- Energy conservation chart (T, V, E curves)
- Drift rate gauge (< 0.1% target)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | System status |
| `/api/infants` | GET | List all infants |
| `/api/infants/{id}` | GET | Infant details |
| `/api/infants` | POST | Create infant |
| `/api/infants/{id}` | DELETE | Delete infant |
| `/api/fractal/messages` | GET | Message history |
| `/api/fractal/echoes` | GET | Echo detector status |
| `/api/physics/fingerprint` | GET | Physics fingerprint |
| `/ws/live` | WebSocket | Real-time updates |
| `/api/simulation/start` | POST | Start simulation |
| `/api/simulation/stop` | POST | Stop simulation |

## Running the Project

```bash
# Terminal 1: Backend
uvicorn gui_server:app --reload --port 8000

# Terminal 2: Frontend
cd gui && npm run dev
```

## Design Philosophy

The GUI follows the same principles as the backend:
1. **Physics as Anchor**: Real-time energy drift visualization
2. **Suspension as Eye**: Breath state indicators (CONTRACT/DIFFUSE/SUSPEND)
3. **1+1>2**: Resonance visualization in fractal dialogue
4. **Wobbly as Alive**: Allow exploration and self-correction

## Version
- GUI: 0.1.0
- Backend API: 0.1.0