from pathlib import Path
import csv, json, hashlib, html, re, base64, zipfile
from collections import Counter
from datetime import datetime, timezone

root = Path(__file__).resolve().parent
repo = root.parent / 'buyeros-audit'
ev = root / 'evidence'
SHA = 'a78859fe474f5722be3755b10e2586436b53bf97'

def csv_write(name, fields, rows):
    with (root/name).open('w', encoding='utf-8-sig', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)

# Preserve old case identities. Historical observations are never promoted to
# a new live result merely because the source SHA is unchanged.
old = list(csv.DictReader((root/'prior-cases.csv').open(encoding='utf-8')))
cases=[]
actuals={
 'U01':('blocked','verified','登入成功；重試後無membership、workspace404；完整業務流程未進入','E01;E07'),
 'U02':('fail','verified','空狀態無重新核對membership／支援聯絡控制項','E01;E03'),
 'U03':('fail','verified','Language選單disabled','E01;E03'),
 'A01':('pass','verified','6個deterministic fixtures正確；屬61通過測試的一項','E04'),
 'A02':('fail','verified','兩組tone/objective：same subject/body；different metadata','E06'),
 'S01':('pass','verified','本次JWT／JWKS單元檢查通過；非Neon或live tenant驗收','E04;E05'),
 'S02':('pass','verified','本次safe_fetch四項單元檢查通過；非完整SSRF驗收','E04'),
 'S03':('pass','verified','本次settlement三項通過；無正式帳本寫入','E04'),
 'S04':('pass','verified','provider gate非DB檢查通過；另一duplicate-settlement DB case跳過','E04'),
 'S05':('pass','verified','Vercel5與worker gateway1，本次共6通過','E05'),
 'S06':('blocked','blocked','無Docker／owned PostgreSQL，未執行RLS／last-admin DB驗收','E04'),
 'R01':('blocked','verified','main與production source相符；DB schema／worker selector尚未readback','E02'),
}
for r in old:
    result,evidence_state,actual,evidence=actuals.get(r['case_id'],('not-tested','code-only' if r['audit_status'].startswith('SOURCE') else 'not-tested','未於本次執行；舊狀態保留於historical_status','E03' if r['audit_status'].startswith('SOURCE') else ''))
    cases.append(dict(case_id=r['case_id'],finding_ids=r['finding'],priority=r['priority'],scenario=r['scenario'],preconditions=r['precondition_data'],steps=r['steps'],expected=r['expected_acceptance'],actual=actual,result=result,evidence_state=evidence_state,evidence_ids=evidence,historical_status=r['audit_status'],environment='本次正式read-only' if r['case_id'] in ['U01','U02','U03'] else '本地／隔離fixture；未執行者須依前置条件提供',cleanup='本次未建立正式資料；未執行者於隔離fixture結束後依runbook處理',owner_role=r['owner']))

new=[
 ('U13','F15','P2','Callback初始化不誤報','有設定auth的乾淨啟動／hydration','登入並記initializing→callback→session各畫面','配置正確時不出現未設定alert','短暫顯示Live sign-in is not configured後完成登入','fail','verified','E03;E07'),
 ('U14','F20','P1','Neon刷新／新分頁與deep link','隔離Neon會員及同源cookie；未實作','登入後刷新、開新分頁、短JWT過期後讀資料','正確恢復scope；限次token renewal；不把token存localStorage','Neon未實作；只見現有記憶體Auth0新頁要登入','not-tested','code-only','E03;E09'),
 ('U15','F17','P2','專案統計與列表同範圍','A零failed；同workspace B五failed','選A看Overview Failed jobs再開列表；切B','A0、B5；或明確標全workspace，統計與列表一致','程式碼未帶project_id；尚未執行DB／UI fixture','not-tested','code-only','E03'),
 ('U16','F21','P1','正式workspace讀取錯誤恢復','正式read-only；登入完成','首次載入；記requestID；按一次Retry','正常read或可恢復錯誤；server log可定位原因','首次500 OperationalError；Retry成功讀取空membership','fail','verified','E07'),
 ('D01','F16','P1','人工改稿至重新審批','隔離addressed grounded draft、operator與reviewer','改正文→保存→來源覆核→request review→approve→export','保留人工內容；新revision精確引用與審批；全鏈可完成','edit清claims；UI無重grounding入口；未跑完整持久化case','not-tested','code-only','E03;E06'),
 ('D02','F19','P2','Dirty稿件refresh不丟失','已開draft且有未保存subject/body/language','按Refresh draft／Refresh job／Open other draft，分別Cancel／Save／Discard','Cancel保留所有輸入；Save成功再換；Discard明確確認','source refresh未guard；尚未執行component互動','not-tested','code-only','E03'),
 ('D03','F16','P1','未覆核人工稿不得直接批准','needs_review與empty claims fictional revision','呼叫實際current_approval_context','拒絕並保持未批准；不可自動grounded','本次實際approval gate拒絕grounded nonempty draft required','pass','verified','E06'),
 ('P09','F18','P1','Workspace查詢量基線','fake SQL connection；W=1/10/100/1000','呼叫真實list_workspaces，固定limit100；測page1/page2','修復目標：不隨無關W線性掃描；只回有權限項目','4/22/202/2002 execute；第二頁仍2002；現版未達修復目標','fail','verified','E06'),
 ('P10','F18','P1','Workspace SQL分頁與租戶保護','owned PG；相同canonical user；active/revoked memberships','EXPLAIN與SQLcount、頁1/2；並發撤回；跨tenant讀寫','有界查詢；無漏列重複；撤回有效；RLS不放寬','本次未有owned PG','blocked','blocked','E03'),
 ('WF01','F14','P1','Offer部分保存與lost response','同一UI建立project／ICP；假文件provider；隔離DB','project已commit後令ICP保存失敗，再按同次Retry','不多建project；原輸入保留；ICP基於正確offer revision','source有ActionIntent／部分成功處理；本次未執行E2E','not-tested','code-only','E03'),
 ('WF02','F14','P1','過期Offer不得沿用舊ICP批准','operator修改offer與reviewer持有舊頁','先改offer，再批准舊ICP，再嘗試research','412／清楚差異；無stale批准／research副作用','本次未執行；需owned PG與兩角色','not-tested','not-tested',''),
 ('WF03','F14;F10','P1','同一專案跨角色handoff','fictional 24公司；operator/reviewer/admin；隔離隊列','從UI建立offer至research、review、list、assign、contact、draft、approval、export、manual outcome後刷新','每角色看到持久化正確scope／版本；只export不send；delivery403','本次正式membership阻擋；歷史fictional journey不算本次完成','blocked','blocked','E01'),
]
for id,f,p,s,pre,steps,expected,actual,result,state,evidence in new:
    cases.append(dict(case_id=id,finding_ids=f,priority=p,scenario=s,preconditions=pre,steps=steps,expected=expected,actual=actual,result=result,evidence_state=state,evidence_ids=evidence,historical_status='NEW_2026-10-03',environment='正式read-only' if id in ['U13','U16'] else '隔離fixture／local',cleanup='不使用正式客戶資料；重現腳本無外部副作用',owner_role='待分派'))

