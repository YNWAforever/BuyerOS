# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-keyboard-workbench.spec.ts >> U09 U10 keyboard zh-HK mobile task3 cross-page assignment, persisted conflict and exact failed-only manifest
- Location: tests\e2e\audit-keyboard-workbench.spec.ts:30:2

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('region', { name: '買家結果', exact: true }).getByRole('region', { name: '批量工作進度', exact: true }).getByText('61–80 / 101', { exact: true })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('region', { name: '買家結果', exact: true }).getByRole('region', { name: '批量工作進度', exact: true }).getByText('61–80 / 101', { exact: true }) with timeout 5000ms
  - waiting for getByRole('region', { name: '買家結果', exact: true }).getByRole('region', { name: '批量工作進度', exact: true }).getByText('61–80 / 101', { exact: true })

```

```yaml
- main:
  - text: FIMMICK BuyerOS 正式工作區 語言
  - combobox "語言":
    - option "English"
    - option "繁體中文" [selected]
  - button "登出"
  - navigation "BuyerOS sections":
    - button "總覽"
    - button "產品資料"
    - button "買家"
    - button "結果"
    - button "研究進度"
    - button "草稿"
    - button "設定"
    - button "營運工作台"
  - region "工作區選擇":
    - heading "工作區" [level=2]
    - text: 工作區
    - combobox "工作區":
      - option "選擇工作區"
      - option "E2E fixture workspace" [selected]
      - option "Other audit fixture"
    - paragraph: "角色: 操作員"
  - region "專案選擇":
    - heading "專案" [level=2]
    - text: 專案
    - combobox "專案":
      - option "選擇專案"
      - option "Buyer Fixture Project" [selected]
      - option "Run Fixture Project"
      - option "T30 Fictional Seller"
      - option "T30 Fictional Seller"
      - option "T30 Fictional Seller"
      - option "T30 Fictional Seller"
      - option "Q14 project B"
    - button "新增專案"
    - button "編輯產品資料"
  - region "買家結果":
    - heading "買家" [level=2]
    - text: 101 項快照
    - group "買家篩選":
      - text: 搜尋買家
      - textbox "搜尋買家": Q08 Manifest Fixture
      - button "套用篩選"
      - text: 配對
      - combobox "配對篩選":
        - option "不限" [selected]
        - option "符合"
        - option "須檢查"
        - option "不符合"
      - text: 審閱
      - combobox "審閱篩選":
        - option "不限" [selected]
        - option "待審買家"
        - option "已接納"
        - option "已拒絕"
        - option "需更多資料"
      - text: 佇列
      - combobox "工作佇列篩選":
        - option "全部" [selected]
        - option "未分派"
        - option "適合度未明"
      - text: 排序
      - combobox "買家排序":
        - option "名稱" [selected]
        - option "最佳配對"
      - button "更新結果"
    - button "選取本頁"
    - button "選取所有篩選結果"
    - button "清除選取"
    - text: 已明確選取 0 項
    - checkbox "選取 Q08 Manifest Fixture 00012"
    - text: Q08 Manifest Fixture 00012
    - paragraph: 尚未評估配對 · 尚未審閱 · 沒有備註
    - button "詳情"
    - checkbox "選取 Q08 Manifest Fixture 00013"
    - text: Q08 Manifest Fixture 00013
    - paragraph: 尚未評估配對 · 尚未審閱 · 沒有備註
    - button "詳情"
    - checkbox "選取 Q08 Manifest Fixture 00014"
    - text: Q08 Manifest Fixture 00014
    - paragraph: 尚未評估配對 · 尚未審閱 · 沒有備註
    - button "詳情"
    - checkbox "選取 Q08 Manifest Fixture 00015"
    - text: Q08 Manifest Fixture 00015
    - paragraph: 尚未評估配對 · 尚未審閱 · 沒有備註
    - button "詳情"
    - checkbox "選取 Q08 Manifest Fixture 00016"
    - text: Q08 Manifest Fixture 00016
    - paragraph: 尚未評估配對 · 尚未審閱 · 沒有備註
    - button "詳情"
    - checkbox "選取 Q08 Manifest Fixture 00017"
    - text: Q08 Manifest Fixture 00017
    - paragraph: 尚未評估配對 · 尚未審閱 · 沒有備註
    - button "詳情"
    - checkbox "選取 Q08 Manifest Fixture 00018"
    - text: Q08 Manifest Fixture 00018
    - paragraph: 尚未評估配對 · 尚未審閱 · 沒有備註
    - button "詳情"
    - checkbox "選取 Q08 Manifest Fixture 00019"
    - text: Q08 Manifest Fixture 00019
    - paragraph: 尚未評估配對 · 尚未審閱 · 沒有備註
    - button "詳情"
    - checkbox "選取 Q08 Manifest Fixture 00020"
    - text: Q08 Manifest Fixture 00020
    - paragraph: 尚未評估配對 · 尚未審閱 · 沒有備註
    - button "詳情"
    - checkbox "選取 Q08 Manifest Fixture 00021"
    - text: Q08 Manifest Fixture 00021
    - paragraph: 尚未評估配對 · 尚未審閱 · 沒有備註
    - button "詳情"
    - checkbox "選取 Q08 Manifest Fixture 00022"
    - text: Q08 Manifest Fixture 00022
    - paragraph: 尚未評估配對 · 尚未審閱 · 沒有備註
    - button "詳情"
    - checkbox "選取 Q08 Manifest Fixture 00023"
    - text: Q08 Manifest Fixture 00023
    - paragraph: 尚未評估配對 · 尚未審閱 · 沒有備註
    - button "詳情"
    - button "上一頁"
    - text: 第 13–24 項，共 101 項
    - button "下一頁"
    - text: 每頁項數
    - combobox "每頁項數":
      - option "8"
      - option "12" [selected]
      - option "24"
    - region "負責人分派結果":
      - heading "負責人分派結果" [level=3]
      - status: 2 列已更新；0 列不變；0 列受阻；0 列衝突。
    - region "分段批量維護":
      - heading "分段批量維護" [level=3]
      - paragraph: 此預覽會凍結所有符合條件的 ID 及版本，上限 10000 筆。確認精確摘要前不會更改買家。
      - group "操作":
        - text: 操作
        - combobox "操作" [disabled]:
          - option "指派負責人" [disabled] [selected]
          - option "更改清單成員" [disabled]
        - text: 搜尋同事
        - textbox "搜尋同事" [disabled]
        - button "搜尋" [disabled]
        - text: 負責人
        - combobox "負責人" [disabled]:
          - option "清除負責人" [disabled]
          - option "e0000000-0000-4000-8000-000000000002 · e0000000-0000-4000-8000-000000000003" [disabled] [selected]
          - option "e0000000-0000-4000-8000-000000000004 · e0000000-0000-4000-8000-000000000005" [disabled]
          - option "e0000000-0000-4000-8000-000000000006 · e0000000-0000-4000-8000-000000000007" [disabled]
          - option "e0000000-0000-4000-8000-000000000008 · e0000000-0000-4000-8000-000000000009" [disabled]
          - option "Alex Chen · f1000000-0000-4000-8000-000000000000" [disabled]
          - option "Alex Chen · f1000000-0000-4000-8000-000000000001" [disabled]
          - option "f2000000-0000-4000-8000-000000000002 · f1000000-0000-4000-8000-000000000002" [disabled]
          - option "Fixture member 003 · f1000000-0000-4000-8000-000000000003" [disabled]
          - option "Fixture member 004 · f1000000-0000-4000-8000-000000000004" [disabled]
          - option "Fixture member 005 · f1000000-0000-4000-8000-000000000005" [disabled]
          - option "Fixture member 006 · f1000000-0000-4000-8000-000000000006" [disabled]
          - option "Fixture member 007 · f1000000-0000-4000-8000-000000000007" [disabled]
          - option "Fixture member 008 · f1000000-0000-4000-8000-000000000008" [disabled]
          - option "Fixture member 009 · f1000000-0000-4000-8000-000000000009" [disabled]
          - option "Fixture member 010 · f1000000-0000-4000-8000-00000000000a" [disabled]
          - option "Fixture member 011 · f1000000-0000-4000-8000-00000000000b" [disabled]
          - option "Fixture member 012 · f1000000-0000-4000-8000-00000000000c" [disabled]
          - option "Fixture member 013 · f1000000-0000-4000-8000-00000000000d" [disabled]
          - option "Fixture member 014 · f1000000-0000-4000-8000-00000000000e" [disabled]
          - option "Fixture member 015 · f1000000-0000-4000-8000-00000000000f" [disabled]
        - text: 1–20 / 250
        - button "上一頁同事" [disabled]
        - button "下一頁同事" [disabled]
      - text: 維護理由
      - textbox "維護理由" [disabled]: Keyboard reviewed exact101 manifest
      - text: 排除買家 ID（每行一個）
      - textbox "排除買家 ID（每行一個）" [disabled]
      - region "已凍結維護清單":
        - heading "已凍結維護清單" [level=4]
        - paragraph: "94359281-36f3-4356-b81b-3d5732034bf1 · 已執行 · 筆數: 101"
        - paragraph: "摘要: 7f99c2f5179c674fed5f5fbcd9e83b2522f3c59e5002259de87cfe4ebde78a56"
        - paragraph: "到期時間: 2026-10-03T21:45:34.319938+00:00"
        - paragraph: 指派負責人
        - text: "{ \"target\": { \"owner_membership_id\": \"e0000000-0000-4000-8000-000000000003\" }, \"filters\": { \"q\": \"Q08 Manifest Fixture\" }, \"reason\": \"Keyboard reviewed exact101 manifest\", \"excluded_ids\": [] }"
        - paragraph: 確認前請核對筆數、操作、目標、理由及篩選條件。
        - checkbox "確認精確維護清單" [disabled]
        - text: 確認精確維護清單
        - button "執行已確認維護清單" [disabled]
        - button "重新查閱維護清單"
      - button "開始新的預覽"
    - region "批量工作進度":
      - heading "批量工作進度" [level=3]
      - button "關閉工作"
      - status: 已完成：已處理 101／101 列；更新 98、不變 2、受阻 0、衝突 1、取消 0。
      - button "更新工作進度"
      - button "匯出失敗買家 ID 與原因"
      - button "按目前版本預覽失敗列"
      - paragraph: 失敗列：1。報告只包含買家 ID 和內部原因碼。
      - list
      - button "隱藏工作結果"
      - paragraph:
        - code: aee8ee38-6c2f-5c15-a538-8f9a72d7e983
        - text: ": 已更新"
      - paragraph:
        - code: 6b498655-74e7-5349-a5fc-603829a12fdd
        - text: ": 已更新"
      - paragraph:
        - code: 96c015dd-ca4f-5906-b089-276f36efce4d
        - text: ": 已更新"
      - paragraph:
        - code: da8094ce-9f3a-529a-8868-39789fdb4ddf
        - text: ": 已更新"
      - paragraph:
        - code: 184621c8-5f2a-5700-9681-a6e63127184f
        - text: ": 已更新"
      - paragraph:
        - code: 9bcd3b38-1322-586e-a916-bd23f2380e1d
        - text: ": 已更新"
      - paragraph:
        - code: 98c16307-fa52-5a02-ac9a-78ddd3e228ae
        - text: ": 已更新"
      - paragraph:
        - code: 99ba2e47-be85-593b-afbe-237df7073d23
        - text: ": 已更新"
      - paragraph:
        - code: 05e4b959-3652-5f04-8f2f-c4cb3125d20f
        - text: ": 已更新"
      - paragraph:
        - code: 85d13b08-685a-5e83-95d4-0c106e65f0a0
        - text: ": 已更新"
      - paragraph:
        - code: 98b93c67-30bc-55a6-b324-523930dc9487
        - text: ": 已更新"
      - paragraph:
        - code: cc4fffa7-da23-54d2-bff1-a0891cd55a5b
        - text: ": 已更新"
      - paragraph:
        - code: 4492589e-d821-5333-91a4-c70cc8991e69
        - text: ": 已更新"
      - paragraph:
        - code: b7bfbab5-9ecf-525f-833c-c01cc978d49e
        - text: ": 已更新"
      - paragraph:
        - code: 117a5761-8b73-54f4-a168-591146d3e91d
        - text: ": 已更新"
      - paragraph:
        - code: d3b8de3e-456e-51a7-be36-5c45c10781b2
        - text: ": 已更新"
      - paragraph:
        - code: b74ffc1a-ecb3-5060-8c09-4971a3d7083f
        - text: ": 已更新"
      - paragraph:
        - code: 451085a0-4901-51c4-a959-20313c57af2a
        - text: ": 已更新"
      - paragraph:
        - code: 51ca3e3c-bc57-5ea4-9604-b13997a1ccba
        - text: ": 已更新"
      - paragraph:
        - code: 71d2da56-d2ea-56d1-8047-b1f6833981e9
        - text: ": 已更新"
      - button "上一頁工作結果" [disabled]
      - text: 41–60 / 101
      - button "下一頁工作結果" [disabled]
    - region "買家清單及已儲存篩選":
      - heading "清單及已儲存篩選" [level=3]
      - text: 買家清單
      - combobox "買家清單":
        - option "選擇清單" [selected]
      - text: 清單名稱
      - textbox "清單名稱"
      - button "建立清單" [disabled]
      - button "重新命名所選清單" [disabled]
      - button "將已選買家加入清單" [disabled]
      - button "將已選買家移出清單" [disabled]
      - button "顯示清單買家" [disabled]
      - text: 已儲存篩選
      - combobox "已儲存篩選":
        - option "選擇已儲存篩選" [selected]
      - button "套用已儲存篩選" [disabled]
      - text: 篩選名稱
      - textbox "篩選名稱"
      - button "儲存目前篩選" [disabled]
