# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-bulk-manifest.spec.ts >> B16 late preview cannot cross A-B-A; viewer has no maintenance; zh-HK mobile exact confirmation
- Location: tests\e2e\audit-bulk-manifest.spec.ts:62:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: true
Received: false
```

# Page snapshot

```yaml
- main [ref=f1e2]:
  - generic [ref=f1e3]:
    - generic [ref=f1e4]:
      - generic [ref=f1e5]: FIMMICK BuyerOS
      - generic [ref=f1e6]: 正式工作區
      - generic [ref=f1e7]:
        - text: 語言
        - combobox "語言" [ref=f1e8]:
          - option "English"
          - option "繁體中文" [selected]
      - button "登出" [ref=f1e9] [cursor=pointer]
    - navigation "BuyerOS sections" [ref=f1e10]:
      - button "總覽" [ref=f1e11] [cursor=pointer]
      - button "產品資料" [ref=f1e12] [cursor=pointer]
      - button "買家" [ref=f1e13] [cursor=pointer]
      - button "結果" [ref=f1e14] [cursor=pointer]
      - button "研究進度" [ref=f1e15] [cursor=pointer]
      - button "草稿" [ref=f1e16] [cursor=pointer]
      - button "設定" [ref=f1e17] [cursor=pointer]
      - button "營運工作台" [ref=f1e18] [cursor=pointer]
    - region "工作區選擇" [ref=f1e19]:
      - heading "工作區" [level=2] [ref=f1e20]
      - generic [ref=f1e21]:
        - text: 工作區
        - combobox "工作區" [ref=f1e22]:
          - option "選擇工作區"
          - option "E2E fixture workspace" [selected]
          - option "Other audit fixture"
      - paragraph [ref=f1e23]: "角色: 操作員"
    - region "專案選擇" [ref=f1e24]:
      - heading "專案" [level=2] [ref=f1e25]
      - generic [ref=f1e26]:
        - text: 專案
        - combobox "專案" [ref=f1e27]:
          - option "選擇專案"
          - option "Buyer Fixture Project" [selected]
          - option "Run Fixture Project"
      - generic [ref=f1e28]:
        - button "新增專案" [ref=f1e29] [cursor=pointer]
        - button "編輯產品資料" [ref=f1e30] [cursor=pointer]
    - region "買家結果" [ref=f1e31]:
      - generic [ref=f1e32]:
        - heading "買家" [level=2] [ref=f1e33]
        - generic [ref=f1e34]: 101 項快照
      - group "買家篩選" [ref=f1e35]:
        - generic [ref=f1e36]:
          - text: 搜尋買家
          - textbox "搜尋買家" [ref=f1e37]: Q08 Manifest Fixture
        - button "套用篩選" [ref=f1e38] [cursor=pointer]
        - generic [ref=f1e39]:
          - text: 配對
          - combobox "配對篩選" [ref=f1e40]:
            - option "不限" [selected]
            - option "符合"
            - option "須檢查"
            - option "不符合"
        - generic [ref=f1e41]:
          - text: 審閱
          - combobox "審閱篩選" [ref=f1e42]:
            - option "不限" [selected]
            - option "待審買家"
            - option "已接納"
            - option "已拒絕"
            - option "需更多資料"
        - generic [ref=f1e43]:
          - text: 佇列
          - combobox "工作佇列篩選" [ref=f1e44]:
            - option "全部" [selected]
            - option "未分派"
            - option "適合度未明"
        - generic [ref=f1e45]:
          - text: 排序
          - combobox "買家排序" [ref=f1e46]:
            - option "名稱" [selected]
            - option "最佳配對"
        - button "更新結果" [ref=f1e47] [cursor=pointer]
      - generic [ref=f1e48]:
        - button "選取本頁" [ref=f1e49] [cursor=pointer]
        - button "選取所有篩選結果" [ref=f1e50] [cursor=pointer]
        - button "清除選取" [ref=f1e51] [cursor=pointer]
        - generic [ref=f1e52]: 已明確選取 0 項
      - generic [ref=f1e53]:
        - checkbox "選取 Q08 Manifest Fixture 00000" [ref=f1e54]
        - generic [ref=f1e55]:
          - text: Q08 Manifest Fixture 00000
          - paragraph [ref=f1e56]: 尚未評估配對 · 尚未審閱 · 沒有備註
        - button "詳情" [ref=f1e57] [cursor=pointer]
      - generic [ref=f1e58]:
        - checkbox "選取 Q08 Manifest Fixture 00001" [ref=f1e59]
        - generic [ref=f1e60]:
          - text: Q08 Manifest Fixture 00001
          - paragraph [ref=f1e61]: 尚未評估配對 · 尚未審閱 · 沒有備註
        - button "詳情" [ref=f1e62] [cursor=pointer]
      - generic [ref=f1e63]:
        - checkbox "選取 Q08 Manifest Fixture 00002" [ref=f1e64]
        - generic [ref=f1e65]:
          - text: Q08 Manifest Fixture 00002
          - paragraph [ref=f1e66]: 尚未評估配對 · 尚未審閱 · 沒有備註
        - button "詳情" [ref=f1e67] [cursor=pointer]
      - generic [ref=f1e68]:
        - checkbox "選取 Q08 Manifest Fixture 00003" [ref=f1e69]
        - generic [ref=f1e70]:
          - text: Q08 Manifest Fixture 00003
          - paragraph [ref=f1e71]: 尚未評估配對 · 尚未審閱 · 沒有備註
        - button "詳情" [ref=f1e72] [cursor=pointer]
      - generic [ref=f1e73]:
        - checkbox "選取 Q08 Manifest Fixture 00004" [ref=f1e74]
        - generic [ref=f1e75]:
          - text: Q08 Manifest Fixture 00004
          - paragraph [ref=f1e76]: 尚未評估配對 · 尚未審閱 · 沒有備註
        - button "詳情" [ref=f1e77] [cursor=pointer]
      - generic [ref=f1e78]:
        - checkbox "選取 Q08 Manifest Fixture 00005" [ref=f1e79]
        - generic [ref=f1e80]:
          - text: Q08 Manifest Fixture 00005
          - paragraph [ref=f1e81]: 尚未評估配對 · 尚未審閱 · 沒有備註
        - button "詳情" [ref=f1e82] [cursor=pointer]
      - generic [ref=f1e83]:
        - checkbox "選取 Q08 Manifest Fixture 00006" [ref=f1e84]
        - generic [ref=f1e85]:
          - text: Q08 Manifest Fixture 00006
          - paragraph [ref=f1e86]: 尚未評估配對 · 尚未審閱 · 沒有備註
        - button "詳情" [ref=f1e87] [cursor=pointer]
      - generic [ref=f1e88]:
        - checkbox "選取 Q08 Manifest Fixture 00007" [ref=f1e89]
        - generic [ref=f1e90]:
          - text: Q08 Manifest Fixture 00007
          - paragraph [ref=f1e91]: 尚未評估配對 · 尚未審閱 · 沒有備註
        - button "詳情" [ref=f1e92] [cursor=pointer]
      - generic [ref=f1e93]:
        - checkbox "選取 Q08 Manifest Fixture 00008" [ref=f1e94]
        - generic [ref=f1e95]:
          - text: Q08 Manifest Fixture 00008
          - paragraph [ref=f1e96]: 尚未評估配對 · 尚未審閱 · 沒有備註
        - button "詳情" [ref=f1e97] [cursor=pointer]
      - generic [ref=f1e98]:
        - checkbox "選取 Q08 Manifest Fixture 00009" [ref=f1e99]
        - generic [ref=f1e100]:
          - text: Q08 Manifest Fixture 00009
          - paragraph [ref=f1e101]: 尚未評估配對 · 尚未審閱 · 沒有備註
        - button "詳情" [ref=f1e102] [cursor=pointer]
      - generic [ref=f1e103]:
        - checkbox "選取 Q08 Manifest Fixture 00010" [ref=f1e104]
        - generic [ref=f1e105]:
          - text: Q08 Manifest Fixture 00010
          - paragraph [ref=f1e106]: 尚未評估配對 · 尚未審閱 · 沒有備註
        - button "詳情" [ref=f1e107] [cursor=pointer]
      - generic [ref=f1e108]:
        - checkbox "選取 Q08 Manifest Fixture 00011" [ref=f1e109]
        - generic [ref=f1e110]:
          - text: Q08 Manifest Fixture 00011
          - paragraph [ref=f1e111]: 尚未評估配對 · 尚未審閱 · 沒有備註
        - button "詳情" [ref=f1e112] [cursor=pointer]
      - generic [ref=f1e113]:
        - generic [ref=f1e114]:
          - button "上一頁" [disabled] [ref=f1e115]
          - generic [ref=f1e116]: 第 1–12 項，共 101 項
          - button "下一頁" [ref=f1e117] [cursor=pointer]
        - generic [ref=f1e118]:
          - text: 每頁項數
          - combobox "每頁項數" [ref=f1e119]:
            - option "8"
            - option "12" [selected]
            - option "24"
      - region "授權匯出" [ref=f1e120]:
        - heading "授權匯出" [level=3] [ref=f1e121]
        - paragraph [ref=f1e122]: 只有現行政策及已指定收件人草稿的有效精確審批，才可取得內容。
        - paragraph [ref=f1e123]: 複製及下載均不會寄送訊息。
        - paragraph [ref=f1e124]: "所選範圍: 尚未選擇"
        - generic [ref=f1e125]:
          - checkbox "包括合資格聯絡資料" [ref=f1e126]
          - text: 包括合資格聯絡資料
        - paragraph [ref=f1e127]: 只含公司資料 CSV
        - button "準備匯出" [disabled] [ref=f1e129]
      - region "批量分派買家負責人" [ref=f1e130]:
        - heading "批量分派買家負責人" [level=3] [ref=f1e131]
        - paragraph [ref=f1e132]: 預覽：已選 0 位買家；提交前會重新檢查每列的版本和負責人資格。
        - paragraph [ref=f1e133]: "工作區／專案: e0000000-0000-4000-8000-000000000001 / e1000000-0000-4000-8000-000000000001"
        - paragraph [ref=f1e134]: "負責人: 我"
        - generic [ref=f1e135]:
          - text: 負責人
          - combobox "負責人" [ref=f1e136]:
            - option "沒有負責人"
            - option "我" [selected]
            - option "e0000000-0000-4000-8000-000000000004 · e0000000-0000-4000-8000-000000000004"
            - option "e0000000-0000-4000-8000-000000000006 · e0000000-0000-4000-8000-000000000006"
            - option "e0000000-0000-4000-8000-000000000008 · e0000000-0000-4000-8000-000000000008"
        - generic [ref=f1e137]:
          - generic [ref=f1e138]:
            - text: 搜尋同事
            - textbox "搜尋同事" [ref=f1e139]
          - button "搜尋" [ref=f1e140] [cursor=pointer]
        - generic [ref=f1e141]:
          - generic [ref=f1e142]: 1–4 / 4
          - button "上一頁同事" [disabled] [ref=f1e143]
          - button "下一頁同事" [disabled] [ref=f1e144]
        - generic [ref=f1e145]:
          - text: 分派原因
          - textbox "分派原因" [ref=f1e146]
        - paragraph [ref=f1e147]: "原因:"
        - generic [ref=f1e148]:
          - generic [ref=f1e149]:
            - checkbox "確認負責人分派" [disabled] [ref=f1e150]
            - text: 確認這份預覽
          - button "分派已選買家" [disabled] [ref=f1e151]
      - region "分段批量維護" [ref=f1e152]:
        - heading "分段批量維護" [level=3] [ref=f1e153]
        - paragraph [ref=f1e154]: 此預覽會凍結所有符合條件的 ID 及版本，上限 10000 筆。確認精確摘要前不會更改買家。
        - group "操作" [ref=f1e155]:
          - combobox "操作" [disabled] [ref=f1e157]:
            - option "指派負責人" [disabled] [selected]
            - option "更改清單成員" [disabled]
          - generic [ref=f1e158]:
            - text: 搜尋同事
            - textbox "搜尋同事" [disabled] [ref=f1e159]
          - button "搜尋" [disabled] [ref=f1e160]
          - generic [ref=f1e161]:
            - text: 負責人
            - combobox "負責人" [disabled] [ref=f1e162]:
              - option "清除負責人" [disabled]
              - option "e0000000-0000-4000-8000-000000000002 · e0000000-0000-4000-8000-000000000003" [disabled] [selected]
              - option "e0000000-0000-4000-8000-000000000004 · e0000000-0000-4000-8000-000000000005" [disabled]
              - option "e0000000-0000-4000-8000-000000000006 · e0000000-0000-4000-8000-000000000007" [disabled]
              - option "e0000000-0000-4000-8000-000000000008 · e0000000-0000-4000-8000-000000000009" [disabled]
          - generic [ref=f1e163]:
            - text: 1–4 / 4
            - button "上一頁同事" [disabled] [ref=f1e164]
            - button "下一頁同事" [disabled] [ref=f1e165]
        - generic [ref=f1e166]:
          - text: 維護理由
          - textbox "維護理由" [disabled] [ref=f1e167]
        - generic [ref=f1e168]:
          - text: 排除買家 ID（每行一個）
          - textbox "排除買家 ID（每行一個）" [disabled] [ref=f1e169]
        - region "已凍結維護清單" [ref=f1e170]:
          - heading "已凍結維護清單" [level=4] [ref=f1e171]
          - paragraph [ref=f1e172]: "5ad1c280-4bf9-479b-a644-56bf22776493 · 就緒 · 筆數: 101"
          - paragraph [ref=f1e173]: "摘要: ca4a7713eb3e65d4bd2b5fdc09a162a89826df88cb81ea5f5592ced9aa93575f"
          - paragraph [ref=f1e174]: "到期時間: 2026-10-03T14:25:42.969469+00:00"
          - paragraph [ref=f1e175]: 指派負責人
          - generic [ref=f1e176]: "{ \"target\": { \"owner_membership_id\": \"e0000000-0000-4000-8000-000000000003\" }, \"filters\": { \"q\": \"Q08 Manifest Fixture\" }, \"reason\": \"Q08 old scope request\", \"excluded_ids\": [] }"
          - paragraph [ref=f1e177]: 確認前請核對筆數、操作、目標、理由及篩選條件。
          - generic [ref=f1e178]:
            - checkbox "確認精確維護清單" [ref=f1e179]
            - text: 確認精確維護清單
          - button "執行已確認維護清單" [disabled] [ref=f1e180]
          - button "重新查閱維護清單" [ref=f1e181] [cursor=pointer]
        - button "開始新的預覽" [ref=f1e182] [cursor=pointer]
      - region "買家清單及已儲存篩選" [ref=f1e183]:
        - heading "清單及已儲存篩選" [level=3] [ref=f1e184]
        - generic [ref=f1e185]:
          - generic [ref=f1e186]:
            - text: 買家清單
            - combobox "買家清單" [ref=f1e187]:
              - option "選擇清單" [selected]
          - generic [ref=f1e188]:
            - text: 清單名稱
            - textbox "清單名稱" [ref=f1e189]
          - button "建立清單" [disabled] [ref=f1e190]
          - button "重新命名所選清單" [disabled] [ref=f1e191]
          - button "將已選買家加入清單" [disabled] [ref=f1e192]
          - button "將已選買家移出清單" [disabled] [ref=f1e193]
          - button "顯示清單買家" [disabled] [ref=f1e194]
        - generic [ref=f1e195]:
          - generic [ref=f1e196]:
            - text: 已儲存篩選
            - combobox "已儲存篩選" [ref=f1e197]:
              - option "選擇已儲存篩選" [selected]
          - button "套用已儲存篩選" [disabled] [ref=f1e198]
          - generic [ref=f1e199]:
            - text: 篩選名稱
            - textbox "篩選名稱" [ref=f1e200]
          - button "儲存目前篩選" [disabled] [ref=f1e201]