neon=list(csv.DictReader((root/'prior-neon-cases.csv').open(encoding='utf-8')))
for r in neon:
    cases.append(dict(case_id=r['case_id'],finding_ids='F20',priority='P1',scenario=r['scenario'],preconditions=r['precondition'],steps=r['steps'],expected=r['expected'],actual='Neon Auth未實作；本次未執行',result='not-tested',evidence_state='not-tested',evidence_ids='E09',historical_status=r['status'],environment='隔離Neon／preview；依'+r['task'],cleanup='依migration rehearsal runbook保留mapping／audit；不自動刪資料',owner_role='Identity／QA'))
assert len(cases)==98 and len({r['case_id'] for r in cases})==98
csv_write('BuyerOS_Test_Cases_2026-10-03.csv',list(cases[0]),cases)

ops=[]
def op(section,route,role,action,pre,expected,result,actual,case,evidence='E03'):
    ops.append(dict(operation_id=f'OP{len(ops)+1:02}',section=section,route=route,role=role,control_action=action,precondition=pre,expected=expected,actual=actual,case_ids=case,evidence_ids=evidence,result=result,source_review='reviewed',scope='代表性操作；不是所有DOM按鈕'))
op('公開入口','/','visitor','開首頁','none','顯示清楚登入入口','pass','FIMMICK BuyerOS＋Sign in可見','U01','E07')
op('登入','/auth/callback','existing user','Sign in／SSO callback','既有登入session','完成登入返回指定workspace','pass','見Sign out與Live workspace；已登入不等於已授權','U01','E01;E07')
op('登入','/auth/callback','existing user','初始化訊息','configured auth','先initializing，無錯誤config alert','fail','短暫誤報未設定','U13','E03;E07')
op('存取','/app?workspace=…','existing user','首次載入workspaces','authenticated','成功取得資料或正確權限回應','fail','GET workspaces500 OperationalError','U16','E07')
op('存取','/app?workspace=…','existing user','Retry loading workspaces','暫時錯誤','重讀並顯示真實結果','pass','錯誤變ready-empty；無membership','U16','E01;E07')
op('存取','/app?workspace=…','member','選指定workspace','active membership','可進八模組','blocked','當前身份未有membership','U01','E01')
op('存取','/app','no membership','空狀態恢復入口','no membership','可核對存取／聯絡admin','fail','只有文字、無對應控制項','U02','E01')
op('存取','/app','no membership','Language','no membership','可選en／zh-HK','fail','disabled','U03','E01')

