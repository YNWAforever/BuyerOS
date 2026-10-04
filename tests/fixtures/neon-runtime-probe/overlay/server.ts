import {fetchViteEnv} from 'nitro/vite/runtime';
// Isolated N00 dispatcher: use Vinext's request entry for API, Flight and HTML.
const dispatcher={fetch(request:Request){return fetchViteEnv('rsc',request);}};
export default dispatcher;
