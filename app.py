from flask import Flask, request, session, jsonify, g
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import secrets
import cloudinary
from PIL import Image
import cloudinary.uploader
import secrets

app = Flask(__name__)
app.secret_key = "supersecretkey"
CORS(app, supports_credentials=True, resources={
    r"/*": {"origins": [
        "https://mealmonkeyapplication.netlify.app",
        "http://localhost:3000"
    ]}
})

app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True
)

# Cloudinary config
cloudinary.config(
    cloud_name="djsaxy3g0",
    api_key="825115494888219",
    api_secret="IlR0mMctCif7jkS6Whn3AfsLxbc"
)

# ---------------- DATABASE ----------------
def get_db():
    if "db" not in g:
        g.db = pymysql.connect(
            host="mealmonkey-mealmonkey-3546.d.aivencloud.com",
            port=26729,  # int
            user="avnadmin",
            password="AVNS_5A05vlS_gakWu8p0-s0",
            db="defaultdb",
            cursorclass=pymysql.cursors.DictCursor
        )
    return g.db
# !!
# def get_db():
#     if "db" not in g:
#         g.db = pymysql.connect(
#             host="localhost",
#             user="root",
#             password="Prithesh0103",
#             db="meal_monkey",
#             cursorclass=pymysql.cursors.DictCursor
#         )
#     return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db:
        db.close()

# ---------------- HELPERS ----------------
def require_role(role):
    def decorator(func):
        def wrapper(*args, **kwargs):
            session_role = session.get("role")
            if session_role != role:
                return jsonify({"message": "Unauthorized"}), 401
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

@app.route("/delete_food/<int:food_id>", methods=["DELETE"])
@require_role("restaurant")
def delete_food(food_id):
    db = get_db()
    with db.cursor() as cursor:
        # First delete any order_items linked to this food
        cursor.execute("DELETE FROM order_items WHERE food_id = %s", (food_id,))
        
        # Then delete the food item itself
        cursor.execute("DELETE FROM menu WHERE food_id = %s", (food_id,))
        
        db.commit()

    return jsonify({"message": "Food deleted successfully"}), 200



# ---------------- USERS ----------------
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    password = generate_password_hash(data.get("password"))
    phone = data.get("phone")

    # generate seed and avatar URL with new format
    seed = secrets.token_hex(8)
    avatar_url = f"https://api.dicebear.com/9.x/thumbs/svg?seed={seed}"

    db = get_db()
    with db.cursor() as cursor:
        try:
            cursor.execute(
                "INSERT INTO users (name, email, password, phone, avatar_url) VALUES (%s, %s, %s, %s, %s)",
                (name, email, password, phone, avatar_url)
            )
            db.commit()  # 🔥 this line is missing
            return jsonify({
                "message": "User registered successfully",
                "avatar_url": avatar_url
            })
        except pymysql.err.IntegrityError:
            return jsonify({"message": "Email already exists"}), 400

@app.route("/user_login", methods=["POST"])
def user_login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    db = get_db()
    with db.cursor(pymysql.cursors.DictCursor) as cursor:  # <-- add DictCursor here
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()


    if user and check_password_hash(user['password'], password):
        session["user_id"] = user["user_id"]
        session["user_name"] = user["name"]
        session["role"] = "user"
        return jsonify({
            "message": "Login successful",
            "avatar_url": user.get("avatar_url")
        })
    else:
        return jsonify({"message": "Invalid email or password"}), 400

@app.route("/user_logout", methods=["POST"])
def user_logout():
    session.clear()
    return jsonify({"message": "Logged out"})

# ---------------- RESTAURANT ----------------
@app.route("/restaurant_register", methods=["POST"])
def restaurant_register():
    data = request.json
    invite_code = data.get("invite_code")
    name = data.get("name")
    email = data.get("email")
    password = generate_password_hash(data.get("password"))

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM restaurant_invites WHERE invite_code=%s AND used=FALSE", (invite_code,))
        invite = cursor.fetchone()
        if not invite:
            return jsonify({"message": "Invalid or used invite code"}), 400
        try:
            cursor.execute(
                "INSERT INTO restaurants (name, email, password) VALUES (%s, %s, %s)",
                (name, email, password)
            )
            cursor.execute("UPDATE restaurant_invites SET used=TRUE WHERE invite_code=%s", (invite_code,))
            db.commit()  # 🔥 this line is missing
            return jsonify({"message": "Restaurant registered successfully"})
        except Exception as e:
            print("DEBUG:", e)
            return jsonify({"message": "Registration failed"}), 400
        