groups=[
 ('Overview','/app',[('overview內容','member','U09'),('工作佇列統計及入口','member','U15'),('usage期間','operator/reviewer','P01'),('ICP精確批准','reviewer','WF02')]),
 ('Offer','/app/discover/new; /app/discover/edit',[('建立四步offer','operator','U09;WF01'),('編輯及衝突','operator','WF02'),('文件／摘錄採納','operator','WF01'),('部分保存／重試','operator','WF01')]),
 ('Buyers','/app/discover',[('搜尋／篩選／分頁','member','B14'),('snapshot跨頁選取','reviewer','B01;B14'),('證據及notes詳情','operator/reviewer','A05'),('review及next','reviewer','U09'),('list／saved filter','operator','U09'),('bulk owner確認','operator','B02;B03'),('bulk取消／失敗重試','operator','B08;B09'),('contact quote／confirm','operator','A08')]),
 ('Results','/app/results',[('usage與cost denominator','operator/reviewer','P01'),('記錄manual outcome','operator/reviewer','U09'),('append correction','operator/reviewer','U09'),('queue filter一致','member','U15')]),
 ('Research runs','/app/runs',[('Start research／lost202','operator','B05;B06'),('status／事件／backfill','member','U09'),('Stop new work','operator','R03'),('safe retry／unknown','operator/admin','R03;S03')]),
 ('Drafts','/app/outreach',[('reviewed sender','reviewer','U09'),('grounded addressed生成','operator','A02;U09'),('人工編輯／來源覆核','operator/reviewer','D01;D02'),('精確approval','reviewer','D01;D03'),('approved export／delivery gate','operator/reviewer','U09')]),
 ('Settings','/app/settings',[('locale／market／budget／policy','member/admin','U09'),('member搜尋／第101位','admin','U06;U07'),('roles／active／last admin','admin','U08;S06')]),
 ('Operations','/app/operations',[('capabilities／readiness','member/admin','R02'),('job list／failed filter','member/admin','U15'),('job lookup／全部results','member/admin','B10;B11'),('audit pagination','admin','U09')]),
]
for section,route,actions in groups:
    for action,role,case in actions:
        op(section,route,role,action,'指定workspace active membership＋所需project／測試資料','依對應案例完成並讀回持久化結果','blocked','正式UI受workspace gate阻擋；本次僅source review',case,'E01;E03')
assert len(ops)==44
csv_write('BuyerOS_Operation_Inventory_2026-10-03.csv',list(ops[0]),ops)

tasks=[]
def task(id,f,p,title,scope,deps,owner,effort,accept,cases,evidence,rollback,blocker='',status='待開始'):
    tasks.append(dict(task_id=id,finding_ids=f,priority=p,title=title,change_scope=scope,dependencies=deps,owner_role=owner,effort_estimate=effort+'人日（粗估，非承諾）',status=status,acceptance_criteria=accept,user_case_ids=cases,evidence_ids=evidence,verification_environment='local／owned PG／isolated preview；正式切換另有授權',rollback=rollback,blocker=blocker))
