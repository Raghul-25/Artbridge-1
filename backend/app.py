import os
import random
import sqlite3
import uuid

from flask import Flask, jsonify, render_template, request

from db import get_connection, init_db
from werkzeug.utils import secure_filename
import razorpay


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Ensure the shared project DB + tables exist
    init_db()

    uploads_dir = os.path.join(app.static_folder, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/checkout")
    def checkout():
        key_id = os.environ.get("RAZORPAY_KEY_ID", "")
        return render_template("checkout.html", razorpay_key_id=key_id)

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
        conn = None
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT id, name, price, description, category, artisan_id, image_url FROM products"
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
            return jsonify({"error": "Failed to fetch products", "details": str(e)}), 500
        finally:
            if conn is not None:
                conn.close()

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
        conn = None
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, name, price, description, category, artisan_id, image_url
                FROM products
                WHERE id = ?
                """,
                (product_id,),
            )
            row = cur.fetchone()
            if row is None:
                return jsonify({"error": "Product not found"}), 404

            return jsonify(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "price": row["price"],
                    "description": row["description"],
                    "category": row["category"],
                    "image_url": row["image_url"],
                }
            )
        except sqlite3.Error as e:
            return jsonify({"error": "Failed to fetch product", "details": str(e)}), 500
        finally:
            if conn is not None:
                conn.close()

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
        key_id = os.environ.get("RAZORPAY_KEY_ID")
        key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
        if not key_id or not key_secret:
            return None, jsonify({"error": "Razorpay keys not configured"}), 500
        return razorpay.Client(auth=(key_id, key_secret)), None, None

    @app.post("/create_order")
    def create_payment_order():
        """
        Creates a Razorpay order in test mode.
        Prefer passing product_id; amount is derived from DB price.
        """
        payload = request.get_json(silent=True) or {}
        product_id = payload.get("product_id")

        try:
            product_id_num = int(product_id)
        except (TypeError, ValueError):
            return jsonify({"error": "product_id must be a number"}), 400

        conn = None
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT id, price FROM products WHERE id = ?",
                (product_id_num,),
            )
            row = cur.fetchone()
            if row is None:
                return jsonify({"error": "Product not found"}), 404

            amount_rupees = float(row["price"])
        except sqlite3.Error as e:
            return jsonify({"error": "Failed to read product", "details": str(e)}), 500
        finally:
            if conn is not None:
                conn.close()

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
        razorpay_order_id = payload.get("razorpay_order_id")
        razorpay_payment_id = payload.get("razorpay_payment_id")
        razorpay_signature = payload.get("razorpay_signature")
        product_id = payload.get("product_id")
        buyer = payload.get("buyer") or "Customer"

        try:
            product_id_num = int(product_id)
        except (TypeError, ValueError):
            return jsonify({"error": "product_id must be a number"}), 400

        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            return jsonify({"error": "Missing Razorpay payment fields"}), 400

        client, err_resp, err_code = _get_razorpay_client()
        if client is None:
            return err_resp, err_code

        try:
            client.utility.verify_payment_signature(
                {
                    "razorpay_order_id": razorpay_order_id,
                    "razorpay_payment_id": razorpay_payment_id,
                    "razorpay_signature": razorpay_signature,
                }
            )
        except Exception as e:
            return jsonify({"error": "Verification failed", "details": str(e)}), 400

        # Only after successful verification, store the order in DB.
        conn = None
        try:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute(
                "SELECT id, artisan_id FROM products WHERE id = ?",
                (product_id_num,),
            )
            product = cur.fetchone()
            if product is None:
                return jsonify({"error": "Product not found"}), 404

            artisan_id = product["artisan_id"]
            status = "Processing"
            tracking = f"ART{random.randint(1000, 9999)}"

            cur.execute(
                """
                INSERT INTO orders (product_id, artisan_id, buyer, status, tracking, payment_status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (product_id_num, artisan_id, buyer, status, tracking, "Paid"),
            )
            conn.commit()

            return jsonify(
                {
                    "message": "Payment verified and order placed",
                    "order_id": cur.lastrowid,
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
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)
