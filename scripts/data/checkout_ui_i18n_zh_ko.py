"""Native-quality UI/checkout/waiver i18n — Simplified Chinese & Korean."""

from __future__ import annotations

# Simplified Chinese (zh-CN) — clear B2B SaaS Mandarin
ZH: dict[str, str] = {
    "Checkout": "结账",
    "Conferma obbligatoria prima del pagamento": "付款前必须确认",
    "Per aprire il checkout Paddle conferma l’erogazione immediata del servizio digitale. Vale anche se hai già un piano (rinnovo / aggiornamento metodo di pagamento).": (
        "要打开 Paddle 结账，请确认立即提供数字服务。"
        "即使您已有套餐（续订 / 更新付款方式），也需要确认。"
    ),
    "Chiedo l’erogazione immediata del servizio digitale (attivazione piano o accredito crediti) e riconosco di perdere il diritto di recesso di 14 giorni una volta iniziata l’erogazione, ai sensi della": (
        "我要求立即提供数字服务（开通套餐或充值额度），"
        "并确认服务开始提供后即失去 14 天冷静期/撤回权，依据"
    ),
    "Politica di rimborso": "退款政策",
    "Spunta la casella per continuare.": "请勾选后继续。",
    "Continua al pagamento": "继续付款",
    "Annulla": "取消",
    "Obbligatorio per procedere al checkout.": "结账前必须勾选。",
    "Obbligatorio per aprire il checkout Paddle. Senza spunta, il pagamento non parte.": (
        "打开 Paddle 结账前必须勾选。未勾选将无法开始付款。"
    ),
    "Paga Plus · 14,99€/mese": "支付 Plus · €14.99/月",
    "Apri checkout / aggiorna pagamento": "打开结账 / 更新付款方式",
    "Paga Business": "支付 Business",
    "Accedi e scegli Plus": "登录并选择 Plus",
    "Prenota Plus": "预约 Plus",
    "Apri DPA": "打开 DPA",
    "Scarica DPA (.txt)": "下载 DPA（.txt）",
    "Scarica DPA": "下载 DPA",
    "Download .txt": "下载 .txt",
    "Trust & security": "信任与安全",
    "Trust Centropic: sicurezza, sub-responsabili, retention, DPA Art. 28 e canali di supporto per procurement SaaS.": (
        "Centropic 信任中心：安全、分包处理方、数据留存、第 28 条 DPA，以及面向 SaaS 采购的支持渠道。"
    ),
    "FAQ Centropic": "Centropic 常见问题",
    "Cookie Policy": "Cookie 政策",
    "Dichiarazione di accessibilità": "无障碍声明",
    "Prodotto": "产品",
    "Analizzato": "已分析",
    "AIO/GEO sono sempre Stimato: predisposizione strutturale dal crawl. Il tab SoV mostra Misurato quando il citation monitor ha campionato gli engine (anche con 0 menzioni).": (
        "AIO/GEO 始终为“估算”：来自抓取的结构就绪度。当引用监测已对引擎完成采样时（即使提及次数为 0），"
        "SoV 选项卡会显示“实测”。"
    ),
    "Sintesi score": "分数摘要",
    "Citation share — probe Misurato eseguito": "引用份额 — 实测探测已完成",
    "Probe LLM eseguito: 0 menzioni su questo engine": "LLM 探测已完成：该引擎提及 0 次",
    "Misurato · 0": "实测 · 0",
    "Vai a": "前往",
    "White-label": "白标",
    "Se richiedi l’erogazione immediata del servizio (accesso al piano o accredito crediti) e riconosci di perdere il diritto di recesso una volta iniziata l’erogazione, il recesso non si applica dopo che il servizio è stato avviato. Il consenso è raccolto con checkbox esplicita prima del checkout Plus/crediti.": (
        "若您要求立即提供服务（开通套餐或充值额度），并确认服务开始后即失去撤回权，"
        "则服务启动后不再适用撤回。同意通过 Plus/额度结账前的显式复选框收集。"
    ),
    "Legale:": "法律：",
    "Crawl, score e pack. Su Plus il SoV measured arriva in background dopo il report.": (
        "抓取、评分与 pack。Plus 上，实测 SoV 会在报告之后于后台到达。"
    ),
    "Stima: 30–90 secondi per crawl e pack": "预计：抓取与 pack 约 30–90 秒",
    "Di solito 30–90 s. Il SoV measured Plus non blocca questa schermata.": (
        "通常 30–90 秒。Plus 的实测 SoV 不会阻塞此界面。"
    ),
    "Avanzamento in tempo reale · report pronto dopo crawl/pack": (
        "实时进度 · 抓取/pack 完成后报告就绪"
    ),
    "AIO/GEO e CVI allineati sul tuo brand e sui rivali del campione.": (
        "AIO/GEO 与 CVI 对齐到您的品牌及样本中的竞品。"
    ),
    "Tu": "您",
    "Tua soglia": "您的阈值",
    "Il tuo brand": "您的品牌",
    "Snapshot non disponibile": "快照不可用",
    "n/d": "无",
    "vs te": "对比您",
    "Rivale": "竞品",
    "Tuo AIO": "您的 AIO",
    "Tuo GEO": "您的 GEO",
    "ricevi un bonus quando attiva il piano Plus.": "对方开通 Plus 套餐后您将获得奖励。",
    "URL · crawl · score": "URL · 抓取 · 评分",
    "Dominio da analizzare": "待分析域名",
    "SoV measured in aggiornamento": "实测 SoV 更新中",
    "Il report Stimato è già pronto. Le citation Misurate arrivano in background (1–3 min) senza bloccare la dashboard.": (
        "估算报告已就绪。实测引用将在后台到达（1–3 分钟），不会阻塞控制台。"
    ),
    # Primary CTAs
    "Analizza gratis": "免费分析",
    "Analizza il tuo sito": "分析你的网站",
    "Analizza il tuo dominio": "分析你的域名",
    "Analizza un sito": "分析网站",
    "Inizia gratis": "免费开始",
    "Passa a Plus": "升级到 Plus",
    "Chiudi": "关闭",
    "Continua": "继续",
    "Apri dashboard": "打开控制台",
}

