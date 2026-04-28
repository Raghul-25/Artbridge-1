"use strict";
/**
 * app.js — ArtBridge Home Page
 *
 * Key design:
 *  masterProducts  — full list fetched once from /products, NEVER overwritten
 *  displayedProducts — subset shown after category filter
 *  Search always filters masterProducts (fixes the original bug where
 *  filterCategory() was overwriting allProducts)
 */

let masterProducts   = [];   // all products, set once, never mutated
let displayedProducts = [];  // current filter subset shown in grid
let currentCategory  = "all";

const CART_KEY = "artbridge_cart_v1";

/* ── Placeholder SVG ────────────────────────────────────────────────────── */
const PLACEHOLDER_IMG =
  "data:image/svg+xml;charset=UTF-8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400">
      <defs>
        <linearGradient id="g" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stop-color="#231810"/>
          <stop offset="1" stop-color="#1a120b"/>
        </linearGradient>
      </defs>
      <rect width="100%" height="100%" fill="url(#g)"/>
      <text x="50%" y="52%" dominant-baseline="middle" text-anchor="middle"
        fill="rgba(184,149,106,0.45)" font-family="Arial,sans-serif" font-size="18">No Image</text>
    </svg>`
  );

/* ── Cart Helpers ───────────────────────────────────────────────────────── */
function readCart() {
  try {
    const raw    = localStorage.getItem(CART_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeCart(items) {
  localStorage.setItem(CART_KEY, JSON.stringify(items));
  updateCartBadge();
}

function updateCartBadge() {
  const cart  = readCart();
  const total = cart.reduce((sum, x) => sum + (x.qty || 1), 0);
  const badge = document.getElementById("cartCount");
  if (badge) badge.textContent = total;
}

function addToCart(product) {
  const id = product?.id;
  if (!id) return;
  const cart     = readCart();
  const existing = cart.find((x) => String(x?.id) === String(id));
  if (existing) {
    existing.qty = (existing.qty || 1) + 1;
  } else {
    cart.push({
      id,
      name:      product?.name ?? "",
      price:     product?.price,
      image_url: product?.image_url ?? null,
      qty:       1,
    });
  }
  writeCart(cart);
  showToast(`"${product?.name}" added to cart 🛒`, "success");
}

/* ── Toast ──────────────────────────────────────────────────────────────── */
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span class="toast-icon"></span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add("leaving");
    setTimeout(() => toast.remove(), 280);
  }, 3000);
}

/* ── Fetch ──────────────────────────────────────────────────────────────── */
async function fetchData(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error(`Fetch failed [${url}]:`, err);
    showToast("Failed to load products. Is the server running?", "error");
    return null;
  }
}

/* ── Skeleton Loader ────────────────────────────────────────────────────── */
function showSkeletons(count = 8) {
  const grid = document.getElementById("productGrid");
  if (!grid) return;
  grid.innerHTML = "";
  for (let i = 0; i < count; i++) {
    grid.innerHTML += `
      <div class="skeleton">
        <div class="skeleton-img"></div>
        <div class="skeleton-body">
          <div class="skeleton-line short"></div>
          <div class="skeleton-line medium"></div>
          <div class="skeleton-line full"></div>
        </div>
      </div>`;
  }
}

/* ── Load Products ──────────────────────────────────────────────────────── */
async function loadProducts() {
  showSkeletons();
  const products = await fetchData("/products");
  masterProducts    = Array.isArray(products) ? products : [];
  displayedProducts = [...masterProducts];

  // Hero stat
  const stat = document.getElementById("statProducts");
  if (stat) stat.textContent = masterProducts.length + "+";

  displayProducts(masterProducts);
  updateSectionMeta("Featured Products", masterProducts.length);
}

/* ── Category Filter ────────────────────────────────────────────────────── */
async function filterCategory(category, chipEl) {
  currentCategory = category;

  // Update active chip
  document.querySelectorAll(".filter-chip").forEach((c) =>
    c.classList.remove("active")
  );
  if (chipEl) chipEl.classList.add("active");

  // Reset search input (but DO NOT reset masterProducts)
  const searchInput = document.getElementById("search");
  if (searchInput) searchInput.value = "";

  if (category === "all") {
    displayedProducts = [...masterProducts];
    displayProducts(displayedProducts);
    updateSectionMeta("All Products", displayedProducts.length);
    return;
  }

  showSkeletons(4);
  const products = await fetchData(`/products/${category}`);
  displayedProducts = Array.isArray(products) ? products : [];

  displayProducts(displayedProducts);
  const labels = { mud: "Mud Pots", basket: "Baskets", handicraft: "Handicrafts" };
  updateSectionMeta(labels[category] || category, displayedProducts.length);
}

/* ── Search ─────────────────────────────────────────────────────────────── */
/**
 * Always filters masterProducts (the full unfiltered set).
 * This was the original bug — previously it filtered allProducts which got
 * replaced by category filter results.
 */
function handleSearch(value) {
  const q = (value || "").toLowerCase().trim();
  const emptyMsg = document.getElementById("emptyMessage");

  // Reset category chip to "All" when user starts searching
  if (q !== "") {
    document.querySelectorAll(".filter-chip").forEach((c) =>
      c.classList.remove("active")
    );
    const allChip = document.getElementById("chip-all");
    if (allChip) allChip.classList.add("active");
  }

  if (q === "") {
    // Restore the current category's displayed products
    displayProducts(displayedProducts);
    updateSectionMeta(
      currentCategory === "all" ? "All Products" : currentCategory,
      displayedProducts.length
    );
    return;
  }

  // Search across the FULL master list regardless of active category
  const filtered = masterProducts.filter(
    (p) =>
      String(p?.name ?? "").toLowerCase().includes(q) ||
      String(p?.description ?? "").toLowerCase().includes(q) ||
      String(p?.category ?? "").toLowerCase().includes(q) ||
      String(p?.tags ?? "").toLowerCase().includes(q)
  );

  displayProducts(filtered);
  updateSectionMeta(`Results for "${value}"`, filtered.length);
}

/* ── Section Meta ───────────────────────────────────────────────────────── */
function updateSectionMeta(title, count) {
  const titleEl = document.getElementById("sectionTitle");
  const countEl = document.getElementById("productCount");
  if (titleEl) titleEl.textContent = title;
  if (countEl)
    countEl.textContent =
      count > 0 ? `${count} item${count !== 1 ? "s" : ""}` : "";
}

/* ── Display Products ───────────────────────────────────────────────────── */
function displayProducts(products) {
  const grid     = document.getElementById("productGrid");
  const emptyMsg = document.getElementById("emptyMessage");
  if (!grid) return;

  grid.innerHTML = "";

  if (!Array.isArray(products) || products.length === 0) {
    if (emptyMsg) emptyMsg.style.display = "block";
    return;
  }
  if (emptyMsg) emptyMsg.style.display = "none";

  products.forEach((p, i) => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.animationDelay = `${i * 50}ms`;
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.title = `View ${p?.name ?? "product"}`;

    /* Image wrapper */
    const imgWrap = document.createElement("div");
    imgWrap.className = "card-img-wrap";

    const img = document.createElement("img");
    img.src   = p?.image_url || PLACEHOLDER_IMG;
    img.alt   = p?.name ?? "Artisan product";
    img.loading = "lazy";
    img.addEventListener("error", () => { img.src = PLACEHOLDER_IMG; });
    imgWrap.appendChild(img);

    /* Category badge */
    if (p?.category) {
      const badge = document.createElement("span");
      badge.className   = "card-badge";
      badge.textContent = p.category;
      imgWrap.appendChild(badge);
    }

    /* Wishlist button */
    const wish = document.createElement("button");
    wish.className = "card-wish";
    wish.innerHTML = "🤍";
    wish.title     = "Save to wishlist";
    wish.addEventListener("click", (e) => {
      e.stopPropagation();
      const isActive = wish.classList.toggle("active");
      wish.innerHTML = isActive ? "❤️" : "🤍";
      showToast(isActive ? "Saved to wishlist" : "Removed from wishlist", "info");
    });
    imgWrap.appendChild(wish);

    /* Body */
    const body = document.createElement("div");
    body.className = "card-body";

    const nameEl = document.createElement("h4");
    nameEl.textContent = p?.name ?? "";

    const descEl = document.createElement("p");
    descEl.className   = "card-desc";
    descEl.textContent = p?.description || "Handcrafted with care by skilled artisans.";

    body.appendChild(nameEl);
    body.appendChild(descEl);

    /* Footer */
    const footer = document.createElement("div");
    footer.className = "card-footer";

    const priceWrap = document.createElement("div");
    const price     = Number(p?.price);
    const priceEl   = document.createElement("div");
    priceEl.className   = "card-price";
    priceEl.textContent = Number.isFinite(price)
      ? `₹${price.toLocaleString("en-IN")}`
      : "₹—";

    const priceSub       = document.createElement("div");
    priceSub.className   = "card-price-sub";
    priceSub.textContent = "Handmade";
    priceWrap.appendChild(priceEl);
    priceWrap.appendChild(priceSub);

    const actions = document.createElement("div");
    actions.className = "card-actions";

    /* Add-to-cart button */
    const cartBtn     = document.createElement("button");
    cartBtn.className = "btn-secondary";
    cartBtn.textContent = "🛒";
    cartBtn.title     = "Add to cart";
    cartBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      addToCart(p);
      cartBtn.textContent = "✓";
      setTimeout(() => { cartBtn.textContent = "🛒"; }, 1500);
    });

    /* View details button (previously "Buy Now") */
    const detailBtn     = document.createElement("button");
    detailBtn.className = "btn-primary";
    detailBtn.textContent = "View Details";
    detailBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = p?.id;
      if (id) window.location.href = `/product_page?id=${id}`;
    });

    actions.appendChild(cartBtn);
    actions.appendChild(detailBtn);
    footer.appendChild(priceWrap);
    footer.appendChild(actions);

    card.appendChild(imgWrap);
    card.appendChild(body);
    card.appendChild(footer);

    /* Whole card click → product detail */
    const goToDetail = () => {
      const id = p?.id;
      if (id) window.location.href = `/product_page?id=${id}`;
    };
    card.addEventListener("click", goToDetail);
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") goToDetail();
    });

    grid.appendChild(card);
  });
}

/* ── Init ───────────────────────────────────────────────────────────────── */
window.addEventListener("DOMContentLoaded", () => {
  loadProducts();
  updateCartBadge();

  const searchInput = document.getElementById("search");
  let debounceTimer;

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => handleSearch(e.target.value), 280);
    });

    // Submit on Enter key
    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        clearTimeout(debounceTimer);
        handleSearch(e.target.value);
      }
    });
  }

  const searchBtn = document.getElementById("searchBtn");
  if (searchBtn) {
    searchBtn.addEventListener("click", () =>
      handleSearch(searchInput?.value ?? "")
    );
  }
});
