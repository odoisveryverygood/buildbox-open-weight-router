import { createRoot } from 'react-dom/client';
import PlanningApp from './PlanningApp';
import DemoStudio from './DemoStudio';
import IntelligenceStudio from './IntelligenceStudio';
import './style.css';
const query=new URLSearchParams(location.search);
createRoot(document.getElementById('root')!).render(query.get('demo')==='1'?<DemoStudio/>:query.get('intelligence')==='1'?<IntelligenceStudio/>:<PlanningApp />);