task('N00','F20','P1','Neon框架相容及精確契約spike','Vinext/Nitro兩種輸出；auth session／JWT／same-origin proxy；pin SDK','','Identity＋Frontend','1–2','登入→session→token→FastAPI→logout在兩種build實測；明列issuer/audience/JWKS與cookie；失敗不能只改env','NA01;NA02','E03;E09','刪隔離spike分支；舊auth不變')
task('N01','F20','P1','隔離Auth設定與production差異','Neon Auth環境、trusted domains、cookie secret、OAuth／email','N00','Platform','1','preview與production分離；secret不在client/log；只設定已選登入方法；用戶資料不跨branch洩漏','NA02;NA03;NA04;NA05','E09','回復設定版本；保留migration evidence','實際建立服務／發驗證信／付費需對應授權')
task('N02','F01;F20','P1','身份映射保持User與membership','新增auth identity關聯；workspace discovery及load_membership用shared canonical resolver','N00','Backend／Identity','2–3','同一已核實使用者保留users.id；roles、ownership、approvals、audit actor均不重建；同email不自動link；唯一鍵與對帳可追查','NA06;NA07;NA08;NA09;NA10','E03;E09','保留additive mapping；關閉新provider，不還原整個DB')
task('N03','F20','P1','Neon JWT驗證及有限雙issuer','verifier／JWKS cache：RSA Auth0與Ed25519 Neon分開allowlist','N00;N02','Backend／Security','2','錯alg／iss／aud／kid／過期拒絕；rotation與cache outage測試；不使用Neon role決定workspace權限','NA11;NA12;NA13;NA14;NA15','E03;E09','provider flag切回已授權舊路徑；撤回新issuer接受')
task('N04','F02;F15;F20','P1','Neon UI及session恢復','登入／callback／session provider／token renewal／zh-HK','N01;N03;Q01','Frontend','2–3','刷新／新分頁／deep link／15分鐘JWT換取／logout撤回／disabled member皆有清楚結果；無token localStorage','NA04;NA05;NA16;NA17;NA18;NA19;U14','E03;E09','旗標回復前一UI；不丟membership／歷史資料')
task('N05','F20','P1','身份及八模組回歸','CSRF／cross-tenant／revocation／role change／full staff flow','N02;N03;N04','QA＋Security','2','必要owned DB／UI cases零skip；所有角色與8模組完整journey；worker HMAC未受影響','NA20;NA21;NA22;NA23;NA24;NA25;NA26;NA27','E09','阻止cutover；不減斷言來通過')
task('N06','F01;F20','P1','帳戶轉移演練與對帳','身份prove-and-link；受控OAuth reauth／password reset；異常清單','N05','Identity＋Admin','1–2','mapping數／membership數／角色／owner／歷史actor逐項一致；duplicate／unmapped拒絕自動提權；無密碼可匯出假設','NA06;NA07;NA08;NA28','E09','關閉新mapping使用；保留可審計舊identity')
task('N07','F20','P1','受控Neon切換及Auth0退役','有限雙auth→Neon only→舊secret／callback清理','N06;Q11','Release owner','1–2','切換前後8模組驗收及觀察；未知寫入不重播；rollback不restore業務DB；到期後Auth0 token拒絕','NA28;NA29;NA30','E02;E09','有期限回舊auth；新Neon會員須明確恢復策略','production授權、可用會員、rollback rehearsal')
task('Q01','F01;F02;F15','P1','修復auth狀態、空存取與語言','workspace-picker／callback／provider；UI初始化與config錯誤分離','','Frontend＋Admin','1–2','無membership能切繁中及重新核對；配置正確無false alert；精確issuer/sub由admin核對，無email自動升權','U01;U02;U03;U13','E01;E03;E07','revert UI；保留授權fail-closed','正式會員核對需管理員；UI可先做')
task('Q02','F03;F04','P1','成員分頁與可辨識身份','settings／memberships API；另提供operator可用的最小eligible-assignee lookup','N02','Frontend＋Backend','2–3','250成員全部可達；搜尋第101位；同名／尾碼碰撞可辨；last-admin競態與逐人原因通過','U06;U07;U08;S06','E03','revert分頁UI／投影欄；不rollback已審計角色變更')
task('Q03','F05','P1','Operations契約與結果分頁','generated AsyncJob／BulkItemResult.id；remove handwritten Job；detail paging','','Frontend','1','21及101結果均可讀完整ID；真實payload render無undefined key；cross-workspace job拒絕','B10;B11','E03','revert consumer；server contract不變')
task('Q04','F08','P1','研究建立保留操作意圖','run-progress／ActionIntent；建立與查詢recovery','','Frontend＋Backend','1–2','commit後丟202再按Retry：只一run／outbox／economic intent；body或scope改變才新key；doubleclick共享pending','B05;B06','E03;E05','暫停新research建立；保留已有run／holds／outbox')
task('Q05','F06','P1','分派同事與精確批量確認','eligible owner picker；scope/selection/owner/reason fingerprint','Q02','Frontend＋Backend','1–2','選5後加1清confirm；可指定同事／自己／無owner；preview後owner失效由server拒絕；逐列版本正確','B02;B03;B04;B07;B16','E03','關閉新版bulk入口；不自動撤銷已完成分派')
task('Q06','F07','P1','有界job summary輪詢','summary／paged results分離；abort／single-flight／visibility／backoff','Q03','Frontend＋Backend','1–2','running1000results/RTT2.5s下每view最多一個progress request；hidden停止；未開結果不遍歷歷史頁；429尊重Retry-After','B12;B13;P04','E03','回退到手動Refresh，不恢復高頻全結果輪詢')
task('Q07','F09','P2','草稿控制項與模板承諾一致','移除無效tone/objective或實作有引用約束的免費style/CTA','','Frontend＋Backend','1','兩組purpose/tone的行為與UI說明一致；zh-HK引用原語言有說明；不新增付費模型','A02;A07','E06','恢復固定模板並明確標示限制')
task('Q08','F11','P2','10k分段維護manifest','server frozen IDs/versions；chunks／結果／failed-only retry','Q05;Q06','Backend＋Frontend','3–5','1000/1001限制不誤選；10k逐段總數一致，50衝突不改寫；重試不重做已成功列；中斷可恢復','B01;B08;B09;B14;B15','E03','停止新manifest；已commit結果保留並可查；不盲目Undo')
task('Q09','F14;F04','P2','日常任務優先的八模組UX','compact scope；buyer主區與sticky bulk bar；human labels；shared dictionaries','Q01;Q02;Q14','Product designer＋Frontend','3–5','3–5員工完成五項任務≥90%；錯scope0；390px／200%／鍵盤／screen reader；記前後時間與失誤','U09;U10;U11;U12','E03','按模組feature flag回退；資料契約不變')
task('Q10','F12','P1','效能與真實準確率驗收','隔離load／goldset／provider canary／可重跑結果','Q06;Q08;Q12;Q13','QA／Data／SRE','3–5','按報告先定門檻；分層200公司holdout及3次重跑；輸出p95/p99與CI；不把fixture當liveaccuracy','A03;A04;A05;A06;A08;P01;P02;P03;P04;P05;P06;P07;P08;P10','E04;E06;E08','停壓測／canary；保留證據與holds','真provider、隔離資料及成本上限未就緒')
task('Q11','F10;F13','P1','單一現況與分能力release gate','CURRENT_STATUS／operation ledger／readiness／owner與時間；記code/deployment/DB/jobs/provider/UAT','','Release owner＋SRE','1–2','main/live明確；每個deployed驗收附case；schema/role/selector讀回；restore及告警有責任人；未驗不得markcomplete','R01;R02;R03;R04;R05;R06','E02;E03','只回復文件與UI；activation rollback依實際service runbook','正式DB／worker readback與外部recovery證據仍缺')
task('Q12','F16','P1','人工改稿的来源覆核與重新審批','revision-bound claims mapping／human grounding review endpoint與UI；current facts/policy再驗','','Backend＋Frontend＋Reviewer','2–4','改正文→保存→逐句來源覆核→exact review→approve→export完成；新revision撤舊approval；無引用／跨company／stale evidence拒絕；不直接設grounded','D01;D03;U09','E03;E06','關閉新覆核入口，保留needs_review與修訂；不自動批准')
task('Q13','F18','P1','Workspace membership discovery去全域掃描','canonical identity lookup；受限制的DB端membership discovery＋pagination','N02','Backend／DB','2–3','ownedPG證明querycount不隨無關workspace線性增长；頁面完整；RLS／active／revocation不退化；禁止BYPASSRLS捷徑','P09;P10;S06','E03;E06','切回舊read策略；保留新schema兼容；不撤銷member資料')
task('Q14','F17','P2','工作數與列表使用相同scope','overview／operations query builder；project_id與workspace視圖切換','','Frontend','1','A0/B5 fixture統計與點入列表一致；admin全workspace明確標籤；非admin仍actor-bound','U15','E03','回復UI；server授權不改')
task('Q15','F19','P1','草稿dirty guard與明確保存選擇','Refresh draft／job／open共用Save/Discard/Cancel','','Frontend','1','Cancel不改local subject/body/language；Save成功再換；Discard明確；412保留local供比較','D02','E03','revert guard UI但保留local暫存；不得清除未保存內容')
task('Q16','F21','P1','調查workspace500根因','精確requestID／時間的DB、pool、schema/role、timeout資訊；唯讀','','SRE／Backend','0.5–1','以同時間診斷確定或明確排除原因；保留最小重現與錯誤分類；不能只寫Neon冷啟動','U16','E07','純調查無產品rollback','目前日志只有OperationalError，缺底層診斷',status='受阻')
task('Q17','F21','P1','按已確認原因修復workspace500','Q16結論所指最小連線／查詢／環境修復；有上限GET retry','Q16','Backend／SRE','待Q16後估','原觸發條件下讀取成功；失效role/schema仍清楚報錯；不加無限retry；無盲目重播write','U16;P01;P02','E07','依具體變更revert設定／程式；不restore業務DB','依賴Q16根因；不預設加pool',status='受阻')
# Keep original Neon case-to-task assignments rather than reinterpreting IDs.
for row in tasks:
    if row['task_id'].startswith('N'):
        ids=[r['case_id'] for r in neon if r['task']==row['task_id']]
        if row['task_id']=='N04':ids.append('U14')
        row['user_case_ids']=';'.join(ids)
