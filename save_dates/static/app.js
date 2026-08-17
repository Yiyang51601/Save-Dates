const $ = (id) => document.getElementById(id);

const STRINGS = {
  zh: {
    eyebrow: "Outlook → 确认 → 日历",
    lede: "有日期的进日历，没写时间的进待办，广告进广告页。点 ✓ 才会写入或清掉。",
    settings: "设置",
    language: "语言",
    backend: "连接",
    backendAuto: "自动（优先经典 Outlook）",
    backendClassic: "经典 Outlook",
    backendGraph: "新 Outlook（进阶）",
    classicHint: "未连接时点红色「未连接」可选经典 Outlook 或登录 Microsoft。选过一次就会记住。",
    connectPickerTitle: "选择邮箱连接方式",
    connectPickerLede: "请选一种。选完后会记住，不会反复弹出。",
    pickClassicTitle: "经典 Outlook",
    pickClassicHelp: "打开 outlook.exe 并保持运行。软件通过 COM 读取邮件。",
    pickGraphTitle: "新 Outlook / 登录 Microsoft",
    pickGraphHelp: "用 Microsoft 账号登录。不用填写应用 ID。",
    connectPickerLater: "稍后再说",
    pickingClassic: "已选择经典 Outlook。请打开 outlook.exe 并保持运行。",
    offlinePickHint: "未连接。点击此处选择经典 Outlook，或登录 Microsoft。",
    choose_connection: "未连接。点击此处选择经典 Outlook，或登录 Microsoft。",
    advancedNewOutlook: "进阶 · 仅新 Outlook",
    advancedHelp: "只有不用经典 Outlook、只开新 Outlook 时，才点下面登录 Microsoft。不用填写应用 ID。",
    loginMs: "登录 Microsoft",
    logoutMs: "退出账号",
    loggingIn: "正在打开 Microsoft 登录页…",
    msConnected: "已用 Microsoft 账号连接。日程会写到同一邮箱的日历。",
    graphClientId: "应用程序 ID（本地覆盖）",
    graphOverride: "开发者：本地覆盖应用 ID",
    saveClientId: "保存",
    openEntra: "开发者：打开 Entra",
    graphHelp: "软件已内置公共客户端 ID，朋友直接点「登录 Microsoft」即可。仅本地调试才需要覆盖。",
    liveTitleGraph: "实时同步 · {account}",
    liveMetaGraph: "新 Outlook / Microsoft 365 · 时区 {timezone}",
    new_outlook_detected: "检测到新 Outlook。请选择经典 Outlook，或登录 Microsoft。",
    graph_login_needed: "请登录 Microsoft 账号以连接新 Outlook。",
    graph_client_id_missing: "还没有可用的 Microsoft 应用 ID。请改用经典 Outlook，或在下方填写本地覆盖 ID。",
    graph_auth_failed: "Microsoft 登录失败。",
    graph_auth_cancelled: "已取消 Microsoft 登录。",
    graph_request_failed: "Microsoft 邮箱请求失败。",
    recent: "最近",
    days: "天",
    maxScan: "最多扫描",
    emails: "封",
    includeProcessed: "包含已处理邮件",
    scanBtn: "补扫",
    demoBtn: "示例",
    searchPlaceholder: "搜邮件里的活动",
    searchHint: "输入任意关键词，中英文都能搜。点加入才会进日历。",
    searchSearching: "正在搜索最近邮件…",
    searchEmpty: "最近邮件里没有找到相关内容。",
    searchLive: "已在最近收件箱中查找 {n} 封。",
    searchSaved: "待确认",
    searchAccepted: "已加入",
    searchInbox: "收件箱",
    searchMailOnly: "未识别出活动",
    searchOpen: "原邮件",
    empty: "在等新邮件。讲座通知、导师往来里的日期会出现在这里。",
    emptyTasks: "暂无待办。没写时间的作业、待约见面、等回复会出现在这里。",
    emptyPromo: "暂无广告。带退订、优惠券的推销邮件会出现在这里，点清掉才进垃圾箱。",
    laneEvent: "日程",
    laneTask: "待办",
    lanePromo: "广告",
    mailboxAll: "全部邮箱",
    promoKind: "广告",
    acceptPromo: "清掉",
    addedPromo: "已移到 Outlook 垃圾箱。",
    addedPromoLocal: "已从列表拿掉。没连上 Outlook 时，邮件还在收件箱。",
    taskKind: "待办",
    taskHomework: "作业",
    taskMeet: "待约",
    taskFollowup: "跟进",
    counts: "待确认 {pending} · 已加入 {accepted} · 已跳过 {rejected}",
    offlineTitle: "未连接",
    allDay: "全天",
    around: "大约",
    received: "{time}",
    fromMail: "{sender} · {subject} · {received}",
    match: "{text} · {n}%",
    accept: "加入",
    acceptTask: "记下",
    reject: "跳过",
    openMail: "原邮件",
    batchAccept: "加入所选",
    batchReject: "跳过所选",
    selected: "已选 {n} 条",
    checking: "正在检查 Outlook…",
    timezonePending: "时区待读取",
    liveTitle: "监听中 · {account}",
    liveMeta: "{timezone}",
    connectedTitle: "已连接 {account}",
    connectedMeta: "{timezone}",
    offlineMeta: "请打开经典 Outlook（outlook.exe）并保持运行，或点击状态栏选择登录 Microsoft",
    serviceDown: "服务未就绪",
    month: "{n}月",
    weekdays: ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
    scanning: "正在补扫历史邮件并识别日期，稍等片刻…",
    scanned: "扫描 {scanned} 封邮件，发现 {found} 项，新增待确认 {added} 条。已跳过 {skipped} 封会议邀请。",
    demoLoaded: "已加载示例。用上面的「日程 / 待办 / 广告」切换。示例不能跳转 Outlook；真实邮件才可以。",
    addedCalendar: "已写入 Outlook 日历。",
    addedTask: "已记入 Outlook 任务。",
    addedTaskLocal: "已记下待办。Outlook 未连接或无法写入任务时，会先保存在这里。",
    skipped: "已跳过。点撤回可以改回来。",
    batchDone: "已处理 {n} 条",
    batchPartial: "已处理 {n} 条，部分失败：{errors}",
    newDates: "新邮件里发现 {n} 项，请确认。",
    openedMail: "已在 Outlook 中打开原邮件。",
    undo: "撤回",
    undone: "已撤回，这条又回到待确认。",
    undonePartial: "已撤回。Outlook 里那条可能还在，请到日历或任务里手动删一下。",
    requestFailed: "请求失败",
    outlook_connecting: "正在连接 Outlook…",
    outlook_not_running: "无法连接经典 Outlook。请打开 outlook.exe 并保持运行。",
    outlook_not_connected: "尚未连接 Outlook。",
    outlook_closed: "Outlook 已关闭，正在等待重新打开…",
    mail_not_found: "找不到原邮件，可能已被删除或移走。",
    mail_is_demo: "这是示例卡片，没有真实 Outlook 邮件可打开。",
    mail_open_failed: "打开原邮件失败，请确认 Outlook 正在运行。",
    candidate_missing: "找不到这条候选日程。",
    conflict_duplicate: "这个标题和日期已在待确认列表里，请改一下再保存。",
    calendar_write_failed: "写入日历失败。",
    scan_failed: "扫描 Outlook 失败。",
    invalid_status: "无效状态",
    invalid_action: "无效操作",
  },
  en: {
    eyebrow: "Outlook → review → calendar",
    lede: "Dated items go to the calendar, open loops to tasks, ads to Junk after you confirm.",
    settings: "Settings",
    language: "Language",
    backend: "Connect",
    backendAuto: "Auto (Classic Outlook first)",
    backendClassic: "Classic Outlook",
    backendGraph: "New Outlook (advanced)",
    classicHint: "When offline, click the red Offline pill to choose Classic Outlook or Microsoft sign-in. We remember the choice.",
    connectPickerTitle: "How do you want to connect?",
    connectPickerLede: "Pick one. We’ll remember it and won’t keep asking.",
    pickClassicTitle: "Classic Outlook",
    pickClassicHelp: "Open outlook.exe and leave it running. Save Dates talks to it over COM.",
    pickGraphTitle: "New Outlook / Sign in to Microsoft",
    pickGraphHelp: "Sign in with your Microsoft account. You do not type an Application ID.",
    connectPickerLater: "Not now",
    pickingClassic: "Classic Outlook selected. Open outlook.exe and leave it running.",
    offlinePickHint: "Not connected. Click here to choose Classic Outlook or Microsoft sign-in.",
    choose_connection: "Not connected. Click here to choose Classic Outlook or Microsoft sign-in.",
    advancedNewOutlook: "Advanced · New Outlook only",
    advancedHelp: "Use this only if you do not have Classic Outlook. Click Sign in to Microsoft. You do not type an Application ID.",
    loginMs: "Sign in to Microsoft",
    logoutMs: "Sign out",
    loggingIn: "Opening the Microsoft sign-in page…",
    msConnected: "Signed in with Microsoft. Events go to the same mailbox calendar.",
    graphClientId: "Application ID (local override)",
    graphOverride: "Developer: local App ID override",
    saveClientId: "Save",
    openEntra: "Developer: open Entra",
    graphHelp: "The app already ships a public client ID. Friends just click Sign in. Override this only for local debugging.",
    liveTitleGraph: "Live sync · {account}",
    liveMetaGraph: "New Outlook / Microsoft 365 · {timezone}",
    new_outlook_detected: "New Outlook is running. Choose Classic Outlook, or sign in with Microsoft.",
    graph_login_needed: "Sign in with Microsoft to connect New Outlook.",
    graph_client_id_missing: "No Microsoft app ID is available. Use Classic Outlook, or enter a local override below.",
    graph_auth_failed: "Microsoft sign-in failed.",
    graph_auth_cancelled: "Microsoft sign-in was cancelled.",
    graph_request_failed: "The Microsoft mailbox request failed.",
    recent: "Last",
    days: "days",
    maxScan: "Scan up to",
    emails: "emails",
    includeProcessed: "Include processed mail",
    scanBtn: "Scan",
    demoBtn: "Sample",
    searchPlaceholder: "Search mail for events",
    searchHint: "Type any keyword — Chinese and English both work. Nothing is added to the calendar until you confirm.",
    searchSearching: "Searching recent mail…",
    searchEmpty: "No matching mail in recent messages.",
    searchLive: "Looked through {n} recent inbox messages.",
    searchSaved: "To review",
    searchAccepted: "Added",
    searchInbox: "Inbox",
    searchMailOnly: "No event extracted",
    searchOpen: "Mail",
    empty: "Waiting for mail. Lectures, advisor threads, and other dates show up here.",
    emptyTasks: "No open loops yet. Homework without a due date, unscheduled meetings, and waiting-for-a-reply items show up here.",
    emptyPromo: "No ads yet. Promos with unsubscribe or coupons show up here. Nothing is junked until you clear it.",
    laneEvent: "Calendar",
    laneTask: "Tasks",
    lanePromo: "Ads",
    mailboxAll: "All inboxes",
    promoKind: "Ad",
    acceptPromo: "Junk",
    addedPromo: "Moved to Junk Email.",
    addedPromoLocal: "Removed from this list. The message is still in the inbox because Outlook is not connected.",
    taskKind: "Task",
    taskHomework: "Homework",
    taskMeet: "To schedule",
    taskFollowup: "Follow-up",
    batchAccept: "Add selected",
    batchReject: "Skip selected",
    selected: "{n} selected",
    counts: "{pending} to review · {accepted} added · {rejected} skipped",
    checking: "Checking Outlook…",
    timezonePending: "Timezone pending",
    liveTitle: "Live · {account}",
    liveMeta: "{timezone}",
    liveTitleGraph: "Live · {account}",
    liveMetaGraph: "{timezone}",
    connectedTitle: "Connected · {account}",
    connectedMeta: "{timezone}",
    offlineTitle: "Offline",
    offlineMeta: "Open Classic Outlook (outlook.exe) and leave it running, or click the status pill to sign in with Microsoft.",
    serviceDown: "Service not ready",
    allDay: "All day",
    around: "Around",
    month: "{n}",
    received: "{time}",
    fromMail: "{sender} · {subject} · {received}",
    match: "{text} · {n}%",
    accept: "Add",
    acceptTask: "Save",
    reject: "Skip",
    openMail: "Mail",
    weekdays: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    scanning: "Scanning mail and extracting dates…",
    scanned: "Scanned {scanned} messages, found {found} items, added {added} to review. Skipped {skipped} meeting invites.",
    demoLoaded: "Sample loaded. Use Calendar / Tasks / Ads above to switch. Samples cannot open Outlook; real messages can.",
    addedCalendar: "Added to the Outlook calendar.",
    addedTask: "Saved to Outlook Tasks.",
    addedTaskLocal: "Saved as a task here. Outlook was not connected or could not write a task.",
    skipped: "Skipped. Undo if that was a mistake.",
    batchDone: "Processed {n} item(s)",
    batchPartial: "Processed {n} item(s), some failed: {errors}",
    newDates: "Found {n} item(s) in new mail. Confirm before they are saved.",
    openedMail: "Opened the original message in Outlook.",
    undo: "Undo",
    undone: "Undone. It’s back in the review list.",
    undonePartial: "Undone here. The Outlook item may still exist — delete it there if needed.",
    requestFailed: "Request failed",
    outlook_connecting: "Connecting to Outlook…",
    outlook_not_running: "Could not connect to Classic Outlook. Open outlook.exe and leave it running.",
    outlook_not_connected: "Outlook is not connected.",
    outlook_closed: "Outlook closed. Waiting for it to reopen…",
    mail_not_found: "The original message could not be found. It may have been deleted or moved.",
    mail_is_demo: "This is a sample card, so there is no real Outlook message to open.",
    mail_open_failed: "Could not open the original message. Make sure Outlook is running.",
    candidate_missing: "This review item was not found.",
    conflict_duplicate: "This title and date are already in the pending list. Change one of them and save again.",
    calendar_write_failed: "Could not write to the calendar.",
    scan_failed: "Outlook scan failed.",
    invalid_status: "Invalid status",
    invalid_action: "Invalid action",
  },
};

