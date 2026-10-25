export type Locale = 'zh-HK' | 'en';

export type PageId =
  | 'home'
  | 'features'
  | 'how-it-works'
  | 'pricing'
  | 'faq'
  | 'demo'
  | 'privacy'
  | 'terms';

export type CopyItem = {title: string; text: string};

export type PageCopy = {
  eyebrow: string;
  title: string;
  intro: string;
  sections: Array<{
    heading: string;
    body: string[];
    items?: CopyItem[];
  }>;
};

export type SiteCopy = {
  nav: Record<PageId, string>;
  common: {
    skip: string;
    navLabel: string;
    menu: string;
    login: string;
    demo: string;
    localeLabel: string;
    preview: string;
    footer: string;
    footerNote: string;
    sampleLabel: string;
    sampleCaption: string;
    learnMore: string;
    backHome: string;
    close: string;
  };
  extra: {
    mobileDemo: string;
    heroFootnote: string;
    beforeLabel: string;
    beforeBody: string;
    afterBody: string;
    illustrationNote: string;
    captureCaption: string;
    pending: string;
    retentionDisabled: string;
    days: string;
    sensorTag: string;
    buyerTag: string;
    draftStatus: string;
  };
  seo: Record<PageId, {title: string; description: string}>;
  pages: Record<PageId, PageCopy>;
  home: {
    headline: string;
    intro: string;
    secondary: string;
    proof: CopyItem[];
    problemTitle: string;
    problemIntro: string;
    benefits: CopyItem[];
    featuresTitle: string;
    workflowTitle: string;
    sampleTitle: string;
    personasTitle: string;
    personas: CopyItem[];
    closingTitle: string;
    closingBody: string;
  };
  features: Array<{id: string; title: string; text: string; detail: string}>;
  steps: Array<{title: string; text: string; detail: string}>;
  faq: Array<{question: string; answer: string}>;
  form: {
    name: string;
    email: string;
    company: string;
    message: string;
    optional: string;
    submit: string;
    pending: string;
    success: string;
    syntheticSuccess: string;
    error: string;
    unavailable: string;
    start: string;
    privacy: string;
    consent: string;
    invalidName: string;
    invalidEmail: string;
    invalidCompany: string;
    invalidMessage: string;
    conflict: string;
    rateLimited: string;
    syntheticNotice: string;
    receiptLabel: string;
    retry: string;
    noJavaScript: string;
  };
  sample: {
    criteriaLabel: string;
    criteria: string;
    companyLabel: string;
    company: string;
    sourceLabel: string;
    source: string;
    reviewLabel: string;
    review: string;
    draftLabel: string;
    draftSubject: string;
    draftBody: string;
  };
  legal: {
    draftLabel: string;
    publisherMissing: string;
    controllerLabel: string;
    contactLabel: string;
    retentionLabel: string;
  };
  pricing: {
    status: string;
    cta: string;
    topics: string[];
  };
};