# ---------------- EDIT FOOD ----------------
@app.route("/edit_food/<int:food_id>", methods=["PATCH"])
@require_role("restaurant")
def edit_food(food_id):
    restaurant_id = session.get("restaurant_id")
    name = request.form.get("name")
    description = request.form.get("description")
    price = request.form.get("price")
    veg_nonveg = request.form.get("veg_nonveg")

    image = request.files.get("image")
    image_url = None
    if image:
        upload_result = cloudinary.uploader.upload(image)
        image_url = upload_result["secure_url"]

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM menu WHERE food_id=%s AND restaurant_id=%s", (food_id, restaurant_id))
        item = cursor.fetchone()
        if not item:
            return jsonify({"message": "Item not found or unauthorized"}), 404

        if image_url:
            cursor.execute(
                "UPDATE menu SET name=%s, description=%s, price=%s, veg_nonveg=%s, image_url=%s WHERE food_id=%s",
                (name, description, float(price), veg_nonveg, image_url, food_id)
            )
        else:
            cursor.execute(
                "UPDATE menu SET name=%s, description=%s, price=%s, veg_nonveg=%s WHERE food_id=%s",
                (name, description, float(price), veg_nonveg, food_id)
            )
        db.commit()
    return jsonify({"message": "Food updated successfully", "food_id": food_id})



@app.route("/restaurant_login", methods=["POST"])
def restaurant_login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM restaurants WHERE email=%s", (email,))
        restaurant = cursor.fetchone()

    if restaurant and check_password_hash(restaurant['password'], password):
        # clear any user session
        session.pop("user_id", None)
        session.pop("user_name", None)
        session["restaurant_id"] = restaurant["restaurant_id"]
        session["restaurant_name"] = restaurant["name"]
        session["role"] = "restaurant"
        return jsonify({"message": "Login successful"})
    else:
        return jsonify({"message": "Invalid email or password"}), 400

@app.route("/restaurant_logout", methods=["POST"])
@require_role("restaurant")
def restaurant_logout():
    session.clear()
    return jsonify({"message": "Restaurant logged out"})

# ---------------- RESTAURANT MENU ----------------
@app.route("/restaurant_menu", methods=["GET"])
@require_role("restaurant")
def restaurant_menu():
    restaurant_id = session.get("restaurant_id")
    search = request.args.get("search", "")
    veg_filter = request.args.get("veg", "")
    price_order = request.args.get("price_order", "asc")

    query = "SELECT * FROM menu WHERE restaurant_id=%s"
    params = [restaurant_id]

    if veg_filter in ["veg", "non-veg"]:
        query += " AND veg_nonveg=%s"
        params.append(veg_filter)

    if search:
        query += " AND name LIKE %s"
        params.append(f"%{search}%")

    query += " ORDER BY price " + ("DESC" if price_order == "desc" else "ASC")

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(query, params)
        menu_items = cursor.fetchall()

    return jsonify({"menu": menu_items})

# ---------------- ADD FOOD ----------------
@app.route("/add_food", methods=["POST"])
@require_role("restaurant")
def add_food():
    restaurant_id = session.get("restaurant_id")
    name = request.form.get("name")
    description = request.form.get("description")
    price = request.form.get("price")
    veg_nonveg = request.form.get("veg_nonveg")

    image = request.files.get("image")
    image_url = None

    if image:
        upload_result = cloudinary.uploader.upload(image)
        image_url = upload_result["secure_url"]

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO menu (restaurant_id, name, description, price, veg_nonveg, image_url)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (restaurant_id, name, description, float(price), veg_nonveg, image_url),
        )
        db.commit()   # 🔥🔥🔥 THIS IS WHAT YOU ARE MISSING

        new_id = cursor.lastrowid

    return jsonify({
        "message": "Food added",
        "food_id": new_id,
        "name": name,
        "description": description,
        "price": price,
        "veg_nonveg": veg_nonveg,
        "image_url": image_url
    })


# ---------------- SHOP STATUS ----------------
@app.route("/get_shop_status", methods=["GET"])
@require_role("restaurant")
def get_shop_status():
    restaurant_id = session.get("restaurant_id")
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT shop_status FROM restaurants WHERE restaurant_id=%s", (restaurant_id,))
        result = cursor.fetchone()
    status = result["shop_status"] if result else None
    return jsonify({"status": status})