let lang = "zh";
let lastItems = [];
let lastStatus = null;
let currentLane = "event";
let currentMailbox = "";
let lastUndoIds = [];
let lastSearchQuery = "";
let lastSearchItems = [];
let lastSearchMeta = { scanned: 0, live: false };
let searchTimer = 0;
let searchSeq = 0;
let connectPickerAutoShown = false;

function t(key, vars = {}) {
  const table = STRINGS[lang] || STRINGS.zh;
  let text = table[key] ?? STRINGS.zh[key] ?? key;
  if (typeof text !== "string") return text;
  return text.replace(/\{(\w+)\}/g, (_, name) => (vars[name] ?? ""));
}

function applyI18n() {
  document.documentElement.lang = lang === "en" ? "en" : "zh-CN";
  document.body.dataset.lang = lang;
  document.title = lang === "en" ? "Save Dates" : "Save Dates";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.getAttribute("data-i18n-placeholder"));
  });
  document.querySelectorAll("#langSeg [data-lang]").forEach((btn) => {
    btn.classList.toggle("on", btn.dataset.lang === lang);
  });
  updateLaneButtons(lastItems);
  if (lastStatus) applyStatus(lastStatus);
  if (lastItems.length) render(lastItems);
  if (lastSearchQuery) renderSearch(lastSearchItems, lastSearchQuery, lastSearchMeta);
}

