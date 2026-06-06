import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import KycVio from './KycVio';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <KycVio />
  </StrictMode>
);