csv_write('BuyerOS_Implementation_Tasks_2026-10-03.csv',list(tasks[0]),tasks)

# Snapshot short, reproducible source evidence with exact commit/per-file hash.
sources={
 'features/live/workspace-picker.tsx':[(65,72),(174,187),(190,209)],
 'features/live/settings.tsx':[(23,30),(57,76)],
 'features/live/operations.tsx':[(1,12),(29,50),(77,89),(119,129)],
 'features/live/bulk-actions.tsx':[(31,61),(73,99)],
 'features/live/buyer-results.tsx':[(149,181)],
 'features/live/run-progress.tsx':[(89,108)],
 'features/live/overview.tsx':[(61,90)],
 'features/live/drafts.tsx':[(153,162),(174,181),(246,256),(277,296)],
 'features/providers/workspace-session.tsx':[(14,27)],
 'app/auth/callback/page.tsx':[(1,29)],
 'app/layout.tsx':[(25,38)],
 'services/api/buyeros_api/services/bulk_service.py':[(175,189)],
 'services/api/buyeros_api/services/draft_service.py':[(343,375)],
 'services/api/buyeros_api/services/approval_service.py':[(120,136)],
 'services/api/buyeros_api/api/routes/workspaces.py':[(20,56)],
 'services/api/buyeros_api/api/routes/jobs.py':[(17,48)],
 'services/api/buyeros_api/api/verifier.py':[(1,37)],
 'services/api/buyeros_api/providers/base.py':[(12,20),(96,105)],
 'services/api/buyeros_api/api/routes/drafts.py':[(275,283)],
 'services/api/buyeros_api/execution/handlers/draft_generate.py':[(27,66)],
 'docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md':[(1,40)],
}
out=['# E03 Source evidence',f'Baseline: {SHA}. Public source; no environment values collected.','Each excerpt is frozen to this commit; current line numbers must be rechecked after changes.']
for path,ranges in sources.items():
    data=(repo/path).read_bytes(); lines=data.decode().splitlines()
    out += [f'\n## {path}',f'SHA256: `{hashlib.sha256(data).hexdigest()}`',f'[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/{SHA}/{path})']
    for a,b in ranges:
        out+=['```text']+[f'{i}: {lines[i-1]}' for i in range(a,min(b,len(lines))+1)]+['```']
(ev/'E03-source-evidence.md').write_text('\n'.join(out),encoding='utf-8')