// Shared by server-rendered pages, metadata, navigation and visible FAQ content.
// Sample records describe a fictional workflow, never a customer outcome.
export const siteCopy = {
  'zh-HK': {
    nav: {
      home: '首頁',
      features: '功能',
      'how-it-works': '使用流程',
      pricing: '方案',
      faq: '常見問題',
      demo: '預約示範',
      privacy: '私隱說明',
      terms: '使用條款',
    },
    common: {
      skip: '跳至主要內容',
      navLabel: '主要導覽',
      menu: '開啟導覽選單',
      login: '登入工作空間',
      demo: '預約示範',
      localeLabel: '網站語言',
      preview: '本機預覽',
      footer: '把買家條件、來源與跟進草稿放在同一個工作空間。',
      footerNote: '合成示例並非實際買家、客戶案例或成效證明。',
      sampleLabel: '合成示例資料',
      sampleCaption: '公司、來源及草稿均為虛構示例。草稿未發送，仍待人手覆核。',
      learnMore: '了解三步工作流程',
      backHome: '返回首頁',
      close: '關閉',
    },
    extra: {
      mobileDemo: '示範',
      heroFootnote: '先覆核資料與來源，再決定下一步；此流程不提供寄送。',
      beforeLabel: '資料分散各處',
      beforeBody: '名單、電郵與筆記各放一處，未有連同資料來源。',
      afterBody: '把買家條件、來源、審閱狀態與草稿一併交接。',
      illustrationNote: '流程示意，並非成效比較測試。',
      captureCaption: '本機產品介面與合成資料；畫面中的數字並非客戶成果。',
      pending: '待確認',
      retentionDisabled: '保存安排待確認；正式申請目前停用。',
      days: '天',
      sensorTag: '工業感應設備',
      buyerTag: '企業買家',
      draftStatus: '草稿・未發送',
    },
    seo: {
      home: {
        title: 'BuyerOS｜從買家條件到有根據的跟進',
        description: '整理買家條件、公司與來源記錄，經人手審閱後儲存跟進草稿。查看 BuyerOS 的示例流程，了解是否適合你的團隊。',
      },
      features: {
        title: 'BuyerOS 功能｜條件、來源、覆核與草稿',
        description: '了解 BuyerOS 如何整理買家條件版本、公司資料與來源、審閱指派、跟進草稿，以及有格式限制的名單和文件匯入。',
      },
      'how-it-works': {
        title: 'BuyerOS 使用流程｜從買家條件到草稿',
        description: '透過三步合成示例，了解如何定義買家條件、檢視公司資料與來源，再儲存交由同事覆核的跟進草稿。',
      },
      pricing: {
        title: 'BuyerOS 方案｜了解團隊使用安排',
        description: 'BuyerOS 的公開價格、免費安排及方案內容尚待確認。先了解示範流程，再討論團隊人數、使用範圍及所需功能。',
      },
      faq: {
        title: 'BuyerOS 常見問題｜資料、草稿與使用範圍',
        description: '查閱 BuyerOS 的資料來源、固定模板草稿、人手覆核、匯入格式、雙語介面、工作空間權限及示範申請說明。',
      },
      demo: {
        title: '預約 BuyerOS 示範｜了解買家開發流程',
        description: '了解 BuyerOS 如何整理買家條件、來源與跟進草稿。本機預覽只供合成示例；正式示範申請須待資料處理安排確認。',
      },
      privacy: {
        title: 'BuyerOS 私隱說明草稿｜本機預覽與資料處理',
        description: '說明 BuyerOS 本機預覽、合成表單資料及停用的對外分析傳輸；正式營運者、聯絡方式與保存安排仍待確認。',
      },
      terms: {
        title: 'BuyerOS 使用條款草稿｜預覽範圍與使用限制',
        description: '了解 BuyerOS 本機預覽的合成示例、人手覆核、草稿與功能限制。正式服務條款及營運資料尚待批准。',
      },
    },
    pages: {
      home: {
        eyebrow: '買家開發工作空間',
        title: '買家名單不少，真正值得跟進的是誰？',
        intro: 'BuyerOS 幫團隊整理理想買家條件、檢視公司資料與來源，並儲存可由同事覆核的跟進草稿。',
        sections: [
          {
            heading: '先看資料，再決定下一步',
            body: ['把判斷條件、已有資料及跟進草稿連在一起，讓接手的同事了解目前進度與仍需確認的地方。'],
          },
        ],
      },
      features: {
        eyebrow: '功能',
        title: '從買家條件到下一份草稿',
        intro: '把條件、資料、來源與人手覆核連成一個工作流程，讓團隊看見每一步的判斷依據。',
        sections: [
          {
            heading: '保留依據，方便接手',
            body: ['條件版本、來源記錄、審閱狀態和草稿修改，為下一位接手的同事提供背景。來源的存在不代表資料已獲核實，團隊仍需判斷內容是否準確及適用。'],
          },
          {
            heading: '使用範圍清楚，才容易安排工作',
            body: ['名單匯入與產品文件有格式及大小等限制。研究供應情況取決於已啟用的服務、權限與設定；這個草稿流程不提供訊息寄送。'],
          },
        ],
      },
      'how-it-works': {
        eyebrow: '使用流程',
        title: '三步整理買家開發工作',
        intro: '由團隊訂立條件，再檢視資料和來源，最後把跟進內容儲存成可覆核的草稿。',
        sections: [
          {
            heading: '每一步都有同事作判斷',
            body: ['BuyerOS 整理工作所需的背景，不代替團隊確認買家是否合適。審閱資料時，請同時考慮來源、內容是否仍然有效，以及尚未取得的資訊。'],
          },
          {
            heading: '示例展示流程，不代表研究成果',
            body: ['本網站的公司、來源與訊息均為合成示例。實際研究需要相應服務與權限；示例不能用來推斷買家數量、資料準確率或商業成效。'],
          },
          {
            heading: '草稿儲存後，仍須覆核',
            body: ['已驗證的草稿流程以已批准資料與來源建立固定模板，供同事修改並儲存新版本。這不代表任意 AI 寫作或自動翻譯，亦不包含寄送。'],
          },
        ],
      },
      pricing: {
        eyebrow: '方案',
        title: '找到適合團隊的使用方式',
        intro: '先了解流程如何配合你的工作，再討論目前可提供的使用安排。公開價目與方案內容尚待確認。',
        sections: [
          {
            heading: '先從你的工作方式談起',
            body: ['團隊人數、現有名單、文件格式及覆核方式，都有助釐清所需範圍。可先查看示例流程，待正式申請入口開放後再預約示範。'],
          },
          {
            heading: '目前沒有公開可購買方案',
            body: ['價格、席位、用量、包含服務及免費安排均未確認。此頁不提供購買或付款，也沒有免費試用承諾。'],
          },
        ],
      },
      faq: {
        eyebrow: '常見問題',
        title: '先了解能做甚麼，以及仍需判斷甚麼',
        intro: '由資料來源、草稿方式到使用安排，先了解能力與限制，再判斷是否適合你的團隊。',
        sections: [
          {
            heading: '示範前，先看完整工作流程',
            body: ['本網站以合成資料說明操作。研究服務、正式使用及示範申請的供應情況，需要按已確認的設定和資料處理安排判斷。'],
          },
        ],
      },
      demo: {
        eyebrow: '預約示範',
        title: '一起看看 BuyerOS 如何配合你的買家開發流程',
        intro: '從你的團隊如何整理買家資料談起，了解條件、來源、覆核與跟進草稿如何銜接。',
        sections: [
          {
            heading: '示範可以看甚麼？',
            body: ['以虛構公司與來源走過一個完整流程，查看條件版本、資料記錄、審閱指派及未發送草稿。'],
            items: [
              {title: '你目前如何整理名單', text: '了解資料放在哪裏、由誰整理，以及接手時需要哪些背景。'},
              {title: '你如何覆核資料與內容', text: '對照來源、審閱狀態與草稿版本，看看流程是否適合團隊。'},
              {title: '你希望先確認的限制', text: '討論匯入格式、語言、權限和所需服務的供應範圍。'},
            ],
          },
          {
            heading: '本機預覽的申請狀態',
            body: ['正式示範申請尚未開放。營運者、接收人、聯絡方式、處理用途及保存安排確認前，這個預覽不接收真實留資。若表單顯示合成示例模式，只可輸入虛構資料；取得的本機收據不代表已向團隊提出申請。'],
          },
        ],
      },
      privacy: {
        eyebrow: '法律文件草稿',
        title: '私隱說明：本機預覽與資料處理',
        intro: '此說明仍是待批准草稿，只記錄目前本機預覽的已知安排。正式營運者、資料控制者、聯絡方式與保存安排尚待確認。',
        sections: [
          {
            heading: '這份草稿適用於甚麼？',
            body: ['本網站以合成公司、虛構來源及未發送草稿介紹 BuyerOS。公開頁面可供閱讀；產品工作空間的登入及成員權限另由產品處理，這份草稿沒有取代其資料處理說明。'],
          },
          {
            heading: '示範申請與合成表單資料',
            body: ['正式示範申請停用，待營運者、接收人、處理用途、聯絡方式及保存安排確認後才可開放。請勿在本機預覽輸入真實姓名、聯絡資料、客戶資料或機密內容。', '若已啟用本機合成示例表單，它只供虛構資料及 .test 電郵使用，會儲存該次合成提交與收據資料，供本機核對。這不是正式留資，不會發送申請電郵或安排團隊跟進。'],
          },
          {
            heading: '分析與可能的請求記錄',
            body: ['此預覽的分析功能不會向外部分析服務傳送資料。主機或基礎設施可能記錄網站請求；實際記錄內容、接收方及保存安排仍須由營運者確認。這份草稿沒有宣稱網站完全不產生記錄。'],
          },
          {
            heading: '誰可以存取產品資料？',
            body: ['BuyerOS 的產品資料按工作空間與成員權限限制存取。這項存取安排本身不代表任何安全認證，亦不能用來推斷未確認的供應商、儲存位置或資料處理條款。'],
          },
          {
            heading: '保存、查詢與正式發布前的確認',
            body: ['正式資料的保存及刪除期限尚未提供，本草稿不設定或承諾任何期限。資料查詢及相關請求的聯絡途徑亦待確認。', '正式收集資料前，須補齊營運者及資料控制者身分、有效聯絡方式、處理用途、接收方、保存與刪除安排，以及適用的請求處理程序，並完成法律審批。'],
          },
        ],
      },
      terms: {
        eyebrow: '法律文件草稿',
        title: '使用條款：預覽範圍與使用限制',
        intro: '此頁是待營運者及法律審批的草稿，說明本機預覽範圍與已知產品限制。正式服務條款尚未提供。',
        sections: [
          {
            heading: '目前提供的是本機預覽',
            body: ['本網站用合成資料展示 BuyerOS 工作流程，沒有提供可購買方案、付款或正式示範申請。預覽所見的功能不代表指定部署已啟用相同服務。', '正式營運者、聯絡資料及服務安排仍待確認；此草稿沒有訂立價格、訂閱、付款或其他未批准的合約條件。'],
          },
          {
            heading: '使用合成示例時',
            body: ['請只使用虛構資料，不要提交真實個人資料、客戶名單或機密文件。示例公司、來源及草稿均為虛構，不應用作實際買家研究或商業成果的證據。', '如本機合成表單已啟用，其收據只確認該次本機合成提交已儲存，不代表已預約示範或會收到團隊回覆。'],
          },
          {
            heading: '資料與人手判斷',
            body: ['公司資料、來源及審閱記錄協助團隊作判斷，不保證第三方資料準確、完整或仍然有效。實際使用時，團隊需要確認所使用資料及文件的來源和使用權限。'],
          },
          {
            heading: '草稿、研究與匯入的範圍',
            body: ['已驗證的草稿方式使用已批准資料及來源建立固定模板，供人手修改與覆核；不代表任意 AI 寫作或自動翻譯。此流程不提供寄送，未來是否提供仍未確認。', '研究取決於已啟用的服務、權限與設定。CSV、XLSX 名單以及 PDF、PPTX、TXT、MD 文件的處理均有限制，匯入本身不會核實內容。'],
          },
          {
            heading: '正式使用前仍需確認',
            body: ['正式服務供應、價格、使用安排及資料處理說明須另行確認。本草稿沒有設定未提供的管轄法律、責任分配、保存期限或合約條件；完整內容須由營運者及法律審批後發布。'],
          },
        ],
      },
    },
    home: {
      headline: '買家名單不少，真正值得跟進的是誰？',
      intro: 'BuyerOS 幫團隊整理理想買家條件、檢視公司資料與來源，並儲存可由同事覆核的跟進草稿。',
      secondary: '查看示例流程',
      proof: [
        {title: '條件保留版本', text: '修改買家條件時，保留先前版本。'},
        {title: '保留資料來源', text: '把公司資料與可用出處一起檢視。'},
        {title: '由同事覆核', text: '看見審閱狀態與負責同事。'},
        {title: '草稿修改有紀錄', text: '儲存新版本，供同事重新檢視。'},
      ],
      problemTitle: '名單、來源、草稿，不必各放一處。',
      problemIntro: '當同事接手一個買家，應能看見判斷條件、已有資料和下一步，而不只是收到一份名單。',
      benefits: [
        {title: '判斷有依據', text: '把公司資料與可用來源放在一起檢視。'},
        {title: '交接更清晰', text: '保留審閱狀態與負責同事，讓接手的人了解背景。'},
        {title: '修改有紀錄', text: '儲存草稿版本，供同事重新檢視內容。'},
      ],
      featuresTitle: '從買家條件到下一份草稿',
      workflowTitle: '三步整理買家開發工作',
      sampleTitle: '看一個示例，了解資料如何接到草稿',
      personasTitle: '為需要一起整理買家開發工作的團隊而設',
      personas: [
        {title: '商務拓展', text: '整理目標條件與下一步，讓同事了解跟進背景。'},
        {title: '研究同事', text: '把公司資料、來源與判斷放在一起。'},
        {title: '覆核同事', text: '看清內容與來源，再提出意見。'},
      ],
      closingTitle: '先看一次完整示範，再決定下一步。',
      closingBody: '由條件、資料與來源，到一份未發送的草稿，了解 BuyerOS 是否配合你的團隊工作方式。',
    },
    features: [
      {id: 'criteria', title: '買家條件與版本', text: '修改條件時保留紀錄。', detail: '整理產品、目標市場與理想買家條件；調整要求時保留版本，供團隊重新檢視。'},
      {id: 'records', title: '公司資料與來源', text: '把可用資料和出處放在一起。', detail: '檢視公司資料與來源記錄，了解判斷所依據的內容。來源不保證資料真確或仍然有效。'},
      {id: 'review', title: '審閱與指派', text: '讓同事看見判斷狀態與負責人。', detail: '以審閱狀態及指派支援同事接手；產品資料的存取按工作空間與成員權限限制。'},
      {id: 'drafts', title: '跟進草稿與版本', text: '先儲存，再覆核，修改保留新版本。', detail: '使用已批准資料與來源建立固定模板，再由同事修改與覆核。此流程不提供寄送。'},
      {id: 'imports', title: '匯入現有名單', text: '支援 CSV 及 XLSX，匯入後仍須覆核。', detail: '名單匯入有格式及列數限制；匯入記錄不代表每項公司資料或來源已核實。'},
      {id: 'documents', title: '整理產品文件', text: '可處理 PDF、PPTX、TXT 及 MD 文件。', detail: '為買家條件整理產品背景；文件處理有格式及檔案大小限制，並非支援所有文件格式。'},
    ],
    steps: [
      {title: '定義條件', text: '說明產品、目標市場及理想買家。', detail: '集中整理團隊的要求，並保留條件版本，方便日後檢視改動。'},
      {title: '整理與覆核', text: '查看公司資料、來源及審閱狀態。', detail: '評估已有資料及仍需確認的地方，指派同事接手。第三方來源仍需人手判斷。'},
      {title: '儲存草稿', text: '根據已批准資料準備訊息，交同事覆核。', detail: '固定模板可由同事修改並儲存新版本。草稿未發送，此流程不提供寄送。'},
    ],
    faq: [
      {question: 'BuyerOS 是甚麼？', answer: 'BuyerOS 是把買家條件、公司資料、來源、人手覆核及跟進草稿整理在同一個工作空間的工具。'},
      {question: '適合甚麼團隊？', answer: '適合需要一起整理企業買家資料及覆核跟進內容的團隊。可先查看示例流程，再透過示範確認是否適合你的工作方式。'},
      {question: '會自動找到真實買家嗎？', answer: '研究功能取決於已啟用的服務供應商、權限及設定。本網站使用合成資料，不代表已取得真實買家，亦不保證資料覆蓋或商業成果。'},
      {question: '草稿是否由 AI 任意撰寫？', answer: '已驗證的流程可使用已批准資料與來源建立固定模板，再由同事修改；這不等於任意 AI 寫作或自動翻譯。'},
      {question: '有來源是否代表資料已核實？', answer: '不是。來源及審閱記錄協助同事判斷，並不保證第三方資料真確、完整或仍然有效。'},
      {question: '會自動寄出訊息嗎？', answer: '這個 BuyerOS 流程不提供寄送，只儲存及覆核草稿。未來是否提供寄送仍未確認。'},
      {question: '能匯入名單及產品文件嗎？', answer: '可匯入 CSV 與 XLSX 名單，並有格式及列數限制。產品文件可使用 PDF、PPTX、TXT 及 MD，另有格式及檔案大小限制。匯入不代表內容已核實。'},
      {question: '支援哪些語言？', answer: '介面已有英文及香港繁體中文。切換介面語言不會自動翻譯來源內容或草稿中的原有資料。'},
      {question: '是否免費？價格是多少？', answer: '免費安排、公開價格及方案內容尚待確認。正式聯絡入口開放後，可向團隊了解目前的使用安排；此頁沒有免費試用承諾。'},
      {question: '誰可以看見資料？示範申請如何處理？', answer: '產品資料按工作空間與成員權限限制存取。正式示範申請目前停用，須先確認營運者、處理用途、接收人、聯絡方式及保存安排。本機合成表單只供虛構資料，收據不代表正式申請。'},
    ],
    form: {
      name: '姓名',
      email: '工作電郵',
      company: '公司',
      message: '你想改善哪個工作步驟？',
      optional: '選填',
      submit: '提交示範申請',
      pending: '正在提交…',
      success: '已收到並儲存你的示範申請。收據編號如下。',
      syntheticSuccess: '已儲存這次本機合成示例。這不是正式示範申請，亦不會安排團隊跟進。',
      error: '暫時未能確認提交。你的輸入仍保留，請重試。',
      unavailable: '正式示範申請尚未開放。接收人、聯絡方式及資料處理安排確認後才會啟用。請先查看示例流程。',
      start: '你的團隊希望先了解甚麼？',
      privacy: '提交前請閱讀私隱說明，了解此表單的資料處理範圍。',
      consent: '我已閱讀私隱說明，並了解目前顯示的表單模式。',
      invalidName: '請填寫姓名，並縮短至欄位允許的長度。',
      invalidEmail: '請填寫有效電郵；合成示例模式只接受虛構的 .test 電郵。',
      invalidCompany: '公司名稱過長，請縮短後再提交。',
      invalidMessage: '訊息過長，請縮短後再提交。',
      conflict: '這次重試的內容與先前提交不同。請檢查輸入，再重新提交。',
      rateLimited: '提交次數較多，請稍後再試。你的輸入仍保留。',
      syntheticNotice: '本機合成示例模式：只可填寫虛構資料及 .test 電郵。這會儲存本機合成收據，不會提交真實留資或發送電郵。',
      receiptLabel: '提交收據編號',
      retry: '重試提交',
      noJavaScript: '請啟用 JavaScript，以完成安全提交表單所需的檢查。',
    },
    sample: {
      criteriaLabel: '買家條件',
      criteria: '工業感應設備供應商；先檢視產品相關資料。',
      companyLabel: '示例公司',
      company: '晴嶼設備示例公司',
      sourceLabel: '虛構來源',
      source: '虛構產品目錄提及工業感應設備。此來源只供流程示意，並非實際研究結果。',
      reviewLabel: '審閱狀態',
      review: '待同事覆核',
      draftLabel: '示例草稿・未發送',
      draftSubject: '交流工業感應設備',
      draftBody: '我們提供工業感應設備，希望了解是否適合貴團隊。此為固定模板示例，內容仍待同事覆核。',
    },
    legal: {
      draftLabel: '待營運者及法律審批的草稿',
      publisherMissing: '正式營運者、資料控制者及聯絡資料尚待確認。正式示範申請目前停用。',
      controllerLabel: '資料控制者',
      contactLabel: '資料查詢聯絡方式',
      retentionLabel: '保存與刪除安排尚待確認，未設定正式期限。',
    },
    pricing: {
      status: '目前方案、收費、席位、用量及包含服務尚待確認。',
      cta: '預約示範，了解使用方式',
      topics: ['團隊人數與覆核方式', '現有名單及文件格式', '所需工作流程與權限', '目前可供使用的功能範圍'],
    },
  },
  en: {
    nav: {
      home: 'Home',
      features: 'Features',
      'how-it-works': 'How it works',
      pricing: 'Plans',
      faq: 'FAQ',
      demo: 'Request a demo',
      privacy: 'Privacy notice',
      terms: 'Terms of use',
    },
    common: {
      skip: 'Skip to content',
      navLabel: 'Main navigation',
      menu: 'Open navigation menu',
      login: 'Workspace login',
      demo: 'Request a demo',
      localeLabel: 'Website language',
      preview: 'Local preview',
      footer: 'Keep buyer criteria, sources and outreach drafts in one workspace.',
      footerNote: 'Synthetic examples are not real buyers, customer stories or evidence of results.',
      sampleLabel: 'Synthetic sample data',
      sampleCaption: 'The company, sources and draft are fictional. The draft is unsent and awaiting human review.',
      learnMore: 'Explore the three-step workflow',
      backHome: 'Back to home',
      close: 'Close',
    },
    extra: {
      mobileDemo: 'Demo',
      heroFootnote: 'Review records and sources before deciding the next step. This workflow does not offer sending.',
      beforeLabel: 'Scattered records',
      beforeBody: 'Lists, emails and notes sit apart, without their sources.',
      afterBody: 'Hand over buyer criteria, sources, review status and the draft together.',
      illustrationNote: 'Illustrative workflow, not a measured performance comparison.',
      captureCaption: 'Local product interface with synthetic data. Numbers shown are not customer outcomes.',
      pending: 'To be confirmed',
      retentionDisabled: 'Retention is unconfirmed; real intake is disabled.',
      days: 'days',
      sensorTag: 'Industrial sensing equipment',
      buyerTag: 'Business buyer',
      draftStatus: 'Draft · Not sent',
    },
    seo: {
      home: {
        title: 'BuyerOS | From buyer criteria to informed follow-up',
        description: 'Organize buyer criteria, company and source records, then save outreach drafts for human review. Explore the BuyerOS sample workflow to assess the fit.',
      },
      features: {
        title: 'BuyerOS Features | Criteria, Sources, Review and Drafts',
        description: 'Explore versioned buyer criteria, company records and sources, review and assignment, outreach drafts, and list and document imports with format limits.',
      },
      'how-it-works': {
        title: 'How BuyerOS Works | From Buyer Criteria to a Draft',
        description: 'Follow a three-step synthetic example: define buyer criteria, review company records and sources, then save an outreach draft for a colleague to review.',
      },
      pricing: {
        title: 'BuyerOS Plans | Discuss Your Team’s Requirements',
        description: 'Public prices, free access and plan details are not yet confirmed. Explore the workflow before discussing team size, scope and required features.',
      },
      faq: {
        title: 'BuyerOS FAQ | Records, Drafts and Scope',
        description: 'Read about sources, fixed-template drafts, human review, import formats, bilingual interfaces, workspace access and demo requests in BuyerOS.',
      },
      demo: {
        title: 'Request a BuyerOS Demo | Explore Buyer Development',
        description: 'Explore buyer criteria, sources and outreach drafts in BuyerOS. This local preview uses synthetic examples; real requests await confirmed data handling.',
      },
      privacy: {
        title: 'BuyerOS Draft Privacy Notice | Local Preview and Data',
        description: 'Read the known local-preview and synthetic-form arrangements. External analytics transmission is off; publisher, contact and retention details await confirmation.',
      },
      terms: {
        title: 'BuyerOS Draft Terms | Preview Scope and Limits',
        description: 'Understand the synthetic examples, human review, draft workflow and feature limits in this local preview. Formal service terms await approval.',
      },
    },
    pages: {
      home: {
        eyebrow: 'A workspace for buyer development',
        title: 'Plenty of buyer names. Who deserves a closer look?',
        intro: 'Organize buyer criteria, review company information and its sources, and save outreach drafts your team can review.',
        sections: [
          {
            heading: 'Review the context before choosing the next step',
            body: ['Connect the criteria, available information and outreach draft so the next colleague can see the current position and what still needs checking.'],
          },
        ],
      },
      features: {
        eyebrow: 'Features',
        title: 'From buyer criteria to the next draft',
        intro: 'Connect criteria, records, sources and human review in a workflow that shows the reasoning behind each step.',
        sections: [
          {
            heading: 'Keep the context for the next handover',
            body: ['Criteria versions, source records, review status and draft revisions give the next colleague useful background. A source does not make a claim verified; your team still needs to assess accuracy and relevance.'],
          },
          {
            heading: 'Plan work with a clear scope',
            body: ['List imports and offer documents have format, size and other limits. Research availability depends on enabled services, permissions and configuration. This draft workflow does not offer message sending.'],
          },
        ],
      },
      'how-it-works': {
        eyebrow: 'How it works',
        title: 'Three steps to organize buyer development',
        intro: 'Set the criteria, inspect the records and sources, then save follow-up content as a draft for a colleague to review.',
        sections: [
          {
            heading: 'Human judgment at each step',
            body: ['BuyerOS organizes the context for your work. Your team decides whether a buyer is relevant. When reviewing records, consider the source, whether the information is current and what is still missing.'],
          },
          {
            heading: 'An example of the workflow',
            body: ['The companies, sources and messages on this website are synthetic. Actual research requires the relevant services and permissions. These examples do not establish buyer volume, data accuracy or commercial results.'],
          },
          {
            heading: 'A saved draft still needs review',
            body: ['The verified draft workflow builds a fixed template from approved information and sources. Colleagues can edit it and save revisions. This does not imply free-form AI writing, automatic translation or sending.'],
          },
        ],
      },
      pricing: {
        eyebrow: 'Plans',
        title: 'Find the right approach for your team',
        intro: 'Explore how the workflow fits your work before discussing available arrangements. Public prices and plan details are not yet confirmed.',
        sections: [
          {
            heading: 'Start with the way your team works',
            body: ['Team size, existing lists, document formats and review practices help establish the scope you need. Explore the sample workflow first, then request a demo when the real intake opens.'],
          },
          {
            heading: 'No publicly purchasable plans are available here',
            body: ['Prices, seats, usage, included services and free access are unconfirmed. This page does not offer purchasing or payment, and makes no free-trial promise.'],
          },
        ],
      },
      faq: {
        eyebrow: 'Frequently asked questions',
        title: 'Understand the workflow and where judgment is needed',
        intro: 'Explore sources, drafts and access, then assess whether the workflow fits your team.',
        sections: [
          {
            heading: 'Explore the full workflow before a demo',
            body: ['This website uses synthetic data to explain the workflow. Research services, production access and real demo requests depend on confirmed configuration and data-handling arrangements.'],
          },
        ],
      },
      demo: {
        eyebrow: 'Request a demo',
        title: 'Explore how BuyerOS fits your buyer development workflow',
        intro: 'Start with how your team organizes buyer information, then explore how criteria, sources, review and outreach drafts connect.',
        sections: [
          {
            heading: 'What can a demonstration cover?',
            body: ['Follow a fictional company and its sources through criteria versions, company records, review and assignment, and an unsent draft.'],
            items: [
              {title: 'How you organize lists today', text: 'Discuss where information lives, who maintains it and what colleagues need during a handover.'},
              {title: 'How you review records and content', text: 'Compare sources, review status and draft revisions with your team’s workflow.'},
              {title: 'The limits you need to understand', text: 'Discuss import formats, language, permissions and the availability of required services.'},
            ],
          },
          {
            heading: 'Requests in this local preview',
            body: ['Real demo requests are not open. This preview does not collect real leads while the publisher, recipient, contact details, purposes and retention arrangements remain unconfirmed. If the form shows synthetic mode, use fictional details only. A local receipt is not a request sent to the team.'],
          },
        ],
      },
      privacy: {
        eyebrow: 'Draft legal document',
        title: 'Privacy notice: local preview and data handling',
        intro: 'This draft awaits approval and records only the known arrangements for the local preview. The publisher, data controller, contact details and retention arrangements remain unconfirmed.',
        sections: [
          {
            heading: 'What does this draft cover?',
            body: ['This website introduces BuyerOS using synthetic companies, fictional sources and unsent drafts. Public pages can be read without entering a product workspace. Product sign-in and membership access are handled separately; this draft does not replace the product’s data-handling information.'],
          },
          {
            heading: 'Demo requests and synthetic form data',
            body: ['Real demo intake is disabled until the publisher, recipient, purposes, contact details and retention arrangements are confirmed. Do not enter real names, contact details, customer data or confidential information in this local preview.', 'If the local synthetic form is enabled, it accepts fictional details and .test email addresses only. It saves the synthetic submission and receipt information for local verification. This is not a real lead, sends no request email and does not arrange team follow-up.'],
          },
          {
            heading: 'Analytics and possible request logs',
            body: ['Analytics in this preview do not transmit data to external analytics services. The host or infrastructure may log website requests; the actual information, recipients and retention arrangements need confirmation by the publisher. This draft does not claim that no logs are created.'],
          },
          {
            heading: 'Who can access product data?',
            body: ['Access to BuyerOS product data is scoped by workspace and membership. That access arrangement does not establish a security certification or confirm any supplier, storage location or data-processing terms.'],
          },
          {
            heading: 'Retention, enquiries and publication requirements',
            body: ['No retention or deletion period for real data has been supplied. This draft does not set or promise one. A contact route for data enquiries and related requests also needs confirmation.', 'Before collecting real data, the publisher must confirm its identity and the controller’s identity, valid contact details, purposes, recipients, retention and deletion arrangements, and applicable request procedures, and complete legal approval.'],
          },
        ],
      },
      terms: {
        eyebrow: 'Draft legal document',
        title: 'Terms of use: preview scope and limits',
        intro: 'This draft awaits publisher and legal approval. It describes the local preview and known product limits. Formal service terms have not been supplied.',
        sections: [
          {
            heading: 'The current scope is a local preview',
            body: ['This website demonstrates the BuyerOS workflow with synthetic data. It does not offer purchasable plans, payment or real demo intake. A feature shown in the preview does not establish that the same service is enabled in a particular deployment.', 'The publisher, contact details and service arrangements remain unconfirmed. This draft does not establish prices, subscriptions, payment terms or other unapproved contract terms.'],
          },
          {
            heading: 'Using the synthetic examples',
            body: ['Use fictional details only. Do not submit real personal data, customer lists or confidential documents. Sample companies, sources and drafts are fictional and should not be used as evidence of actual buyer research or commercial results.', 'If the local synthetic form is enabled, its receipt confirms only that the local synthetic submission was saved. It does not book a demonstration or promise a response from the team.'],
          },
          {
            heading: 'Records and human judgment',
            body: ['Company records, sources and review history support your team’s decisions. They do not guarantee that third-party information is accurate, complete or current. In actual use, teams need to confirm the provenance of records and documents and their permission to use them.'],
          },
          {
            heading: 'Draft, research and import scope',
            body: ['The verified draft workflow builds a fixed template from approved information and sources for human editing and review. It does not imply free-form AI writing or automatic translation. This workflow does not offer sending, and future sending availability is unconfirmed.', 'Research depends on enabled services, permissions and configuration. CSV and XLSX lists and PDF, PPTX, TXT and MD documents are subject to limits. Importing does not verify their contents.'],
          },
          {
            heading: 'What remains to be confirmed',
            body: ['Production service availability, pricing, access arrangements and data-handling information need separate confirmation. This draft does not set an unspecified governing law, allocation of liability, retention period or contract terms. The complete text requires publisher and legal approval before publication.'],
          },
        ],
      },
    },
    home: {
      headline: 'Plenty of buyer names. Who deserves a closer look?',
      intro: 'Organize buyer criteria, review company information and its sources, and save outreach drafts your team can review.',
      secondary: 'Explore the sample workflow',
      proof: [
        {title: 'Versioned buyer criteria', text: 'Retain earlier versions when requirements change.'},
        {title: 'Source-linked records', text: 'Review company information alongside available sources.'},
        {title: 'Human review', text: 'See the review status and responsible colleague.'},
        {title: 'Saved draft revisions', text: 'Keep new versions for the next review.'},
      ],
      problemTitle: 'Keep the list, the context and the draft together.',
      problemIntro: 'When a colleague takes over, they need the criteria, the available evidence and the next step, alongside the list of names.',
      benefits: [
        {title: 'Make informed decisions', text: 'Review company information alongside its available sources.'},
        {title: 'Make handovers clearer', text: 'Retain review status and ownership so the next colleague has context.'},
        {title: 'Keep a record of changes', text: 'Save draft revisions for a colleague to review again.'},
      ],
      featuresTitle: 'From buyer criteria to the next draft',
      workflowTitle: 'Three steps to organize buyer development',
      sampleTitle: 'See how a sample record connects to a draft',
      personasTitle: 'For teams working together on buyer development',
      personas: [
        {title: 'Business development', text: 'Organize criteria and next steps so colleagues understand the follow-up context.'},
        {title: 'Researchers', text: 'Keep company records, sources and assessments together.'},
        {title: 'Reviewers', text: 'Inspect the content and its sources before giving feedback.'},
      ],
      closingTitle: 'See the complete demonstration, then decide what comes next.',
      closingBody: 'Follow criteria, records and sources through to an unsent draft to assess how BuyerOS fits the way your team works.',
    },
    features: [
      {id: 'criteria', title: 'Buyer criteria and versions', text: 'Keep a record as requirements change.', detail: 'Organize your offer, target markets and ideal buyer criteria. Retain versions as requirements change so your team can revisit them.'},
      {id: 'records', title: 'Company records and sources', text: 'Keep information alongside its provenance.', detail: 'Inspect company information and source records to understand the basis for a decision. A source does not guarantee accuracy or freshness.'},
      {id: 'review', title: 'Review and assignment', text: 'Show the current review status and owner.', detail: 'Use review status and assignment to support handovers. Access to product data is scoped by workspace and membership.'},
      {id: 'drafts', title: 'Outreach drafts and revisions', text: 'Save first, review next, and retain revisions.', detail: 'Build a fixed template from approved information and sources, then edit and review it with a colleague. This workflow does not offer sending.'},
      {id: 'imports', title: 'Import an existing list', text: 'CSV and XLSX are supported; imported claims still need review.', detail: 'List imports have format and row limits. Importing a record does not verify its company information or sources.'},
      {id: 'documents', title: 'Work with offer documents', text: 'Use PDF, PPTX, TXT and MD documents.', detail: 'Organize offer context for your buyer criteria. Document handling has format and file-size limits and does not support every file type.'},
    ],
    steps: [
      {title: 'Define the criteria', text: 'Describe your offer, target markets and ideal buyers.', detail: 'Organize the team’s requirements and retain criteria versions so changes can be reviewed later.'},
      {title: 'Organize and review', text: 'Inspect company records, sources and review status.', detail: 'Assess the available information and what still needs checking, then assign a colleague. Third-party sources still require human judgment.'},
      {title: 'Save a draft', text: 'Prepare a message from approved information for a colleague to review.', detail: 'Colleagues can edit the fixed template and save revisions. The draft is unsent; this workflow does not offer sending.'},
    ],
    faq: [
      {question: 'What is BuyerOS?', answer: 'BuyerOS is a workspace for buyer criteria, company records, sources, human review and outreach drafts.'},
      {question: 'Who is it for?', answer: 'Teams that organize business-buyer information and review follow-up content together. Explore the sample workflow, then use a demonstration to assess the fit.'},
      {question: 'Does it automatically find real buyers?', answer: 'Research depends on enabled providers, permissions and configuration. This website uses synthetic data. It does not establish actual buyer results or guarantee data coverage or commercial outcomes.'},
      {question: 'Are drafts freely written by AI?', answer: 'The verified workflow can build a fixed template from approved information and sources for human editing. That does not imply free-form AI writing or automatic translation.'},
      {question: 'Does a source mean the information is verified?', answer: 'No. Sources and review history support a human decision. They do not guarantee that third-party information is accurate, complete or current.'},
      {question: 'Will it send messages automatically?', answer: 'This BuyerOS workflow does not offer sending. It saves drafts for review. Future sending availability is unconfirmed.'},
      {question: 'Can I import lists and offer documents?', answer: 'CSV and XLSX lists can be imported, subject to format and row limits. Offer documents can use PDF, PPTX, TXT and MD, with format and file-size limits. Importing does not verify the contents.'},
      {question: 'Which languages are supported?', answer: 'English and Traditional Chinese for Hong Kong are present in the interface. Switching interface language does not automatically translate sources or existing information in drafts.'},
      {question: 'Is it free, and what does it cost?', answer: 'Free access, public pricing and plan details are not confirmed. When the real contact route opens, ask the team about available arrangements. This page makes no free-trial promise.'},
      {question: 'Who can see data, and how are demo requests handled?', answer: 'Product access is scoped by workspace and membership. Real demo intake is currently disabled until the publisher, purposes, recipient, contact details and retention arrangements are confirmed. The local synthetic form accepts fictional data only; its receipt is not a real demo request.'},
    ],
    form: {
      name: 'Name',
      email: 'Work email',
      company: 'Company',
      message: 'Which part of the workflow would you like to improve?',
      optional: 'Optional',
      submit: 'Send demo request',
      pending: 'Submitting…',
      success: 'Your demo request has been received and saved. Your receipt number is below.',
      syntheticSuccess: 'Your local synthetic example has been saved. This is not a real demo request and does not arrange team follow-up.',
      error: 'We could not confirm your submission. Your entries are still here; please try again.',
      unavailable: 'Real demo requests are not open. Intake will be enabled after the recipient, contact details and data handling are confirmed. Explore the sample workflow first.',
      start: 'What would your team like to understand first?',
      privacy: 'Read the privacy notice before submitting to understand this form’s data-handling scope.',
      consent: 'I have read the privacy notice and understand the form mode currently shown.',
      invalidName: 'Enter a name within the field’s allowed length.',
      invalidEmail: 'Enter a valid email address. Synthetic mode accepts fictional .test addresses only.',
      invalidCompany: 'The company name is too long. Shorten it before submitting.',
      invalidMessage: 'The message is too long. Shorten it before submitting.',
      conflict: 'The contents of this retry differ from the earlier submission. Check your entries, then submit again.',
      rateLimited: 'Too many submissions. Please try again later. Your entries are still here.',
      syntheticNotice: 'Local synthetic mode: use fictional details and a .test email address only. This saves a local synthetic receipt; it does not collect a real lead or send email.',
      receiptLabel: 'Submission receipt number',
      retry: 'Retry submission',
      noJavaScript: 'Enable JavaScript to complete the checks required to submit this form safely.',
    },
    sample: {
      criteriaLabel: 'Buyer criteria',
      criteria: 'Industrial sensing equipment suppliers; review relevant product information first.',
      companyLabel: 'Sample company',
      company: 'Clear Isle Equipment Example',
      sourceLabel: 'Fictional source',
      source: 'A fictional product catalogue mentions industrial sensing equipment. This source illustrates the workflow and is not a real research result.',
      reviewLabel: 'Review status',
      review: 'Awaiting human review',
      draftLabel: 'Sample draft · Not sent',
      draftSubject: 'Discussing industrial sensing equipment',
      draftBody: 'We supply industrial sensing equipment and would like to understand whether it is relevant to your team. This fixed-template example still needs a colleague’s review.',
    },
    legal: {
      draftLabel: 'Draft awaiting publisher and legal approval',
      publisherMissing: 'The publisher, data controller and contact details remain unconfirmed. Real demo intake is disabled.',
      controllerLabel: 'Data controller',
      contactLabel: 'Contact for data enquiries',
      retentionLabel: 'Retention and deletion arrangements are unconfirmed. No formal period has been set.',
    },
    pricing: {
      status: 'Plans, prices, seats, usage and included services are not yet confirmed.',
      cta: 'Request a demo to discuss your workflow',
      topics: ['Team size and review practices', 'Existing lists and document formats', 'Required workflow and access', 'Currently available feature scope'],
    },
  },
} satisfies Record<Locale, SiteCopy>;
