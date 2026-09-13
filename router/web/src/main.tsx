import { createRoot } from 'react-dom/client';
import PlanningApp from './PlanningApp';
import DemoStudio from './DemoStudio';
import './style.css';
createRoot(document.getElementById('root')!).render(new URLSearchParams(location.search).get('demo')==='1'?<DemoStudio/>:<PlanningApp />);
