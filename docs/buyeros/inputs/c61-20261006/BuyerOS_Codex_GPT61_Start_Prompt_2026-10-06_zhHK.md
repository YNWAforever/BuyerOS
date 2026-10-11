# 給 Codex GPT‑6.1 Sol 的開始指令

請以此包的 `docs/superpowers/plans/2026-10-06-buyeros-gpt61-fixes.md` 為總計劃，依四份子計劃執行 BuyerOS 修復。先閱讀隨包原audit、114-case追蹤及task tracker，不重新猜測產品現況。

目標：整合已有Q修復；改善workspace查詢/每日及批量維護；以Neon Auth取代Auth0並保留canonical User UUID；完成真實research及approved export；站內send按獨立C61-20/30交付。

先執行 C61-01，再 C61-02。確認最新HEAD、工作樹、AGENTS.md及原證據與目前branch差異；不要覆蓋既有修復或使用者修改。以原生 `superpowers:executing-plans` 工作，不自動啟動subagents。

繼續依dependency完成所有已授權且可開始的本地實作、測試及可審閱PR。每個任務先focused失敗測試（已存在正確修復直接驗收），最小修復、驗證、獨立commit、更新狀態。外部帳戶/供應商/真人UAT阻塞只標該gate blocked；繼續其他可做工作。

約束：不按email自動link、不改歷史UUID/FK、不放寬RLS/JWT信任、不把fixture帶入production、不移除503/403假裝功能完成、不盲重送accepted/unknown intent、不丟dirty draft、不重播bulk成功列。歷史workspace500先C61-04取根因，再C61-05修復，不能猜pool/cold start。

原114個case欄位/結果保留，所有本次新結果寫execution欄位；新高風險案例為C61T-01–16。required DB suite零skip；Playwright/CI必須驗discovery，空跑不得pass。fixture、built preview、real provider、production readback、human UAT分開報告。

先把程式、tests、migration/rollback及部署payload做到可審閱；只有已有授權覆蓋才發布、改正式auth、花費外部額度或對外寄送。未涵蓋的外部操作待具體產物完成後再提出所需授權；這不阻礙已授權本地工作。

每輪交接請提供：task IDs、source SHA、檔案變更、實際測試與artifact、剩餘blockers、下一個可開始task及rollback點。不可因PR merge/fixture pass就聲稱live已修。最終區分Release A（research+approved export）、Neon-only和native send是否各已驗收。
