'use client';

import { ArrowRight, Check, ChevronRight, Download, FileText, FolderOpen, Info, Mail, Search, ShieldCheck, SlidersHorizontal } from 'lucide-react';
import type { ReactNode } from 'react';
import { Button, Pick, Pill } from '../ui';
import { Checkbox } from '@/components/ui/checkbox';
import { Pagination, PaginationContent, PaginationItem, PaginationNext, PaginationPrevious } from '@/components/ui/pagination';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { Company } from '@/services/contracts';

type DemoBuyerTableProps = {
  t: (value: string) => string;
  isLists: boolean;
  currentListName?: string;
  rows: Company[];
  pageRows: Company[];
  selected: string[];
  q: string;
  filterFields: ReactNode;
  canApplyPreset: boolean;
  sort: string;
  optional: boolean;
  page: number;
  pageCount: number;
  size: string;
  onSavePreset: () => void;
  onExport: () => void;
  onQueryChange: (value: string) => void;
  onOpenFilters: () => void;
  onApplyPreset: () => void;
  onSortChange: (value: string) => void;
  onSelectionChange: (ids: string[]) => void;
  onAction: (name: string, ids: string[]) => void;
  onRemoveFromList: () => void;
  onOpenBuyer: (id: string) => void;
  onClearFilters: () => void;
  onPageSizeChange: (value: string) => void;
  onPageChange: (page: number) => void;
};

