(function () {
  "use strict";

  const getTg = () => window.Telegram?.WebApp;
  const hasTgAuth = () => Boolean(getTg()?.initData);

  const $ = (s) => document.querySelector(s);
  const main = $("#main");
  const loader = $("#loader");
  const coinsEl = $("#coins");
  const modeEl = $("#mode");
  const tabbar = $("#tabbar");

  let state = null;
  let currentTab = "garden";
  let tickId = null;
  let globalStatsLoading = false;
  let harvestModalOpen = false;
  let harvestQueue = [];
  let refreshing = false;
  let adsOpen = false;
  let adsView = "list";
  let adsConversationId = null;
  let adsInbox = null;
  let adsMessages = [];
  let adsBlocked = false;

  const TABS = ["garden", "plot", "friends", "shop", "profile"];

  const UPGRADE_META = {
    plot: {
      icon: "🌱",
      name: "Доп. грядка",
      desc: (s) => {
        if (!s) return "До 10 грядок одновременно";
        if (s.owned >= s.max) return `Максимум: ${s.max + 1} грядок`;
        return `Сейчас ${1 + s.owned} · макс. ${s.max + 1} · +1 за ${s.price}`;
      },
    },
    speed: {
      icon: "⚡",
      name: "Ускорение роста",
      desc: (s) => {
        if (!s || s.level >= s.max) return "Максимум: −30% ко времени";
        const next = (s.level + 1) * 15;
        return `Сейчас −${s.level * 15}% · след. −${next}%`;
      },
    },
    water_can: {
      icon: "💧",
      name: "Золотая лейка",
      desc: (s) => {
        if (!s || s.level >= s.max) return "Максимум: +30% к своему поливу";
        const next = (s.level + 1) * 10;
        return `Сейчас +${s.level * 10}% · след. +${next}%`;
      },
    },
  };

  const RARITY_EMOJI = {
    common: "🌿",
    uncommon: "🌱",
    rare: "🌸",
    epic: "🌺",
    legendary: "🌳",
  };

  const RARITY_LABEL = {
    common: "Обычное",
    uncommon: "Необычное",
    rare: "Редкое",
    epic: "Эпическое",
    legendary: "Легендарное",
  };

  const PLANT_PRICE_ORDER = [13, 3, 9, 10, 11, 8, 6, 5, 4, 2, 1, 12, 7];

  const RARITY_MARKET = {
    common: { weight: 60, base: 18 },
    uncommon: { weight: 25, base: 45 },
    rare: { weight: 10, base: 120 },
    epic: { weight: 4, base: 340 },
    legendary: { weight: 1, base: 1200 },
  };

  const BACKGROUND_MARKET = {
    1: { name: "Фон 10", weight: 22, mult: 1.0, image: "1.jpg" },
    2: { name: "Фон 8", weight: 18, mult: 1.08, image: "2.jpg" },
    3: { name: "Фон 1", weight: 15, mult: 1.15, image: "3.jpg" },
    4: { name: "Фон 3", weight: 11, mult: 1.28, image: "4.jpg" },
    5: { name: "Фон 7", weight: 10, mult: 1.42, image: "5.jpg" },
    6: { name: "Фон 6", weight: 8, mult: 1.6, image: "6.jpg" },
    7: { name: "Фон 5", weight: 6, mult: 1.9, image: "7.jpg" },
    8: { name: "Фон 4", weight: 4, mult: 2.4, image: "8.jpg" },
    9: { name: "Фон 9", weight: 3, mult: 3.0, image: "9.jpg" },
    10: { name: "Фон 2", weight: 2, mult: 3.8, image: "10.jpg" },
  };

  function plantBgAttrs(backgroundId) {
    const bg = BACKGROUND_MARKET[backgroundId] || BACKGROUND_MARKET[1];
    if (!bg.image) return { classExtra: "", style: "" };
    return {
      classExtra: " seed-card--bgimg",
      style: `--bg-image:url(/static/images/bg/${bg.image});`,
    };
  }

  const GLOBAL_STATS_CACHE_KEY = "garden_global_stats_v1";
  const LEADERBOARD_CACHE_KEY = "garden_leaderboard_v1";

  function formatLeaderboardTime(ts) {
    const d = new Date(ts * 1000);
    const h = String(d.getHours()).padStart(2, "0");
    const m = String(d.getMinutes()).padStart(2, "0");
    return `${h}:${m}`;
  }

  function readLeaderboardCache() {
    try {
      const raw = localStorage.getItem(LEADERBOARD_CACHE_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw);
      const now = Math.floor(Date.now() / 1000);
      if (!data?.next_update_at || data.next_update_at <= now) return null;
      return data;
    } catch (_) {
      return null;
    }
  }

  function renderLeaderboardHtml(lb) {
    if (!lb?.entries?.length) {
      return `
        <div class="leaderboard">
          <div class="section-title">🏆 Топ садов</div>
          <p class="leaderboard__empty">Пока никого в рейтинге — вырасти коллекцию!</p>
        </div>`;
    }
    const rows = lb.entries
      .map((e) => {
        const handle = e.username ? `@${e.username}` : "";
        return `
        <div class="leaderboard__row">
          <div class="leaderboard__rank">${e.rank}</div>
          <div class="leaderboard__info">
            <div class="leaderboard__name">${e.display_name}</div>
            ${handle ? `<div class="leaderboard__handle">${handle}</div>` : ""}
          </div>
          <div class="leaderboard__value">${formatNum(e.garden_value)}</div>
        </div>`;
      })
      .join("");
    const updated = formatLeaderboardTime(lb.updated_at);
    const next = formatLeaderboardTime(lb.next_update_at);
    return `
      <div class="leaderboard" id="leaderboard-section">
        <div class="section-title">🏆 Топ садов</div>
        <div class="leaderboard__meta">Обновлено в ${updated} · след. в ${next}</div>
        <div class="leaderboard__list">${rows}</div>
      </div>`;
  }

  async function ensureLeaderboard() {
    const now = Math.floor(Date.now() / 1000);
    if (state.leaderboard?.next_update_at > now) return;
    const cached = readLeaderboardCache();
    if (cached) {
      state.leaderboard = cached;
      return;
    }
    try {
      const data = await api("GET", "/api/leaderboard");
      state.leaderboard = data;
      try {
        localStorage.setItem(LEADERBOARD_CACHE_KEY, JSON.stringify(data));
      } catch (_) {}
    } catch (_) {}
  }

  function updateLeaderboardSection() {
    const sec = document.getElementById("leaderboard-section");
    if (!sec || !state.leaderboard) return;
    const wrap = document.createElement("div");
    wrap.innerHTML = renderLeaderboardHtml(state.leaderboard);
    sec.replaceWith(wrap.firstElementChild);
  }

  function adsUnreadBadge() {
    const n = state.user?.is_admin ? state.ads_unread || 0 : 0;
    return n > 0 ? `<span class="ads-btn__badge">${n > 99 ? "99+" : n}</span>` : "";
  }

  function formatAdsTime(ts) {
    const d = new Date(ts * 1000);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderAdsMessages() {
    if (!adsMessages.length) {
      return `<div class="ads-chat__empty">Напишите о рекламе — администратор увидит сообщение здесь.</div>`;
    }
    return adsMessages
      .map((m) => {
        const cls = m.is_mine ? "ads-chat__msg ads-chat__msg--mine" : "ads-chat__msg";
        const who = m.is_admin ? "Админ" : m.display_name || "Вы";
        return `
        <div class="${cls}">
          <div class="ads-chat__who">${who}</div>
          <div class="ads-chat__body">${escapeHtml(m.body)}</div>
          <div class="ads-chat__time">${formatAdsTime(m.created_at)}</div>
        </div>`;
      })
      .join("");
  }

  function renderAdsInboxList() {
    const convs = adsInbox?.conversations || [];
    if (!convs.length) {
      return `<div class="ads-chat__empty">Пока нет чатов с рекламодателями.</div>`;
    }
    return convs
      .map((c) => {
        const name = c.display_name || c.username || "Рекламодатель";
        const preview = c.last_body ? escapeHtml(c.last_body).slice(0, 80) : "Нет сообщений";
        const badge = c.unread > 0 ? `<span class="ads-inbox__badge">${c.unread}</span>` : "";
        const blocked = c.blocked ? `<span class="ads-inbox__blocked">заблок.</span>` : "";
        return `
        <button type="button" class="ads-inbox__item" data-conv="${c.id}" data-blocked="${c.blocked ? 1 : 0}">
          <div class="ads-inbox__top">
            <span class="ads-inbox__name">${escapeHtml(name)} ${blocked}</span>
            ${badge}
          </div>
          <div class="ads-inbox__preview">${preview}</div>
        </button>`;
      })
      .join("");
  }

  function bindAdsEvents() {
    document.getElementById("ads-close")?.addEventListener("click", closeAdsPanel);
    document.getElementById("ads-back")?.addEventListener("click", async () => {
      adsView = "list";
      adsConversationId = null;
      await openAdsPanel();
    });
    document.querySelectorAll(".ads-inbox__item").forEach((btn) => {
      btn.addEventListener("click", async () => {
        adsConversationId = parseInt(btn.dataset.conv, 10);
        adsView = "chat";
        adsBlocked = btn.dataset.blocked === "1";
        const res = await api("GET", `/api/ads/messages/${adsConversationId}`);
        adsMessages = res.messages || [];
        renderAdsPanel();
      });
    });
    document.getElementById("ads-block")?.addEventListener("click", async () => {
      if (!adsConversationId) return;
      await api("POST", "/api/ads/block", { conversation_id: adsConversationId });
      adsBlocked = true;
      toast("Чат заблокирован");
      renderAdsPanel();
    });
    document.getElementById("ads-unblock")?.addEventListener("click", async () => {
      if (!adsConversationId) return;
      await api("POST", "/api/ads/unblock", { conversation_id: adsConversationId });
      adsBlocked = false;
      toast("Чат разблокирован");
      renderAdsPanel();
    });
    document.getElementById("ads-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const input = document.getElementById("ads-input");
      const text = (input?.value || "").trim();
      if (!text) return;
      try {
        const payload = { text };
        if (state.user?.is_admin && adsConversationId) {
          payload.conversation_id = adsConversationId;
        }
        const res = await api("POST", "/api/ads/messages", payload);
        adsMessages.push(res.message);
        input.value = "";
        renderAdsPanel();
      } catch (err) {
        if (err?.detail?.error === "blocked") toast("Чат заблокирован");
        else toast("Не удалось отправить");
      }
    });
  }

  function renderAdsPanel() {
    let panel = document.getElementById("ads-panel");
    if (!panel) {
      panel = document.createElement("div");
      panel.id = "ads-panel";
      panel.className = "ads-panel";
      document.body.appendChild(panel);
    }

    const isAdmin = state.user?.is_admin;
    let headerTitle = "Реклама";
    let backBtn = "";
    let blockBtn = "";

    if (isAdmin && adsView === "chat" && adsConversationId) {
      headerTitle = "Чат";
      backBtn = `<button type="button" class="ads-panel__back" id="ads-back">←</button>`;
      blockBtn = adsBlocked
        ? `<button type="button" class="ads-panel__block ads-panel__block--on" id="ads-unblock">Разблок.</button>`
        : `<button type="button" class="ads-panel__block" id="ads-block">Блок</button>`;
    } else if (isAdmin) {
      headerTitle = "Реклама — чаты";
    }

    let body = "";
    if (isAdmin && adsView === "list") {
      body = `<div class="ads-inbox">${renderAdsInboxList()}</div>`;
    } else {
      body = `<div class="ads-chat__messages" id="ads-messages">${renderAdsMessages()}</div>`;
    }

    const blockedNote =
      !isAdmin && adsBlocked
        ? `<div class="ads-chat__blocked-note">Чат заблокирован администратором.</div>`
        : "";

    panel.innerHTML = `
      <div class="ads-panel__sheet">
        <div class="ads-panel__head">
          ${backBtn}
          <h3>${headerTitle}</h3>
          ${blockBtn}
          <button type="button" class="ads-panel__close" id="ads-close">✕</button>
        </div>
        ${blockedNote}
        <div class="ads-panel__body">${body}</div>
        ${
          isAdmin && adsView === "list"
            ? ""
            : `<form class="ads-panel__form" id="ads-form">
          <input type="text" id="ads-input" maxlength="2000" placeholder="Сообщение…" ${!isAdmin && adsBlocked ? "disabled" : ""} autocomplete="off" />
          <button type="submit" class="ads-panel__send" ${!isAdmin && adsBlocked ? "disabled" : ""}>➤</button>
        </form>`
        }
      </div>`;

    panel.hidden = false;
    bindAdsEvents();
    const msgBox = document.getElementById("ads-messages");
    if (msgBox) msgBox.scrollTop = msgBox.scrollHeight;
  }

  async function openAdsPanel() {
    adsOpen = true;
    try {
      const data = await api("GET", "/api/ads/inbox");
      adsInbox = data;
      if (data.is_admin) {
        adsView = adsConversationId ? "chat" : "list";
        if (adsConversationId) {
          const res = await api("GET", `/api/ads/messages/${adsConversationId}`);
          adsMessages = res.messages || [];
          const conv = (data.conversations || []).find((c) => c.id === adsConversationId);
          adsBlocked = Boolean(conv?.blocked);
          state.ads_unread = 0;
        }
      } else {
        adsView = "chat";
        adsConversationId = data.conversation?.id || null;
        adsMessages = data.messages || [];
        adsBlocked = Boolean(data.conversation?.blocked);
      }
      renderAdsPanel();
      updateAdsButtonBadge();
    } catch (_) {
      toast("Не удалось открыть чат");
      adsOpen = false;
    }
  }

  function closeAdsPanel() {
    adsOpen = false;
    const panel = document.getElementById("ads-panel");
    if (panel) panel.hidden = true;
    if (state.user?.is_admin) {
      adsView = "list";
      adsConversationId = null;
    }
  }

  function updateAdsButtonBadge() {
    const btn = document.getElementById("ads-btn");
    if (!btn) return;
    const badge = btn.querySelector(".ads-btn__badge");
    const n = state.user?.is_admin ? state.ads_unread || 0 : 0;
    if (n > 0) {
      if (badge) badge.textContent = n > 99 ? "99+" : String(n);
      else {
        const span = document.createElement("span");
        span.className = "ads-btn__badge";
        span.textContent = n > 99 ? "99+" : String(n);
        btn.appendChild(span);
      }
    } else if (badge) badge.remove();
  }

  function coinHtml(sm) {
    return `<span class="coin${sm ? " coin--sm" : ""}" aria-hidden="true"></span>`;
  }

  function formatNum(n) {
    return new Intl.NumberFormat("ru-RU").format(Math.max(0, Math.round(n || 0)));
  }

  function variantPriceMult(variantId) {
    if (!variantId) return 1;
    const idx = PLANT_PRICE_ORDER.indexOf(Number(variantId));
    if (idx < 0) return 1;
    return 1 + idx * (0.45 / Math.max(1, PLANT_PRICE_ORDER.length - 1));
  }

  function plantArtHtml(plant, className = "seed-card__plant") {
    const vid = plant?.plant_variant_id;
    if (!vid) {
      const rarity = plant?.rarity || "common";
      return `<div class="${className} ${className}--emoji">${RARITY_EMOJI[rarity] || "🌿"}</div>`;
    }
    return `<img class="${className}" src="/static/images/plants/${vid}.png" alt="" loading="lazy">`;
  }

  function getPlantPrice(plant) {
    const rarity = RARITY_MARKET[plant?.rarity] || RARITY_MARKET.common;
    const bg = BACKGROUND_MARKET[plant?.background_id] || BACKGROUND_MARKET[1];
    const rarityScarcity = 60 / rarity.weight;
    const bgScarcity = 22 / bg.weight;
    const comboBoost = Math.pow(rarityScarcity * bgScarcity, 0.38);
    return Math.round(rarity.base * bg.mult * comboBoost * variantPriceMult(plant?.plant_variant_id));
  }

  function getCollectionValue() {
    return (state?.ready_plants || []).reduce((sum, plant) => sum + getPlantPrice(plant), 0);
  }

  function getGlobalDisplayCount() {
    const g = state?.global_stats;
    if (!g) return 0;
    const now = Math.floor(Date.now() / 1000);
    const span = Math.max(1, g.window_end - g.window_start);
    const progress = Math.min(1, Math.max(0, (now - g.window_start) / span));
    return Math.round(g.from_count + (g.to_count - g.from_count) * progress);
  }

  function getGrowingPlants() {
    if (state?.growing_plants?.length) return state.growing_plants;
    return state?.growing ? [state.growing] : [];
  }

  function getPlotCount() {
    return state?.upgrades?.plot_count || 1;
  }

  function getSelfWaterPercent() {
    return (
      state?.upgrades?.self_water_total_percent ??
      state?.config?.self_water_reduction_percent ??
      15
    );
  }

  function getSelfWaterSeconds() {
    return (
      state?.upgrades?.self_water_seconds ??
      state?.config?.self_water_seconds ??
      state?.config?.water_time_reduction ??
      3600
    );
  }

  function formatSavedTime(sec) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    if (h > 0 && m > 0) return `${h} ч ${m} мин`;
    if (h > 0) return `${h} ч`;
    if (m > 0) return `${m} мин`;
    return `${sec} сек`;
  }

  function formatGrowthDuration(sec) {
    if (state?.config?.mode === "test") return "5 минут";
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    if (h > 0 && m > 0) return `${h} ч ${m} мин`;
    if (h > 0) return `${h} часов`;
    if (m > 0) return `${m} минут`;
    return `${sec} сек`;
  }

  function showHarvestModal(plant) {
    if (!plant || harvestModalOpen) return;
    harvestModalOpen = true;
    const bg = BACKGROUND_MARKET[plant.background_id] || BACKGROUND_MARKET[1];
    const price = getPlantPrice(plant);
    const rarity = plant.rarity || "common";
    const tile = plantBgAttrs(plant.background_id);
    const overlay = document.createElement("div");
    overlay.className = "harvest-overlay";
    overlay.innerHTML = `
      <div class="harvest-modal" role="dialog" aria-modal="true">
        <div class="harvest-modal__title">🎉 Растение выросло!</div>
        <div class="harvest-modal__sub">Новый урожай в коллекции</div>
        <div class="harvest-modal__plant seed-card--${rarity}${tile.classExtra}" style="${tile.style}">
          ${plantArtHtml(plant, "harvest-modal__plant-img")}
          <div class="harvest-modal__tag tag-${rarity}">${RARITY_LABEL[rarity] || rarity}</div>
          <div class="harvest-modal__bg">${bg.name}</div>
          <div class="harvest-modal__price">≈ ${formatNum(price)} ${coinHtml(true)}</div>
        </div>
        <button class="harvest-modal__btn" type="button">Ура! 🌼</button>
      </div>`;
    const close = () => {
      harvestModalOpen = false;
      overlay.remove();
      if (harvestQueue.length) showHarvestModal(harvestQueue.shift());
    };
    overlay.querySelector(".harvest-modal__btn").addEventListener("click", close);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close();
    });
    document.body.appendChild(overlay);
  }

  function queueHarvestModal(plant) {
    if (!plant) return;
    if (harvestModalOpen) harvestQueue.push(plant);
    else showHarvestModal(plant);
  }

  function getEggQueryId() {
    const p = new URLSearchParams(location.search);
    const raw = p.get("egg") || p.get("egg_edit");
    if (!raw) return null;
    const id = parseInt(raw, 10);
    return id >= 1 && id <= 37 ? id : null;
  }

  function isEggEditMode() {
    const p = new URLSearchParams(location.search);
    if (p.get("edit") !== "1") return false;
    return Boolean(state?.config?.dev_mode) || !hasTgAuth();
  }

  async function fetchEggFromCatalog(id) {
    const res = await fetch("/static/images/easter/catalog.json");
    if (!res.ok) return null;
    const catalog = await res.json();
    return catalog.find((e) => e.id === id) || null;
  }

  const HORIZON_Y = 38;
  const MEADOW_BAND = 100 - HORIZON_Y;
  let meadowScrollBound = false;

  function viewportTopToMeadow(top) {
    return ((top - HORIZON_Y) / MEADOW_BAND) * 100;
  }

  function isGrassEgg(egg) {
    if (!egg) return false;
    if (egg.layer === "grass") return true;
    if (egg.layer === "sky") return false;
    const top = egg.top ?? 50;
    if (top < HORIZON_Y + 3) return false;
    if (egg.animation?.type === "path") {
      const points = [{ top: egg.top ?? 50 }];
      egg.animation.segments?.forEach((seg) => {
        if (seg.to) points.push(seg.to);
      });
      const minTop = Math.min(...points.map((p) => p.top ?? 100));
      if (minTop < HORIZON_Y + 3) return false;
    }
    return true;
  }

  function isGrassEggVisibleOnProfile(btn) {
    if (isEggEditMode()) return true;
    if (currentTab !== "profile") return false;

    const grid = document.querySelector(".profile-grid");
    if (!grid) return false;

    const viewportTop = parseFloat(btn.dataset.viewportTop || "0");
    const eggY =
      btn.dataset.viewportTopUnit === "px"
        ? viewportTop
        : (viewportTop / 100) * window.innerHeight;
    const meadowTop = (HORIZON_Y / 100) * window.innerHeight;
    const meadowBottom = window.innerHeight;

    if (eggY < meadowTop || eggY > meadowBottom) return false;

    const gridRect = grid.getBoundingClientRect();
    const scrollUpHidePx = Math.max(56, window.innerHeight * 0.12);
    const scrollDownHidePx = 16;
    const hideWhenGridTopAbove = eggY - scrollUpHidePx;

    if (gridRect.bottom < meadowTop || gridRect.top > meadowBottom) return false;
    if (gridRect.top > hideWhenGridTopAbove) return false;
    if (eggY > gridRect.bottom + scrollDownHidePx) return false;

    return true;
  }

  function updateGrassEggVisibility(target) {
    const buttons = target
      ? [target]
      : [...document.querySelectorAll(".meadow-egg--grass")];
    if (!buttons.length) return;
    buttons.forEach((btn) => {
      btn.classList.toggle("is-hidden", !isGrassEggVisibleOnProfile(btn));
    });
  }

  function ensureMeadowScrollListener() {
    if (meadowScrollBound) return;
    meadowScrollBound = true;
    const tick = () => {
      updateGrassEggVisibility();
      document.querySelectorAll(".meadow-egg--sky").forEach((btn) => {
        if (btn.dataset.topPx) return;
        const left = parseFloat(btn.style.left);
        const catalogTop = parseFloat(btn.dataset.catalogTop || btn.dataset.viewportTop);
        if (!Number.isNaN(left) && !Number.isNaN(catalogTop)) {
          setEggPosition(btn, left, catalogTop);
        }
      });
    };
    window.addEventListener("scroll", () => updateGrassEggVisibility(), { passive: true });
    window.addEventListener("resize", tick, { passive: true });
  }

  function clearEggHosts() {
    document.getElementById("meadow-eggs")?.replaceChildren();
    document.getElementById("sky-eggs")?.replaceChildren();
    document.getElementById("egg-edit-panel")?.remove();
  }

  function clampSkyEggTop(top, size, anchor) {
    if (anchor === "top") {
      return Math.min(98, Math.max(-4, top));
    }
    const margin = 10;
    const halfPx = (size || 48) / 2;
    const minTop = ((halfPx + margin) / window.innerHeight) * 100;
    return Math.min(98, Math.max(minTop, top));
  }

  function skyEscapeTop(size) {
    const halfPx = (size || 48) / 2;
    const margin = 20;
    return -((halfPx + margin) / window.innerHeight) * 100;
  }

  function eggAnimRaw(btn) {
    return btn.dataset.animOffScreen === "1";
  }

  function setEggPosition(btn, left, top, opts = {}) {
    btn.style.left = `${left}%`;
    const topPxMode = btn.dataset.topPx != null && btn.dataset.topPx !== "";

    if (topPxMode) {
      const y = Math.round(top);
      btn.dataset.viewportTop = String(y);
      btn.dataset.viewportTopUnit = "px";
      btn.style.top = `${y}px`;
      return;
    }

    const size = parseInt(btn.style.width, 10) || 48;
    const anchor = btn.dataset.anchor || "center";
    const raw = opts.raw || eggAnimRaw(btn);
    const viewportTop =
      btn.dataset.zone === "sky" && !raw
        ? clampSkyEggTop(top, size, anchor)
        : top;
    btn.dataset.viewportTop = String(viewportTop);
    btn.dataset.viewportTopUnit = "pct";
    if (btn.dataset.zone === "grass") {
      btn.style.top = `${viewportTopToMeadow(viewportTop)}%`;
      updateGrassEggVisibility(btn);
      return;
    }
    btn.style.top = `${viewportTop}%`;
  }

  function animateEggSegment(btn, from, to, durationMs, token, opts = {}) {
    const raw = opts.raw ?? eggAnimRaw(btn);
    return new Promise((resolve) => {
      const start = performance.now();
      const step = (now) => {
        if (token.cancelled) {
          resolve(false);
          return;
        }
        const t = Math.min(1, (now - start) / durationMs);
        const left = from.left + (to.left - from.left) * t;
        const top = from.top + (to.top - from.top) * t;
        setEggPosition(btn, left, top, { raw });
        if (t < 1) requestAnimationFrame(step);
        else resolve(true);
      };
      requestAnimationFrame(step);
    });
  }

  function startEggPathAnimation(btn, egg) {
    const anim = egg.animation;
    if (!anim || anim.type !== "path" || !anim.segments?.length) return null;

    const token = { cancelled: false };
    let escaping = false;
    const raw = Boolean(anim.offScreen);

    const getPos = () => ({
      left: parseFloat(btn.style.left),
      top: parseFloat(btn.dataset.viewportTop || btn.style.top),
    });

    const runLoop = async () => {
      const start = anim.start || { left: egg.left, top: egg.top };
      setEggPosition(btn, start.left, start.top, { raw });
      while (!token.cancelled) {
        let from = { left: start.left, top: start.top };
        for (const seg of anim.segments) {
          if (token.cancelled) return;
          let durationMs = (seg.duration || 0) * 1000;
          if (seg.durationMin != null && seg.durationMax != null) {
            const sec =
              seg.durationMin + Math.random() * (seg.durationMax - seg.durationMin);
            durationMs = sec * 1000;
          }
          const ok = await animateEggSegment(btn, from, seg.to, durationMs, token, { raw });
          if (!ok) return;
          from = seg.to;
        }
        if (!anim.loop) break;
      }
      if (anim.hideAfter && !token.cancelled) {
        btn.style.visibility = "hidden";
        btn.style.pointerEvents = "none";
      }
    };

    runLoop();

    const onClick = async (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (escaping) return;
      if (anim.clickEscape) {
        escaping = true;
        token.cancelled = true;
        const from = getPos();
        const size = parseInt(btn.style.width, 10) || 48;
        const to = {
          left: from.left,
          top:
            anim.clickEscape.top != null
              ? anim.clickEscape.top
              : skyEscapeTop(size),
        };
        const escapeMs = anim.clickEscape.duration * 1000;
        await claimEasterEgg(egg);
        await animateEggSegment(
          btn,
          from,
          to,
          escapeMs,
          { cancelled: false },
          { raw: true },
        );
        return;
      }
      await claimEasterEgg(egg);
    };

    return { token, onClick };
  }

  function renderEasterEgg(egg, options = {}) {
    const { editable = false } = options;
    clearEggHosts();
    if (!egg) return null;

    const grass = !editable && isGrassEgg(egg);
    const host = document.getElementById(grass ? "meadow-eggs" : "sky-eggs");
    if (!host) return null;

    const btn = document.createElement("button");
    btn.type = "button";
    let className = "meadow-egg";
    if (grass) className += " meadow-egg--grass is-hidden";
    else className += " meadow-egg--sky";
    if (editable) className += " meadow-egg--edit";
    if (egg.effect === "smoke") className += " meadow-egg--smoke";
    btn.className = className;
    btn.dataset.zone = grass ? "grass" : "sky";
    if (egg.anchor) btn.dataset.anchor = egg.anchor;
    btn.title = egg.name || "";
    const size = egg.size || 48;
    btn.style.width = `${size}px`;
    btn.style.height = `${size}px`;
    btn.dataset.catalogTop = String(egg.topPx != null ? egg.topPx : egg.top);
    if (egg.topPx != null) btn.dataset.topPx = String(egg.topPx);
    if (egg.animation?.offScreen) btn.dataset.animOffScreen = "1";
    if (egg.anchor === "top") btn.classList.add("meadow-egg--anchor-top");
    setEggPosition(btn, egg.left, egg.topPx != null ? egg.topPx : egg.top);

    if (egg.effect === "smoke") {
      btn.innerHTML = `<span class="meadow-egg__smoke" aria-hidden="true"></span><img src="${egg.image}" alt="">`;
    } else {
      btn.innerHTML = `<img src="${egg.image}" alt="">`;
    }

    if (editable) {
      setupEggEditor(btn, egg);
    } else {
      const motion = startEggPathAnimation(btn, egg);
      if (motion) {
        btn.addEventListener("click", motion.onClick);
      } else {
        btn.addEventListener("click", (e) => {
          e.preventDefault();
          claimEasterEgg(egg);
        });
      }
    }

    host.appendChild(btn);
    ensureMeadowScrollListener();
    updateGrassEggVisibility(btn);
    return btn;
  }

  function setupEggEditor(btn, egg) {
    const panel = document.createElement("div");
    panel.id = "egg-edit-panel";
    panel.className = "egg-edit-panel";
    panel.innerHTML = `
      <div class="egg-edit-panel__title">Редактор пасхалки #${egg.id} — ${egg.name}</div>
      <div class="egg-edit-panel__coords"></div>
      <div class="egg-edit-panel__size">
        <span class="egg-edit-panel__size-label">Размер</span>
        <button type="button" class="egg-edit-panel__size-btn" data-size-delta="-8" aria-label="Меньше">−</button>
        <button type="button" class="egg-edit-panel__size-btn" data-size-delta="-4" aria-label="Чуть меньше">−</button>
        <span class="egg-edit-panel__size-val"></span>
        <button type="button" class="egg-edit-panel__size-btn" data-size-delta="4" aria-label="Чуть больше">+</button>
        <button type="button" class="egg-edit-panel__size-btn" data-size-delta="8" aria-label="Больше">+</button>
      </div>
      <div class="egg-edit-panel__hint">Тяни — двигать. Колёсико мыши на иконке — размер. Вставь JSON в <code>static/images/easter/catalog.json</code></div>
      <button type="button" class="egg-edit-panel__copy">Скопировать JSON</button>`;
    document.body.appendChild(panel);

    const coordsEl = panel.querySelector(".egg-edit-panel__coords");
    const sizeValEl = panel.querySelector(".egg-edit-panel__size-val");

    const readPos = () => {
      const usePx = btn.dataset.topPx != null && btn.dataset.topPx !== "";
      return {
        left: Math.round(parseFloat(btn.style.left) * 10) / 10,
        top: usePx
          ? Math.round(parseFloat(btn.dataset.viewportTop || btn.style.top))
          : Math.round(
              parseFloat(btn.dataset.viewportTop || btn.style.top) * 10,
            ) / 10,
        topPx: usePx,
        size: parseInt(btn.style.width, 10) || 48,
      };
    };

    const applySize = (next) => {
      const size = Math.min(128, Math.max(20, Math.round(next)));
      btn.style.width = `${size}px`;
      btn.style.height = `${size}px`;
      refreshPanel();
    };

    const snippet = () => {
      const p = readPos();
      const block = {
        id: egg.id,
        name: egg.name,
        image: egg.image,
        left: p.left,
        size: p.size,
      };
      if (p.topPx) block.topPx = p.top;
      else block.top = p.top;
      if (egg.anchor) block.anchor = egg.anchor;
      return JSON.stringify(block, null, 2);
    };

    const refreshPanel = () => {
      const p = readPos();
      const topLabel = p.topPx ? `${p.top}px` : `${p.top}%`;
      coordsEl.innerHTML = `left: <b>${p.left}</b>% · top: <b>${topLabel}</b> · size: <b>${p.size}</b>px`;
      sizeValEl.textContent = `${p.size}px`;
    };

    panel.querySelectorAll("[data-size-delta]").forEach((b) => {
      b.addEventListener("click", () => {
        applySize(readPos().size + parseInt(b.dataset.sizeDelta, 10));
      });
    });

    panel.querySelector(".egg-edit-panel__copy").addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(snippet());
        toast("JSON скопирован");
      } catch (_) {
        toast(snippet());
      }
    });

    refreshPanel();

    let dragging = false;
    btn.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        applySize(readPos().size + (e.deltaY < 0 ? 4 : -4));
      },
      { passive: false },
    );
    btn.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      dragging = true;
      btn.setPointerCapture(e.pointerId);
      e.preventDefault();
    });
    btn.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      const left = Math.min(98, Math.max(2, (e.clientX / window.innerWidth) * 100));
      if (btn.dataset.topPx != null && btn.dataset.topPx !== "") {
        const topPx = Math.min(
          window.innerHeight - 20,
          Math.max(0, Math.round(e.clientY)),
        );
        setEggPosition(btn, left, topPx);
      } else {
        const top = Math.min(98, Math.max(2, (e.clientY / window.innerHeight) * 100));
        setEggPosition(btn, left, top);
      }
      refreshPanel();
    });
    const stopDrag = (e) => {
      if (!dragging) return;
      dragging = false;
      try {
        btn.releasePointerCapture(e.pointerId);
      } catch (_) {}
    };
    btn.addEventListener("pointerup", stopDrag);
    btn.addEventListener("pointercancel", stopDrag);
  }

  async function resolveEasterEggDisplay() {
    const previewId = getEggQueryId();
    if (previewId) {
      const fromCatalog = await fetchEggFromCatalog(previewId);
      if (fromCatalog) {
        renderEasterEgg(fromCatalog, { editable: isEggEditMode() });
        return;
      }
    }
    renderEasterEgg(state?.easter_egg);
  }

  async function claimEasterEgg(egg) {
    if (!egg?.id) return;
    try {
      const res = await api("POST", `/api/easter-egg/claim?egg_id=${egg.id}`);
      if (state.easter_found != null) state.easter_found = res.found_total;
      if (res.already_found) {
        toast(`Уже найдена: ${res.egg.name}`);
      } else {
        toast(`Найдено: ${res.egg.name} · ${res.found_total}/${res.total}`);
      }
    } catch (_) {
      toast("Не удалось забрать пасхалку");
    }
  }

  function toast(msg) {
    let el = document.querySelector(".toast");
    if (!el) {
      el = document.createElement("div");
      el.className = "toast";
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2600);
  }

  function waterSplash() {
    const el = document.createElement("div");
    el.className = "water-splash";
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    for (let i = 0; i < 8; i++) {
      const s = document.createElement("span");
      s.textContent = "💧";
      s.style.left = cx + (Math.random() - 0.5) * 120 + "px";
      s.style.top = cy + (Math.random() - 0.5) * 80 + "px";
      s.style.animationDelay = Math.random() * 0.2 + "s";
      el.appendChild(s);
    }
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 900);
  }

  function initDevUser() {
    if (hasTgAuth()) return;
    const p = new URLSearchParams(location.search);
    const as = p.get("as");
    const ref = p.get("ref");
    if (as) {
      const id = parseInt(as, 10);
      if (!isNaN(id)) sessionStorage.setItem("dev_user_id", String(id));
    } else if (!sessionStorage.getItem("dev_user_id")) {
      sessionStorage.setItem("dev_user_id", ref ? "1002" : "1001");
    }
  }

  function getDevUserId() {
    return sessionStorage.getItem("dev_user_id") || "1001";
  }

  function parseRefCode(raw) {
    if (!raw) return null;
    const s = raw.startsWith("ref_") ? raw.slice(4) : raw;
    const code = parseInt(s, 10);
    return isNaN(code) ? null : code;
  }

  function parseRef() {
    const tg = getTg();
    const sp = tg?.initDataUnsafe?.start_param;
    const fromSp = parseRefCode(sp);
    if (fromSp) return fromSp;
    const p = new URLSearchParams(location.search);
    const directRef = p.get("ref");
    if (directRef) return parseRefCode(directRef);
    const startapp = p.get("startapp");
    if (startapp) return parseRefCode(startapp);
    return null;
  }

  async function api(method, path, body) {
    const tg = getTg();
    const apiBase =
      document.querySelector('meta[name="api-url"]')?.content?.replace(/\/$/, "") ||
      "";
    const opts = { method, headers: {} };
    if (tg?.initData) opts.headers["X-Telegram-Init-Data"] = tg.initData;
    if (!hasTgAuth()) opts.headers["X-Dev-User-Id"] = getDevUserId();
    if (body) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(apiBase + path, opts);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const msg =
        typeof err.detail === "string"
          ? err.detail
          : err.detail
            ? JSON.stringify(err.detail)
            : `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return res.json();
  }

  function formatTime(sec) {
    if (sec <= 0) return "00:00";
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (h > 0)
      return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  function progress(planted, ready) {
    const now = Math.floor(Date.now() / 1000);
    const total = ready - planted;
    return Math.min(100, Math.max(0, ((now - planted) / total) * 100));
  }

  function remaining(ready) {
    return Math.max(0, ready - Math.floor(Date.now() / 1000));
  }

  function bed(sprite, small) {
    const cls = small ? "bed__sprite bed__sprite--small" : "bed__sprite";
    return `
      <div class="bed">
        <span class="bed__sparkle">✨</span>
        <span class="bed__sparkle">⭐</span>
        <span class="bed__sparkle">✨</span>
        <div class="${cls} bed__sprite--${sprite}"></div>
        <div class="bed__grass"></div>
        <div class="bed__ground"></div>
      </div>`;
  }

  function selfWaterBtn(plantId) {
    const sw = state.self_water;
    const saved = formatSavedTime(getSelfWaterSeconds());
    const can = sw?.can_water;
    const wait = sw?.wait_seconds || 0;
    if (can) {
      return `
        <button class="btn btn-water self-water-btn" data-plant-id="${plantId}">
          <span>💧 Полить своё растение</span>
        </button>
        <span class="btn-water__sub">Ускорит рост на ${saved}</span>`;
    }
    return `
      <button class="btn btn-water self-water-btn" data-plant-id="${plantId}" disabled>
        <span>💧 Полив через ${formatTime(wait)}</span>
      </button>
      <span class="btn-water__sub">Следующий полив ускорит на ${saved}</span>`;
  }

  function renderGrowing(plant, slot) {
    const left = remaining(plant.ready_at);
    const pct = progress(plant.planted_at, plant.ready_at);
    return `
      <div class="plot" data-plant-id="${plant.id}">
        <span class="plot-badge">Растёт!</span>
        <h2>Грядка №${slot}</h2>
        ${bed("sprout", false)}
        <div class="timer-box">
          <div class="timer-box__label">⏳ До цветения</div>
          <div class="timer plant-timer" data-plant-id="${plant.id}">${formatTime(left)}</div>
          <div class="progress-track">
            <div class="progress-fill plant-progress" data-plant-id="${plant.id}" style="width:${pct}%"></div>
          </div>
        </div>
        ${selfWaterBtn(plant.id)}
        <p class="plot-desc" style="margin-top:12px;margin-bottom:0">Друзья тоже могут полить и ускорить рост</p>
      </div>`;
  }

  function renderEmpty(slot) {
    const dur = formatGrowthDuration(state.config.growth_duration);
    return `
      <div class="plot">
        <span class="plot-badge">Свободно</span>
        <h2>Грядка №${slot}</h2>
        <p class="plot-desc">Через ${dur} вырастет растение случайной редкости. Поливай сам — ускоришь рост!</p>
        ${bed("seed", true)}
        <button class="btn btn-plant plant-btn" data-slot="${slot}">
          <span>🌱 Посадить</span>
        </button>
      </div>`;
  }

  function renderReady(plants) {
    if (!plants.length) {
      return `<div class="empty-hint"><span class="empty-hint__seed"></span>Пока пусто — посади первое семечко на грядке!</div>`;
    }
    const items = plants
      .map(
        (p, i) => {
      const bg = BACKGROUND_MARKET[p.background_id] || BACKGROUND_MARKET[1];
      const price = getPlantPrice(p);
      const tile = plantBgAttrs(p.background_id);
      return `
      <div class="seed-card seed-card--${p.rarity}${tile.classExtra}" style="animation-delay:${i * 0.05}s;${tile.style}">
        ${plantArtHtml(p)}
        <div class="seed-card__tag tag-${p.rarity}">${RARITY_LABEL[p.rarity] || p.rarity}</div>
        <div class="seed-card__bg">${bg.name}</div>
        <div class="seed-card__bg">≈ ${formatNum(price)} ${coinHtml(true)}</div>
      </div>`;
    }
      )
      .join("");
    return `<div class="grid">${items}</div>`;
  }

  function renderFriend(plant) {
    const name =
      plant.owner_display_name ||
      (plant.owner_username ? `@${plant.owner_username}` : "друга");
    const left = remaining(plant.ready_at);
    return `
      <div class="plot plot--friend">
        <span class="plot-badge" style="background:var(--blue)">Сад друга</span>
        <h2>${name}</h2>
        <p class="plot-desc">Полей — ускоришь рост сада друга!</p>
        ${bed("leaf", false)}
        <div class="timer-box">
          <div class="timer-box__label">Осталось</div>
          <div class="timer" id="friend-timer">${formatTime(left)}</div>
        </div>
        <button class="btn btn-water" id="water-btn">
          <span>💧 Полить</span>
        </button>
      </div>`;
  }

  function renderStats() {
    return `
      <div class="stats">
        <div class="stat">
          <div class="stat-emoji">👫</div>
          <div class="stat-num">${state.stats.referrals}</div>
          <div class="stat-lbl">Друзей</div>
        </div>
        <div class="stat">
          <div class="stat-emoji">💧</div>
          <div class="stat-num">${state.stats.waterings}</div>
          <div class="stat-lbl">Поливов</div>
        </div>
      </div>`;
  }

  function renderStatusCard() {
    const growing = getGrowingPlants();
    if (growing.length) {
      const soonest = growing.reduce((a, b) =>
        a.ready_at < b.ready_at ? a : b
      );
      const left = remaining(soonest.ready_at);
      const title =
        growing.length === 1
          ? "Растёт на грядке"
          : `Растёт на ${growing.length} грядках`;
      return `
        <div class="status-card" id="go-plot">
          <div class="status-card__sprite status-card__sprite--sprout"></div>
          <div class="status-card__info">
            <div class="status-card__title">${title}</div>
            <div class="status-card__sub">Осталось ${formatTime(left)}</div>
          </div>
          <div class="status-card__arrow">→</div>
        </div>`;
    }
    return `
      <div class="status-card" id="go-plot">
        <div class="status-card__sprite status-card__sprite--seed"></div>
        <div class="status-card__info">
          <div class="status-card__title">Грядка свободна</div>
          <div class="status-card__sub">Посади семечко!</div>
        </div>
        <div class="status-card__arrow">→</div>
      </div>`;
  }

  function renderGardenTab() {
    const collectionValue = getCollectionValue();
    const globalCount = getGlobalDisplayCount();
    let html = `<div class="page-head">🏡 Мой сад</div>`;
    if (state.user.is_new) {
      html += `
        <div class="welcome">
          <strong>🎉 Ура, ты в садике!</strong>
          <span>Бонус за вход уже у тебя на счету</span>
        </div>`;
    }
    html += `
      <div class="stats">
        <div class="stat stat--wide">
          <div class="stat-emoji">🌍</div>
          <div class="stat-num" id="global-grown-count">${formatNum(globalCount)}</div>
          <div class="stat-lbl">Выращено в мире</div>
        </div>
        <div class="stat">
          <div class="stat-emoji">🌼</div>
          <div class="stat-num">${formatNum(state.ready_plants.length)}</div>
          <div class="stat-lbl">Твоих растений</div>
        </div>
        <div class="stat">
          <div class="stat-emoji">💎</div>
          <div class="stat-num">${formatNum(collectionValue)}</div>
          <div class="stat-lbl">Цена коллекции</div>
        </div>
      </div>`;
    html += renderStatusCard();
    html += renderStats();
    html += state.leaderboard
      ? renderLeaderboardHtml(state.leaderboard)
      : `
      <div class="leaderboard" id="leaderboard-section">
        <div class="section-title">🏆 Топ садов</div>
        <p class="leaderboard__empty">Загрузка рейтинга…</p>
      </div>`;
    html += `<div class="section-title">🏆 Коллекция</div>`;
    html += renderReady(state.ready_plants);
    return html;
  }

  function renderPlotTab() {
    const plotCount = getPlotCount();
    const growing = getGrowingPlants();
    const bySlot = Object.fromEntries(
      growing.map((p) => [p.plot_slot || 1, p])
    );
    let html = `<div class="page-head">🌱 Грядки (${plotCount})</div>`;
    const friendRef = parseRef();
    const isFriend = friendRef && friendRef !== state.user.ref_code;
    if (isFriend) html += `<div id="friend-section"></div>`;
    for (let slot = 1; slot <= plotCount; slot++) {
      if (bySlot[slot]) html += renderGrowing(bySlot[slot], slot);
      else html += renderEmpty(slot);
    }
    return html;
  }

  function renderFriendsTab() {
    const link = state.referral_link || `https://t.me/${state.bot_username}?start=ref_${state.user.telegram_id}`;
    return `
      <div class="page-head">👥 Друзья</div>
      <div class="ref-hero">
        <div class="ref-hero__icon">🎁</div>
        <h2>Приглашай друзей!</h2>
        <p>Вы оба получите бонус. Друг сможет полить твоё растение и ускорить рост.</p>
      </div>
      <ul class="ref-steps">
        <li><span class="ref-steps__num">1</span><span class="ref-steps__text">Поделись ссылкой с другом</span></li>
        <li><span class="ref-steps__num">2</span><span class="ref-steps__text">Друг регистрируется — вы оба получаете бонусные монеты</span></li>
        <li><span class="ref-steps__num">3</span><span class="ref-steps__text">Друг поливает твоё растение — рост быстрее</span></li>
      </ul>
      ${renderStats()}
      <button class="btn btn-share" id="copy-ref" style="width:100%;margin-top:4px">
        <span>📋 Скопировать ссылку</span>
      </button>
      <div class="page-card" style="margin-top:12px">
        <h3>Твоя ссылка</h3>
        <p style="word-break:break-all;font-size:0.78rem;margin-top:6px">${link}</p>
      </div>`;
  }

  function renderProfileTab() {
    const u = state.user;
    const initial = (u.display_name || "?").charAt(0).toUpperCase();
    const handle = u.username ? `@${u.username}` : "без username";
    const link = state.referral_link || "";
    const collectionValue = getCollectionValue();
    return `
      <div class="page-head">👤 Профиль</div>
      <div class="profile-hero">
        <div class="profile-avatar">${initial}</div>
        <div class="profile-name">${u.display_name || "Садовник"}</div>
        <div class="profile-handle">${handle}</div>
        <div class="profile-coins">${coinHtml(true)} ${u.coins}</div>
      </div>
      <div class="profile-grid">
        <div class="profile-stat">
          <div class="profile-stat-num">${state.stats.referrals}</div>
          <div class="profile-stat-lbl">Друзей</div>
        </div>
        <div class="profile-stat">
          <div class="profile-stat-num">${state.stats.waterings}</div>
          <div class="profile-stat-lbl">Поливов</div>
        </div>
        <div class="profile-stat">
          <div class="profile-stat-num">${state.ready_plants.length}</div>
          <div class="profile-stat-lbl">Растений</div>
        </div>
        <div class="profile-stat">
          <div class="profile-stat-num">${u.ref_code}</div>
          <div class="profile-stat-lbl">Код сада</div>
        </div>
        <div class="profile-stat">
          <div class="profile-stat-num">${formatNum(collectionValue)}</div>
          <div class="profile-stat-lbl">Цена коллекции</div>
        </div>
      </div>
      <button class="btn btn-share" id="copy-ref" style="width:100%">
        <span>📋 Скопировать реф. ссылку</span>
      </button>
      <div class="page-card" style="margin-top:12px">
        <h3>Твоя ссылка</h3>
        <p style="word-break:break-all;font-size:0.78rem;margin-top:6px">${link}</p>
      </div>
      <button type="button" class="btn btn-ads" id="ads-btn" style="width:100%;margin-top:14px">
        <span>📢 Реклама</span>${adsUnreadBadge()}
      </button>`;
  }

  function renderShopTab() {
    const shop = state.shop || {};
    const order = ["plot", "speed", "water_can"];
    const items = order
      .map((id, i) => {
        const meta = UPGRADE_META[id];
        const s = shop[id] || {};
        const maxed =
          id === "plot" ? (s.owned ?? 0) >= (s.max ?? 9) : s.level >= s.max;
        const price = s.price;
        const canBuy = s.can_buy;
        let action = "";
        if (maxed) {
          action = `<div class="upgrade-card__badge">Макс.</div>`;
        } else if (canBuy) {
          action = `<button class="upgrade-card__buy buy-btn" data-upgrade="${id}">${formatNum(price)} ${coinHtml(true)}</button>`;
        } else {
          action = `<div class="upgrade-card__badge">${formatNum(price)} ${coinHtml(true)}</div>`;
        }
        return `
        <div class="upgrade-card${maxed ? " upgrade-card--maxed" : ""}" style="animation-delay:${i * 0.05}s">
          <div class="upgrade-card__icon">${meta.icon}</div>
          <div class="upgrade-card__body">
            <div class="upgrade-card__name">${meta.name}</div>
            <div class="upgrade-card__desc">${meta.desc(s)}</div>
          </div>
          ${action}
        </div>`;
      })
      .join("");
    return `
      <div class="page-head">⚡ Улучшения</div>
      <div class="page-card">
        <h3>Магазин сада</h3>
        <p>На счету: ${formatNum(state.user.coins)} ${coinHtml(true)}. Монеты за рефералов — на грядки и усиления.</p>
      </div>
      ${items}`;
  }

  function setTab(tab) {
    if (!TABS.includes(tab)) return;
    currentTab = tab;
    tabbar.querySelectorAll(".tabbar__btn").forEach((btn) => {
      btn.classList.toggle("tabbar__btn--active", btn.dataset.tab === tab);
    });
    render();
  }

  function render() {
    if (!state) return;
    let html = "";
    switch (currentTab) {
      case "garden":
        html = renderGardenTab();
        break;
      case "plot":
        html = renderPlotTab();
        break;
      case "friends":
        html = renderFriendsTab();
        break;
      case "shop":
        html = renderShopTab();
        break;
      case "profile":
        html = renderProfileTab();
        break;
    }
    main.innerHTML = html;
    bindEvents();
    ensureTickLoop();
    if (currentTab === "garden") {
      ensureLeaderboard().then(() => updateLeaderboardSection());
    }
    updateGrassEggVisibility();
  }

  async function loadFriend(refCode) {
    try {
      const data = await api("GET", `/api/friend/${refCode}`);
      const sec = $("#friend-section");
      if (!sec) return;
      if (data.plant) {
        sec.innerHTML = renderFriend(data.plant);
        state._friendPlant = data.plant;
        $("#water-btn")?.addEventListener("click", () => waterFriend(refCode, data.plant));
      } else {
        sec.innerHTML = `
          <div class="welcome">
            <strong>Ты перешёл по ссылке друга!</strong>
            <span>Но у него пока нет растения — попроси посадить семечко 🌱</span>
          </div>`;
      }
    } catch (_) {}
  }

  function bindEvents() {
    document.querySelectorAll(".plant-btn").forEach((btn) => {
      btn.addEventListener("click", () => plantSeed(parseInt(btn.dataset.slot, 10)));
    });
    document.querySelectorAll(".self-water-btn").forEach((btn) => {
      btn.addEventListener("click", () =>
        waterSelf(parseInt(btn.dataset.plantId, 10), btn)
      );
    });
    document.querySelectorAll(".buy-btn").forEach((btn) => {
      btn.addEventListener("click", () => buyUpgrade(btn.dataset.upgrade, btn));
    });
    $("#copy-ref")?.addEventListener("click", copyRef);
    $("#ads-btn")?.addEventListener("click", openAdsPanel);
    $("#go-plot")?.addEventListener("click", () => setTab("plot"));

    const friendRef = parseRef();
    const isFriend = friendRef && friendRef !== state.user.ref_code;
    if (currentTab === "plot" && isFriend && friendRef) loadFriend(friendRef);
  }

  function copyRef() {
    const link = state.referral_link || "";
    navigator.clipboard.writeText(link).then(() => toast("Ссылка скопирована! 🎁"));
  }

  async function plantSeed(slot) {
    const btn = document.querySelector(`.plant-btn[data-slot="${slot}"]`);
    if (btn) btn.disabled = true;
    try {
      const data = await api("POST", `/api/plant?slot=${slot}`);
      const plants = getGrowingPlants().filter((p) => p.plot_slot !== slot);
      plants.push(data.plant);
      state.growing_plants = plants.sort((a, b) => a.plot_slot - b.plot_slot);
      state.growing = state.growing_plants[0] || null;
      render();
      toast("Семечко посажено! 🌱");
    } catch (e) {
      toast("Не удалось посадить");
      if (btn) btn.disabled = false;
    }
  }

  async function waterSelf(plantId, btnEl) {
    const btn = btnEl || document.querySelector(`.self-water-btn[data-plant-id="${plantId}"]`);
    if (btn) btn.disabled = true;
    try {
      const res = await api("POST", `/api/water-self?plant_id=${plantId}`);
      waterSplash();
      const plant = getGrowingPlants().find((p) => p.id === plantId);
      if (plant) plant.ready_at = res.new_ready_at;
      state.self_water = { can_water: false, wait_seconds: state.config.self_water_cooldown };
      toast(`Полито! −${formatSavedTime(res.reduction_seconds || res.time_saved)} 💧`);
      render();
    } catch (e) {
      const msg =
        e.detail?.error === "cooldown"
          ? `Подожди ${formatTime(e.detail.wait_seconds)}`
          : "Не удалось полить";
      toast(msg);
      if (btn) btn.disabled = false;
    }
  }

  async function buyUpgrade(id, btnEl) {
    if (btnEl) btnEl.disabled = true;
    try {
      const res = await api("POST", `/api/buy/${id}`);
      state.user.coins = res.coins;
      state.upgrades = res.upgrades;
      state.shop = res.shop;
      state.config.growth_duration = res.upgrades.growth_duration;
      state.config.self_water_seconds = res.upgrades.self_water_seconds;
      updateHeader();
      render();
      const names = { plot: "Грядка", speed: "Ускорение", water_can: "Лейка" };
      toast(`${names[id] || "Улучшение"} куплено! 🎉`);
    } catch (e) {
      const err = e.detail?.error || e.error;
      const msg =
        err === "not_enough_coins"
          ? "Не хватает монет"
          : err === "max_level"
          ? "Уже максимум"
          : "Не удалось купить";
      toast(msg);
      if (btnEl) btnEl.disabled = false;
    }
  }

  async function waterFriend(ownerRef, plant) {
    const btn = $("#water-btn");
    if (btn) btn.disabled = true;
    try {
      const res = await api(
        "POST",
        `/api/water/${plant.id}?owner_ref=${ownerRef}`
      );
      waterSplash();
      toast("Спасибо за полив! 💧");
      await refresh();
    } catch (e) {
      const msg =
        e.detail?.error === "cooldown"
          ? `Подожди ${formatTime(e.detail.wait_seconds)}`
          : e.detail?.error === "cannot_water_own"
          ? "Это твой сад — используй свой полив"
          : "Не удалось полить";
      toast(msg);
      if (btn) btn.disabled = false;
    }
  }

  function ensureTickLoop() {
    if (tickId) return;
    tickId = setInterval(onTick, 1000);
  }

  function onTick() {
    if (!state) return;

    const now = Math.floor(Date.now() / 1000);
    if (state.global_stats?.window_end && state.global_stats.window_end <= now) {
      ensureGlobalStats();
    }

    if (currentTab === "garden" && state.global_stats) {
      const counter = document.getElementById("global-grown-count");
      if (counter) counter.textContent = formatNum(getGlobalDisplayCount());
    }

    const growing = getGrowingPlants();
    if (growing.length) {
      let anyReady = false;
      const soonest = growing.reduce((a, b) =>
        a.ready_at < b.ready_at ? a : b
      );

      for (const plant of growing) {
        const left = remaining(plant.ready_at);
        const t = document.querySelector(`.plant-timer[data-plant-id="${plant.id}"]`);
        const p = document.querySelector(`.plant-progress[data-plant-id="${plant.id}"]`);
        if (t) t.textContent = formatTime(left);
        if (p) p.style.width = progress(plant.planted_at, plant.ready_at) + "%";
        if (left <= 0) anyReady = true;
      }

      const ft = $("#friend-timer");
      if (ft && state._friendPlant)
        ft.textContent = formatTime(remaining(state._friendPlant.ready_at));

      const statusSub = document.querySelector(".status-card__sub");
      if (statusSub && currentTab === "garden")
        statusSub.textContent = `Осталось ${formatTime(remaining(soonest.ready_at))}`;

      if (anyReady && !refreshing) refresh(true);
    }

    if (
      growing.length &&
      !state.self_water?.can_water &&
      state.self_water?.wait_seconds > 0
    ) {
      state.self_water.wait_seconds = Math.max(0, state.self_water.wait_seconds - 1);
      const saved = formatSavedTime(getSelfWaterSeconds());
      if (state.self_water.wait_seconds <= 0) {
        state.self_water.can_water = true;
        if (currentTab === "plot") {
          document.querySelectorAll(".self-water-btn").forEach((btn) => {
            btn.disabled = false;
            btn.innerHTML = `<span>💧 Полить своё растение</span>`;
          });
          document.querySelectorAll(".btn-water__sub").forEach((sub) => {
            sub.textContent = `Ускорит рост на ${saved}`;
          });
        }
      } else if (currentTab === "plot") {
        document.querySelectorAll(".self-water-btn").forEach((btn) => {
          btn.innerHTML = `<span>💧 Полив через ${formatTime(state.self_water.wait_seconds)}</span>`;
        });
      }
    }
  }

  function updateHeader() {
    const num = coinsEl.querySelector(".coin-num");
    if (num) num.textContent = state.user.coins;
    else
      coinsEl.innerHTML = `${coinHtml()}<span class="coin-num">${state.user.coins}</span>`;
    modeEl.textContent =
      (state.config.mode === "test" ? "тест" : "игра") +
      (hasTgAuth() ? "" : ` · игрок ${getDevUserId()}`);
  }

  async function refresh(fromMaturity) {
    if (refreshing) return;
    refreshing = true;
    try {
      const globalStats = state?.global_stats || readGlobalStatsCache();
      const prevGrowingIds = fromMaturity
        ? new Set(getGrowingPlants().map((p) => p.id))
        : null;
      const prevReadyIds = new Set((state?.ready_plants || []).map((p) => p.id));
      const ref = parseRef();
      const q = ref ? `?ref=${ref}` : "";
      state = await api("GET", "/api/me" + q);
      if (globalStats) state.global_stats = globalStats;
      updateHeader();
      render();

      if (fromMaturity && prevGrowingIds) {
        const newPlants = state.ready_plants.filter((p) => !prevReadyIds.has(p.id));
        newPlants.forEach((plant) => queueHarvestModal(plant));
      }
    } finally {
      refreshing = false;
    }
  }

  function readGlobalStatsCache() {
    try {
      const raw = localStorage.getItem(GLOBAL_STATS_CACHE_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw);
      const now = Math.floor(Date.now() / 1000);
      if (!data?.window_end || data.window_end <= now) return null;
      return data;
    } catch (_) {
      return null;
    }
  }

  async function ensureGlobalStats() {
    if (globalStatsLoading) return;
    globalStatsLoading = true;
    try {
    const cached = readGlobalStatsCache();
    if (cached) {
      state.global_stats = cached;
      return;
    }
    const data = await api("GET", "/api/global-stats");
    state.global_stats = data;
    try {
      localStorage.setItem(GLOBAL_STATS_CACHE_KEY, JSON.stringify(data));
    } catch (_) {}
    } finally {
      globalStatsLoading = false;
    }
  }

  tabbar.addEventListener("click", (e) => {
    const btn = e.target.closest(".tabbar__btn");
    if (btn?.dataset.tab) setTab(btn.dataset.tab);
  });

  async function init() {
    const tg = getTg();
    if (tg?.initData) {
      tg.ready();
      tg.expand();
    }
    initDevUser();
    try {
      const ref = parseRef();
      const meParams = new URLSearchParams();
      if (ref) meParams.set("ref", String(ref));
      meParams.set("fresh_egg", "1");
      const meQuery = meParams.toString();
      const cachedStats = readGlobalStatsCache();
      const mePromise = api("GET", "/api/me" + (meQuery ? `?${meQuery}` : ""));
      const statsPromise = cachedStats
        ? Promise.resolve(cachedStats)
        : api("GET", "/api/global-stats").catch(() => null);

      state = await mePromise;
      updateHeader();
      loader.remove();
      tabbar.hidden = false;

      const stats = await statsPromise;
      if (stats) {
        state.global_stats = stats;
        if (!cachedStats) {
          try {
            localStorage.setItem(GLOBAL_STATS_CACHE_KEY, JSON.stringify(stats));
          } catch (_) {}
        }
      }

      if (ref && ref !== state.user.ref_code) setTab("plot");
      else render();
      await resolveEasterEggDisplay();
      ensureTickLoop();
      startAdPlane();
    } catch (e) {
      const tg = getTg();
      const detail = e?.message && e.message !== "HTTP error" ? ` (${e.message})` : "";
      loader.querySelector("p").textContent = tg?.initData
        ? `Ошибка загрузки${detail}. Если не помогло — проверь BOT_TOKEN на Amvera.`
        : location.hostname === "localhost" || location.hostname === "127.0.0.1"
          ? "Локально: в .env нужен DEV_MODE=true, затем открой /?egg=7&edit=1"
          : "Открой через бота @flt_garden_bot → «Открыть сад»";
    }
  }

  function startAdPlane() {
    const plane = document.getElementById("ad-plane");
    if (!plane) return;

    const messages = [
      "Здесь могла бы быть ваша реклама",
      "Место для вашего бренда",
      "Рекламируйтесь в нашем саду",
      "Ваш баннер — прямо тут",
    ];

    let flying = false;

    function fly() {
      if (flying) return;
      flying = true;

      const text = plane.querySelector(".ad-plane__text");
      if (text) text.textContent = messages[Math.floor(Math.random() * messages.length)];

      plane.hidden = false;
      plane.classList.remove("ad-plane--fly");
      void plane.offsetWidth;
      plane.classList.add("ad-plane--fly");

      plane.addEventListener(
        "animationend",
        () => {
          plane.classList.remove("ad-plane--fly");
          plane.hidden = true;
          flying = false;
          schedule();
        },
        { once: true }
      );
    }

    function schedule() {
      const wait = 90000 + Math.random() * 90000;
      setTimeout(fly, wait);
    }

    setTimeout(fly, 5000 + Math.random() * 5000);
  }

  init();
})();
