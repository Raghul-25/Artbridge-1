const CART_KEY = "artbridge_cart_v1";

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

function removeItem(productId) {
  const cart = readCart().filter((x) => Number(x?.id) !== Number(productId));
  writeCart(cart);
  displayCart(cart);
}

function displayCart(cartItems) {
  const container = document.getElementById("cartContainer");
  const emptyMessage = document.getElementById("cartEmptyMessage");

  if (!container) {
    console.log("cartContainer element not found");
    return;
  }

  container.innerHTML = "";

  if (!Array.isArray(cartItems) || cartItems.length === 0) {
    if (emptyMessage) emptyMessage.style.display = "block";
    return;
  }

  if (emptyMessage) emptyMessage.style.display = "none";

  cartItems.forEach((item) => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.textAlign = "left";
    card.style.marginBottom = "14px";

    if (item?.image_url) {
      const img = document.createElement("img");
      img.src = item.image_url;
      img.alt = item?.name ?? "Product image";
      card.appendChild(img);
    }

    const title = document.createElement("h4");
    title.textContent = item?.name ?? "";

    const priceEl = document.createElement("p");
    const price = Number(item?.price);
    priceEl.textContent = Number.isFinite(price) ? `₹${price}` : "₹";

    const qtyEl = document.createElement("p");
    qtyEl.style.fontWeight = "normal";
    qtyEl.textContent = `Qty: ${item?.qty ?? 1}`;

    const actions = document.createElement("div");
    actions.style.display = "flex";
    actions.style.gap = "10px";
    actions.style.marginTop = "10px";

    const buyBtn = document.createElement("button");
    buyBtn.textContent = "Checkout";
    buyBtn.addEventListener("click", () => {
      const id = Number(item?.id);
      if (!Number.isFinite(id)) return;
      window.location.href = `/checkout?id=${id}`;
    });

    const removeBtn = document.createElement("button");
    removeBtn.textContent = "Remove";
    removeBtn.style.background = "linear-gradient(135deg, #f1d1b2 0%, #e9c3a1 100%)";
    removeBtn.addEventListener("click", () => removeItem(item?.id));

    actions.appendChild(buyBtn);
    actions.appendChild(removeBtn);

    card.appendChild(title);
    card.appendChild(priceEl);
    card.appendChild(qtyEl);
    card.appendChild(actions);

    container.appendChild(card);
  });
}

window.addEventListener("DOMContentLoaded", () => {
  displayCart(readCart());
});

