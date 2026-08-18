"""Native dashboard UI i18n — Simplified Chinese & Korean."""

from __future__ import annotations

ZH: dict[str, str] = {
    "Avvia": "开始",
    "Salva": "保存",
    "Salva alert": "保存告警",
    "Salva prompt bank": "保存提示词库",
    "Salva white-label": "保存白标",
    "Salva nuova password": "保存新密码",
    "Aggiorna password": "更新密码",
    "Disattivato": "关闭",
    "Ogni giorno": "每天",
    "Ogni settimana": "每周",
    "Frequenza re-scan": "重新扫描频率",
    "Frequenza": "频率",
    "Orario (UTC)": "时间（UTC）",
    "Email alert su regressioni": "回归时发送邮件告警",
    "Prompt bank (un prompt per riga)": "提示词库（每行一条）",
    "Applica pack al prompt bank": "将套件应用到提示词库",
    "— seleziona —": "— 请选择 —",
    "Brand agenzia": "代理商品牌",
    "Colore primario": "主色",
    "Nota piè di pagina": "页脚说明",
    "URL del sito": "网站 URL",
    "Competitor (max 3 URL, uno per riga)": "竞品（最多 3 个 URL，每行一个）",
    "Deep crawl (Plus: più pagine, più lento)": "深度抓取（Plus：更多页面，更慢）",
    "Analisi dominio %(host)s: %(n)s pagine · suite AIO/GEO completa.": (
        "域名分析 %(host)s：%(n)s 个页面 · 完整 AIO/GEO 套件。"
    ),
    "Analisi di %(host)s: suite AIO/GEO completa (content, brand, GEO, tecnico, llms/robots).": (
        "%(host)s 分析：完整 AIO/GEO 套件（内容、品牌、GEO、技术、llms/robots）。"
    ),
    "ChatGPT / Perplexity / Claude / Gemini API / Grok / Azure OpenAI: mention rate da prompt pack. Non è AI Overview o Copilot nativo, né ranking garantito nelle risposte live.": (
        "ChatGPT / Perplexity / Claude / Gemini（AI Overview 代理）/ Grok / "
        "Azure AI（Copilot 代理）：来自提示词包的提及率。"
        "并不等同于实时回答中的保证排名。"
    ),
    "Monitoraggio": "监控",
    "Prossimo:": "下次：",
    "Ultimo": "上次",
    "Schedule attivo, in coda al worker.": "计划已启用，已进入 worker 队列。",
    "Scegli frequenza e orario, poi salva. Il worker Plus/Business esegue i controlli in automatico.": (
        "选择频率和时间后保存。Plus/Business worker 会自动执行检查。"
    ),
    "Misurato (multi-engine probe)": "实测（多引擎探测）",
    "Non disponibile": "不可用",
    "SoV Misurato in corso": "实测 SoV 进行中",
    "SoV Misurato in coda": "实测 SoV 排队中",
    "SoV Misurato in corso: stiamo campionando le citazioni sugli engine. Intanto vedi solo la stima strutturale.": (
        "实测 SoV 进行中：正在对各引擎采样引用。"
        "目前只显示结构性估算。"
    ),
    "SoV Misurato in coda: i probe LLM partono a breve. Intanto vedi solo la stima strutturale.": (
        "实测 SoV 排队中：LLM 探测即将开始。"
        "目前只显示结构性估算。"
    ),
    "SoV Misurato in attesa di coda o budget. Finché i probe non completano, vedi solo la stima strutturale — non è ancora una misurazione live.": (
        "实测 SoV 在等待队列或每日预算。探测完成前，"
        "只显示结构性估算——还不是实时测量。"
    ),
    "Il report Stimato è già pronto. I probe LLM stanno misurando le citazioni in background (1–3 min): i valori Misurati aggiornano questa vista a job completato.": (
        "估算报告已就绪。LLM 探测在后台测量引用（约 1–3 分钟）："
        "任务完成后实测数值会刷新此视图。"
    ),
    # SoV 面板标题（地道中文）
    "Ripartizione per engine IA": "AI 引擎细分",
    "Citation share": "引用份额",
    "Citation share — Misurato · 0 menzioni": "引用份额 — 实测 · 0 次提及",
    "Citation share — Misurato 0 menzioni": "引用份额 — 实测 · 0 次提及",
    "Citation share (stimata · readiness)": "引用份额（估计 · 就绪度）",
    "Citation share brand": "品牌引用份额",
    "AI Engine Breakdown": "AI 引擎细分",
}