(ev/'E07-live-observations.md').write_text('''# E07 Live observations — 2026-10-03 HK

- Public root renders FIMMICK BuyerOS, Sign in to access your workspaces, Sign in.
- Exact workspace URL from user opened, then Sign in activated. Existing SSO completed; no credentials inspected or retained.
- Initial callback briefly rendered “Live sign-in is not configured”. Subsequent observation of the same tab showed signed-in Live workspace and Sign out. This is a transient initialization message, not proof of missing config.
- First workspace read showed “Service temporarily unavailable. Retry after checking the status.” Request ID: 1d123054-2633-40b7-8e07-b6aed83dad98.
- One Retry loading workspaces action: loading then “No workspace membership. Ask an administrator for access.” and “Workspace not found (404)”.
- Language disabled; Overview navigation enabled; Offer, Buyers, Results, Research runs, Drafts, Settings, Operations disabled. E01 screenshot is this final state.
- No actual business action, membership update, email, paid provider, or deployment was performed.
- Browser extension metadata errors were excluded from website findings.

## Correlated server evidence

Vercel plugin get_runtime_logs; production dpl_7A95afQdDSUsaPRw2RnPFouQ1hEp; query exact request ID; range 2026-10-02T13:51:18.868Z to 2026-10-02T19:51:18.868Z; limit5. One matching entry:

```text
2026-10-02 19:40:34 UTC GET /v1/workspaces 500 [info/serverless]
deployment=dpl_7A95afQdDSUsaPRw2RnPFouQ1hEp branch=main cache=BYPASS
Auth0 public JWKS fetch: HTTP/1.1 200 OK
unexpected_api_error request_id=1d123054-2633-40b7-8e07-b6aed83dad98 type=OperationalError
```

Underlying OperationalError detail, overall error rate, and DB schema were not retrieved. Do not infer cold-start, authentication rejection, sustained outage, or a membership defect from this single request. Callback authorization code/query was intentionally not retained.
''',encoding='utf-8')
bench=repo/'artifacts/cloudflare/CF07-read-benchmark.json'
if bench.exists():
    (ev/'E08-historical-CF07-read-benchmark.json').write_bytes(bench.read_bytes())
(ev/'E08-method-boundary.md').write_text('''# Historical benchmark boundary
The adjacent CF07 benchmark is copied unchanged from audited public repository a78859f.
It is historical local Win/PG16 in-process ASGI evidence, not this audit's production timing.
Its source-bound 10k-buyers/100-workspaces fixture reported sequential p95 58.603ms,
10-distinct-actors p95 258.649ms, 11 queries/request and 50,721 bytes. Consult JSON for exact source and method.
It measures buyer reads, not the workspace-list fanout exercised by E06.
No new production LCP, INP, CLS, p95, p99, contact accuracy or real-provider benchmark was run.
''',encoding='utf-8')
(ev/'E09-neon-doc-check.md').write_text('''# Neon documentation check — 2026-10-03 HK
Retrieved using Neon documentation plugin after official index discovery. No Neon resource mutated.

- https://neon.com/docs/auth/guides/plugins/jwt : Managed Better Auth browser sessions use HTTP-only cookies; authClient.token() provides external-service JWT. EdDSA/Ed25519, 15-minute token. iss/aud use auth URL origin; JWKS uses full auth base path. Custom JWT claims currently unsupported. Cross-origin cookie limitations require care.
- https://neon.com/docs/auth/reference/nextjs-server : createNeonAuth and handler() support standard Next.js server integration; cookie secret is server-only. This is not proof of Vinext/Nitro compatibility.
- https://neon.com/docs/auth/production-checklist : Verify trusted domains, production OAuth/email setup, application name and chosen verification method. Preview and production settings remain separate.

BuyerOS design inference: retain canonical User identity and workspace roles in its own DB; add verified issuer/subject mapping. Do not auto-link by email or grant workspace privileges from provider role claims. Recheck actual SDK and docs before implementation.
''',encoding='utf-8')

opc=Counter(r['result'] for r in ops); cc=Counter(r['result'] for r in cases)
mdpath=root/'BuyerOS_Audit_2026-10-03_zhHK.md'
md=mdpath.read_text()
md=md.replace('{{OP_COVERAGE}}',f'本次正式執行 {opc["pass"]+opc["fail"]}／44 項：{opc["pass"]} pass、{opc["fail"]} fail；其餘 {opc["blocked"]} blocked。失敗集中在入口／恢復／語言；blocked 不納入通過數。')
md=md.replace('{{CASE_COVERAGE}}',f'按本次證據：{cc["pass"]} pass、{cc["fail"]} fail、{cc["blocked"]} blocked、{cc["not-tested"]} not-tested。')
mdpath.write_text(md,encoding='utf-8')