@app.route("/toggle_shop_status", methods=["PATCH"])
@require_role("restaurant")
def toggle_shop_status():
    restaurant_id = session.get("restaurant_id")
    data = request.json
    new_status = data.get("status")

    if new_status is None:
        return jsonify({"message": "Missing status"}), 400

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            "UPDATE restaurants SET shop_status=%s WHERE restaurant_id=%s",
            (new_status, restaurant_id)
        )
    db.commit()   # ⭐ REQUIRED

    return jsonify({"status": new_status})


# ---------------- INVITE GENERATION ----------------
@app.route("/generate_invite", methods=["POST"])
def generate_invite():
    invite_code = secrets.token_hex(8)
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("INSERT INTO restaurant_invites (invite_code) VALUES (%s)", (invite_code,))
        db.commit()
    return jsonify({"invite_code": invite_code})


# ---------------- TOGGLE FOOD AVAILABILITY ----------------
@app.route("/toggle_availability/<int:food_id>", methods=["PATCH"])
@require_role("restaurant")
def toggle_availability(food_id):
    restaurant_id = session.get("restaurant_id")
    db = get_db()
    with db.cursor() as cursor:
        # Make sure the food belongs to this restaurant
        cursor.execute("SELECT available FROM menu WHERE food_id=%s AND restaurant_id=%s", (food_id, restaurant_id))
        item = cursor.fetchone()
        if not item:
            return jsonify({"message": "Item not found or unauthorized"}), 404
        
        new_status = not item["available"]
        cursor.execute("UPDATE menu SET available=%s WHERE food_id=%s", (new_status, food_id))
        db.commit()
    return jsonify({"food_id": food_id, "available": new_status})

@app.route("/get_restaurant_profile", methods=["GET"])
@require_role("restaurant")
def get_restaurant_profile():
    restaurant_id = session.get("restaurant_id")
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT name, email, image_url, shop_status FROM restaurants WHERE restaurant_id=%s", (restaurant_id,))
        profile = cursor.fetchone()
    return jsonify(profile)

@app.route("/upload_restaurant_image", methods=["POST"])
@require_role("restaurant")
def upload_restaurant_image():
    restaurant_id = session.get("restaurant_id")
    image = request.files.get("image")

    if not image:
        return jsonify({"message": "No image provided"}), 400

    # Pillow check for 16:9
    img = Image.open(image.stream)
    width, height = img.size
    ratio = width / height
    
    # Check for 1:1 ratio
    if abs(ratio - 1) > 0.01:
        return jsonify({"message": "Image must be 1:1 ratio"}), 400


    # Upload to Cloudinary (use stream!)
    image.stream.seek(0)  # reset pointer after Pillow read
    upload_result = cloudinary.uploader.upload(image.stream, resource_type="image")
    image_url = upload_result["secure_url"]

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            "UPDATE restaurants SET image_url=%s WHERE restaurant_id=%s",
            (image_url, restaurant_id)
        )
        db.commit()

    return jsonify({"message": "Image uploaded successfully", "url": image_url})

