import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { MainContent } from './components/MainContent';
import { Dashboard } from './views/Dashboard';
import { InfantList } from './views/InfantList';
import { InfantDetail } from './views/InfantDetail';
import { FractalDialogue } from './views/FractalDialogue';
import { PhysicsLab } from './views/PhysicsLab';

function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <Header />
          <MainContent>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/infants" element={<InfantList />} />
              <Route path="/infants/:id" element={<InfantDetail />} />
              <Route path="/dialogue" element={<FractalDialogue />} />
              <Route path="/physics" element={<PhysicsLab />} />
            </Routes>
          </MainContent>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;