plan=['# BuyerOS — Codex GPT-6 Sol 執行計劃（2026-10-03 更新）',
      '', '本計劃依本次八模組稽核與之前Neon Auth計劃重寫。基線 main／production為 `'+SHA+'`。完整結論及證據在同包稽核報告；21 findings、25 tasks。',
      '', '**產品修復尚未開始。** 本次稽核沒有產品commit、正式membership變更、Neon配置、provider啟用、寄信或部署。',
      '', '## 第一批',
      '先做Q01的UI、Q03、Q04、Q15；可先在本地／隔離fixture完成。N00先做相容性spike，Q12獨立實作來源覆核。Q16以唯讀資料調查workspace500；未有根因前不猜測Q17修法。',
      '', '## 不可破壞的條件',
      '保留canonical users.id、membership、歷史actor及RLS；不依email自動link；Neon provider role不代表workspace角色；寫入保持If-Match與idempotency；unknown provider結果保留hold並reconcile；delivery維持403。',
      'Auth0→Neon須按N00–N07分步。先驗證Vinext／Nitro相容，再加入身份映射與EdDSA verifier、session恢復及有限雙issuer切換。不可只改issuer環境變數。',
      '舊N00–N07及Q01–Q11 ID維持；新增Q12–Q17。估算為人日，不是Codex執行時間承諾。',
      '', '## 任務']
for t in tasks:
    plan += ['',f'### {t["task_id"]} · {t["title"]}',
             f'- 問題／優先：{t["finding_ids"]}；{t["priority"]}。狀態：{t["status"]}。',
             f'- 修改範圍：{t["change_scope"]}。',
             f'- 依賴：{t["dependencies"] or "無"}。責任：{t["owner_role"]}。估算：{t["effort_estimate"]}。',
             f'- 驗收：{t["acceptance_criteria"]}。',
             f'- 案例：{t["user_case_ids"]}。證據：{t["evidence_ids"]}。',
             f'- 回退：{t["rollback"]}。',
             f'- 受阻：{t["blocker"] or "沒有已知阻擋；按repo與環境核對"}。']
plan += ['', '## 執行提示',md.split('## 8. Codex GPT-6 Sol 第一批執行提示')[1].split('## 9.')[0],
         '', '## 完成定義',
         '每個任務須有commit SHA、相關測試命令、pass/fail/skip、案例結果及artifact。程式碼存在或CI success不等於正式UAT；缺DB／角色／provider時記受阻，其他獨立工作繼續。所有正式切換需具體授權與可review的readback／rollback方案。']
(root/'BuyerOS_Codex_GPT6Sol_Plan_2026-10-03_zhHK.md').write_text('\n'.join(plan),encoding='utf-8')

(root/'README.md').write_text('''# BuyerOS audit pack — 2026-10-03 HK

Read the zhHK HTML/Markdown report first. The HTML is self-contained, including
the live screenshot. CSV files are UTF-8 with BOM. Task and case IDs preserve
the previous reports; historical outcomes are not current pass results.

## Reproduce read-only probes

Clone YNWAforever/BuyerOS and check out a78859fe474f5722be3755b10e2586436b53bf97.
Install services/api locked dependencies in an isolated environment. Then run:

    <repo>/services/api/.venv/bin/python evidence/reproduce_audit.py <repo>

This uses fictional data and a fake SQL connection. It counts actual route
execute calls but does not benchmark PostgreSQL or production latency.

## Existing checks rerun during this audit

From services/api, with BUYEROS_TEST_DATABASE_URL and DATABASE_URL removed:

    python -m pytest tests/test_api_app.py tests/test_api_auth.py tests/test_jwks_cache.py tests/test_safe_fetch.py tests/test_provider_contracts.py tests/test_snapshot.py tests/test_approval.py tests/test_settlement.py tests/test_fit_eval.py -q

61 pass / 1 DB skip. The sandbox TestClient timeout is retained separately;
the unchanged bounded rerun passed in 1.75 seconds. No DB was provisioned.

From the repository root, with TypeScript 5.9.3 available:

    node tests/domain-checks.mjs
    node tests/live-adapter-checks.mjs
    node tests/live-auth-checks.mjs
    node tests/live-runs-checks.mjs
    node --experimental-strip-types tests/vercel-services.test.mjs
    node --experimental-strip-types tests/worker-gateway.test.mjs

103 checks total. Original outer --test file summary was 2 files; individual
proxy/gateway runs prove 5+1 checks. Do not add both counts.

## Evidence limits

No credentials, callback authorization code, provider calls, production
business data exports, or full production DB copies are included.
The source excerpts are frozen to the stated SHA. E08 is historical.
SHA256SUMS.json covers the packaged artifacts; the archive itself is excluded.
The builder expects the repo next to this pack as buyeros-audit.
''',encoding='utf-8')

# Minimal deterministic Markdown renderer for this authored report. No scripts,
# remote resources, or JS dependencies; embeds the single local screenshot.
def inline(s):
    s=html.escape(s)
    s=re.sub(r'`([^`]+)`',r'<code>\1</code>',s)
    s=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',s)
    s=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',r'<a href="\2">\1</a>',s)
    return s

