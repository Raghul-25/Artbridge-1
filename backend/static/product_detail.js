"use strict";
/**
 * product_detail.js — ArtBridge Product Detail Page
 *
 * Reads ?id= from the URL, fetches /product/<id> (which includes artisan
 * sub-object), then renders the full product + artisan sections.
 */

const CART_KEY = "artbridge_cart_v1";

/* ── Utilities ──────────────────────────────────────────────────────────── */

function getProductIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const id = params.get("id");
  return id || null;
}

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
  }, 3200);
}

/* ── Cart ───────────────────────────────────────────────────────────────── */

function readCart() {
  try {
    const raw = localStorage.getItem(CART_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeCart(items) {
  localStorage.setItem(CART_KEY, JSON.stringify(items));
}

function updateCartBadge() {
  const cart = readCart();
  const total = cart.reduce((s, x) => s + (x.qty || 1), 0);
  const badge = document.getElementById("cartCount");
  if (badge) badge.textContent = total;
}

function addToCart(product) {
  const id = product?.id;
  if (!id) return;
  const cart = readCart();
  const existing = cart.find((x) => String(x?.id) === String(id));
  if (existing) {
    existing.qty = (existing.qty || 1) + 1;
  } else {
    cart.push({
      id,
      name: product?.name ?? "",
      price: product?.price,
      image_url: product?.image_url ?? null,
      qty: 1,
    });
  }
  writeCart(cart);
  updateCartBadge();
  showToast(`"${product?.name}" added to cart 🛒`, "success");
}

/* ── Star Rating ────────────────────────────────────────────────────────── */

function renderStars(rating) {
  const r = Math.round((rating || 0) * 2) / 2; // round to nearest 0.5
  let html = "";
  for (let i = 1; i <= 5; i++) {
    if (r >= i) html += `<span class="star full">★</span>`;
    else if (r >= i - 0.5) html += `<span class="star half">★</span>`;
    else html += `<span class="star empty">★</span>`;
  }
  return html;
}

/* ── Placeholder Image ──────────────────────────────────────────────────── */

const PLACEHOLDER_IMG =
  "data:image/svg+xml;charset=UTF-8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600">
      <defs>
        <linearGradient id="g" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stop-color="#231810"/>
          <stop offset="1" stop-color="#1a120b"/>
        </linearGradient>
      </defs>
      <rect width="100%" height="100%" fill="url(#g)"/>
      <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle"
        fill="rgba(184,149,106,0.5)" font-family="Arial,sans-serif" font-size="20">
        No Image
      </text>
    </svg>`
  );

const ARTISAN_PLACEHOLDER =
  "data:image/svg+xml;charset=UTF-8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">
      <rect width="100%" height="100%" fill="#231810"/>
      <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle"
        fill="rgba(184,149,106,0.5)" font-family="Arial,sans-serif" font-size="52">🧑‍🎨</text>
    </svg>`
  );

/* ── Render Product ─────────────────────────────────────────────────────── */

function renderProduct(product) {
  // Page metadata
  const pName = product?.name ?? "Product";
  document.title = `${pName} – ArtBridge`;
  const metaDesc = document.getElementById("metaDesc");
  if (metaDesc) metaDesc.content = product?.description || pName;

  // Breadcrumb
  const bcName = document.getElementById("breadcrumbName");
  const bcCat  = document.getElementById("breadcrumbCategory");
  if (bcName) bcName.textContent = pName;
  if (bcCat && product?.category) {
    bcCat.textContent =
      product.category.charAt(0).toUpperCase() + product.category.slice(1);
  }

  // Gather all images
  const images = [];
  if (product?.image_url) images.push(product.image_url);
  if (product?.image_url_2) images.push(product.image_url_2);
  if (product?.image_url_3) images.push(product.image_url_3);
  if (product?.image_url_4) images.push(product.image_url_4);

  // Hero image
  const mainImg = document.getElementById("mainImg");
  if (mainImg) {
    mainImg.src = images.length > 0 ? images[0] : PLACEHOLDER_IMG;
    mainImg.alt = pName;
    mainImg.addEventListener("error", () => {
      mainImg.src = PLACEHOLDER_IMG;
    });
  }

  // Thumbnails
  const thumbsContainer = document.getElementById("detailThumbnails");
  if (thumbsContainer) {
    if (images.length > 1) {
      thumbsContainer.innerHTML = images.map((imgUrl, idx) => `
        <img src="${imgUrl}" 
             class="thumb-img" 
             style="width:80px; height:80px; object-fit:cover; border-radius:8px; cursor:pointer; opacity: ${idx === 0 ? '1' : '0.6'}; border: 2px solid ${idx === 0 ? '#b8956a' : 'transparent'}; transition: all 0.3s;"
             onclick="document.getElementById('mainImg').src='${imgUrl}'; document.querySelectorAll('.thumb-img').forEach(el => {el.style.opacity='0.6'; el.style.borderColor='transparent';}); this.style.opacity='1'; this.style.borderColor='#b8956a';"
             alt="Thumbnail ${idx + 1}"
             onerror="this.src='${PLACEHOLDER_IMG}'">
      `).join("");
    } else {
      thumbsContainer.innerHTML = "";
    }
  }

  // Category badge (on image)
  const badgeCat = document.getElementById("badgeCategory");
  if (badgeCat && product?.category) {
    badgeCat.textContent = product.category;
    badgeCat.style.display = "inline-block";
  }

  // Category tag (above title)
  const catTag = document.getElementById("detailCategoryTag");
  if (catTag && product?.category) catTag.textContent = product.category;

  // Title
  const nameEl = document.getElementById("detailName");
  if (nameEl) nameEl.textContent = pName;

  // Price
  const priceEl = document.getElementById("detailPrice");
  if (priceEl) {
    const price = Number(product?.price);
    priceEl.textContent = Number.isFinite(price)
      ? `₹${price.toLocaleString("en-IN")}`
      : "Price on request";
  }

  // Description
  const descEl = document.getElementById("detailDescription");
  if (descEl)
    descEl.textContent =
      product?.description || "Handcrafted with care by skilled artisans.";



  // Tags
  const tagsEl = document.getElementById("detailTags");
  if (tagsEl && product?.tags) {
    const tags = String(product.tags)
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    if (tags.length) {
      tagsEl.innerHTML = tags
        .map((t) => `<span class="detail-tag">${t}</span>`)
        .join("");
    }
  }

  // Care notes
  const careSection = document.getElementById("detailCare");
  const careText    = document.getElementById("careText");
  if (product?.care_notes && careSection && careText) {
    careText.textContent = product.care_notes;
    careSection.style.display = "block";
  }

  // Wire up action buttons
  const cartBtn = document.getElementById("detailCartBtn");
  const buyBtn  = document.getElementById("detailBuyBtn");
  const pid     = product?.id;

  if (cartBtn) {
    cartBtn.addEventListener("click", () => {
      addToCart(product);
      cartBtn.textContent = "✓ Added!";
      cartBtn.classList.add("added");
      setTimeout(() => {
        cartBtn.textContent = "🛒 Add to Cart";
        cartBtn.classList.remove("added");
      }, 2000);
    });
  }

  if (buyBtn && pid) {
    buyBtn.addEventListener("click", () => {
      window.location.href = `/checkout?id=${pid}`;
    });
  }
}

/* ── Render Artisan ─────────────────────────────────────────────────────── */

function renderArtisan(artisan) {
  const section   = document.getElementById("artisanSection");
  const card      = document.getElementById("artisanCard");
  const emptyDiv  = document.getElementById("artisanEmpty");

  if (!artisan || !artisan.name) {
    if (card)     card.style.display    = "none";
    if (emptyDiv) emptyDiv.style.display = "flex";
    return;
  }

  if (card)     card.style.display    = "flex";
  if (emptyDiv) emptyDiv.style.display = "none";

  // Photo
  const photoEl = document.getElementById("artisanPhoto");
  if (photoEl) {
    photoEl.src = artisan?.photo_url || ARTISAN_PLACEHOLDER;
    photoEl.alt = artisan?.name ?? "Artisan";
    photoEl.addEventListener("error", () => { photoEl.src = ARTISAN_PLACEHOLDER; });
  }

  // Verified badge
  const verified = document.getElementById("artisanVerified");
  if (verified && artisan?.verified) verified.style.display = "flex";

  // Name
  const nameEl = document.getElementById("artisanName");
  if (nameEl) nameEl.textContent = artisan?.name ?? "";

  // Stars
  const starsEl = document.getElementById("artisanCardStars");
  if (starsEl && artisan?.rating) {
    starsEl.innerHTML = renderStars(artisan.rating);
    starsEl.title = `${artisan.rating} / 5`;
  }

  // Meta chips (location, specialty)
  const chipsEl = document.getElementById("artisanMetaChips");
  if (chipsEl) {
    const chips = [];
    if (artisan?.location)  chips.push(`📍 ${artisan.location}`);
    if (artisan?.specialty) chips.push(`🎨 ${artisan.specialty}`);
    if (artisan?.years_active) chips.push(`⏳ ${artisan.years_active} yrs experience`);
    chipsEl.innerHTML = chips
      .map((c) => `<span class="artisan-chip">${c}</span>`)
      .join("");
  }

  // Bio
  const bioEl = document.getElementById("artisanBio");
  if (bioEl)
    bioEl.textContent =
      artisan?.bio || "This artisan creates beautiful handcrafted products with traditional techniques passed down through generations.";

  // Stats
  const statsEl = document.getElementById("artisanStats");
  if (statsEl) {
    const stats = [];
    if (artisan?.products_sold)
      stats.push({ value: artisan.products_sold + "+", label: "Products Sold" });
    if (artisan?.rating)
      stats.push({ value: artisan.rating.toFixed(1), label: "Avg Rating" });
    if (artisan?.years_active)
      stats.push({ value: artisan.years_active, label: "Yrs Active" });

    if (stats.length) {
      statsEl.innerHTML = stats
        .map(
          (s) =>
            `<div class="artisan-stat-item">
               <span class="artisan-stat-value">${s.value}</span>
               <span class="artisan-stat-label">${s.label}</span>
             </div>`
        )
        .join("");
    }
  }
}

/* ── Main Load ──────────────────────────────────────────────────────────── */

async function loadProductDetail(productId) {
  try {
    const res = await fetch("/products");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const products = await res.json();
    const product = products.find(p => String(p.id) === String(productId));
    
    if (!product) {
      throw new Error("Product not found in products list");
    }

    // Hide skeleton, show content
    const loading = document.getElementById("detailLoading");
    const content = document.getElementById("detailContent");
    if (loading) loading.style.display = "none";
    if (content) content.style.display = "block";

    renderProduct(product);
    renderArtisan(product?.artisan);

  } catch (err) {
    console.error("Failed to load product:", err);
    const loading = document.getElementById("detailLoading");
    const errDiv  = document.getElementById("detailError");
    if (loading) loading.style.display = "none";
    if (errDiv)  errDiv.style.display  = "flex";
    showToast("Could not load product details.", "error");
  }
}

/* ── Init ───────────────────────────────────────────────────────────────── */

window.addEventListener("DOMContentLoaded", () => {
  updateCartBadge();

  const productId = getProductIdFromUrl();
  if (!productId) {
    const loading = document.getElementById("detailLoading");
    const errDiv  = document.getElementById("detailError");
    if (loading) loading.style.display = "none";
    if (errDiv)  errDiv.style.display  = "flex";
    return;
  }

  loadProductDetail(productId);
});
