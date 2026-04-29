/* ── Toast Helper ───────────────────────────────────────── */
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

/* ── Load Orders ────────────────────────────────────────── */
async function loadOrders() {
  try {
    const res = await fetch("/orders");
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const orders = await res.json();
    displayOrders(orders);
  } catch (err) {
    console.error("Failed to load orders:", err);
    showToast("Failed to load orders. Is the server running?", "error");
    const container = document.getElementById("ordersContainer");
    if (container) {
      container.innerHTML = `<div class="empty-state" style="border:1px solid var(--border); border-radius:var(--radius); padding:40px;">
        <div class="empty-icon">⚠️</div>
        <h3>Could not connect</h3>
        <p>Make sure the ArtBridge backend is running.</p>
      </div>`;
    }
  }
}

/* ── Status Badge ───────────────────────────────────────── */
function getStatusBadge(status) {
  const s = String(status || "").toLowerCase();
  let cls = "order-badge";
  let icon = "⏳";
  if (s.includes("delivered")) { cls += " delivered"; icon = "✅"; }
  else if (s.includes("shipped")) { cls += " shipped"; icon = "🚚"; }
  else if (s.includes("processing")) { cls += " processing"; icon = "🔄"; }
  return `<span class="${cls}">${icon} ${status || "Unknown"}</span>`;
}

function getPaymentBadge(paymentStatus) {
  const s = String(paymentStatus || "").toLowerCase();
  if (s.includes("paid")) return `<span class="order-badge paid">✅ Paid</span>`;
  return `<span class="order-badge" style="color:var(--text-3);">${paymentStatus || "—"}</span>`;
}

/* ── Display Orders ─────────────────────────────────────── */
function displayOrders(orders) {
  const container = document.getElementById("ordersContainer");
  const emptyMsg  = document.getElementById("ordersEmptyMessage");
  if (!container) return;

  container.innerHTML = "";

  if (!Array.isArray(orders) || orders.length === 0) {
    if (emptyMsg) emptyMsg.style.display = "block";
    return;
  }

  if (emptyMsg) emptyMsg.style.display = "none";

  orders.forEach((o, i) => {
    const card = document.createElement("div");
    card.className = "order-card";
    card.style.animationDelay = `${i * 60}ms`;

    card.innerHTML = `
      <div class="order-card-header">
        <div class="order-id">Order #${o?.order_id ?? "—"}</div>
        ${getStatusBadge(o?.status)}
      </div>
      <div class="order-meta">
        <div class="order-meta-item">
          <label>Product Name</label>
          <span>${o?.product_name ?? "—"}</span>
        </div>
        <div class="order-meta-item">
          <label>Tracking</label>
          <span>${o?.tracking ?? "—"}</span>
        </div>
        <div class="order-meta-item">
          <label>Payment</label>
          <span>${o?.payment_status ?? "—"}</span>
        </div>
      </div>
    `;

    container.appendChild(card);
  });
}

/* ── Init ───────────────────────────────────────────────── */
window.addEventListener("DOMContentLoaded", loadOrders);
