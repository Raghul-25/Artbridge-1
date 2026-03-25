let allProducts = [];
const CART_KEY = "artbridge_cart_v1";
const PLACEHOLDER_IMG =
  "data:image/svg+xml;charset=UTF-8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400">
      <defs>
        <linearGradient id="g" x1="0" x2="1">
          <stop offset="0" stop-color="#f3e5d3"/>
          <stop offset="1" stop-color="#ead7c0"/>
        </linearGradient>
      </defs>
      <rect width="100%" height="100%" fill="url(#g)"/>
      <rect x="18" y="18" width="564" height="364" rx="18" fill="rgba(255,255,255,0.55)" stroke="rgba(42,29,20,0.10)"/>
      <g fill="rgba(42,29,20,0.45)" font-family="Arial, sans-serif" font-size="22">
        <text x="50%" y="52%" dominant-baseline="middle" text-anchor="middle">No Image</text>
      </g>
    </svg>`
  );

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

function addToCart(product) {
  const id = Number(product?.id);
  if (!Number.isFinite(id)) {
    console.log("Invalid product id:", product);
    return;
  }

  const cart = readCart();
  const existing = cart.find((x) => Number(x?.id) === id);
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
  alert("Added to cart");
}

async function fetchData(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
    return await res.json();
  } catch (err) {
    console.log(`Failed to fetch from ${url}:`, err);
    return null;
  }
}

async function loadProducts() {
  const loading = document.getElementById("loadingMessage");
  const grid = document.getElementById("productGrid");
  const empty = document.getElementById("emptyMessage");
  if (loading) loading.style.display = "block";
  if (empty) empty.style.display = "none";
  if (grid) grid.innerHTML = "";

  const products = await fetchData("/products");
  
  if (loading) loading.style.display = "none";
  allProducts = Array.isArray(products) ? products : [];
  displayProducts(allProducts);
}

async function selectCategory(category) {
  const loading = document.getElementById("loadingMessage");
  const grid = document.getElementById("productGrid");
  const empty = document.getElementById("emptyMessage");
  if (loading) loading.style.display = "block";
  if (empty) empty.style.display = "none";
  if (grid) grid.innerHTML = "";

  const products = await fetchData(`/products/${category}`);
  
  if (loading) loading.style.display = "none";
  allProducts = Array.isArray(products) ? products : [];
  displayProducts(allProducts);
  highlightSelectedCategory(category);

  const searchInput = document.getElementById("search");
  if (searchInput) searchInput.value = "";
}

function displayProducts(products) {
  const productGrid = document.getElementById("productGrid");
  const emptyMessage = document.getElementById("emptyMessage");

  if (!productGrid) {
    console.log("productGrid element not found");
    return;
  }

  productGrid.innerHTML = "";

  if (!Array.isArray(products) || products.length === 0) {
    if (emptyMessage) emptyMessage.style.display = "block";
    return;
  }

  if (emptyMessage) emptyMessage.style.display = "none";

  products.forEach((p) => {
    const card = document.createElement("div");
    card.className = "card";

    const nameEl = document.createElement("h4");
    nameEl.textContent = p?.name ?? "";

    const img = document.createElement("img");
    img.src = p?.image_url || PLACEHOLDER_IMG;
    img.alt = p?.name ?? "Product image";
    img.loading = "lazy";
    img.addEventListener("error", () => {
      img.src = PLACEHOLDER_IMG;
    });

    const priceEl = document.createElement("p");
    const price = Number(p?.price);
    priceEl.textContent = Number.isFinite(price) ? `₹${price}` : "₹";

    const buyBtn = document.createElement("button");
    buyBtn.textContent = "Buy Now";
    buyBtn.addEventListener("click", () => {
      const id = Number(p?.id);
      if (!Number.isFinite(id)) {
        console.log("Invalid product id:", p);
        return;
      }
      window.location.href = `/checkout?id=${id}`;
    });

    const cartBtn = document.createElement("button");
    cartBtn.textContent = "Add to Cart";
    cartBtn.className = "secondary-btn";
    cartBtn.addEventListener("click", () => addToCart(p));

    const footer = document.createElement("div");
    footer.className = "card-footer";

    const btns = document.createElement("div");
    btns.className = "card-actions";
    btns.appendChild(buyBtn);
    btns.appendChild(cartBtn);

    footer.appendChild(priceEl);
    footer.appendChild(btns);

    card.appendChild(nameEl);
    card.appendChild(img);
    card.appendChild(footer);

    productGrid.appendChild(card);
  });
}

window.addEventListener("DOMContentLoaded", () => {
  loadProducts();

  const searchInput = document.getElementById("search");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const value = (e.target.value || "").toLowerCase().trim();

      if (value === "") {
        // Reset behavior: when search cleared, reload all products.
        displayProducts(allProducts);
        return;
      }

      const filtered = allProducts.filter((p) =>
        String(p?.name ?? "").toLowerCase().includes(value)
      );
      displayProducts(filtered);
    });
  }
});

function highlightSelectedCategory(category) {
  // Optional UX: simple highlight without changing HTML/CSS files
  const items = document.querySelectorAll(".sidebar li");
  items.forEach((li) => {
    li.style.fontWeight = "normal";
    li.style.color = "";

    const onclick = li.getAttribute("onclick") || "";
    if (onclick.includes(`'${category}'`) || onclick.includes(`\"${category}\"`)) {
      li.style.fontWeight = "bold";
      li.style.color = "#8b5e3c";
    }
  });
}

