# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-template-copy.spec.ts >> A07 zh-HK mobile template keeps original English citations through exact approval and authorized export
- Location: tests\e2e\audit-template-copy.spec.ts:37:1

# Error details

```
Test timeout of 60000ms exceeded.
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
    - region "草稿" [ref=f1e31]:
      - heading "草稿" [level=2] [ref=f1e32]
      - paragraph [ref=f1e33]: 準備有證據草稿；發送功能已停用。
      - status [ref=f1e34]: 已要求審核此精確版本。
      - region "寄件人身份" [ref=f1e35]:
        - heading "寄件人身份" [level=3] [ref=f1e36]
        - paragraph [ref=f1e37]: "已審核寄件人: Fixture Alex · Fictional Seller · alex@example.test · sender:ea000000-0000-4000-8000-000000000001:1"
      - region "準備有證據草稿" [ref=f1e38]:
        - heading "準備有證據草稿" [level=3] [ref=f1e39]
        - paragraph [ref=f1e40]:
          - strong [ref=f1e41]: 免費固定模板
        - paragraph [ref=f1e42]: 模板語言只改變固定標題、開場及結尾；產品事實與來源引用保留原語言，不會自動翻譯。
        - paragraph [ref=f1e43]: 產生後請人手修改草稿；更改須重新審核證據才可批准。
        - paragraph [ref=f1e44]: Buyer Fixture 01 · 1 · 已接納
        - group "已批准的產品事實" [ref=f1e45]:
          - generic [ref=f1e47]:
            - checkbox "Fictional industrial sensors" [checked] [ref=f1e48]
            - text: Fictional industrial sensors
        - group "支持買家的證據" [ref=f1e49]:
          - generic [ref=f1e51]:
            - checkbox "Fixture public catalog lists industrial sensors. · v1" [checked] [ref=f1e52]
            - text: Fixture public catalog lists industrial sensors. · v1
        - paragraph [ref=f1e53]: 首次聯絡
        - generic [ref=f1e54]:
          - text: 收件人（可選）
          - combobox "收件人（可選）" [ref=f1e55]:
            - option "不指定收件人 — 未指定收件人的草稿"
            - option "recipient@fixture.example.test · v1" [selected]
        - generic [ref=f1e56]:
          - generic [ref=f1e57]:
            - text: 內部工作目的，不會改變模板正文
            - textbox "內部工作目的，不會改變模板正文" [ref=f1e58]: 內部跟進工作
          - generic [ref=f1e59]:
            - text: 模板語言
            - combobox "模板語言" [ref=f1e60]:
              - option "English"
              - option "繁體中文" [selected]
        - button "產生已指定收件人的草稿" [ref=f1e61] [cursor=pointer]
      - status [ref=f1e62]:
        - heading "工作狀態" [level=3] [ref=f1e63]
        - paragraph [ref=f1e64]: adbddfe5-e569-4dac-86ca-8bc726c21d02 · completed
        - button "重新整理工作" [ref=f1e65] [cursor=pointer]
      - region "草稿列表" [ref=f1e66]:
        - heading "草稿列表" [level=3] [ref=f1e67]
        - paragraph [ref=f1e68]: 1–4 / 4
        - generic [ref=f1e69]:
          - generic [ref=f1e70]: "Introduction: Fictional industrial sensors · 草稿 · v1"
          - button "開啟草稿" [ref=f1e71] [cursor=pointer]
        - generic [ref=f1e72]:
          - generic [ref=f1e73]: "Introduction: Fictional industrial sensors · 草稿 · v1"
          - button "開啟草稿" [ref=f1e74] [cursor=pointer]
        - generic [ref=f1e75]:
          - generic [ref=f1e76]: Q07 manual subject · 草稿 · v2
          - button "開啟草稿" [ref=f1e77] [cursor=pointer]
        - generic [ref=f1e78]:
          - generic [ref=f1e79]: 業務簡介：Fictional industrial sensors · 待審核 · v2
          - button "開啟草稿" [ref=f1e80] [cursor=pointer]
        - generic [ref=f1e81]:
          - button "上一頁" [disabled] [ref=f1e82]
          - button "下一頁" [disabled] [ref=f1e83]
      - region "開啟草稿" [ref=f1e84]:
        - heading "業務簡介：Fictional industrial sensors" [level=3] [ref=f1e85]
        - paragraph [ref=f1e86]: "版本: 1 · 待審核 · zh-HK"
        - paragraph [ref=f1e87]: 寄送功能已停用。
        - generic [ref=f1e88]:
          - generic [ref=f1e89]:
            - text: 主旨
            - textbox "主旨" [ref=f1e90]: 業務簡介：Fictional industrial sensors
          - generic [ref=f1e91]:
            - text: 內容
            - textbox "內容" [ref=f1e92]: 你好， 我們提供：Fictional industrial sensors [offer_fact:eb000000-0000-4000-8000-000000000001] 參考公開資料："Fixture public catalog lists industrial sensors." [evidence:e5000000-0000-4000-8000-000000000001:v1] 如果合適，歡迎安排交流。
          - generic [ref=f1e93]:
            - text: 語言
            - combobox "語言" [ref=f1e94]:
              - option "English"
              - option "繁體中文" [selected]
        - generic [ref=f1e95]:
          - button "儲存修訂" [disabled] [ref=f1e96]
          - button "準備跟進草稿" [ref=f1e97] [cursor=pointer]
        - heading "陳述及來源" [level=4] [ref=f1e98]
        - paragraph [ref=f1e99]: Fictional industrial sensors · eb000000-0000-4000-8000-000000000001
        - paragraph [ref=f1e100]: Fixture public catalog lists industrial sensors. · e5000000-0000-4000-8000-000000000001
        - region "精確版本審核" [ref=f1e101]:
          - heading "精確版本審核" [level=4] [ref=f1e102]
          - paragraph [ref=f1e103]: "版本: 1 · 73a0361d179767b573b45691c2f6549f6f04a2e32425687105e377552a6a234a"
          - heading "收件人" [level=5] [ref=f1e104]
          - paragraph [ref=f1e105]: recipient@fixture.example.test · v1 · provider_marked_valid
          - heading "寄件人身份" [level=5] [ref=f1e106]
          - paragraph [ref=f1e107]: Fixture Alex · Fictional Seller · alex@example.test · sender:ea000000-0000-4000-8000-000000000001:1
          - heading "陳述及來源" [level=5] [ref=f1e108]
          - paragraph [ref=f1e109]: e5000000-0000-4000-8000-000000000001 · v1 · e4000000-0000-4000-8000-000000000001
          - heading "政策條件" [level=5] [ref=f1e110]
          - paragraph [ref=f1e111]: 779c6c71-900b-4276-9f2b-adc8654683ed, a0b6da76-0bd0-43de-b1b8-b09c6e3163b6, ed000000-0000-4000-8000-000000000001
          - paragraph [ref=f1e112]: e6000000-0000-4000-8000-000000000001 · e7000000-0000-4000-8000-000000000001 · e8000000-0000-4000-8000-000000000001
          - paragraph [ref=f1e113]: "審核背景: f19452509d7a6c5aee623dac492a86e3dcc49179919aa77c637b9060fa55fadc"
          - button "重新整理草稿" [ref=f1e115] [cursor=pointer]
```