# ---------------- CART ROUTES ----------------
@app.route("/cart", methods=["GET"])
def get_cart():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Login required"}), 401

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT c.cart_id, c.quantity, m.food_id, m.name, m.price, m.image_url, m.restaurant_id
            FROM cart c
            JOIN menu m ON c.food_id = m.food_id
            WHERE c.user_id = %s
        """, (user_id,))

        cart_items = cursor.fetchall()
    total_price = sum(item["price"] * item["quantity"] for item in cart_items)
    return jsonify({"items": cart_items, "total_price": total_price})


@app.route("/cart/add", methods=["POST"])
def add_to_cart():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Login required"}), 401

    data = request.json
    food_id = data.get("food_id")
    quantity = data.get("quantity", 1)

    db = get_db()
    with db.cursor() as cursor:
        # Get restaurant of this food
        cursor.execute("SELECT restaurant_id FROM menu WHERE food_id=%s", (food_id,))
        food = cursor.fetchone()
        if not food:
            return jsonify({"message": "Food not found"}), 404
        food_restaurant_id = food["restaurant_id"]

        # Check existing cart items
        cursor.execute("""
            SELECT c.*, m.restaurant_id FROM cart c
            JOIN menu m ON c.food_id = m.food_id
            WHERE c.user_id=%s
        """, (user_id,))
        cart_items = cursor.fetchall()

        if cart_items and cart_items[0]["restaurant_id"] != food_restaurant_id:
            return jsonify({
                "message": "You can only add items from one restaurant at a time. Clear your cart first."
            }), 400

        # Check if item already exists in cart
        cursor.execute("SELECT quantity FROM cart WHERE user_id=%s AND food_id=%s", (user_id, food_id))
        item = cursor.fetchone()
        if item:
            new_qty = item["quantity"] + quantity
            cursor.execute("UPDATE cart SET quantity=%s WHERE user_id=%s AND food_id=%s", (new_qty, user_id, food_id))
        else:
            cursor.execute("INSERT INTO cart (user_id, food_id, quantity) VALUES (%s,%s,%s)", (user_id, food_id, quantity))

        db.commit()

    return jsonify({"message": "Added to cart"})



@app.route("/cart/update", methods=["PATCH"])
def update_cart_item():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Login required"}), 401

    data = request.json
    food_id = data.get("food_id")
    quantity = data.get("quantity", 1)

    db = get_db()
    with db.cursor() as cursor:
        if quantity <= 0:
            cursor.execute("DELETE FROM cart WHERE user_id=%s AND food_id=%s", (user_id, food_id))
        else:
            cursor.execute("UPDATE cart SET quantity=%s WHERE user_id=%s AND food_id=%s", (quantity, user_id, food_id))
        db.commit()
    return jsonify({"message": "Cart updated"})


@app.route("/cart/remove/<int:food_id>", methods=["DELETE"])
def remove_from_cart(food_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Login required"}), 401

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("DELETE FROM cart WHERE user_id=%s AND food_id=%s", (user_id, food_id))
        db.commit()
    return jsonify({"message": "Item removed from cart"})


@app.route("/place_order", methods=["POST"])
@require_role("user")
def place_order():
    user_id = session.get("user_id")
    db = get_db()
    with db.cursor() as cursor:
        # Fetch cart items + price + restaurant_id
        cursor.execute("""
            SELECT c.food_id, c.quantity, m.price, m.restaurant_id
            FROM cart c
            JOIN menu m ON c.food_id = m.food_id
            WHERE c.user_id = %s
        """, (user_id,))
        cart_items = cursor.fetchall()
        if not cart_items:
            return jsonify({"message": "Cart is empty"}), 400

        # Check all items belong to the same restaurant
        restaurant_ids = {item["restaurant_id"] for item in cart_items}
        if len(restaurant_ids) > 1:
            return jsonify({"message": "Cart has items from multiple restaurants"}), 400
        restaurant_id = restaurant_ids.pop()

        # Calculate total price
        total_price = sum(item["price"] * item["quantity"] for item in cart_items)

        # Insert order
        cursor.execute(
            "INSERT INTO orders (user_id, restaurant_id, total_price) VALUES (%s, %s, %s)",
            (user_id, restaurant_id, total_price)
        )
        order_id = cursor.lastrowid

        # Insert order items
        for item in cart_items:
            cursor.execute(
                "INSERT INTO order_items (order_id, food_id, quantity, price) VALUES (%s, %s, %s, %s)",
                (order_id, item["food_id"], item["quantity"], item["price"])
            )

        # Clear cart
        cursor.execute("DELETE FROM cart WHERE user_id=%s", (user_id,))
        db.commit()

    return jsonify({"message": "Order placed successfully!", "order_id": order_id})


# ---------------- GET ALL RESTAURANTS ----------------
@app.route("/restaurants", methods=["GET"])
def get_all_restaurants():
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT restaurant_id, name, image_url, shop_status FROM restaurants")
        restaurants = cursor.fetchall()
    return jsonify(restaurants)
@app.route("/restaurants/<int:restaurant_id>", methods=["GET"])
def get_restaurant_by_id(restaurant_id):
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT restaurant_id, name, image_url, shop_status FROM restaurants WHERE restaurant_id=%s",
            (restaurant_id,)
        )
        restaurant = cursor.fetchone()
        if not restaurant:
            return jsonify({"message": "Restaurant not found"}), 404
    return jsonify(restaurant)



# For users (public access)
@app.route("/menu", methods=["GET"])
def get_menu():
    restaurant_id = request.args.get("restaurant_id")
    filter_type = request.args.get("type")   # breakfast/lunch/dinner/snacks
    available = request.args.get("available")

    query = "SELECT * FROM menu WHERE restaurant_id=%s"
    params = [restaurant_id]

    if filter_type:
        query += " AND type=%s"
        params.append(filter_type)

    if available is not None:
        query += " AND available=%s"
        params.append(available.lower() == "true")

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(query, params)
        items = cursor.fetchall()

    return jsonify(items)

@app.route("/cart/clear", methods=["DELETE"])
def clear_cart():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Login required"}), 401

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("DELETE FROM cart WHERE user_id=%s", (user_id,))
        db.commit()

    return jsonify({"message": "Cart cleared"})
@app.route("/checkout", methods=["POST"])
@require_role("user")
def checkout():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login first!"}), 401

    db = get_db()

    cart = request.json.get("cart", [])
    if not cart:
        return jsonify({"error": "Cart is empty!"}), 400

    # ensure all items are from one restaurant
    restaurant_ids = {item["restaurant_id"] for item in cart}
    if len(restaurant_ids) > 1:
        return jsonify({"error": "Cart has items from multiple restaurants"}), 400
    restaurant_id = restaurant_ids.pop()

    # calculate total_amount safely
    total_amount = sum(float(item["price"]) * int(item["quantity"]) for item in cart)

    try:
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO orders (user_id, restaurant_id, total_amount, order_status)
            VALUES (%s, %s, %s, 'Pending')
        """, (user_id, restaurant_id, total_amount))
        order_id = cursor.lastrowid

        for item in cart:
            cursor.execute("""
                INSERT INTO order_items (order_id, food_id, quantity, price)
                VALUES (%s, %s, %s, %s)
            """, (order_id, int(item["food_id"]), int(item["quantity"]), float(item["price"])))

        # clear cart
        cursor.execute("DELETE FROM cart WHERE user_id=%s", (user_id,))
        db.commit()
        cursor.close()

        return jsonify({"message": "Order placed!", "order_id": order_id})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500


