const state = {
  mediaVersion: Date.now(),
};

const fallbackRecords = [
  {
    id: "sample-1",
    name: "エチオピア イルガチェフェ G1",
    date: "2024-05-18",
    country: "エチオピア",
    processing: "ウォッシュド",
    roast_level: "シティロースト",
    taste_rating: 5,
    public_summary: "華やかな香り。レモンのような酸味と紅茶のような余韻。",
  },
  {
    id: "sample-2",
    name: "ブラジル ショコラ",
    date: "2024-05-15",
    country: "ブラジル",
    processing: "ナチュラル",
    roast_level: "フルシティロースト",
    taste_rating: 4,
    public_summary: "チョコレートのような甘さ。ナッツ感とコクが心地よい。",
  },
  {
    id: "sample-3",
    name: "グアテマラ アンティグア",
    date: "2024-05-12",
    country: "グアテマラ",
    processing: "ウォッシュド",
    roast_level: "ハイロースト",
    taste_rating: 3,
    public_summary: "柑橘の明るい酸味。すっきりとして飲みやすい。",
  },
  {
    id: "sample-4",
    name: "コロンビア スプレモ",
    date: "2024-05-09",
    country: "コロンビア",
    processing: "ウォッシュド",
    roast_level: "シティロースト",
    taste_rating: 4,
    public_summary: "バランスが良く、毎日飲みたくなる味。",
  },
];

const $ = (selector, root = document) => root.querySelector(selector);

init();

async function init() {
  try {
    const data = await fetchPublicJournal();
    const records = data.journal?.length ? data.journal : fallbackRecords;
    renderHero(data.stats || {}, records);
    renderJournal(records.slice(0, 4));
    renderFavorites(records.slice(0, 3));
  } catch (error) {
    renderHero({}, fallbackRecords);
    renderJournal(fallbackRecords);
    renderFavorites(fallbackRecords.slice(0, 3));
  }
}

async function fetchPublicJournal() {
  const res = await fetch(`/api/public/journal?v=${state.mediaVersion}`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

function renderHero(stats, records) {
  const count = stats.count ?? records.length ?? 0;
  $("#hero-title")?.setAttribute("data-count", String(count));
}

function renderJournal(records) {
  const grid = $("#journal-grid");
  if (!grid) return;
  grid.innerHTML = records.length ? records.map((record, index) => roastCard(record, index)).join("") : emptyNote();
}

function renderFavorites(records) {
  const list = $("#favorite-list");
  if (!list) return;
  list.innerHTML = records.length ? records.map((record, index) => favoriteCard(record, index)).join("") : emptyNote();
}

function roastCard(record, index) {
  return `
    <article class="roast-card">
      <div class="roast-image">
        <img src="${escapeAttr(recordImage(record, index))}" alt="">
        <span class="roast-date">${escapeHtml(displayDate(record.date))}</span>
      </div>
      <h3 class="roast-title">${escapeHtml(record.name || "無題の焙煎")}</h3>
      <dl class="detail-list">
        ${detailRow("焙煎日", displayDate(record.date))}
        ${detailRow("豆", beanLine(record))}
        ${detailRow("焙煎度", record.roast_level || "-")}
        ${detailRow("味メモ", record.public_summary || "香りと余韻を記録中。")}
        ${detailRow("評価", stars(record.taste_rating), "rating")}
      </dl>
      <a class="card-link" href="#journal">もっと見る <span aria-hidden="true">→</span></a>
    </article>`;
}

function favoriteCard(record, index) {
  return `
    <article class="favorite-card">
      <div class="roast-image">
        <img src="${escapeAttr(recordImage(record, index + 2))}" alt="">
      </div>
      <div class="favorite-body">
        <h3 class="roast-title">${escapeHtml(record.name || "お気に入りの焙煎")}</h3>
        <dl class="detail-list">
          ${detailRow("焙煎日", displayDate(record.date))}
          ${detailRow("焙煎度", record.roast_level || "-")}
          ${detailRow("評価", stars(record.taste_rating), "rating")}
        </dl>
        <span class="reason-label">お気に入り理由</span>
        <p class="summary">${escapeHtml(record.public_summary || "何度も飲みたくなる、印象の残るコーヒー。")}</p>
      </div>
    </article>`;
}

function detailRow(label, value, className = "") {
  return `<div class="detail-row ${className}"><dt>${escapeHtml(label)}</dt><dd>${value}</dd></div>`;
}

function beanLine(record) {
  const parts = [record.country, record.region, record.processing].filter(Boolean);
  return escapeHtml(parts.length ? parts.join(" / ") : record.name || "-");
}

function displayDate(value) {
  if (!value) return "-";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return String(value);
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}.${m}.${d}`;
}

function stars(value) {
  const rating = Math.max(0, Math.min(5, Number(value) || 0));
  return `${"★".repeat(rating)}${"☆".repeat(5 - rating)}`;
}

function recordImage(record, index) {
  if (record.lead_photo_url) return mediaUrl(record.lead_photo_url);
  return `/assets/roast-level.png#crop-${index}`;
}

function mediaUrl(url) {
  return `${url}${url.includes("?") ? "&" : "?"}v=${state.mediaVersion}`;
}

function emptyNote() {
  return `<div class="empty-note">公開された焙煎記録がまだありません。管理画面で「公開LPに掲載する」を選ぶと、ここに焙煎日記として表示されます。</div>`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}
