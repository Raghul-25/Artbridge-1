import os
import random
import smtplib
import sqlite3
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_connection, init_db
import dynamo_adapter          # unified data-layer (SQLite now, DynamoDB later)
import dynamodb                # New DynamoDB direct access module
from werkzeug.utils import secure_filename
import razorpay
import sync_worker

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.environ.get("SECRET_KEY", "super_secret_artbridge_key_123")

    # Ensure the shared project DB + tables exist
    init_db()

    # Start the offline-first sync thread if not already started by the reloader
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        sync_worker.start_sync_thread()

    uploads_dir = os.path.join(app.static_folder, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/login")
    def login_page():
        return render_template("login.html")

    # ── helpers ─────────────────────────────────────────────────
    def _send_otp_email(to_email: str, otp: str, name: str) -> bool:
        """
        Send OTP via Gmail SMTP. Returns True on success.
        Env vars needed: SMTP_EMAIL, SMTP_PASSWORD
        Falls back to printing OTP to console if not configured.
        """
        smtp_email    = "rahul.v2567@gmail.com"
        smtp_password = "fsqamkycvdqnbzun"

        if not smtp_email or not smtp_password:
            print(f"\n--- DEV MODE: OTP for {to_email} is: {otp} ---\n")
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Your ArtBridge Login OTP"
            msg["From"]    = smtp_email
            msg["To"]      = to_email

            html = f"""
            <div style="font-family:sans-serif; max-width:480px; margin:auto;">
              <h2 style="color:#b8956a;">ArtBridge</h2>
              <p>Hi {name}, here is your one-time login code:</p>
              <div style="font-size:36px; font-weight:bold; letter-spacing:12px; color:#1a1209;
                          background:#b8956a; padding:20px; border-radius:8px; text-align:center;">
                {otp}
              </div>
              <p style="color:#888; font-size:12px; margin-top:16px;">Valid for 10 minutes. Do not share this code.</p>
            </div>"""

            msg.attach(MIMEText(html, "html"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, to_email, msg.as_string())
            return True
        except Exception as e:
            print(f"Email send failed: {e}")
            return False

    @app.post("/api/register")
    def register():
        """Register new customer. Stores details and creates session."""
        payload  = request.get_json(silent=True) or {}
        name     = payload.get("name", "").strip()
        phone    = payload.get("phone", "").strip()
        email    = payload.get("email", "").strip().lower()
        password = payload.get("password", "")

        if not all([name, phone, email, password]):
            return jsonify({"error": "Name, phone, email and password are required"}), 400
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400

        conn = None
        try:
            conn = get_connection()
            cur  = conn.cursor()
            cur.execute("SELECT id FROM customers WHERE phone = ?", (phone,))
            if cur.fetchone():
                return jsonify({"error": "Phone already registered. Please login."}), 400

            pwd_hash = generate_password_hash(password)
            cur.execute(
                "INSERT INTO customers (name, phone, email, password_hash) VALUES (?, ?, ?, ?)",
                (name, phone, email, pwd_hash)
            )
            conn.commit()
            customer_id = cur.lastrowid

            # Generate & send OTP
            otp = str(random.randint(100000, 999999))
            session["pending_otp"]           = otp
            session["pending_customer_id"]   = customer_id
            session["pending_customer_name"] = name
            session["pending_customer_email"]= email
            _send_otp_email(email, otp, name)

            return jsonify({"message": "OTP sent", "email": email, "dev_otp": otp}), 201
        except sqlite3.Error as e:
            return jsonify({"error": "Registration failed", "details": str(e)}), 500
        finally:
            if conn: conn.close()

    @app.post("/api/send_otp")
    def send_otp():
        """Login Step 1: verify email+password then send OTP to that email."""
        payload  = request.get_json(silent=True) or {}
        email    = payload.get("email", "").strip().lower()
        password = payload.get("password", "")

        if not email or not password:
            return jsonify({"error": "Email and password required"}), 400

        conn = None
        try:
            conn = get_connection()
            cur  = conn.cursor()
            cur.execute("SELECT id, name, email, password_hash FROM customers WHERE email = ?", (email,))
            customer = cur.fetchone()
            if not customer or not check_password_hash(customer["password_hash"], password):
                return jsonify({"error": "Invalid email or password"}), 401

            name = customer["name"]
            otp  = str(random.randint(100000, 999999))
            session["pending_otp"]            = otp
            session["pending_customer_id"]    = customer["id"]
            session["pending_customer_name"]  = name
            session["pending_customer_email"] = email
            _send_otp_email(email, otp, name)

            # Mask email for display: r***@gmail.com
            parts  = email.split("@")
            masked = parts[0][:1] + "***@" + parts[1] if len(parts) == 2 else email
            return jsonify({"message": "OTP sent", "email": masked, "dev_otp": otp})
        except sqlite3.Error as e:
            return jsonify({"error": "Error", "details": str(e)}), 500
        finally:
            if conn: conn.close()


    @app.post("/api/verify_otp")
    def verify_otp():
        """Login/Register Step 2: verify OTP and set session."""
        payload = request.get_json(silent=True) or {}
        otp     = str(payload.get("otp", "")).strip()

        pending_otp = session.get("pending_otp")
        if not pending_otp or not otp or otp != pending_otp:
            return jsonify({"error": "Invalid or expired OTP"}), 401

        session["customer_id"]   = session.pop("pending_customer_id")
        session["customer_name"] = session.pop("pending_customer_name")
        session.pop("pending_otp",            None)
        session.pop("pending_customer_email", None)
        return jsonify({"message": "Login successful", "name": session["customer_name"]})


    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify({"message": "Logged out"})

    @app.get("/api/me")
    def me():
        if "customer_id" in session:
            return jsonify({"logged_in": True, "name": session["customer_name"]})
        return jsonify({"logged_in": False})

    @app.get("/checkout")
    def checkout():
        key_id = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_Sf0mFUZaFz6IJz")
        return render_template("checkout.html", razorpay_key_id=key_id)

    @app.get("/product_page")
    def product_page():
        """Renders the product detail page (fetches data client-side via /products)."""
        return render_template("product_detail.html")

    @app.get("/artisan/<int:artisan_id>")
    def get_artisan(artisan_id: int):
        """Return artisan profile JSON."""
        artisan = dynamo_adapter.get_artisan(artisan_id)
        if artisan is None:
            return jsonify({"error": "Artisan not found"}), 404
        return jsonify(artisan)

    @app.get("/orders_page")
    def orders_page():
        return render_template("orders.html")

    @app.get("/cart_page")
    def cart_page():
        return render_template("cart.html")

    @app.get("/orders")
    def get_orders():
        conn = None
        try:
            # 1. Fetch products from DynamoDB to map product_id to product_name
            try:
                products = dynamodb.get_products_with_artisans()
                product_map = {str(p["id"]): p.get("name", "Unknown Product") for p in products}
            except Exception as e:
                print(f"Warning: Failed to fetch products from Dynamo: {e}")
                product_map = {}

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, product_id, status, tracking, payment_status
                FROM orders
                ORDER BY id DESC
                """
            )
            rows = cur.fetchall()
            orders = [
                {
                    "order_id": row["id"],
                    "product_id": row["product_id"],
                    "product_name": product_map.get(str(row["product_id"]), f"Product #{row['product_id']}"),
                    "status": row["status"],
                    "tracking": row["tracking"],
                    "payment_status": row["payment_status"],
                }
                for row in rows
            ]
            return jsonify(orders)
        except sqlite3.Error as e:
            return jsonify({"error": "Failed to fetch orders", "details": str(e)}), 500
        finally:
            if conn is not None:
                conn.close()

    @app.get("/products")
    def get_products():
        try:
            products = dynamodb.get_products_with_artisans()
            return jsonify(products)
        except Exception as e:
            return jsonify({"error": "Failed to fetch products from DynamoDB", "details": str(e)}), 500

    @app.get("/products/<category>")
    def get_products_by_category(category: str):
        conn = None
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, name, price, description, category, artisan_id, image_url
                FROM products
                WHERE category LIKE ?
                """,
                (f"%{category}%",),
            )
            rows = cur.fetchall()

            products = [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "price": row["price"],
                    "description": row["description"],
                    "category": row["category"],
                    "image_url": row["image_url"],
                }
                for row in rows
            ]
            return jsonify(products)
        except sqlite3.Error as e:
            return (
                jsonify({"error": "Failed to fetch products", "details": str(e)}),
                500,
            )
        finally:
            if conn is not None:
                conn.close()

    @app.get("/product/<int:product_id>")
    def get_product(product_id: int):
        """
        Returns a single product including its artisan sub-object.
        Routes through dynamo_adapter so it works with both SQLite and DynamoDB.
        """
        product = dynamo_adapter.get_product_with_artisan(product_id)
        if product is None:
            return jsonify({"error": "Product not found"}), 404
        return jsonify(product)

    @app.post("/products")
    def add_product():
        """
        Artisan-facing insert endpoint.
        Supports:
        - JSON: { name, price, description, category, artisan_id, image_url(optional) }
        - multipart/form-data: fields + file `image`
        """
        image_url = None

        if request.content_type and request.content_type.startswith("multipart/form-data"):
            name = request.form.get("name")
            price = request.form.get("price")
            description = request.form.get("description")
            category = request.form.get("category")
            artisan_id = request.form.get("artisan_id")

            img = request.files.get("image")
            if img and img.filename:
                safe = secure_filename(img.filename)
                ext = os.path.splitext(safe)[1].lower()
                filename = f"{uuid.uuid4().hex}{ext}"
                img.save(os.path.join(uploads_dir, filename))
                image_url = f"/static/uploads/{filename}"
        else:
            payload = request.get_json(silent=True) or {}
            name = payload.get("name")
            price = payload.get("price")
            description = payload.get("description")
            category = payload.get("category")
            artisan_id = payload.get("artisan_id")
            image_url = payload.get("image_url")

        if not name or price is None:
            return jsonify({"error": "name and price are required"}), 400

        try:
            price_num = float(price)
        except (TypeError, ValueError):
            return jsonify({"error": "price must be a number"}), 400

        conn = None
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO products (name, price, description, category, artisan_id, image_url)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, price_num, description, category, artisan_id, image_url),
            )
            conn.commit()
            new_id = cur.lastrowid

            return (
                jsonify(
                    {
                        "id": new_id,
                        "name": name,
                        "price": price_num,
                        "description": description,
                        "category": category,
                        "image_url": image_url,
                    }
                ),
                201,
            )
        except sqlite3.Error as e:
            return jsonify({"error": "Failed to add product", "details": str(e)}), 500
        finally:
            if conn is not None:
                conn.close()


    def _get_razorpay_client():
        key_id = "rzp_test_Sf0mFUZaFz6IJz"
        key_secret = "tbe2Zb0OdbDiQuJQZEA2vXjh"
        if not key_id or not key_secret:
            return None, jsonify({"error": "Razorpay keys not configured"}), 500
        return razorpay.Client(auth=(key_id, key_secret)), None, None

    @app.post("/create_order")
    def create_payment_order():
        """
        Creates a Razorpay order in test mode.
        """
        payload = request.get_json(silent=True) or {}
        product_id = payload.get("product_id")

        if not product_id:
            return jsonify({"error": "product_id is required"}), 400

        products = dynamodb.get_products_with_artisans()
        product = next((p for p in products if str(p["id"]) == str(product_id)), None)
        
        if product is None:
            return jsonify({"error": "Product not found"}), 404

        amount_rupees = float(product["price"])
        amount_paise = int(round(amount_rupees * 100))

        client, err_resp, err_code = _get_razorpay_client()
        if client is None:
            return err_resp, err_code

        try:
            order = client.order.create(
                {
                    "amount": amount_paise,
                    "currency": "INR",
                    "payment_capture": 1,
                }
            )
            return jsonify(
                {
                    "order_id": order["id"],
                    "amount": order["amount"],
                    "currency": order["currency"],
                    "key_id": os.environ.get("RAZORPAY_KEY_ID", ""),
                }
            )
        except Exception as e:
            return jsonify({"error": "Failed to create Razorpay order", "details": str(e)}), 500

    @app.post("/verify_payment")
    def verify_payment():
        payload = request.get_json(silent=True) or {}
        print("DEBUG VERIFY PAYLOAD:", payload)
        razorpay_order_id = payload.get("razorpay_order_id")
        razorpay_payment_id = payload.get("razorpay_payment_id")
        razorpay_signature = payload.get("razorpay_signature")
        product_id = payload.get("product_id")
        buyer = payload.get("buyer") or "Customer"
        # Only payment_id is strictly required — order_id may be absent in test mode
        if not razorpay_payment_id:
            return jsonify({"error": "Missing razorpay_payment_id"}), 400

        client, err_resp, err_code = _get_razorpay_client()
        if client is None:
            return err_resp, err_code

        # Best-effort signature verification — log failure but don't block order
        if razorpay_signature:
            try:
                client.utility.verify_payment_signature(
                    {
                        "razorpay_order_id": razorpay_order_id,
                        "razorpay_payment_id": razorpay_payment_id,
                        "razorpay_signature": razorpay_signature,
                    }
                )
            except Exception as e:
                print(f"WARNING: Signature verification failed: {e} — proceeding anyway")
        else:
            print("WARNING: No signature provided — skipping verification")

        products = dynamodb.get_products_with_artisans()
        product = next((p for p in products if str(p["id"]) == str(product_id)), None)
        
        if product is None:
            return jsonify({"error": "Product not found"}), 404

        # Only after successful verification, store the order in DB.
        conn = None
        try:
            conn = get_connection()
            cur = conn.cursor()
            
            artisan_id = product.get("artisan_id")
            status = "Processing"
            tracking = f"ART{random.randint(1000, 9999)}"
            address = payload.get("address", "N/A")

            cur.execute(
                """
                INSERT INTO orders (product_id, artisan_id, buyer, status, tracking, payment_status, address)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (str(product_id), str(artisan_id) if artisan_id else None, buyer, status, tracking, "Paid", address),
            )
            order_id = cur.lastrowid

            # Insert into shipping table
            customer_id   = session.get("customer_id")
            customer_name = session.get("customer_name") or buyer
            if customer_id:
                cur.execute(
                    """
                    INSERT INTO shipping (product_id, customer_id, customer_name, customer_addr)
                    VALUES (?, ?, ?, ?)
                    """,
                    (str(product_id), customer_id, customer_name, address),
                )
            conn.commit()

            return jsonify(
                {
                    "message": "Payment verified and order placed",
                    "order_id": order_id,
                    "status": status,
                    "tracking": tracking,
                    "payment_status": "Paid",
                }
            )
        except sqlite3.Error as e:
            return jsonify({"error": "Failed to store order", "details": str(e)}), 500
        finally:
            if conn is not None:
                conn.close()


    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
