import {expect,test} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
import {signInWorkbench,workspace,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
const labels:Record<string,string>={research:'研究',contact_enrichment:'聯絡資料增補',draft_generation:'草稿產生',mailbox:'郵箱',crm:'CRM',unconfigured:'未設定',disabled:'已停用',blocked:'已阻止',ready:'已備妥',degraded:'服務受影響'};
for(const locale of ['en','zh-HK'] as const)test(`C61-23 Settings ${locale} shows actual capability blockers and recovers a failed read`,async({page})=>{
 await resetWorkbenchFixtureRateWindows();if(locale==='zh-HK')await page.setViewportSize({width:390,height:844});
 await signInWorkbench(page,true,locale==='en'?'access':'viewer');await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption(locale);
 const response=page.waitForResponse(r=>r.request().method()==='GET'&&new URL(r.url()).pathname===`/v1/workspaces/${workspace}/capabilities`);
 await page.getByRole('button',{name:locale==='en'?'Settings':'設定',exact:true}).click();
 const panel=page.getByRole('region',{name:locale==='en'?'Provider capabilities':'供應商功能',exact:true});
 await expect(panel.getByRole('button',{name:locale==='en'?'Refresh capabilities':'重新整理功能狀態',exact:true})).toBeVisible();
 const actual=await response;expect(actual.status()).toBe(200);const data=(await actual.json()).data;expect(data.total).toBe(5);expect(data.items).toHaveLength(5);
 for(const item of data.items){const row=panel.locator(`[data-capability="${item.name}"]`);await expect(row.locator('output')).toHaveText(locale==='en'?item.status:labels[item.status]);await expect(row.locator('time')).toHaveAttribute('datetime',item.checked_at);await expect(row).toContainText(locale==='en'?item.name:labels[item.name]);}
 await expect(page.getByRole('region',{name:locale==='en'?'Role responsibilities':'角色責任',exact:true}).locator('output')).toContainText(locale==='en'?'operator':'檢視者');
 if(locale==='zh-HK')await expect(page.getByRole('region',{name:/^(Member management|成員管理)$/,exact:true})).toHaveCount(0);
 await expect(panel).toContainText(locale==='en'?'Confirm provider, price, approved budget and connection test with a workspace administrator.':'請與工作區管理員確認供應商、價格、已批准預算及連線測試。');
 const path=`**/v1/workspaces/${workspace}/capabilities`;await page.route(path,route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({code:'PROVIDER_UNAVAILABLE',message:'Isolated C61 capability read failure',request_id:'00000000-0000-4000-8000-000000000023',retryable:true})}));
 await panel.getByRole('button',{name:locale==='en'?'Refresh capabilities':'重新整理功能狀態',exact:true}).click();await expect(panel.getByRole('alert')).toBeVisible();for(const item of data.items){await expect(panel.locator(`[data-capability="${item.name}"] output`)).toHaveText('—');await expect(panel.locator(`[data-capability="${item.name}"] time`)).toHaveCount(0);}
 await page.unroute(path);await panel.getByRole('button',{name:locale==='en'?'Refresh capabilities':'重新整理功能狀態',exact:true}).click();for(const item of data.items)await expect(panel.locator(`[data-capability="${item.name}"] output`)).toHaveText(locale==='en'?item.status:labels[item.status]);
 await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:`test-results/c61-settings-${locale}.png`,fullPage:true});await writeFile(`test-results/c61-settings-${locale}.json`,JSON.stringify({fixture_only:true,locale,observed:data,synthetic_503_unavailable:true,actual_read_recovered:true},null,2));
});