lines=md.splitlines(); fragments=[]; i=0
while i<len(lines):
    line=lines[i]
    if line.startswith('```'):
        code=[]; i+=1
        while i<len(lines) and not lines[i].startswith('```'):
            code.append(lines[i]);i+=1
        fragments.append('<pre><code>'+html.escape('\n'.join(code))+'</code></pre>')
    elif re.match(r'^#{1,6} ',line):
        n=len(line)-len(line.lstrip('#'))
        fragments.append(f'<h{n}>'+inline(line[n+1:])+f'</h{n}>')
    elif line.startswith('!['):
        m=re.match(r'!\[([^\]]+)\]\(([^)]+)\)',line)
        image=(root/m[2]).read_bytes()
        fragments.append('<figure><img alt="'+html.escape(m[1])+'" src="data:image/jpeg;base64,'+base64.b64encode(image).decode()+'"><figcaption>'+html.escape(m[1])+'</figcaption></figure>')
    elif line.startswith('|'):
        table=[]
        while i<len(lines) and lines[i].startswith('|'):
            cells=[x.strip() for x in lines[i].strip('|').split('|')]
            if not all(re.fullmatch(r':?-+:?',c) for c in cells):table.append(cells)
            i+=1
        fragments.append('<div class="table-scroll"><table><thead><tr>'+''.join('<th>'+inline(x)+'</th>' for x in table[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(x)+'</td>' for x in row)+'</tr>' for row in table[1:])+'</tbody></table></div>')
        continue
    elif line:
        fragments.append('<p>'+inline(line)+'</p>')
    i+=1
css='''body{margin:0;background:#f1f5f9;color:#172033;font:16px/1.75 system-ui,-apple-system,"Noto Sans TC",sans-serif}main{max-width:1180px;margin:0 auto;background:white;padding:38px 46px 80px}h1{font-size:32px;color:#122d42}h2{margin-top:46px;padding-top:18px;border-top:2px solid #087c83;font-size:25px}h3{margin-top:30px;color:#164e63;font-size:20px}a{color:#075985}code{font-family:ui-monospace,monospace;font-size:.88em;overflow-wrap:anywhere}pre{background:#102434;color:#e0f2fe;padding:24px;white-space:pre-wrap;border-radius:9px}table{border-collapse:collapse;min-width:820px;width:100%;font-size:14px}th,td{padding:12px;border:1px solid #d8e2ec;vertical-align:top}th{background:#e7f2f3;text-align:left}tr:nth-child(even){background:#f8fafc}.table-scroll{overflow-x:auto;margin:24px 0}img{max-width:100%;border:1px solid #d8e2ec;border-radius:8px}figure{margin:28px 0}figcaption{font-size:13px;color:#52677d}@media(max-width:650px){main{padding:24px 18px}h1{font-size:26px}h2{font-size:23px}}@media print{body{background:white}main{max-width:none;padding:0}table{min-width:0;font-size:10px}h2,h3{break-after:avoid}pre{font-size:10px}}'''
(root/'BuyerOS_Audit_2026-10-03_zhHK.html').write_text('<!doctype html><html lang="zh-HK"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>BuyerOS 八模組稽核 · 2026-10-03</title><style>'+css+'</style><main>'+''.join(fragments)+'</main></html>',encoding='utf-8')

# Validate traceability and dependencies before writing the evidence pack.
caseids={r['case_id'] for r in cases}; taskids={r['task_id'] for r in tasks}
for row in tasks:
    for ref in row['user_case_ids'].split(';'):
        assert ref in caseids,(row['task_id'],ref)
    for ref in filter(None,row['dependencies'].split(';')):
        assert ref in taskids,(row['task_id'],ref)
seen=set(); visiting=set()
def visit(id):
    assert id not in visiting,('cyclic dependency',id)
    if id in seen:return
    visiting.add(id)
    row=next(t for t in tasks if t['task_id']==id)
    for dep in filter(None,row['dependencies'].split(';')):visit(dep)
    visiting.remove(id);seen.add(id)
for id in taskids:visit(id)
for row in ops:
    assert all(ref in caseids for ref in row['case_ids'].split(';'))
assert '{{' not in md

summary={'repo_sha':SHA,'operations':dict(opc),'cases':dict(cc),'tasks':len(tasks),'task_statuses':dict(Counter(t['status'] for t in tasks)),'source_files_excerpted':len(sources),'python':{'passed':61,'skipped':1},'javascript_checks_passed':103,'production_business_modules_completed':0,'production_business_modules_requested':8}
(root/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
deliverables=[root/'BuyerOS_Audit_2026-10-03_zhHK.md',root/'BuyerOS_Audit_2026-10-03_zhHK.html',root/'BuyerOS_Codex_GPT6Sol_Plan_2026-10-03_zhHK.md',root/'BuyerOS_Test_Cases_2026-10-03.csv',root/'BuyerOS_Operation_Inventory_2026-10-03.csv',root/'BuyerOS_Implementation_Tasks_2026-10-03.csv']
include=deliverables+sorted(p for p in ev.iterdir() if p.is_file() and p.stat().st_size)+[root/'validation.json',root/'README.md',root/'prior-cases.csv',root/'prior-neon-cases.csv',Path(__file__)]
manifest=[{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in include]
(root/'SHA256SUMS.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
with zipfile.ZipFile(root/'BuyerOS_Audit_2026-10-03_Evidence.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for p in include+[root/'SHA256SUMS.json']:
        archive.write(p,p.relative_to(root))
print(json.dumps(summary,ensure_ascii=False,indent=2))