KO: dict[str, str] = {
    "Avvia": "시작",
    "Salva": "저장",
    "Salva alert": "알림 저장",
    "Salva prompt bank": "프롬프트 뱅크 저장",
    "Salva white-label": "화이트라벨 저장",
    "Salva nuova password": "새 비밀번호 저장",
    "Aggiorna password": "비밀번호 업데이트",
    "Disattivato": "끔",
    "Ogni giorno": "매일",
    "Ogni settimana": "매주",
    "Frequenza re-scan": "재스캔 주기",
    "Frequenza": "주기",
    "Orario (UTC)": "시간(UTC)",
    "Email alert su regressioni": "회귀 시 이메일 알림",
    "Prompt bank (un prompt per riga)": "프롬프트 뱅크(한 줄에 하나)",
    "Applica pack al prompt bank": "팩을 프롬프트 뱅크에 적용",
    "— seleziona —": "— 선택 —",
    "Brand agenzia": "에이전시 브랜드",
    "Colore primario": "기본 색상",
    "Nota piè di pagina": "바닥글 메모",
    "URL del sito": "사이트 URL",
    "Competitor (max 3 URL, uno per riga)": "경쟁사(최대 3개 URL, 한 줄에 하나)",
    "Deep crawl (Plus: più pagine, più lento)": "딥 크롤(Plus: 더 많은 페이지, 더 느림)",
    "Analisi dominio %(host)s: %(n)s pagine · suite AIO/GEO completa.": (
        "도메인 분석 %(host)s: %(n)s페이지 · 전체 AIO/GEO 스위트."
    ),
    "Analisi di %(host)s: suite AIO/GEO completa (content, brand, GEO, tecnico, llms/robots).": (
        "%(host)s 분석: 전체 AIO/GEO 스위트(콘텐츠, 브랜드, GEO, 기술, llms/robots)."
    ),
    "ChatGPT / Perplexity / Claude / Gemini API / Grok / Azure OpenAI: mention rate da prompt pack. Non è AI Overview o Copilot nativo, né ranking garantito nelle risposte live.": (
        "ChatGPT / Perplexity / Claude / Gemini(AI Overview 프록시) / Grok / "
        "Azure AI(Copilot 프록시): 프롬프트 팩 기반 멘션률. "
        "라이브 응답의 보장된 순위와는 다릅니다."
    ),
    "Monitoraggio": "모니터링",
    "Prossimo:": "다음:",
    "Ultimo": "최근",
    "Schedule attivo, in coda al worker.": "스케줄 활성, 워커 대기열에 있음.",
    "Scegli frequenza e orario, poi salva. Il worker Plus/Business esegue i controlli in automatico.": (
        "주기와 시간을 선택한 뒤 저장하세요. Plus/Business 워커가 자동으로 검사를 실행합니다."
    ),
    "Misurato (multi-engine probe)": "실측(멀티 엔진 프로브)",
    "Non disponibile": "사용 불가",
    "SoV Misurato in corso": "실측 SoV 진행 중",
    "SoV Misurato in coda": "실측 SoV 대기열",
    "SoV Misurato in corso: stiamo campionando le citazioni sugli engine. Intanto vedi solo la stima strutturale.": (
        "실측 SoV 진행 중: 엔진별 인용을 샘플링하고 있습니다. "
        "지금은 구조적 추정만 보입니다."
    ),
    "SoV Misurato in coda: i probe LLM partono a breve. Intanto vedi solo la stima strutturale.": (
        "실측 SoV 대기열: LLM 프로브가 곧 시작됩니다. "
        "지금은 구조적 추정만 보입니다."
    ),
    "SoV Misurato in attesa di coda o budget. Finché i probe non completano, vedi solo la stima strutturale — non è ancora una misurazione live.": (
        "실측 SoV가 대기열 또는 일일 예산을 기다립니다. 프로브가 끝날 때까지 "
        "구조적 추정만 보입니다 — 아직 실시간 측정이 아닙니다."
    ),
    "Il report Stimato è già pronto. I probe LLM stanno misurando le citazioni in background (1–3 min): i valori Misurati aggiornano questa vista a job completato.": (
        "추정 리포트는 이미 준비되었습니다. LLM 프로브가 백그라운드에서 인용을 측정합니다"
        "(1–3분): 작업이 끝나면 실측 값이 이 화면을 갱신합니다."
    ),
    # SoV 패널 제목 (자연스러운 한국어)
    "Ripartizione per engine IA": "AI 엔진별 분석",
    "Citation share": "인용 점유율",
    "Citation share — Misurato · 0 menzioni": "인용 점유율 — 실측 · 언급 0건",
    "Citation share — Misurato 0 menzioni": "인용 점유율 — 실측 · 언급 0건",
    "Citation share (stimata · readiness)": "인용 점유율(추정 · 준비도)",
    "Citation share brand": "브랜드 인용 점유율",
    "AI Engine Breakdown": "AI 엔진별 분석",
}