export function DemoBuyerTable({
  t, isLists, currentListName, rows, pageRows, selected, q, filterFields,
  canApplyPreset, sort, optional, page, pageCount, size,
  onSavePreset, onExport, onQueryChange: Q, onOpenFilters, onApplyPreset,
  onSortChange: Sort, onSelectionChange: Sel, onAction: action,
  onRemoveFromList, onOpenBuyer: openBuyer, onClearFilters: clear,
  onPageSizeChange: Size, onPageChange: P,
}: DemoBuyerTableProps) {
  return <><div className="panel results-panel"><div className="table-toolbar"><div className="inline"><h3>{isLists?t(currentListName||'Buyer Lists'):t('Buyer results')}</h3><Pill>{rows.length}</Pill></div><div className="inline"><Button variant="ghost" onClick={onSavePreset}><FolderOpen size={15}/>{t('Save filter preset')}</Button><Button variant="outline" onClick={onExport}><Download size={15}/>{t('Export sample CSV')}</Button></div></div><div className="filterbar"><div className="searchbox"><Search size={17}/><input aria-label={t('Search companies…')} placeholder={t('Search companies…')} value={q} onChange={e=>Q(e.target.value)}/></div><div className="desktop-filters">{filterFields}</div><Button variant="outline" onClick={onOpenFilters}><SlidersHorizontal size={16}/>{t('Filters')}</Button></div><div className="table-sub"><span>{rows.length} {t('companies')} · {selected.length} {t('selected')}</span><div className="inline">{canApplyPreset&&<Button variant="ghost" onClick={onApplyPreset}>{t('Apply saved preset')}</Button>}<Pick value={sort} onChange={Sort} items={['Best fit first','Name A–Z']}/></div></div>{selected.length>0&&<div className="bulkbar"><b>{selected.length} {t("selected")}</b><button onClick={()=>Sel(rows.map(c=>c.id))}>{t("Select all")}{rows.length} {t("filtered companies")}</button>{['accept','reject','save','lookup'].map(a=><Button size="sm" variant="outline" key={a} onClick={()=>action(a,selected)}>{t({accept:'Accept buyer',reject:'Reject buyer',save:'Save to list',lookup:'Find business contacts'}[a]!)}</Button>)}{isLists&&<Button size="sm" variant="outline" onClick={onRemoveFromList}>{t('Remove from list')}</Button>}<button onClick={()=>Sel([])}>{t("Clear")}</button></div>}<div className="desktop-table"><Table><TableHeader><TableRow><TableHead><Checkbox aria-label="Select current page" checked={pageRows.length>0&&pageRows.every(c=>selected.includes(c.id))} onCheckedChange={v=>Sel(v?Array.from(new Set([...selected,...pageRows.map(c=>c.id)])):selected.filter(id=>!pageRows.some(c=>c.id===id)))}/></TableHead><TableHead>{t('Company')}</TableHead><TableHead>{t('Buyer type')}</TableHead><TableHead className="fit-column">{t('Why it fits')}</TableHead><TableHead>{t('Contact status')}</TableHead><TableHead>{t('Review status')}</TableHead>{optional&&<TableHead>{t("Owner")}</TableHead>}<TableHead><span className="sr-only">{t("Open buyer")}</span></TableHead></TableRow></TableHeader><TableBody>{pageRows.map(c=><TableRow key={c.id} data-state={selected.includes(c.id)?'selected':undefined}><TableCell><Checkbox aria-label={'Select '+c.name} checked={selected.includes(c.id)} onCheckedChange={v=>Sel(v?[...selected,c.id]:selected.filter(id=>id!==c.id))}/></TableCell><TableCell><button className="company-cell" onClick={()=>openBuyer(c.id)}><span className={'avatar a'+Number(c.id.split('-')[1])%4}>{c.name.slice(0,2).toUpperCase()}</span><span><b>{c.name}</b><small>{t(c.market)} <span className="dot">·</span> {c.name.split(' ')[0].toLowerCase()}.example</small></span></button></TableCell><TableCell><span className="type-text">{t(c.type)}</span></TableCell><TableCell><button className="why-cell" onClick={()=>openBuyer(c.id)}><div className="inline"><Pill kind={c.fit==='Match'?'green':c.fit==='Needs review'?'amber':'gray'}>{c.fit==='Match'&&<Check size={12}/>} {t(c.fit)}</Pill><span className="evidence-count"><FileText size={12}/>{c.evidence.length} {t("sources")}</span></div><p>{t(c.why)}</p></button></TableCell><TableCell><span className={'contact-label '+(c.contact==='Provider-marked valid'?'valid':'')}>{c.contact==='Provider-marked valid'?<ShieldCheck size={14}/>:<Mail size={14}/>} {t(c.contact)}</span></TableCell><TableCell><Pill kind={c.review==='Accepted'?'blue':'plain'}>{c.review==='Accepted'&&<Check size={12}/>} {t(c.review)}</Pill></TableCell>{optional&&<TableCell>{c.owner}</TableCell>}<TableCell><Button variant="ghost" size="icon" aria-label={'Open '+c.name} onClick={()=>openBuyer(c.id)}><ChevronRight size={18}/></Button></TableCell></TableRow>)}</TableBody></Table></div><div className="mobile-cards">{pageRows.map(c=><div className="buyer-card" key={c.id}><div className="inline"><Checkbox aria-label={'Select '+c.name} checked={selected.includes(c.id)} onCheckedChange={v=>Sel(v?[...selected,c.id]:selected.filter(id=>id!==c.id))}/><button onClick={()=>openBuyer(c.id)}><b>{c.name}</b></button></div><p>{t(c.market)} · {t(c.type)}</p><div className="inline"><Pill kind={c.fit==='Match'?'green':'amber'}>{t(c.fit)}</Pill><Pill>{t(c.review)}</Pill></div><p>{t(c.why)}</p><Button variant="outline" onClick={()=>openBuyer(c.id)}>{t('Review evidence')}<ArrowRight size={16}/></Button></div>)}</div>{rows.length===0&&<div className="empty"><Search size={30}/><h3>{t('No buyers found')}</h3><p>{t('Adjust your filters or start a new demo search.')}</p><Button variant="outline" onClick={clear}>{t('Clear filters')}</Button></div>}<div className="table-footer"><span>{rows.length?((Math.min(page,pageCount)-1)*+size+1):0}–{Math.min(Math.min(page,pageCount)*+size,rows.length)} {t("of")}{rows.length} {t("companies")}</span><div className="inline"><span>{t("Rows")}</span><Pick value={size} onChange={Size} items={['8','12','24']}/><Pagination><PaginationContent><PaginationItem><PaginationPrevious href="#previous" aria-label="Previous page" onClick={e=>{e.preventDefault();P(Math.max(1,page-1))}}/></PaginationItem><PaginationItem><span className="page-number">{Math.min(page,pageCount)}</span></PaginationItem><PaginationItem><PaginationNext href="#next" aria-label="Next page" onClick={e=>{e.preventDefault();P(Math.min(pageCount,page+1))}}/></PaginationItem></PaginationContent></Pagination></div></div></div><p className="footnote"><Info size={14}/>{t("All companies, sources and contact results are fictional. A fit match does not indicate purchase intent.")}</p></>;
}