```

# Test source

```ts
  1  | import {expect,test,type Page} from '@playwright/test';
  2  | import {execFile} from 'node:child_process';
  3  | import {promisify} from 'node:util';
  4  | import {resolve} from 'node:path';
  5  | import {writeFileSync} from 'node:fs';
  6  | import {signInWorkbench,workspace,project,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
  7  | const root=`/v1/workspaces/${workspace}/projects/${project}/bulk-manifests`;
  8  | const prefix='Q08 Manifest Fixture';
  9  | async function fixture(command:string,...args:string[]):Promise<{fixture_only:boolean;count:number;ids:string[];buyers:{id:string;version:number;owner:string|null}[];manifests:{id:string;count:number;status:string;job_id:string|null}[];total:number}>{
  10 |  const cwd=resolve('services/worker'),python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  11 |  const value=JSON.parse((await promisify(execFile)(python,['tests/fixtures/audit_manifests.py',command,...args],{cwd,timeout:45_000})).stdout);expect(value.fixture_only).toBe(true);return value;
  12 | }
  13 | async function open(page:Page,actor:'access'|'reviewer'|'viewer'='access',entry?:string){
  14 |  await signInWorkbench(page,true,actor,entry);await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');await page.getByRole('button',{name:'Buyers',exact:true}).click();
  15 |  const buyers=page.getByRole('region',{name:'Buyer results',exact:true});
  16 |  await buyers.getByRole('textbox',{name:'Search buyers',exact:true}).fill(prefix);await buyers.getByRole('textbox',{name:'Search buyers',exact:true}).press('Enter');
  17 |  await expect(buyers.getByRole('checkbox',{name:/^Select /})).toHaveCount(12);
  18 |  return page.getByRole('region',{name:'Segmented maintenance',exact:true});
  19 | }
  20 | async function preview(page:Page,panel:ReturnType<Page['getByRole']>){
  21 |  await panel.getByRole('textbox',{name:'Maintenance reason',exact:true}).fill('Q08 human reviewed maintenance');
  22 |  const read=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname===root);
  23 |  await panel.getByRole('button',{name:'Preview segmented maintenance',exact:true}).click();const response=await read;expect(response.status()).toBe(201);
  24 |  const data=(await response.json()).data;await expect(panel.getByRole('region',{name:'Frozen manifest'})).toContainText(`count: ${data.count}`);return data as {id:string;count:number;digest:string;version:number};
  25 | }
  26 | async function execute(page:Page,panel:ReturnType<Page['getByRole']>,id:string){
  27 |  await panel.getByRole('checkbox',{name:'Confirm exact manifest'}).check();const response=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname===root+`/${id}/execute`);
  28 |  await panel.getByRole('button',{name:'Execute confirmed manifest'}).click();return await response;
  29 | }
  30 | test.beforeEach(async()=>{await resetWorkbenchFixtureRateWindows();});
  31 | for(const count of [100,101,1001])test(`B01 B08 B14 ${count} actual rows require frozen preview and explicit execution`,async({page})=>{
  32 |  const seed=await fixture('seed',String(count)),panel=await open(page);
  33 |  await expect(panel.getByRole('button',{name:'Execute confirmed manifest'})).toHaveCount(0);
  34 |  if(count===1001)await expect(page.getByRole('region',{name:'Buyer results',exact:true})).toContainText(/clipped|1000/i);
  35 |  const manifest=await preview(page,panel);expect(manifest.count).toBe(count);expect((await fixture('inspect')).buyers.every(b=>b.version===1&&b.owner===null)).toBe(true);
  36 |  await expect(panel.getByRole('button',{name:'Execute confirmed manifest'})).toBeDisabled();const response=await execute(page,panel,manifest.id);expect(response.status()).toBe(count===100?200:202);const result=(await response.json()).data;
  37 |  if(count>100){const drain=await fixture('drain',result.id);expect(drain.total).toBe(count);const job=page.getByRole('region',{name:'Bulk job progress'});await job.getByRole('button',{name:'Refresh job'}).click();await expect(job).toContainText(`${count} of ${count}`);
  38 |   await job.getByRole('button',{name:'Show job results'}).click();await expect(job.locator('code')).toHaveCount(20);const seen:string[]=[];
  39 |   for(let offset=0;offset<count;offset+=20){await expect(job.getByText(`${offset+1}–${Math.min(offset+20,count)} / ${count}`,{exact:true})).toBeVisible();seen.push(...await job.locator('code').allTextContents());if(offset+20<count)await job.getByRole('button',{name:'Next job results'}).click();}
  40 |   expect(new Set(seen).size).toBe(count);expect(seen.sort()).toEqual(seed.ids.sort());
  41 |  }
  42 |  const state=await fixture('inspect');expect(state.buyers).toHaveLength(count);expect(state.buyers.every(b=>b.version===2&&b.owner!==null)).toBe(true);
  43 |  writeFileSync(`test-results/q08-ui-${count}.json`,JSON.stringify({fixture_only:true,manifest,result,state},null,2));await page.screenshot({path:`test-results/q08-en-${count}.png`,fullPage:true});
  44 | });
  45 | test('B15 lost preview and committed 202 retry one frozen body/key and restore after re-login',async({page})=>{
  46 |  await fixture('seed','101');const panel=await open(page);const previews:{key:string;body:unknown}[]=[],executions:{key:string;body:unknown}[]=[];
  47 |  await page.route(`**${root}`,async route=>{if(route.request().method()!=='POST')return route.continue();previews.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});const response=await route.fetch();if(previews.length===1)return route.abort('connectionfailed');await route.fulfill({response});});
  48 |  await panel.getByRole('textbox',{name:'Maintenance reason'}).fill('Q08 frozen unknown preview');await panel.getByRole('button',{name:'Preview segmented maintenance'}).click();await expect(panel.getByRole('button',{name:'Retry same preview'})).toBeVisible();await expect(panel.getByRole('textbox',{name:'Maintenance reason'})).toBeDisabled();
  49 |  await panel.getByRole('button',{name:'Retry same preview'}).click();await expect(panel.getByRole('region',{name:'Frozen manifest'})).toBeVisible();expect(previews).toHaveLength(2);expect(previews[1]).toEqual(previews[0]);
  50 |  const id=new URL(page.url()).searchParams.get('bulk_manifest')!;
  51 |  await page.route(`**${root}/${id}/execute`,async route=>{executions.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});const response=await route.fetch();expect(response.status()).toBe(202);if(executions.length===1)return route.abort('connectionfailed');await route.fulfill({response});});
  52 |  await panel.getByRole('checkbox',{name:'Confirm exact manifest'}).check();await panel.getByRole('button',{name:'Execute confirmed manifest'}).click();await expect(panel.getByRole('alert')).toBeVisible();await expect(panel.getByRole('button',{name:'Start a new preview'})).toBeDisabled();await panel.getByRole('button',{name:'Execute confirmed manifest'}).click();await expect(page.getByRole('region',{name:'Bulk job progress'})).toBeVisible();expect(executions).toHaveLength(2);expect(executions[1]).toEqual(executions[0]);
  53 |  const proof=await fixture('inspect');expect(proof.manifests.filter(m=>m.id===id)).toHaveLength(1);expect(proof.manifests.find(m=>m.id===id)?.status).toBe('executed');const entry=new URL(page.url()).pathname+new URL(page.url()).search;await signInWorkbench(page,true,'access',entry);await page.getByRole('button',{name:'Buyers',exact:true}).click();await expect(page.getByRole('region',{name:'Frozen manifest'})).toContainText('executed');expect(executions).toHaveLength(2);
  54 |  writeFileSync('test-results/q08-ui-unknown-recovery.json',JSON.stringify({fixture_only:true,previews,executions,proof},null,2));
  55 | });
  56 | test('B09 failed rows get a new exact digest and current versions; successes are retained',async({page})=>{
  57 |  const seed=await fixture('seed','101'),panel=await open(page),manifest=await preview(page,panel);await fixture('stale',seed.ids[0]);const response=await execute(page,panel,manifest.id),jobId=(await response.json()).data.id;await fixture('drain',jobId);
  58 |  const job=page.getByRole('region',{name:'Bulk job progress'});await job.getByRole('button',{name:'Refresh job'}).click();await expect(job).toContainText('1 conflicts');let directRetry=0;page.on('request',r=>{if(new URL(r.url()).pathname.endsWith('/retry-failed'))directRetry++;});
  59 |  await job.getByRole('button',{name:'Preview failed rows with current versions'}).click();const childPanel=page.getByRole('region',{name:'Segmented maintenance'});await expect(childPanel).toContainText('Failed rows only');const child=await preview(page,childPanel);expect(child.count).toBe(1);expect(child.digest).not.toBe(manifest.digest);expect(directRetry).toBe(0);const childResponse=await execute(page,childPanel,child.id);expect(childResponse.status()).toBe(200);const state=await fixture('inspect');expect(state.buyers.filter(b=>b.version===2)).toHaveLength(100);expect(state.buyers.find(b=>b.id===seed.ids[0])?.version).toBe(3);
  60 |  writeFileSync('test-results/q08-ui-child.json',JSON.stringify({fixture_only:true,manifest,child,state},null,2));
  61 | });
  62 | test('B16 late preview cannot cross A-B-A; viewer has no maintenance; zh-HK mobile exact confirmation',async({page,browser})=>{
  63 |  await fixture('seed','101');const panel=await open(page);let release:()=>void=()=>{},received:()=>void=()=>{};const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);
  64 |  await page.route(`**${root}`,async route=>{if(route.request().method()!=='POST')return route.continue();const response=await route.fetch();received();await held;await route.fulfill({response}).catch(()=>{});});
  65 |  await panel.getByRole('textbox',{name:'Maintenance reason'}).fill('Q08 old scope request');await panel.getByRole('button',{name:'Preview segmented maintenance'}).click();await started;await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption('e0000000-0000-4000-8000-000000000101');await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(workspace);release();await page.waitForTimeout(300);await expect(page.getByRole('region',{name:'Frozen manifest'})).toHaveCount(0);
  66 |  const viewer=await browser.newPage();try{await signInWorkbench(viewer,true,'viewer');await viewer.getByRole('button',{name:'Buyers',exact:true}).click();await expect(viewer.getByRole('region',{name:'Segmented maintenance'})).toHaveCount(0);}finally{await viewer.close();}
> 67 |  await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(project);await page.getByRole('button',{name:'Buyers',exact:true}).click();await page.unroute(`**${root}`);await page.setViewportSize({width:390,height:844});await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');const zh=page.getByRole('region',{name:'分段批量維護'});await expect(zh).toBeVisible();await zh.getByRole('button',{name:'重試同一預覽'}).click();await expect(zh.getByRole('region',{name:'已凍結維護清單'})).toBeVisible();await expect(zh.getByRole('button',{name:'執行已確認維護清單'})).toBeDisabled();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:'test-results/q08-zh-mobile.png',fullPage:true});
     |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        ^ Error: expect(received).toBe(expected) // Object.is equality
  68 | });
  69 | 
  70 | test('B01 reviewer executes current fit-bound review while operator cannot select review',async({page})=>{
  71 |  await fixture('seed','101');await fixture('assess');const panel=await open(page,'reviewer');await panel.getByRole('combobox',{name:'Operation',exact:true}).selectOption('reviewBuyers');const manifest=await preview(page,panel),response=await execute(page,panel,manifest.id);expect(response.status()).toBe(202);const job=(await response.json()).data;expect((await fixture('drain',job.id)).total).toBe(101);
  72 |  const progress=page.getByRole('region',{name:'Bulk job progress'});await progress.getByRole('button',{name:'Refresh job'}).click();await expect(progress).toContainText('101 updated');await page.screenshot({path:'test-results/q08-review-en.png',fullPage:true});
  73 | });
  74 | test('B08 typed list target supports confirmed add and explicit new remove preview',async({page})=>{
  75 |  await fixture('seed','100');const panel=await open(page),management=page.getByRole('region',{name:'Buyer lists and saved filters'});
  76 |  await management.getByRole('textbox',{name:'List name'}).fill('Q08 reviewed list');const created=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/lists'));await management.getByRole('button',{name:'Create list',exact:true}).click();const list=(await (await created).json()).data;
  77 |  await panel.getByRole('combobox',{name:'Operation',exact:true}).selectOption('changeListMemberships');await panel.getByRole('button',{name:'Reload lists'}).click();await expect(panel.getByRole('combobox',{name:'Target list'}).locator('option',{hasText:'Q08 reviewed list'})).toBeAttached();await panel.getByRole('combobox',{name:'Target list'}).selectOption(list.id);
  78 |  const first=await preview(page,panel),added=await execute(page,panel,first.id);expect(added.status()).toBe(200);expect((await added.json()).data.updated).toBe(100);
  79 |  await panel.getByRole('button',{name:'Start a new preview'}).click();await panel.getByRole('combobox',{name:'List change'}).selectOption('remove');const second=await preview(page,panel);expect(second.digest).not.toBe(first.digest);const removed=await execute(page,panel,second.id);expect(removed.status()).toBe(200);expect((await removed.json()).data.updated).toBe(100);expect((await fixture('inspect')).buyers.every(b=>b.version===1&&b.owner===null)).toBe(true);
  80 | });
  81 | 
```