# Korean (ko-KR) — polite formal 합니다체 for B2B
KO: dict[str, str] = {
    "Checkout": "결제",
    "Conferma obbligatoria prima del pagamento": "결제 전 필수 확인",
    "Per aprire il checkout Paddle conferma l’erogazione immediata del servizio digitale. Vale anche se hai già un piano (rinnovo / aggiornamento metodo di pagamento).": (
        "Paddle 결제를 열려면 디지털 서비스의 즉시 제공에 동의해 주세요. "
        "이미 요금제를 이용 중인 경우(갱신 / 결제 수단 변경)에도 동일하게 적용됩니다."
    ),
    "Chiedo l’erogazione immediata del servizio digitale (attivazione piano o accredito crediti) e riconosco di perdere il diritto di recesso di 14 giorni una volta iniziata l’erogazione, ai sensi della": (
        "디지털 서비스의 즉시 제공(요금제 활성화 또는 크레딧 충전)을 요청하며, "
        "제공이 시작되면 14일 철회권을 상실함을 인정합니다. 근거:"
    ),
    "Politica di rimborso": "환불 정책",
    "Spunta la casella per continuare.": "계속하려면 체크박스를 선택하세요.",
    "Continua al pagamento": "결제 계속하기",
    "Annulla": "취소",
    "Obbligatorio per procedere al checkout.": "결제를 진행하려면 필수입니다.",
    "Obbligatorio per aprire il checkout Paddle. Senza spunta, il pagamento non parte.": (
        "Paddle 결제를 열려면 필수입니다. 체크하지 않으면 결제가 시작되지 않습니다."
    ),
    "Paga Plus · 14,99€/mese": "Plus 결제 · €14.99/월",
    "Apri checkout / aggiorna pagamento": "결제 열기 / 결제 수단 업데이트",
    "Paga Business": "Business 결제",
    "Accedi e scegli Plus": "로그인 후 Plus 선택",
    "Prenota Plus": "Plus 대기 신청",
    "Apri DPA": "DPA 열기",
    "Scarica DPA (.txt)": "DPA 다운로드 (.txt)",
    "Scarica DPA": "DPA 다운로드",
    "Download .txt": ".txt 다운로드",
    "Trust & security": "신뢰 및 보안",
    "Trust Centropic: sicurezza, sub-responsabili, retention, DPA Art. 28 e canali di supporto per procurement SaaS.": (
        "Centropic 신뢰 센터: 보안, 하위처리자, 보관 기간, 제28조 DPA 및 SaaS 조달용 지원 채널."
    ),
    "FAQ Centropic": "Centropic FAQ",
    "Cookie Policy": "쿠키 정책",
    "Dichiarazione di accessibilità": "접근성 선언",
    "Prodotto": "제품",
    "Analizzato": "분석됨",
    "AIO/GEO sono sempre Stimato: predisposizione strutturale dal crawl. Il tab SoV mostra Misurato quando il citation monitor ha campionato gli engine (anche con 0 menzioni).": (
        "AIO/GEO는 항상 추정값입니다(크롤 기반 구조 준비도). 인용 모니터가 엔진을 샘플링하면 "
        "(언급 0회여도) SoV 탭에 실측이 표시됩니다."
    ),
    "Sintesi score": "점수 요약",
    "Citation share — probe Misurato eseguito": "인용 점유율 — 실측 프로브 완료",
    "Probe LLM eseguito: 0 menzioni su questo engine": "LLM 프로브 완료: 이 엔진에서 언급 0회",
    "Misurato · 0": "실측 · 0",
    "Vai a": "이동",
    "White-label": "화이트라벨",
    "Se richiedi l’erogazione immediata del servizio (accesso al piano o accredito crediti) e riconosci di perdere il diritto di recesso una volta iniziata l’erogazione, il recesso non si applica dopo che il servizio è stato avviato. Il consenso è raccolto con checkbox esplicita prima del checkout Plus/crediti.": (
        "서비스의 즉시 제공(요금제 이용 또는 크레딧 충전)을 요청하고 제공 시작 시 철회권을 상실함을 인정하면, "
        "서비스가 시작된 후에는 철회가 적용되지 않습니다. 동의는 Plus/크레딧 결제 전 명시적 체크박스로 수집됩니다."
    ),
    "Legale:": "법률:",
    "Crawl, score e pack. Su Plus il SoV measured arriva in background dopo il report.": (
        "크롤, 점수, 팩. Plus에서는 실측 SoV가 리포트 이후 백그라운드로 도착합니다."
    ),
    "Stima: 30–90 secondi per crawl e pack": "예상: 크롤·팩 30–90초",
    "Di solito 30–90 s. Il SoV measured Plus non blocca questa schermata.": (
        "보통 30–90초. Plus 실측 SoV는 이 화면을 막지 않습니다."
    ),
    "Avanzamento in tempo reale · report pronto dopo crawl/pack": (
        "실시간 진행 · 크롤/팩 후 리포트 준비"
    ),
    "AIO/GEO e CVI allineati sul tuo brand e sui rivali del campione.": (
        "샘플의 브랜드·경쟁사에 맞춘 AIO/GEO 및 CVI."
    ),
    "Tu": "나",
    "Tua soglia": "내 기준선",
    "Il tuo brand": "내 브랜드",
    "Snapshot non disponibile": "스냅샷 없음",
    "n/d": "없음",
    "vs te": "나와 비교",
    "Rivale": "경쟁사",
    "Tuo AIO": "내 AIO",
    "Tuo GEO": "내 GEO",
    "ricevi un bonus quando attiva il piano Plus.": (
        "추천인이 Plus 요금제를 활성화하면 보너스를 받습니다."
    ),
    "URL · crawl · score": "URL · 크롤 · 점수",
    "Dominio da analizzare": "분석할 도메인",
    "SoV measured in aggiornamento": "실측 SoV 업데이트 중",
    "Il report Stimato è già pronto. Le citation Misurate arrivano in background (1–3 min) senza bloccare la dashboard.": (
        "추정 리포트는 이미 준비되었습니다. 실측 인용은 백그라운드(1–3분)로 도착하며 대시보드를 막지 않습니다."
    ),
    # Primary CTAs
    "Analizza gratis": "무료 분석",
    "Analizza il tuo sito": "내 사이트 분석",
    "Analizza il tuo dominio": "내 도메인 분석",
    "Analizza un sito": "사이트 분석",
    "Inizia gratis": "무료로 시작",
    "Passa a Plus": "Plus로 업그레이드",
    "Chiudi": "닫기",
    "Continua": "계속",
    "Apri dashboard": "대시보드 열기",
}
