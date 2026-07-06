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
  let timerId = null;
  let selfWaterTimerId = null;

  const TABS = ["garden", "plot", "friends", "shop", "profile"];

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

  const UPGRADES = [
    { id: "plot2", icon: "🌱", name: "Вторая грядка", desc: "Выращивай 2 растения одновременно", price: 500 },
    { id: "speed", icon: "⚡", name: "Ускорение роста", desc: "−15% ко времени выращивания", price: 300 },
    { id: "water", icon: "💧", name: "Золотая лейка", desc: "Свой полив сильнее на 10%", price: 250 },
    { id: "bonus", icon: "💰", name: "Щедрый урожай", desc: "+20% монет за поливы друзей", price: 400 },
  ];

  function coinHtml(sm) {
    return `<span class="coin${sm ? " coin--sm" : ""}" aria-hidden="true"></span>`;
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
      throw err;
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

  function selfWaterBtn() {
    const sw = state.self_water;
    const pct = state.config.self_water_reduction_percent;
    const can = sw?.can_water;
    const wait = sw?.wait_seconds || 0;
    if (can) {
      return `
        <button class="btn btn-water" id="self-water-btn">
          <span>💧 Полить своё растение</span>
        </button>
        <span class="btn-water__sub">Ускорит рост на ${pct}%</span>`;
    }
    return `
      <button class="btn btn-water" id="self-water-btn" disabled>
        <span>💧 Полив через ${formatTime(wait)}</span>
      </button>
      <span class="btn-water__sub">Следующий полив ускорит на ${pct}%</span>`;
  }

  function renderGrowing(plant) {
    const left = remaining(plant.ready_at);
    const pct = progress(plant.planted_at, plant.ready_at);
    return `
      <div class="plot">
        <span class="plot-badge">Растёт!</span>
        <h2>Грядка №1</h2>
        ${bed("sprout", false)}
        <div class="timer-box">
          <div class="timer-box__label">⏳ До цветения</div>
          <div class="timer" id="timer">${formatTime(left)}</div>
          <div class="progress-track">
            <div class="progress-fill" id="progress" style="width:${pct}%"></div>
          </div>
        </div>
        ${selfWaterBtn()}
        <p class="plot-desc" style="margin-top:12px;margin-bottom:0">Друзья тоже могут полить — им достанется бонус ${coinHtml(true)}</p>
      </div>`;
  }

  function renderEmpty() {
    const dur = state.config.mode === "test" ? "5 минут" : "10 часов";
    return `
      <div class="plot">
        <span class="plot-badge">Свободно</span>
        <h2>Грядка №1</h2>
        <p class="plot-desc">Через ${dur} вырастет растение случайной редкости. Поливай сам — ускоришь рост!</p>
        ${bed("seed", true)}
        <button class="btn btn-plant" id="plant-btn">
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
        (p, i) => `
      <div class="seed-card seed-card--${p.rarity}" style="animation-delay:${i * 0.05}s">
        <div class="seed-card__emoji">${RARITY_EMOJI[p.rarity] || "🌿"}</div>
        <div class="seed-card__tag tag-${p.rarity}">${RARITY_LABEL[p.rarity] || p.rarity}</div>
        <div class="seed-card__bg">фон №${p.background_id}</div>
      </div>`
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
        <p class="plot-desc">Полей — ускоришь рост и получишь бонус!</p>
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
    if (state.growing) {
      const left = remaining(state.growing.ready_at);
      return `
        <div class="status-card" id="go-plot">
          <div class="status-card__sprite status-card__sprite--sprout"></div>
          <div class="status-card__info">
            <div class="status-card__title">Растёт на грядке</div>
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
    let html = `<div class="page-head">🏡 Мой сад</div>`;
    if (state.user.is_new) {
      html += `
        <div class="welcome">
          <strong>🎉 Ура, ты в садике!</strong>
          <span>Бонус за вход уже у тебя на счету</span>
        </div>`;
    }
    html += renderStatusCard();
    html += renderStats();
    html += `<div class="section-title">🏆 Коллекция</div>`;
    html += renderReady(state.ready_plants);
    return html;
  }

  function renderPlotTab() {
    let html = `<div class="page-head">🌱 Грядка</div>`;
    const friendRef = parseRef();
    const isFriend = friendRef && friendRef !== state.user.ref_code;
    if (isFriend) html += `<div id="friend-section"></div>`;
    if (state.growing) html += renderGrowing(state.growing);
    else html += renderEmpty();
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
        <li><span>1</span> Поделись ссылкой с другом</li>
        <li><span>2</span> Друг регистрируется — вы оба получаете ${coinHtml(true)} монеты</li>
        <li><span>3</span> Друг поливает твоё растение — рост быстрее</li>
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
      </div>
      <button class="btn btn-share" id="copy-ref" style="width:100%">
        <span>📋 Скопировать реф. ссылку</span>
      </button>
      <div class="page-card" style="margin-top:12px">
        <h3>Твоя ссылка</h3>
        <p style="word-break:break-all;font-size:0.78rem;margin-top:6px">${link}</p>
      </div>`;
  }

  function renderShopTab() {
    const coins = state.user.coins;
    const items = UPGRADES.map((u, i) => {
      const canBuy = coins >= u.price;
      return `
        <div class="upgrade-card upgrade-card--locked" style="animation-delay:${i * 0.05}s">
          <div class="upgrade-card__icon">${u.icon}</div>
          <div class="upgrade-card__body">
            <div class="upgrade-card__name">${u.name}</div>
            <div class="upgrade-card__desc">${u.desc}</div>
          </div>
          <div class="upgrade-card__badge">Скоро</div>
        </div>`;
    }).join("");
    return `
      <div class="page-head">⚡ Улучшения</div>
      <div class="page-card">
        <h3>Магазин сада</h3>
        <p>Трать монеты на улучшения — больше грядок, быстрее рост, круче бонусы.</p>
      </div>
      ${items}
      <p class="shop-soon">Покупки появятся в следующем обновлении 🛠</p>`;
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
    if (state.growing) {
      startTimer();
      if (currentTab === "plot") startSelfWaterTimer();
    }
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
    $("#plant-btn")?.addEventListener("click", plantSeed);
    $("#self-water-btn")?.addEventListener("click", waterSelf);
    $("#copy-ref")?.addEventListener("click", copyRef);
    $("#go-plot")?.addEventListener("click", () => setTab("plot"));

    const friendRef = parseRef();
    const isFriend = friendRef && friendRef !== state.user.ref_code;
    if (currentTab === "plot" && isFriend && friendRef) loadFriend(friendRef);
  }

  function copyRef() {
    const link = state.referral_link || "";
    navigator.clipboard.writeText(link).then(() => toast("Ссылка скопирована! 🎁"));
  }

  async function plantSeed() {
    const btn = $("#plant-btn");
    if (btn) btn.disabled = true;
    try {
      const data = await api("POST", "/api/plant");
      state.growing = data.plant;
      state.self_water = { can_water: true, wait_seconds: 0 };
      render();
      toast("Семечко посажено! 🌱");
    } catch (e) {
      toast("Не удалось посадить");
      if (btn) btn.disabled = false;
    }
  }

  async function waterSelf() {
    const btn = $("#self-water-btn");
    if (btn) btn.disabled = true;
    try {
      const res = await api("POST", "/api/water-self");
      waterSplash();
      if (state.growing) state.growing.ready_at = res.new_ready_at;
      state.self_water = { can_water: false, wait_seconds: state.config.self_water_cooldown };
      toast(`Полито! −${res.reduction_percent}% времени 💧`);
      render();
      await refresh();
    } catch (e) {
      const msg =
        e.detail?.error === "cooldown"
          ? `Подожди ${formatTime(e.detail.wait_seconds)}`
          : "Не удалось полить";
      toast(msg);
      if (btn) btn.disabled = false;
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
      toast(`+${res.bonus_coins} монет! Спасибо за полив!`);
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

  function startTimer() {
    if (timerId) clearInterval(timerId);
    if (!state?.growing) return;

    timerId = setInterval(() => {
      const left = remaining(state.growing.ready_at);
      const t = $("#timer");
      const p = $("#progress");
      const ft = $("#friend-timer");

      if (t) t.textContent = formatTime(left);
      if (p)
        p.style.width =
          progress(state.growing.planted_at, state.growing.ready_at) + "%";
      if (ft && state._friendPlant)
        ft.textContent = formatTime(remaining(state._friendPlant.ready_at));

      const statusSub = document.querySelector(".status-card__sub");
      if (statusSub && currentTab === "garden")
        statusSub.textContent = `Осталось ${formatTime(left)}`;

      if (left <= 0) {
        clearInterval(timerId);
        refresh();
      }
    }, 1000);
  }

  function startSelfWaterTimer() {
    if (selfWaterTimerId) clearInterval(selfWaterTimerId);
    if (!state?.growing || state.self_water?.can_water) return;

    selfWaterTimerId = setInterval(() => {
      if (!state.self_water || state.self_water.can_water) {
        clearInterval(selfWaterTimerId);
        return;
      }
      state.self_water.wait_seconds = Math.max(0, state.self_water.wait_seconds - 1);
      const btn = $("#self-water-btn");
      if (btn) {
        if (state.self_water.wait_seconds <= 0) {
          state.self_water.can_water = true;
          clearInterval(selfWaterTimerId);
          if (currentTab === "plot") render();
        } else {
          btn.innerHTML = `<span>💧 Полив через ${formatTime(state.self_water.wait_seconds)}</span>`;
        }
      }
    }, 1000);
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

  async function refresh() {
    const ref = parseRef();
    const q = ref ? `?ref=${ref}` : "";
    state = await api("GET", "/api/me" + q);
    updateHeader();
    render();
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
      const q = ref ? `?ref=${ref}` : "";
      state = await api("GET", "/api/me" + q);
      updateHeader();
      loader.remove();
      tabbar.hidden = false;

      if (ref && ref !== state.user.ref_code) setTab("plot");
      else render();
    } catch (e) {
      const tg = getTg();
      loader.querySelector("p").textContent = tg?.initData
        ? "Ошибка загрузки. Проверь BOT_TOKEN на Amvera."
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

    setTimeout(fly, 20000 + Math.random() * 25000);
  }

  init();
  startAdPlane();
})();
