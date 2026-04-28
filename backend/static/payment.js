let checkoutProduct = null;
let currentUser = null;

/* ── Toast ──────────────────────────────────────────────── */
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

/* ── URL Parsing ────────────────────────────────────────── */
function getProductIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const id = params.get("id");
  return id || null;
}

/* ── Load Product for Checkout ──────────────────────────── */
async function loadCheckoutProduct(productId) {
  try {
    const res = await fetch("/products");
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const products = await res.json();
    checkoutProduct = products.find(p => String(p.id) === String(productId));
    if (!checkoutProduct) throw new Error("Product not found");
    renderCheckoutProduct(checkoutProduct);
  } catch (err) {
    console.error("Failed to load product for checkout:", err);
    showToast("Could not load product details.", "error");
    const nameEl = document.getElementById("productName");
    if (nameEl) nameEl.textContent = "Product not found";
  }
}

/* ── Render Product ─────────────────────────────────────── */
function renderCheckoutProduct(product) {
  const nameEl     = document.getElementById("productName");
  const priceEl    = document.getElementById("productPrice");
  const descEl     = document.getElementById("productDescription");
  const imgEl      = document.getElementById("productImage");
  const catEl      = document.getElementById("productCategory");

  if (nameEl) nameEl.textContent = product?.name ?? "";

  const price = Number(product?.price);
  if (priceEl) priceEl.textContent = Number.isFinite(price) ? `₹${price.toLocaleString('en-IN')}` : "₹—";

  if (descEl) descEl.textContent = product?.description ?? "";

  if (catEl && product?.category) catEl.textContent = product.category;

  if (imgEl) {
    if (product?.image_url) {
      imgEl.src = product.image_url;
      imgEl.style.display = "block";
    } else {
      imgEl.style.display = "none";
    }
  }
}

/* ── Razorpay Order Creation ────────────────────────────── */
async function createRazorpayOrder(productId) {
  const res = await fetch("/create_order", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_id: productId }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Create order failed: ${res.status} ${text}`);
  }
  return await res.json();
}

/* ── Razorpay Payment Verification ─────────────────────── */
async function verifyPayment({ productId, orderId, paymentId, signature, address, buyer }) {
  const res = await fetch("/verify_payment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_id: productId,
      buyer: buyer || "Customer",
      address: address,
      razorpay_order_id: orderId,
      razorpay_payment_id: paymentId,
      razorpay_signature: signature,
    }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Verify failed: ${res.status} ${text}`);
  }
  return await res.json();
}

/* ── Pay Now Flow ───────────────────────────────────────── */
async function payNow(productId) {
  const l1 = document.getElementById("addrLine1")?.value.trim() || "";
  const l2 = document.getElementById("addrLine2")?.value.trim() || "";
  const l3 = document.getElementById("addrLine3")?.value.trim() || "";
  const lm = document.getElementById("addrLandmark")?.value.trim() || "";
  const ci = document.getElementById("addrCity")?.value.trim() || "";
  const st = document.getElementById("addrState")?.value.trim() || "";
  const pc = document.getElementById("addrPincode")?.value.trim() || "";

  if (!l1 || !ci || !st || !pc) {
    showToast("Please fill in Line 1, City, State, and Pincode", "error");
    document.getElementById("addrLine1").focus();
    return;
  }

  const parts = [l1, l2, l3, lm ? `Landmark: ${lm}` : "", ci, st, pc].filter(Boolean);
  const address = parts.join(", ");


  const payBtn = document.getElementById("payNow");
  if (payBtn) { payBtn.textContent = "Processing…"; payBtn.disabled = true; }

  try {
    const orderData = await createRazorpayOrder(productId);

    const keyId = orderData?.key_id || window.RAZORPAY_KEY_ID || "";

    if (!keyId) {
      showToast("Payment gateway not configured.", "error");
      if (payBtn) { payBtn.textContent = "Pay Now ✦"; payBtn.disabled = false; }
      return;
    }

    const options = {
      key: keyId,
      amount: orderData.amount,
      currency: orderData.currency || "INR",
      name: "ArtBridge",
      description: checkoutProduct?.name || "Artisan Purchase",
      order_id: orderData.id,
      handler: function (response) {
        console.log("RAZORPAY HANDLER RESPONSE:", response);
        const buyer = currentUser ? currentUser.name : "Customer";
        fetch("/verify_payment", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            product_id: productId,
            buyer: buyer,
            address: address,
            razorpay_order_id: response.razorpay_order_id || orderData.id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature || "",
          }),
        })
        .then(function(res) {
          if (!res.ok) {
            return res.text().then(function(text) {
              throw new Error("Verify failed: " + res.status + " " + text);
            });
          }
          return res.json();
        })
        .then(function(data) {
          console.log("Payment verified:", data);
          showToast("Payment successful! Redirecting…", "success");
          setTimeout(function() { window.location.href = "/orders_page"; }, 1000);
        })
        .catch(function(err) {
          console.error("Payment verification failed:", err);
          showToast(err.message || "Payment verification failed.", "error");
          if (payBtn) { payBtn.textContent = "Pay Now ✦"; payBtn.disabled = false; }
        });
      },
      modal: {
        ondismiss: function () {
          if (payBtn) { payBtn.textContent = "Pay Now ✦"; payBtn.disabled = false; }
        },
      },
      theme: { color: "#d4a373" },
    };

    const rzp = new window.Razorpay(options);
    rzp.on("payment.failed", function (resp) {
      console.error("Payment failed:", resp?.error);
      showToast("Payment failed. Please try again.", "error");
      if (payBtn) { payBtn.textContent = "Pay Now ✦"; payBtn.disabled = false; }
    });
    rzp.open();

  } catch (err) {
    console.error("Pay Now failed:", err);
    showToast("Could not initiate payment. " + err.message, "error");
    if (payBtn) { payBtn.textContent = "Pay Now ✦"; payBtn.disabled = false; }
  }
}

/* ── Init ───────────────────────────────────────────────── */
window.addEventListener("DOMContentLoaded", async () => {
  // Check auth first
  try {
    const authRes = await fetch('/api/me');
    const authData = await authRes.json();
    if (!authData.logged_in) {
      window.location.href = '/login';
      return;
    }
    currentUser = authData;
  } catch (e) {
    console.error("Auth check failed", e);
  }

  const productId = getProductIdFromUrl();

  if (!productId) {
    console.error("Invalid product id in URL");
    const nameEl = document.getElementById("productName");
    if (nameEl) nameEl.textContent = "Invalid product";
    showToast("No product ID found in URL.", "error");
    return;
  }

  loadCheckoutProduct(productId);

  const payBtn = document.getElementById("payNow");
  if (payBtn) payBtn.addEventListener("click", () => payNow(productId));
});
