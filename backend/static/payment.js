let checkoutProduct = null;

function getProductIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const idStr = params.get("id");
  const id = Number(idStr);
  return Number.isFinite(id) ? id : null;
}

async function loadCheckoutProduct(productId) {
  try {
    const res = await fetch(`/product/${productId}`);
    if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
    checkoutProduct = await res.json();
    renderCheckoutProduct(checkoutProduct);
  } catch (err) {
    console.log("Failed to load product for checkout:", err);
    const nameEl = document.getElementById("productName");
    if (nameEl) nameEl.textContent = "Product not found";
  }
}

function renderCheckoutProduct(product) {
  const nameEl = document.getElementById("productName");
  const priceEl = document.getElementById("productPrice");
  const descEl = document.getElementById("productDescription");
  const imgEl = document.getElementById("productImage");

  if (nameEl) nameEl.textContent = product?.name ?? "";

  const price = Number(product?.price);
  if (priceEl) priceEl.textContent = Number.isFinite(price) ? `₹${price}` : "₹";

  if (descEl) descEl.textContent = product?.description ?? "";

  if (imgEl) {
    if (product?.image_url) {
      imgEl.src = product.image_url;
      imgEl.style.display = "block";
    } else {
      imgEl.style.display = "none";
    }
  }
}

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

async function verifyPayment({ productId, orderId, paymentId, signature }) {
  const res = await fetch("/verify_payment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_id: productId,
      buyer: "Customer",
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

async function payNow(productId) {
  try {
    const created = await createRazorpayOrder(productId);

    const keyId =
      created?.key_id || window.RAZORPAY_KEY_ID || "";
    if (!keyId) {
      alert("Payment not configured");
      return;
    }

    const options = {
      key: keyId,
      amount: created.amount,
      currency: created.currency || "INR",
      name: "ArtBridge",
      description: checkoutProduct?.name || "Purchase",
      order_id: created.order_id,
      handler: async function (response) {
        try {
          await verifyPayment({
            productId,
            orderId: response.razorpay_order_id,
            paymentId: response.razorpay_payment_id,
            signature: response.razorpay_signature,
          });
          alert("Payment Successful");
          window.location.href = "/orders_page";
        } catch (err) {
          console.log("Payment verification failed:", err);
          alert("Payment Failed");
        }
      },
      modal: {
        ondismiss: function () {
          // user closed the popup
        },
      },
      theme: { color: "#8b5e3c" },
    };

    const rzp = new window.Razorpay(options);
    rzp.on("payment.failed", function (resp) {
      console.log("Payment failed:", resp?.error);
      alert("Payment Failed");
    });
    rzp.open();
  } catch (err) {
    console.log("Pay Now failed:", err);
    alert("Payment Failed");
  }
}

window.addEventListener("DOMContentLoaded", () => {
  const productId = getProductIdFromUrl();
  if (!productId) {
    console.log("Invalid product id in URL");
    const nameEl = document.getElementById("productName");
    if (nameEl) nameEl.textContent = "Invalid product";
    return;
  }

  loadCheckoutProduct(productId);

  const payBtn = document.getElementById("payNow");
  if (payBtn) {
    payBtn.addEventListener("click", () => payNow(productId));
  }
});

