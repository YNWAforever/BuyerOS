import {fetchViteEnv} from 'nitro/vite/runtime';
// N00 overlay only. Vinext's fetch entry dispatches API, Flight and HTML together.
const dispatcher={fetch(request:Request){return fetchViteEnv('rsc',request);}};
export default dispatcher;