function pad(n) {
  return String(n).padStart(2, "0");
}

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function parseTs(value) {
  if (!value) return new Date(NaN);
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split("-").map(Number);
    return new Date(y, m - 1, d);
  }
  const local = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (local && !/Z|[+-]\d{2}:\d{2}$/.test(value)) {
    return new Date(
      Number(local[1]),
      Number(local[2]) - 1,
      Number(local[3]),
      Number(local[4]),
      Number(local[5])
    );
  }
  return new Date(value);
}

function toLocalInput(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function toDateInput(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function fmtReceived(value) {
  const d = parseTs(value);
  if (lang === "en") {
    return d.toLocaleString("en", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  }
  return `${d.getMonth() + 1}月${d.getDate()}日 ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fmtTime(date, allDay) {
  if (allDay) return t("allDay");
  if (lang === "en") {
    return date.toLocaleString("en", { hour: "numeric", minute: "2-digit" });
  }
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fmtMonth(date) {
  if (lang === "en") return date.toLocaleString("en", { month: "short" }).toUpperCase();
  return t("month", { n: date.getMonth() + 1 });
}

function highlight(snippet, matched) {
  const safe = snippet.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  if (!matched) return safe;
  const m = matched.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  return safe.replace(m, `<mark>${m}</mark>`);
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightQuery(snippet, query, fragment) {
  const safe = escapeHtml(snippet || "");
  const needle = fragment || query;
  if (!needle) return safe;
  try {
    const re = new RegExp(escapeRegExp(needle), "ig");
    const marked = safe.replace(re, (m) => `<mark>${m}</mark>`);
    if (marked !== safe) return marked;
  } catch {
    return safe;
  }
  return safe;
}

function setBanner(text, isError = false, undoIds = []) {
  const el = $("banner");
  const textEl = $("bannerText");
  const undoBtn = $("undoBtn");
  lastUndoIds = Array.isArray(undoIds) ? undoIds : [];
  if (!text) {
    el.classList.add("hidden");
    if (textEl) textEl.textContent = "";
    if (undoBtn) undoBtn.classList.add("hidden");
    return;
  }
  el.classList.remove("hidden");
  el.classList.toggle("error", isError);
  if (textEl) textEl.textContent = text;
  else el.textContent = text;
  if (undoBtn) undoBtn.classList.toggle("hidden", lastUndoIds.length === 0 || isError);
}

function setCounts(counts) {
  const c = counts || { pending: 0, accepted: 0, rejected: 0 };
  $("counts").textContent = t("counts", {
    pending: c.pending || 0,
    accepted: c.accepted || 0,
    rejected: c.rejected || 0,
  });
}

function translateError(message) {
  if (!message) return t("requestFailed");
  if (STRINGS[lang][message] || STRINGS.zh[message]) return t(message);
  return message;
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", "X-Lang": lang },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(translateError(formatDetail(data)));
  }
  return data;
}

function formatDetail(data) {
  const detail = data.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
  }
  return data.message || "requestFailed";
}

function applyStatus(s) {
  lastStatus = s;
  const hello = $("hello");
  if (hello) hello.textContent = s.greeting || "";
  const live = Boolean(s.watching && s.connected);
  $("statusDot").className = `status-dot ${live ? "live" : s.connected ? "ok" : "bad"}`;
  if (live && s.backend === "graph") {
    $("statusTitle").textContent = t("liveTitleGraph", { account: s.account || "Microsoft 365" });
    $("statusMeta").textContent = t("liveMetaGraph", { timezone: s.timezone || "" });
  } else if (live) {
    $("statusTitle").textContent = t("liveTitle", { account: s.account || "Outlook" });
    $("statusMeta").textContent = t("liveMeta", { timezone: s.timezone || "" });
  } else if (s.connected) {
    $("statusTitle").textContent = t("connectedTitle", { account: s.account || "" });
    $("statusMeta").textContent = s.error ? translateError(s.error) : t("connectedMeta", { timezone: s.timezone || "" });
  } else {
    $("statusTitle").textContent = t("offlineTitle");
    const pref = s.settings?.backend || "auto";
    if (pref === "auto") {
      $("statusMeta").textContent = t("offlinePickHint");
    } else {
      $("statusMeta").textContent = translateError(s.error) || t("offlineMeta");
    }
  }
  const pill = $("statusCard");
  if (pill) {
    const pickable = !s.connected;
    pill.classList.toggle("pickable", pickable);
    pill.setAttribute("role", pickable ? "button" : "status");
    pill.tabIndex = pickable ? 0 : -1;
    pill.setAttribute("aria-haspopup", pickable ? "dialog" : "false");
  }
  setCounts(s.counts);
  if (s.settings?.backend) $("backendSelect").value = s.settings.backend;
  if (s.settings?.graph_client_id && !$("graphClientId").value) {
    $("graphClientId").value = s.settings.graph_client_id;
  }
  $("msLoginBtn").classList.toggle("hidden", Boolean(s.graph_logged_in));
  $("msLogoutBtn").classList.toggle("hidden", !s.graph_logged_in);
  const bundled = Boolean(s.settings?.has_bundled_graph_client);
  const savedId = Boolean(s.settings?.graph_client_id);
  const needId = !bundled && !savedId;
  const showOverride = needId && (
    s.error === "graph_client_id_missing" || s.settings?.backend === "graph"
  );
  if (showOverride) {
    $("advancedBox").open = true;
    $("graphSetup").open = true;
  } else if (s.settings?.backend === "graph") {
    $("advancedBox").open = true;
  }
  maybeOfferConnectPicker(s);
}

function maybeOfferConnectPicker(s, force = false) {
  const overlay = $("connectPicker");
  if (!overlay) return;
  if (!s || s.connected) {
    hideConnectPicker();
    if (s?.connected) connectPickerAutoShown = false;
    return;
  }
  if (force) {
    connectPickerAutoShown = true;
    showConnectPicker();
    return;
  }
  if (!overlay.classList.contains("hidden")) return;
  if (connectPickerAutoShown) return;
  const pref = s.settings?.backend || "auto";
  if (pref !== "auto") return;
  connectPickerAutoShown = true;
  showConnectPicker();
}

function showConnectPicker() {
  const overlay = $("connectPicker");
  if (!overlay) return;
  overlay.classList.remove("hidden");
  document.body.classList.add("modal-open");
  const first = $("pickClassic");
  if (first) first.focus();
}

function hideConnectPicker() {
  const overlay = $("connectPicker");
  if (!overlay) return;
  overlay.classList.add("hidden");
  document.body.classList.remove("modal-open");
}

function openConnectPickerFromStatus() {
  if (!lastStatus || lastStatus.connected) return;
  maybeOfferConnectPicker(lastStatus, true);
}

async function chooseClassicOutlook() {
  hideConnectPicker();
  try {
    await api("/api/settings", { method: "PUT", body: JSON.stringify({ backend: "classic" }) });
    setBanner(t("pickingClassic"));
    await refreshStatus();
  } catch (err) {
    setBanner(err.message, true);
  }
}

async function chooseGraphOutlook() {
  hideConnectPicker();
  setBanner(t("loggingIn"));
  try {
    await api("/api/settings", { method: "PUT", body: JSON.stringify({ backend: "graph" }) });
    const status = await api("/api/microsoft/login", { method: "POST" });
    applyStatus(status);
    setBanner(status.connected ? t("msConnected") : "");
  } catch (err) {
    setBanner(err.message, true);
    $("advancedBox").open = true;
  }
}

async function refreshStatus() {
  try {
    const s = await api("/api/status");
    if (s.settings?.lang && s.settings.lang !== lang) {
      lang = s.settings.lang;
      applyI18n();
    }
    applyStatus(s);
  } catch (err) {
    $("statusTitle").textContent = t("serviceDown");
    $("statusMeta").textContent = err.message;
  }
}

function selectedIds() {
  return [...document.querySelectorAll(".pick:checked")].map((el) => Number(el.value));
}

function updateBatchBar() {
  const ids = selectedIds();
  $("batchBar").classList.toggle("hidden", ids.length === 0);
  $("selectedCount").textContent = t("selected", { n: ids.length });
}

function isTask(item) {
  return (item.kind || "event") === "task";
}

function isPromo(item) {
  return (item.kind || "event") === "promo";
}

function taskTypeLabel(item) {
  if (item.task_type === "homework") return t("taskHomework");
  if (item.task_type === "meet") return t("taskMeet");
  if (item.task_type === "followup") return t("taskFollowup");
  return t("taskKind");
}

function laneItems(items, lane) {
  const rows = (items || []).filter((item) => {
    if (currentMailbox && item.mailbox && item.mailbox !== currentMailbox) return false;
    return true;
  });
  if (lane === "task") return rows.filter(isTask);
  if (lane === "promo") return rows.filter(isPromo);
  return rows.filter((item) => !isTask(item) && !isPromo(item));
}

function updateLaneButtons(items) {
  const eventBtn = $("laneEventBtn");
  const taskBtn = $("laneTaskBtn");
  const promoBtn = $("lanePromoBtn");
  if (!eventBtn || !taskBtn) return;
  eventBtn.textContent = `${t("laneEvent")} ${laneItems(items, "event").length}`;
  taskBtn.textContent = `${t("laneTask")} ${laneItems(items, "task").length}`;
  if (promoBtn) {
    promoBtn.textContent = `${t("lanePromo")} ${laneItems(items, "promo").length}`;
    promoBtn.classList.toggle("on", currentLane === "promo");
  }
  eventBtn.classList.toggle("on", currentLane === "event");
  taskBtn.classList.toggle("on", currentLane === "task");
  updateMailboxButtons(items);
}

function updateMailboxButtons(items) {
  const host = $("mailboxSeg");
  if (!host) return;
  const names = [...new Set((items || []).map((item) => item.mailbox).filter(Boolean))];
  if (names.length < 2) {
    host.classList.add("hidden");
    host.innerHTML = "";
    currentMailbox = "";
    return;
  }
  host.classList.remove("hidden");
  const buttons = [`<button type="button" data-mailbox="" class="${currentMailbox ? "" : "on"}">${escapeHtml(t("mailboxAll"))}</button>`];
  for (const name of names) {
    buttons.push(
      `<button type="button" data-mailbox="${escapeHtml(name)}" class="${currentMailbox === name ? "on" : ""}">${escapeHtml(name)}</button>`
    );
  }
  host.innerHTML = buttons.join("");
}

function render(items) {
  lastItems = items;
  updateLaneButtons(items);
  const visible = laneItems(items, currentLane);
  const list = $("list");
  list.innerHTML = "";
  $("empty").textContent = t(
    currentLane === "task" ? "emptyTasks" : currentLane === "promo" ? "emptyPromo" : "empty"
  );
  $("empty").classList.toggle("hidden", visible.length > 0);
  const weekdays = t("weekdays");
  for (const item of visible) {
    const start = parseTs(item.start_at);
    const task = isTask(item);
    const promo = isPromo(item);
    const card = document.createElement("article");
    card.className = promo ? "card promo-card" : task ? "card task-card" : "card";
    card.dataset.id = item.id;
    card.dataset.kind = promo ? "promo" : task ? "task" : "event";
    const approx = !task && !promo && item.fuzzy ? `<span class="fuzzy-tag">${escapeHtml(t("around"))}</span>` : "";
    let dateBlock;
    if (promo) {
      dateBlock = `<div class="date-block promo-block">
          <div class="month">${escapeHtml(t("promoKind"))}</div>
          <div class="day task-mark">×</div>
          <div class="meta">${escapeHtml(t("lanePromo"))}</div>
        </div>`;
    } else if (task) {
      dateBlock = `<div class="date-block task-block">
          <div class="month">${escapeHtml(t("taskKind"))}</div>
          <div class="day task-mark">✓</div>
          <div class="meta">${escapeHtml(taskTypeLabel(item))}</div>
        </div>`;
    } else {
      dateBlock = `<div class="date-block">
          <div class="month">${escapeHtml(fmtMonth(start))}</div>
          <div class="day">${start.getDate()}</div>
          <div class="meta">${weekdays[(start.getDay() + 6) % 7]}</div>
          <div class="meta">${escapeHtml(fmtTime(start, item.all_day))}</div>
        </div>`;
    }
    const fields = (task || promo)
      ? `<div class="fields">
          <input class="title" data-field="title" value="${escapeHtml(item.title)}" />
        </div>`
      : `<div class="fields">
          <input class="title" data-field="title" value="${escapeHtml(item.title)}" />
          <input data-field="when" type="${item.all_day ? "date" : "datetime-local"}" value="${item.all_day ? toDateInput(start) : toLocalInput(start)}" />
          <label class="check"><input data-field="all_day" type="checkbox" ${item.all_day ? "checked" : ""} /> ${t("allDay")}</label>
        </div>`;
    const mailbox = item.mailbox ? `<span class="mailbox-tag">${escapeHtml(item.mailbox)}</span> ` : "";
    card.innerHTML = `
      <input class="pick" type="checkbox" value="${item.id}" />
      ${dateBlock}
      <div class="body">
        <h2>${escapeHtml(item.title)}${approx}</h2>
        <p class="who">${mailbox}${escapeHtml(t("fromMail", {
          sender: item.sender,
          subject: item.subject,
          received: fmtReceived(item.received_at),
        }))}</p>
        <div class="snippet">${highlight(item.snippet || "", item.matched_text || "")}</div>
        ${fields}
        <div class="confidence">${escapeHtml(t("match", { text: item.matched_text, n: Math.round(item.confidence * 100) }))}</div>
      </div>
      <div class="actions">
        <button class="yes" type="button" data-act="accept">${t(promo ? "acceptPromo" : task ? "acceptTask" : "accept")}</button>
        <button class="no" type="button" data-act="reject">${t("reject")}</button>
        <button class="mail" type="button" data-act="open-mail" ${item.can_open_mail ? "" : "disabled"}>${t("openMail")}</button>
      </div>
    `;
    list.appendChild(card);
  }
  updateBatchBar();
}

function sourceLabel(item) {
  if (item.status === "accepted") return t("searchAccepted");
  if (item.id && item.status === "pending") return t("searchSaved");
  if (item.extracted === false) return t("searchMailOnly");
  return t("searchInbox");
}

function sourceClass(item) {
  if (item.status === "accepted") return "accepted";
  if (item.id && item.status === "pending") return "pending";
  return "";
}

function renderSearch(items, query, meta = {}) {
  lastSearchItems = items || [];
  lastSearchQuery = query || "";
  lastSearchMeta = meta || lastSearchMeta;
  const panel = $("searchPanel");
  const hint = $("searchHint");
  const host = $("searchResults");
  if (!panel || !host) return;
  if (!query) {
    panel.classList.add("hidden");
    host.innerHTML = "";
    return;
  }
  panel.classList.remove("hidden");
  const liveNote = meta.live ? ` ${t("searchLive", { n: meta.scanned || 0 })}` : "";
  hint.textContent = `${t("searchHint")}${liveNote}`;
  if (!lastSearchItems.length) {
    host.innerHTML = `<p class="search-hint">${escapeHtml(t("searchEmpty"))}</p>`;
    return;
  }
  host.innerHTML = lastSearchItems.map((item, index) => {
    const start = parseTs(item.start_at || item.received_at);
    const when = Number.isNaN(start.getTime()) ? "" : (item.all_day ? toDateInput(start) : fmtReceived(item.start_at || item.received_at));
    const snippet = highlightQuery(item.snippet || item.subject || "", query, item.highlight || "");
    const openDisabled = item.can_open_mail ? "" : "disabled";
    return `<div class="search-hit" data-search-index="${index}" role="button" tabindex="0">
      <div class="hit-top">
        <div class="hit-title">${escapeHtml(item.title || item.subject || "")}</div>
        <div class="hit-when">${escapeHtml(when)}</div>
      </div>
      <div class="hit-meta"><span class="hit-tag ${sourceClass(item)}">${escapeHtml(sourceLabel(item))}</span>${escapeHtml(t("fromMail", {
        sender: item.sender || "",
        subject: item.subject || "",
        received: fmtReceived(item.received_at),
      }))}</div>
      <div class="hit-snippet">${snippet}</div>
      <button class="ghost small hit-mail" type="button" data-search-open="${index}" ${openDisabled}>${escapeHtml(t("searchOpen"))}</button>
    </div>`;
  }).join("");
}

function jumpToCard(item) {
  if (!item || !item.id) return false;
  currentLane = isPromo(item) ? "promo" : isTask(item) ? "task" : "event";
  if (item.mailbox) currentMailbox = "";
  render(lastItems);
  const card = document.querySelector(`.card[data-id="${item.id}"]`);
  if (!card) return false;
  card.classList.add("flash");
  card.scrollIntoView({ behavior: "smooth", block: "center" });
  setTimeout(() => card.classList.remove("flash"), 1600);
  return true;
}

async function focusSearchItem(item) {
  if (!item) return;
  if (item.id) {
    if (item.status === "pending") {
      const found = lastItems.some((row) => row.id === item.id);
      if (!found) await loadList();
      if (jumpToCard(item)) return;
    }
    return;
  }
  if (item.extracted === false) return;
  const pinned = await api("/api/search/pin", {
    method: "POST",
    body: JSON.stringify({
      email_id: item.email_id || "",
      internet_id: item.internet_id || "",
      store_id: item.store_id || "",
      mail_url: item.mail_url || "",
      subject: item.subject || "",
      sender: item.sender || "",
      received_at: item.received_at,
      title: item.title || item.subject || "",
      start_at: item.start_at,
      end_at: item.end_at,
      all_day: Boolean(item.all_day),
      snippet: item.snippet || "",
      matched_text: item.matched_text || "",
      confidence: item.confidence || 0.5,
      fuzzy: Boolean(item.fuzzy),
      kind: item.kind || "event",
      task_type: item.task_type || "",
      mailbox: item.mailbox || "",
    }),
  });
  await loadList();
  await refreshStatus();
  jumpToCard(pinned.item);
}

async function openSearchMail(item) {
  if (!item) return;
  if (item.id && item.can_open_mail) {
    await api(`/api/candidates/${item.id}/open-mail`, { method: "POST" });
    setBanner(t("openedMail"));
    return;
  }
  await api("/api/search/open-mail", {
    method: "POST",
    body: JSON.stringify({
      email_id: item.email_id || "",
      store_id: item.store_id || "",
      mail_url: item.mail_url || "",
    }),
  });
  setBanner(t("openedMail"));
}

async function runMailSearch(query) {
  const q = String(query || "").trim();
  lastSearchQuery = q;
  const panel = $("searchPanel");
  const hint = $("searchHint");
  const host = $("searchResults");
  if (!q) {
    lastSearchItems = [];
    if (panel) panel.classList.add("hidden");
    if (host) host.innerHTML = "";
    return;
  }
  if (panel) panel.classList.remove("hidden");
  if (hint) hint.textContent = t("searchSearching");
  const seq = ++searchSeq;
  try {
    const data = await api(`/api/search?q=${encodeURIComponent(q)}`);
    if (seq !== searchSeq) return;
    renderSearch(data.items || [], q, { scanned: data.scanned || 0, live: Boolean(data.live) });
    if (data.added) {
      await loadList();
      await refreshStatus();
    }
  } catch (err) {
    if (seq !== searchSeq) return;
    setBanner(err.message, true);
  }
}

async function loadList() {
  const data = await api("/api/candidates?status=pending");
  render(data.items || []);
  setCounts(data.counts);
}

async function saveEdits(card) {
  const id = Number(card.dataset.id);
  const title = card.querySelector("[data-field=title]").value.trim();
  if (card.dataset.kind === "task" || card.dataset.kind === "promo") {
    await api(`/api/candidates/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
    return;
  }
  const allDay = card.querySelector("[data-field=all_day]").checked;
  const when = card.querySelector("[data-field=when]").value;
  const startAt = allDay ? `${when}T00:00` : when;
  await api(`/api/candidates/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ title, all_day: allDay, start_at: startAt }),
  });
}

async function act(id, action) {
  const data = await api(`/api/candidates/${id}/${action}`, { method: "POST" });
  await loadList();
  await refreshStatus();
  return data;
}

$("scanBtn").addEventListener("click", async () => {
  $("scanBtn").disabled = true;
  setBanner(t("scanning"));
  try {
    const data = await api("/api/scan", {
      method: "POST",
      body: JSON.stringify({
        days: Number($("days").value),
        max_emails: Number($("maxEmails").value),
        include_processed: $("includeProcessed").checked,
      }),
    });
    setBanner(t("scanned", {
      scanned: data.scanned,
      found: data.found,
      added: data.added,
      skipped: data.skipped_invite,
    }));
    await loadList();
    await refreshStatus();
  } catch (err) {
    setBanner(err.message, true);
  } finally {
    $("scanBtn").disabled = false;
  }
});

$("demoBtn").addEventListener("click", async () => {
  await api("/api/scan", { method: "POST", body: JSON.stringify({ demo: true }) });
  setBanner(t("demoLoaded"));
  await loadList();
});

$("mailSearch").addEventListener("input", () => {
  const query = $("mailSearch").value.trim();
  window.clearTimeout(searchTimer);
  if (!query) {
    searchSeq += 1;
    lastSearchQuery = "";
    lastSearchItems = [];
    $("searchPanel").classList.add("hidden");
    $("searchResults").innerHTML = "";
    return;
  }
  searchTimer = window.setTimeout(() => {
    runMailSearch(query);
  }, 280);
});

$("mailSearch").addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    $("mailSearch").value = "";
    $("mailSearch").dispatchEvent(new Event("input"));
    return;
  }
  if (event.key === "Enter") {
    event.preventDefault();
    window.clearTimeout(searchTimer);
    runMailSearch($("mailSearch").value.trim());
  }
});

$("searchResults").addEventListener("click", async (event) => {
  const openBtn = event.target.closest("[data-search-open]");
  if (openBtn) {
    event.preventDefault();
    event.stopPropagation();
    const item = lastSearchItems[Number(openBtn.dataset.searchOpen)];
    try {
      await openSearchMail(item);
    } catch (err) {
      setBanner(err.message, true);
    }
    return;
  }
  const hit = event.target.closest("[data-search-index]");
  if (!hit) return;
  const item = lastSearchItems[Number(hit.dataset.searchIndex)];
  document.querySelectorAll(".search-hit").forEach((el) => el.classList.toggle("on", el === hit));
  try {
    await focusSearchItem(item);
  } catch (err) {
    setBanner(err.message, true);
  }
});

$("searchResults").addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const hit = event.target.closest("[data-search-index]");
  if (!hit) return;
  event.preventDefault();
  hit.click();
});

$("list").addEventListener("change", async (event) => {
  if (event.target.classList.contains("pick")) {
    updateBatchBar();
    return;
  }
  const card = event.target.closest(".card");
  if (!card || !event.target.dataset.field) return;
  if (event.target.dataset.field === "all_day") {
    const start = parseTs(card.querySelector("[data-field=when]").value);
    const input = card.querySelector("[data-field=when]");
    const allDay = event.target.checked;
    input.type = allDay ? "date" : "datetime-local";
    input.value = allDay ? toDateInput(start) : toLocalInput(Number.isNaN(start.getTime()) ? new Date() : start);
  }
  try {
    await saveEdits(card);
  } catch (err) {
    setBanner(err.message, true);
  }
});

$("list").addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-act]");
  if (!btn) return;
  const card = event.target.closest(".card");
  const action = btn.dataset.act;
  try {
    if (action === "open-mail") {
      await api(`/api/candidates/${card.dataset.id}/open-mail`, { method: "POST" });
      setBanner(t("openedMail"));
      return;
    }
    await saveEdits(card);
    const id = Number(card.dataset.id);
    const data = await act(id, action);
    if (action === "reject") {
      setBanner(t("skipped"), false, [id]);
    } else if (card.dataset.kind === "task") {
      setBanner(data.item?.calendar_entry_id ? t("addedTask") : t("addedTaskLocal"), false, [id]);
    } else if (card.dataset.kind === "promo") {
      setBanner(data.item?.calendar_entry_id ? t("addedPromo") : t("addedPromoLocal"), false, [id]);
    } else {
      setBanner(t("addedCalendar"), false, [id]);
    }
  } catch (err) {
    setBanner(err.message, true);
  }
});

async function batch(action) {
  const ids = selectedIds();
  if (!ids.length) return;
  for (const id of ids) {
    const card = document.querySelector(`.card[data-id="${id}"]`);
    if (card) await saveEdits(card);
  }
  const data = await api("/api/batch", { method: "POST", body: JSON.stringify({ action, ids }) });
  if (data.errors?.length) {
    setBanner(t("batchPartial", { n: data.done, errors: data.errors.join("; ") }), true);
  } else {
    setBanner(t("batchDone", { n: data.done }), false, ids);
  }
  await loadList();
  await refreshStatus();
}

$("batchAccept").addEventListener("click", () => batch("accept"));
$("batchReject").addEventListener("click", () => batch("reject"));

$("undoBtn").addEventListener("click", async () => {
  const ids = lastUndoIds.slice();
  if (!ids.length) return;
  try {
    const data = ids.length === 1
      ? await api(`/api/candidates/${ids[0]}/undo`, { method: "POST" })
      : await api("/api/batch", { method: "POST", body: JSON.stringify({ action: "undo", ids }) });
    setBanner(data.outlook_deleted === false ? t("undonePartial") : t("undone"));
    await loadList();
    await refreshStatus();
  } catch (err) {
    setBanner(err.message, true);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !$("connectPicker")?.classList.contains("hidden")) {
    event.preventDefault();
    hideConnectPicker();
    return;
  }
  if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "z") return;
  if (editingNow()) return;
  if ($("undoBtn")?.classList.contains("hidden")) return;
  event.preventDefault();
  $("undoBtn").click();
});

$("laneSeg").addEventListener("click", (event) => {
  const btn = event.target.closest("[data-lane]");
  if (!btn) return;
  currentLane = btn.dataset.lane === "task" ? "task" : btn.dataset.lane === "promo" ? "promo" : "event";
  render(lastItems);
});

$("mailboxSeg").addEventListener("click", (event) => {
  const btn = event.target.closest("[data-mailbox]");
  if (!btn) return;
  currentMailbox = btn.dataset.mailbox || "";
  render(lastItems);
});

$("settingsBtn").addEventListener("click", () => {
  $("settingsPanel").classList.toggle("hidden");
});

$("langSeg").addEventListener("click", async (event) => {
  const btn = event.target.closest("[data-lang]");
  if (!btn) return;
  lang = btn.dataset.lang === "en" ? "en" : "zh";
  applyI18n();
  try {
    await api("/api/settings", { method: "PUT", body: JSON.stringify({ lang }) });
    await refreshStatus();
  } catch (err) {
    setBanner(err.message, true);
  }
});

$("backendSelect").addEventListener("change", async (event) => {
  try {
    await api("/api/settings", { method: "PUT", body: JSON.stringify({ backend: event.target.value }) });
    await refreshStatus();
  } catch (err) {
    setBanner(err.message, true);
  }
});

$("statusCard").addEventListener("click", () => {
  openConnectPickerFromStatus();
});

$("statusCard").addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  event.preventDefault();
  openConnectPickerFromStatus();
});

$("pickClassic").addEventListener("click", () => {
  chooseClassicOutlook();
});

$("pickGraph").addEventListener("click", () => {
  chooseGraphOutlook();
});

$("connectPickerLater").addEventListener("click", () => {
  hideConnectPicker();
});

$("connectPicker").addEventListener("click", (event) => {
  if (event.target === $("connectPicker")) hideConnectPicker();
});

$("msLoginBtn").addEventListener("click", async () => {
  setBanner(t("loggingIn"));
  try {
    const status = await api("/api/microsoft/login", { method: "POST" });
    applyStatus(status);
    setBanner(status.connected ? t("msConnected") : "");
  } catch (err) {
    setBanner(err.message, true);
    $("advancedBox").open = true;
    if (String(err.message).includes("graph_client_id_missing") || t("graph_client_id_missing") === err.message) {
      $("graphSetup").open = true;
    }
  }
});

$("msLogoutBtn").addEventListener("click", async () => {
  try {
    const status = await api("/api/microsoft/logout", { method: "POST" });
    applyStatus(status);
  } catch (err) {
    setBanner(err.message, true);
  }
});

$("saveClientId").addEventListener("click", async () => {
  try {
    await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify({ graph_client_id: $("graphClientId").value.trim() }),
    });
    setBanner(t("saveClientId"));
  } catch (err) {
    setBanner(err.message, true);
  }
});

function editingNow() {
  const el = document.activeElement;
  return el && ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName);
}

function connectLive() {
  const source = new EventSource("/api/stream");
  source.onmessage = (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      return;
    }
    applyStatus(data);
    if (data.type !== "update") return;
    if (data.added) {
      setBanner(t("newDates", { n: data.added }));
    }
    if (!editingNow()) {
      loadList().catch((err) => setBanner(err.message, true));
    }
  };
  source.onerror = () => {};
}

async function boot() {
  applyI18n();
  try {
    const settings = await api("/api/settings");
    lang = settings.lang === "en" ? "en" : "zh";
    applyI18n();
  } catch {
    lang = "zh";
  }
  await refreshStatus();
  await loadList().catch((err) => setBanner(err.message, true));
  connectLive();
}

boot();
