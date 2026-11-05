import React from 'react';
import {createRoot} from 'react-dom/client';
import {AppRouterContext} from '../node_modules/vinext/dist/shims/internal/app-router-context.js';
import {appRouterInstance} from 'vinext/shims/navigation';
import {AppWorkspace} from '../features/app-workspace';
if(!AppRouterContext)throw new Error('Router context unavailable');
createRoot(document.getElementById('root')!).render(<AppRouterContext.Provider value={appRouterInstance}><AppWorkspace/></AppRouterContext.Provider>);
