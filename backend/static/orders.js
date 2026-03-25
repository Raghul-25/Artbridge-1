async function loadOrders() {
  try {
    const res = await fetch("/orders");
    if (!res.ok) {
      throw new Error(`API error: ${res.status} ${res.statusText}`);
    }
    const orders = await res.json();
    displayOrders(orders);
  } catch (err) {
    console.log("Failed to load orders:", err);
  }
}

function statusColor(status) {
  const s = String(status || "").toLowerCase();
  if (s.includes("delivered")) return "green";
  if (s.includes("shipped")) return "#1e66c5";
  if (s.includes("processing")) return "orange";
  return "#555";
}

function displayOrders(orders) {
  const container = document.getElementById("ordersContainer");
  const emptyMessage = document.getElementById("ordersEmptyMessage");

  if (!container) {
    console.log("ordersContainer element not found");
    return;
  }

  container.innerHTML = "";

  if (!Array.isArray(orders) || orders.length === 0) {
    if (emptyMessage) emptyMessage.style.display = "block";
    return;
  }

  if (emptyMessage) emptyMessage.style.display = "none";

  orders.forEach((o) => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.marginBottom = "15px";
    card.style.textAlign = "left";

    const orderIdEl = document.createElement("h4");
    orderIdEl.textContent = `Order #${o?.order_id ?? ""}`;

    const productEl = document.createElement("p");
    productEl.style.fontWeight = "normal";
    productEl.textContent = `Product ID: ${o?.product_id ?? ""}`;

    const statusEl = document.createElement("p");
    statusEl.style.fontWeight = "normal";
    statusEl.innerHTML = `Status: <span style="color:${statusColor(
      o?.status
    )}; font-weight:bold;">${o?.status ?? ""}</span>`;

    const trackingEl = document.createElement("p");
    trackingEl.style.fontWeight = "normal";
    trackingEl.textContent = `Tracking: ${o?.tracking ?? ""}`;

    card.appendChild(orderIdEl);
    card.appendChild(productEl);
    card.appendChild(statusEl);
    card.appendChild(trackingEl);

    container.appendChild(card);
  });
}

window.addEventListener("DOMContentLoaded", () => {
  loadOrders();
});

