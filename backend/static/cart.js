const CART_KEY = "artbridge_cart_v1";

/* ── Helpers ────────────────────────────────────────────── */
function readCart() {
  try {
    const raw = localStorage.getItem(CART_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch { return []; }
}

function writeCart(items) {
  localStorage.setItem(CART_KEY, JSON.stringify(items));
}

function removeItem(productId) {
  const cart = readCart().filter(x => Number(x?.id) !== Number(productId));
  writeCart(cart);
  displayCart(cart);
  showToast("Item removed from cart", "info");
}

function showToast(message, type = 'info') {
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

/* ── Display Cart ───────────────────────────────────────── */
function displayCart(cartItems) {
  const container = document.getElementById("cartContainer");
  const emptyMsg  = document.getElementById("cartEmptyMessage");
  const summary   = document.getElementById("cartSummary");
  const subtitle  = document.getElementById("cartSubtitle");
  if (!container) return;

  container.innerHTML = "";

  if (!Array.isArray(cartItems) || cartItems.length === 0) {
    if (emptyMsg) emptyMsg.style.display = "block";
    if (summary) summary.style.display = "none";
    if (subtitle) subtitle.textContent = "Your cart is empty";
    return;
  }

  if (emptyMsg) emptyMsg.style.display = "none";
  if (summary) summary.style.display = "block";

  const itemCount = cartItems.reduce((s, x) => s + (x.qty || 1), 0);
  if (subtitle) subtitle.textContent = `${itemCount} item${itemCount !== 1 ? 's' : ''} in your cart`;

  let total = 0;

  cartItems.forEach((item, i) => {
    const price = Number(item?.price) || 0;
    const qty   = item?.qty || 1;
    total += price * qty;

    const row = document.createElement("div");
    row.className = "cart-item";
    row.style.animationDelay = `${i * 60}ms`;

    // Image
    if (item?.image_url) {
      const img = document.createElement("img");
      img.className = "cart-item-img";
      img.src = item.image_url;
      img.alt = item?.name ?? "Product";
      row.appendChild(img);
    }

    // Info
    const info = document.createElement("div");
    info.className = "cart-item-info";

    const name = document.createElement("div");
    name.className = "cart-item-name";
    name.textContent = item?.name ?? "";

    const priceEl = document.createElement("div");
    priceEl.className = "cart-item-price";
    priceEl.textContent = `₹${(price * qty).toLocaleString('en-IN')}`;

    const qtyEl = document.createElement("div");
    qtyEl.className = "cart-item-qty";
    qtyEl.textContent = `Qty: ${qty} × ₹${price.toLocaleString('en-IN')}`;

    info.appendChild(name);
    info.appendChild(priceEl);
    info.appendChild(qtyEl);

    // Actions
    const actions = document.createElement("div");
    actions.className = "cart-item-actions";

    const buyBtn = document.createElement("button");
    buyBtn.className = "btn-primary";
    buyBtn.textContent = "Checkout";
    buyBtn.addEventListener("click", () => {
      const id = Number(item?.id);
      if (!Number.isFinite(id)) return;
      window.location.href = `/checkout?id=${id}`;
    });

    const removeBtn = document.createElement("button");
    removeBtn.className = "btn-danger";
    removeBtn.textContent = "Remove";
    removeBtn.addEventListener("click", () => removeItem(item?.id));

    actions.appendChild(buyBtn);
    actions.appendChild(removeBtn);

    row.appendChild(info);
    row.appendChild(actions);
    container.appendChild(row);
  });

  // Update summary totals
  const subtotalEl = document.getElementById("cartSubtotal");
  const totalEl    = document.getElementById("cartTotal");
  const formatted  = `₹${total.toLocaleString('en-IN')}`;
  if (subtotalEl) subtotalEl.textContent = formatted;
  if (totalEl)    totalEl.textContent    = formatted;
}

/* ── Init ───────────────────────────────────────────────── */
window.addEventListener("DOMContentLoaded", () => {
  displayCart(readCart());
});
