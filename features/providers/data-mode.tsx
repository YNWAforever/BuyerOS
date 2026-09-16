'use client';
import {createContext, useContext, type ReactNode} from 'react';
import type {DataMode} from '@/services/live/mode';

interface DataModeValue { mode: DataMode; apiBaseUrl: string; }
const DataModeContext = createContext<DataModeValue>({mode: 'demo', apiBaseUrl: ''});

export function DataModeProvider({mode, apiBaseUrl, children}: DataModeValue & {children: ReactNode}) {
  return <DataModeContext.Provider value={{mode, apiBaseUrl}}>{children}</DataModeContext.Provider>;
}

export function useDataMode(): DataModeValue {
  return useContext(DataModeContext);
}
