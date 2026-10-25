import type {ReactNode} from 'react';
import {AppWorkspace} from '@/features/app-workspace';
/** One persistent workspace shell for the /app subtree; auth has no workspace gate. */
export default function AppLayout({children}:{children:ReactNode}){
 return <><AppWorkspace/>{children}</>;
}