```

# Test source

```ts
  1   | import {expect,test} from '@playwright/test';
  2   | import {execFile} from 'node:child_process';
  3   | import {promisify} from 'node:util';
  4   | import {resolve} from 'node:path';
  5   | import {readFile} from 'node:fs/promises';
  6   | import {createJourneyInput} from './fixtures/journey-input';
  7   | import {workspace,project,signInWorkbench,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
  8   | 
  9   | type Seed={fixture_only:boolean;ids:string[]};
  10  | type State={fixture_only:boolean;buyers:{id:string;version:number;owner:string|null}[]};
  11  | type Jobs={fixture_only:boolean;own_ids:string[];other_ids:string[]};
  12  | async function fixture<T extends {fixture_only:boolean}>(script:string,...args:string[]):Promise<T>{
  13  |  const cwd=resolve('services/worker'),python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  14  |  const {stdout}=await promisify(execFile)(python,[`tests/fixtures/${script}.py`,...args],{cwd,timeout:script==='audit_manifests'?45_000:30_000,maxBuffer:1024*1024});
  15  |  const value=JSON.parse(stdout.trim().split(/\r?\n/).at(-1)!) as T;expect(value.fixture_only).toBe(true);return value;
  16  | }
  17  | const zh:Record<string,string>={
  18  |  'Buyers':'買家','Buyer results':'買家結果','Search buyers':'搜尋買家','Next page':'下一頁',
  19  |  'Assign buyer owners':'批量分派買家負責人','Assignment reason':'分派原因','Confirm owner assignment':'確認負責人分派','Assign selected buyers':'分派已選買家',
  20  |  'Segmented maintenance':'分段批量維護','Maintenance reason':'維護理由','Preview segmented maintenance':'預覽分段批量維護','Frozen manifest':'已凍結維護清單',
  21  |  'Confirm exact manifest':'確認精確維護清單','Execute confirmed manifest':'執行已確認維護清單','Bulk job progress':'批量工作進度','Refresh job':'更新工作進度',
  22  |  'Show job results':'顯示工作結果','Next job results':'下一頁工作結果','Export failed IDs and reasons':'匯出失敗買家 ID 與原因','Preview failed rows with current versions':'按目前版本預覽失敗列',
  23  |  'Settings':'設定','Member management':'成員管理','Search members':'搜尋成員','Search':'搜尋','Member':'成員','operator':'操作員','Change reason':'變更原因','Save member':'儲存成員',
  24  |  'Project':'專案','Overview':'總覽','Failed jobs':'失敗工作','Open':'開啟','Bulk jobs':'批量工作','Next':'下一頁','Job details':'工作詳情',
  25  | };
  26  | const ownActor='e0000000-0000-4000-8000-000000000002',projectB='e1140000-0000-4000-8000-000000000002';
  27  | for(const [locale,layout] of [['en','desktop'],['zh-HK','mobile']] as const){
  28  |  const t=(text:string)=>locale==='zh-HK'?(zh[text]??text):text;
  29  |  const viewport=layout==='desktop'?{width:1280,height:800}:{width:390,height:844};
  30  |  test(`U09 U10 keyboard ${locale} ${layout} task3 cross-page assignment, persisted conflict and exact failed-only manifest`,async({page})=>{
  31  |   test.setTimeout(300_000);await page.setViewportSize(viewport);await resetWorkbenchFixtureRateWindows();
  32  |   const seeded=await fixture<Seed>('audit_manifests','seed','101'),input=createJourneyInput('keyboard');
  33  |   await signInWorkbench(page,true,'access',undefined,input);
  34  |   await input.choose(page.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}),locale);
  35  |   await input.activate(page.getByRole('button',{name:t('Buyers'),exact:true}));
  36  |   const buyers=page.getByRole('region',{name:t('Buyer results'),exact:true});
  37  |   await input.fill(buyers.getByRole('textbox',{name:t('Search buyers'),exact:true}),'Q08 Manifest Fixture');await page.keyboard.press('Enter');
  38  |   const selected=buyers.getByRole('checkbox',{name:/^(Select |選取 )/});await expect(selected).toHaveCount(12);
  39  |   await input.check(selected.first());await input.activate(buyers.getByRole('button',{name:t('Next page'),exact:true}));
  40  |   await expect(selected.first()).toHaveAttribute('aria-label',locale==='en'?'Select Q08 Manifest Fixture 00012':'選取 Q08 Manifest Fixture 00012');await input.check(selected.first());
  41  |   const panel=buyers.getByRole('region',{name:t('Assign buyer owners'),exact:true});await expect(panel).toContainText(locale==='en'?'Preview: 2 selected buyers':'預覽：已選 2 位買家');
  42  |   await input.fill(panel.getByRole('textbox',{name:t('Assignment reason'),exact:true}),'Keyboard reviewed two pages');await input.check(panel.getByRole('checkbox',{name:t('Confirm owner assignment'),exact:true}));
  43  |   const assigned=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/buyer-owner-assignments'));
  44  |   await input.activate(panel.getByRole('button',{name:t('Assign selected buyers'),exact:true}));const response=await assigned;expect(response.status()).toBe(200);
  45  |   const first=(await response.json()).data;expect([first.updated,first.conflicts,first.blocked]).toEqual([2,0,0]);
  46  |   const initial=await fixture<State>('audit_manifests','inspect');expect(initial.buyers.filter(b=>b.owner===ownActor).map(b=>b.id)).toEqual([seeded.ids[0],seeded.ids[12]]);
  47  |   expect(initial.buyers.filter(b=>b.version===2)).toHaveLength(2);expect(initial.buyers.filter(b=>b.version===1&&b.owner===null)).toHaveLength(99);
  48  |   const maintenance=buyers.getByRole('region',{name:t('Segmented maintenance'),exact:true});
  49  |   await input.fill(maintenance.getByRole('textbox',{name:t('Maintenance reason'),exact:true}),'Keyboard reviewed exact101 manifest');
  50  |   async function preview(){
  51  |    const pending=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/bulk-manifests'));
  52  |    await input.activate(maintenance.getByRole('button',{name:t('Preview segmented maintenance'),exact:true}));const r=await pending;expect(r.status()).toBe(201);return (await r.json()).data as {id:string;count:number;digest:string};
  53  |   }
  54  |   async function execute(id:string){
  55  |    await input.check(maintenance.getByRole('checkbox',{name:t('Confirm exact manifest'),exact:true}));
  56  |    const pending=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith(`/bulk-manifests/${id}/execute`));
  57  |    await input.activate(maintenance.getByRole('button',{name:t('Execute confirmed manifest'),exact:true}));return await pending;
  58  |   }
  59  |   const manifest=await preview();expect(manifest.count).toBe(101);await fixture<Seed>('audit_manifests','stale',seeded.ids[1]);
  60  |   const executed=await execute(manifest.id);expect(executed.status()).toBe(202);const job=(await executed.json()).data;
  61  |   const drained=await fixture<{fixture_only:boolean;total:number}>('audit_manifests','drain',job.id);expect(drained.total).toBe(101);
  62  |   const progress=buyers.getByRole('region',{name:t('Bulk job progress'),exact:true});await input.activate(progress.getByRole('button',{name:t('Refresh job'),exact:true}));
  63  |   const summary=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/jobs/${job.id}/summary`,{headers:{Authorization:'Bearer fixture-access'}});expect(summary.status()).toBe(200);
  64  |   const result=(await summary.json()).data;expect([result.processed,result.updated,result.unchanged,result.conflicts,result.blocked]).toEqual([101,98,2,1,0]);
  65  |   await expect(progress).toContainText(locale==='en'?'1 conflicts':'衝突 1');await input.activate(progress.getByRole('button',{name:t('Show job results'),exact:true}));
  66  |   const seen:string[]=[];
> 67  |   for(let offset=0;offset<101;offset+=20){await expect(progress.getByText(`${offset+1}–${Math.min(offset+20,101)} / 101`,{exact:true})).toBeVisible();seen.push(...await progress.locator('code').allTextContents());if(offset+20<101)await input.activate(progress.getByRole('button',{name:t('Next job results'),exact:true}));}
      |                                                                                                                                         ^ Error: expect(locator).toBeVisible() failed
  68  |   expect(seen.length).toBe(101);expect(new Set(seen)).toEqual(new Set(seeded.ids));
  69  |   const download=page.waitForEvent('download');await input.activate(progress.getByRole('button',{name:t('Export failed IDs and reasons'),exact:true}));
  70  |   const csv=await readFile((await (await download).path())!,'utf8');expect(csv.trim().split(/\r?\n/)).toHaveLength(2);expect(csv).toContain(seeded.ids[1]);expect(csv).not.toContain(seeded.ids[0]);
  71  |   const before=await fixture<State>('audit_manifests','inspect');
  72  |   await input.activate(progress.getByRole('button',{name:t('Preview failed rows with current versions'),exact:true}));
  73  |   const retry=await preview();expect(retry.count).toBe(1);expect(retry.digest).not.toBe(manifest.digest);const retried=await execute(retry.id);expect(retried.status()).toBe(200);expect((await retried.json()).data.updated).toBe(1);
  74  |   const after=await fixture<State>('audit_manifests','inspect');expect(after.buyers.filter(b=>b.owner===ownActor)).toHaveLength(101);
  75  |   expect(after.buyers.filter((b,i)=>b.version!==before.buyers[i].version).map(b=>b.id)).toEqual([seeded.ids[1]]);expect(after.buyers.find(b=>b.id===seeded.ids[1])?.version).toBe(3);
  76  |   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  77  |   await page.screenshot({path:`test-results/q09-keyboard-task3-${locale}-${layout}.png`,fullPage:true});
  78  |   await test.info().attach('keyboard-task3-proof',{body:JSON.stringify({fixture_only:true,manifest,retry,job:job.id,result,csv,before,after,input:await input.verify(page)},null,2),contentType:'application/json'});
  79  |  });
  80  |  test(`U09 U10 keyboard ${locale} ${layout} task5 versioned member change, failed-job paging and scope recovery`,async({page,browser})=>{
  81  |   test.setTimeout(300_000);await page.setViewportSize(viewport);await resetWorkbenchFixtureRateWindows();
  82  |   await fixture<Seed>('audit_memberships');const jobs=await fixture<Jobs>('audit_job_scopes','21'),input=createJourneyInput('keyboard');
  83  |   await signInWorkbench(page,true,'admin',undefined,input);await input.choose(page.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}),locale);
  84  |   await input.activate(page.getByRole('button',{name:t('Settings'),exact:true}));const directory=page.getByRole('region',{name:t('Member management'),exact:true});
  85  |   await input.fill(directory.getByRole('textbox',{name:t('Search members'),exact:true}),'Alex');await input.activate(directory.getByRole('button',{name:t('Search'),exact:true}));
  86  |   const members=directory.getByRole('group',{name:`${t('Member')} Alex Chen`,exact:true});await expect(members).toHaveCount(2);
  87  |   const first=members.filter({has:page.locator('code').filter({hasText:'71000001-0000-4000-8000-000000c011de'})});
  88  |   await input.activate(first.getByText(locale==='en'?'Technical details':'技術資料',{exact:true}));await expect(first.locator('code')).toBeVisible();
  89  |   await input.check(first.getByRole('checkbox',{name:t('operator'),exact:true}));await input.fill(directory.getByRole('textbox',{name:t('Change reason'),exact:true}),'Keyboard fixture duty rotation');
  90  |   const pending=page.waitForResponse(r=>r.request().method()==='PATCH'&&new URL(r.url()).pathname.includes('/memberships/'));
  91  |   await input.activate(first.getByRole('button',{name:t('Save member'),exact:true}));const changed=await pending;expect(changed.status()).toBe(200);expect(changed.request().headers()['if-match']).toBe('"1"');expect(changed.request().headers()['idempotency-key']).toBeTruthy();
  92  |   const member=(await changed.json()).data;expect(member.user_id).toBe('71000001-0000-4000-8000-000000c011de');expect(member.version).toBe(2);
  93  |   const read=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/memberships?q=Alex`,{headers:{Authorization:'Bearer fixture-admin'}});expect(read.status()).toBe(200);expect((await read.json()).data.items.map((m:{version:number})=>m.version)).toEqual([2,1]);
  94  |   await input.choose(page.getByRole('combobox',{name:t('Project'),exact:true}),projectB);await input.activate(page.getByRole('button',{name:t('Overview'),exact:true}));
  95  |   const card=page.locator('.activity').filter({has:page.getByText(t('Failed jobs'),{exact:true})});await expect(card.locator('p')).toHaveText('24');await input.activate(card.getByRole('button',{name:t('Open'),exact:true}));
  96  |   const list=page.getByRole('region',{name:t('Bulk jobs'),exact:true});await expect(list).toContainText(locale==='en'?'24 jobs in scope':'24 項範圍內工作');
  97  |   const seen=await list.getByRole('button').filter({hasText:/^[0-9a-f-]{36}$/}).allTextContents();expect(seen).toHaveLength(20);
  98  |   await input.activate(list.getByRole('button',{name:t('Next'),exact:true}));await expect(list.getByText('21–24 / 24',{exact:true})).toBeVisible();seen.push(...await list.getByRole('button').filter({hasText:/^[0-9a-f-]{36}$/}).allTextContents());
  99  |   expect(new Set(seen)).toEqual(new Set([...jobs.own_ids,...jobs.other_ids]));await input.activate(list.getByRole('button',{name:seen[20],exact:true}));
  100 |   const details=page.getByRole('region',{name:t('Job details'),exact:true});await expect(details).toBeVisible();
  101 |   const jobRead=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/jobs/${seen[20]}`,{headers:{Authorization:'Bearer fixture-admin'}});expect(jobRead.status()).toBe(200);expect((await jobRead.json()).data.project_id).toBe(projectB);
  102 |   await input.choose(page.getByRole('combobox',{name:t('Project'),exact:true}),project);await expect(list).toContainText(locale==='en'?'0 jobs in scope':'0 項範圍內工作');await expect(details).toHaveCount(0);
  103 |   const viewerContext=await browser.newContext({viewport}),viewer=await viewerContext.newPage();
  104 |   try{await signInWorkbench(viewer,true,'viewer',undefined,input);await input.choose(viewer.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}),locale);await input.activate(viewer.getByRole('button',{name:t('Settings'),exact:true}));await expect(viewer.getByRole('region',{name:t('Member management'),exact:true})).toHaveCount(0);
  105 |    expect((await viewer.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/memberships`,{headers:{Authorization:'Bearer fixture-viewer'}})).status()).toBe(403);
  106 |    expect((await viewer.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/jobs/${jobs.own_ids[0]}`,{headers:{Authorization:'Bearer fixture-viewer'}})).status()).toBe(404);
  107 |    await test.info().attach('keyboard-task5-viewer',{body:JSON.stringify(await input.verify(viewer),null,2),contentType:'application/json'});
  108 |   }finally{await viewerContext.close();}
  109 |   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:`test-results/q09-keyboard-task5-${locale}-${layout}.png`,fullPage:true});
  110 |   await test.info().attach('keyboard-task5-proof',{body:JSON.stringify({fixture_only:true,member,jobs:seen,input:await input.verify(page)},null,2),contentType:'application/json'});
  111 |  });
  112 | }
  113 | 
```