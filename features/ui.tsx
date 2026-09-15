'use client';
import {Select,SelectTrigger,SelectContent,SelectItem,SelectValue} from '@/components/ui/select';
import {Button} from '@/components/ui/button';
import {useT} from '@/locales/context';
import type {ReactNode} from 'react';
export {Button};
export function Pick({value,onChange,items,label}:{value:string;onChange:(v:string)=>void;items:string[];label?:string}){const t=useT();return <Select value={value} onValueChange={onChange}><SelectTrigger aria-label={t(label||items[0])} className="pick"><SelectValue>{t(value)}</SelectValue></SelectTrigger><SelectContent>{items.map(x=><SelectItem key={x} value={x}>{t(x)}</SelectItem>)}</SelectContent></Select>}
export function Pill({children,kind}:{children:ReactNode;kind?:string}){return <span className={'pill '+(kind||'')}>{children}</span>}
export function Field({label,children}:{label:string;children:ReactNode}){const t=useT();return <label className="field"><span>{t(label)}</span>{children}</label>}
