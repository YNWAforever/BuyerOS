import type {Response} from '@playwright/test';
export function responseReceipt(response:Response):Promise<{path:string;method:string;status:number;request_id:string|null}>;
