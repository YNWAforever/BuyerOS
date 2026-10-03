# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-job-scope.spec.ts >> U15 held B list and count cannot overwrite newer A-B-A generation
- Location: tests\e2e\audit-job-scope.spec.ts:39:1

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
      - generic [ref=f1e6]: Live workspace
      - generic [ref=f1e7]:
        - text: Language
        - combobox "Language" [ref=f1e8]:
          - option "English" [selected]
          - option "繁體中文"
      - button "Sign out" [ref=f1e9] [cursor=pointer]
    - navigation "BuyerOS sections" [ref=f1e10]:
      - button "Overview" [ref=f1e11] [cursor=pointer]
      - button "Offer" [disabled] [ref=f1e12]
      - button "Buyers" [ref=f1e13] [cursor=pointer]
      - button "Results" [ref=f1e14] [cursor=pointer]
      - button "Research runs" [ref=f1e15] [cursor=pointer]
      - button "Drafts" [ref=f1e16] [cursor=pointer]
      - button "Settings" [ref=f1e17] [cursor=pointer]
      - button "Operations" [ref=f1e18] [cursor=pointer]
    - region "Workspace selection" [ref=f1e19]:
      - heading "Workspaces" [level=2] [ref=f1e20]
      - generic [ref=f1e21]:
        - text: Workspace
        - combobox "Workspace" [ref=f1e22]:
          - option "Choose workspace"
          - option "E2E fixture workspace" [selected]
      - paragraph [ref=f1e23]: "Role: reviewer"
    - region "Project selection" [ref=f1e24]:
      - heading "Projects" [level=2] [ref=f1e25]
      - generic [ref=f1e26]:
        - text: Project
        - combobox "Project" [ref=f1e27]:
          - option "Choose project"
          - option "Buyer Fixture Project"
          - option "Run Fixture Project"
          - option "Q14 project B" [selected]
    - region "Operations" [ref=f1e28]:
      - heading "Operations" [level=2] [ref=f1e29]
      - paragraph [ref=f1e30]: Live domain state only. Provider readiness remains blocked until verified.
      - region "Work queue" [ref=f1e31]:
        - heading "Work queue" [level=3] [ref=f1e32]
        - paragraph [ref=f1e33]: "Profile approval: 0"
        - paragraph [ref=f1e34]: "Failed jobs: 5"
        - paragraph [ref=f1e35]: "Buyer review: Open the live buyer list for current review status."
        - button "Open buyer list" [ref=f1e36] [cursor=pointer]
      - region "Integrations" [ref=f1e37]:
        - heading "Integrations" [level=3] [ref=f1e38]
        - paragraph [ref=f1e39]: "research: unconfigured · live_providers_not_activated"
        - paragraph [ref=f1e40]: "contact_enrichment: unconfigured · live_providers_not_activated"
        - paragraph [ref=f1e41]: "draft_generation: unconfigured · live_providers_not_activated"
        - paragraph [ref=f1e42]: "mailbox: disabled · live_providers_not_activated"
        - paragraph [ref=f1e43]: "crm: disabled · live_providers_not_activated"
      - region "Bulk jobs" [ref=f1e44]:
        - heading "Bulk jobs" [level=3] [ref=f1e45]
        - generic [ref=f1e46]:
          - text: Job scope
          - combobox "Job scope" [ref=f1e47]:
            - option "Project jobs"
            - option "Workspace jobs" [selected]
        - paragraph [ref=f1e48]:
          - text: "Workspace jobs:"
          - code [ref=f1e49]: e0000000-0000-4000-8000-000000000001
        - paragraph [ref=f1e50]: Only jobs created by your account are included.
        - generic [ref=f1e51]:
          - text: Filter status
          - combobox "Filter status" [ref=f1e52]:
            - option "All statuses"
            - option "queued"
            - option "running"
            - option "cancel_requested"
            - option "cancelled"
            - option "completed"
            - option "failed" [selected]
        - paragraph [ref=f1e53]: 5 jobs in scope
        - generic [ref=f1e54]:
          - button "de347d1d-dbe4-49a6-a70e-2910cf70dfc0" [ref=f1e55] [cursor=pointer]
          - generic [ref=f1e56]: failed · 1/1
        - generic [ref=f1e57]:
          - button "bfaa7481-825f-4fd7-b131-99a4dd146f4f" [ref=f1e58] [cursor=pointer]
          - generic [ref=f1e59]: failed · 1/1
        - generic [ref=f1e60]:
          - button "9601fbf4-1b49-486e-b00b-ceb3413daa14" [ref=f1e61] [cursor=pointer]
          - generic [ref=f1e62]: failed · 1/1
        - generic [ref=f1e63]:
          - button "49309772-7d05-4d74-ab89-5be8a58de53f" [ref=f1e64] [cursor=pointer]
          - generic [ref=f1e65]: failed · 1/1
        - generic [ref=f1e66]:
          - button "30292214-68bf-4532-9339-a423bffa88ae" [ref=f1e67] [cursor=pointer]
          - generic [ref=f1e68]: failed · 1/1
        - generic [ref=f1e69]:
          - button "Previous" [disabled] [ref=f1e70]
          - generic [ref=f1e71]: 1–5 / 5
          - button "Next" [disabled] [ref=f1e72]
      - region "Job lookup" [ref=f1e73]:
        - heading "Job lookup" [level=3] [ref=f1e74]
        - generic [ref=f1e75]:
          - text: Job ID
          - textbox "Job ID" [ref=f1e76]
        - button "Load job" [ref=f1e77] [cursor=pointer]
```