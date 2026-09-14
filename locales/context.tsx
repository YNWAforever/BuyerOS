'use client';
import {createContext,useContext} from 'react';
export const LocaleContext=createContext<(x:string)=>string>(x=>x);
export const useT=()=>useContext(LocaleContext);
