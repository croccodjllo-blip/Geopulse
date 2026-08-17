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
}
