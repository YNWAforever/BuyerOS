type Props = {
  t: (value:string)=>string;
  navigate: (path:string)=>void;
  authorized: boolean;
  projectKnown: boolean;
  canEdit: boolean;
  projectActive: boolean;
  canCreate: boolean;
};

/** Route navigation keeps the parent workspace session and scope checks authoritative. */
export function LiveNavigation({t,navigate,authorized,projectKnown,canEdit,projectActive,canCreate}:Props){
  return <nav aria-label="BuyerOS sections" style={{display:'flex',gap:'1rem',flexWrap:'wrap',padding:'0.75rem 0'}}>
    <button onClick={()=>navigate('/app')}>{t('Overview')}</button>
    <button onClick={()=>navigate(projectKnown?'/app/discover/edit':'/app/discover/new')} disabled={!authorized || !(projectKnown?canEdit&&projectActive:canCreate)}>{t('Offer')}</button>
    <button onClick={()=>navigate('/app/discover')} disabled={!projectKnown}>{t('Buyers')}</button>
    <button onClick={()=>navigate('/app/results')} disabled={!projectKnown}>{t('Results')}</button>
    <button onClick={()=>navigate('/app/runs')} disabled={!projectKnown}>{t('Research runs')}</button>
    <button onClick={()=>navigate('/app/outreach')} disabled={!projectKnown}>{t('Drafts')}</button>
    <button onClick={()=>navigate('/app/settings')} disabled={!authorized}>{t('Settings')}</button>
    <button onClick={()=>navigate('/app/operations')} disabled={!authorized}>{t('Operations')}</button>
  </nav>;
}
