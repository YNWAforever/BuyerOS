import {fetchViteEnv} from 'nitro/vite/runtime';
const dispatcher={fetch(request:Request){return fetchViteEnv('rsc',request);}};
export default dispatcher;