@app.route("/orders", methods=["GET"])
def get_orders():
    try:
        db = get_db()
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Login first!"}), 401

        cursor = db.cursor()  # <-- default cursor returns tuples

        # Use this to get dicts instead of tuples
        cursor = db.cursor(pymysql.cursors.DictCursor)  # <-- key fix here
        cursor.execute("""
            SELECT 
                o.*,
                r.name AS restaurant_name,
                r.image_url AS restaurant_image
            FROM orders o
            JOIN restaurants r ON o.restaurant_id = r.restaurant_id
            WHERE o.user_id = %s
            ORDER BY o.created_at DESC
        """, (user_id,))
        orders = cursor.fetchall()
        
        for order in orders:
            cursor.execute("""
                SELECT 
                    oi.*,
                    m.name AS food_name,
                    m.image_url
                FROM order_items oi
                JOIN menu m ON m.food_id = oi.food_id
                WHERE oi.order_id = %s
            """, (order["order_id"],))
            order["items"] = cursor.fetchall()


        cursor.close()
        return jsonify(orders)

    except Exception as e:
        print("DEBUG /orders error:", e)
        return jsonify({"error": str(e)}), 500



@app.route("/menu/all", methods=["GET"])
def get_all_menu_items():
    db = get_db()
    with db.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("""
            SELECT 
                m.*, 
                r.name AS restaurant_name
            FROM menu m
            JOIN restaurants r 
                ON m.restaurant_id = r.restaurant_id
            WHERE m.available = TRUE
        """)
        items = cursor.fetchall()
    return jsonify(items)

@app.route("/get_user_name", methods=["GET"])
def get_user_name():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT name, avatar_url FROM users WHERE user_id=%s", (user_id,))
        user = cursor.fetchone()  # now returns dict

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "user_name": user["name"],
        "avatar_url": user["avatar_url"]
    })

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})

@app.route("/debug_session")
def debug_session():
    return jsonify(dict(session))

@app.route("/get_restaurant_image", methods=["GET"])
def get_restaurant_image():
    try:
        cur = get_db().cursor()
        cur.execute(
            "SELECT image_url FROM restaurants WHERE restaurant_id = %s",
            (session["restaurant_id"],)
        )
        row = cur.fetchone()

        if row and row["image_url"]:
            return jsonify({"url": row["image_url"]})
        else:
            return jsonify({"url": None})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)
