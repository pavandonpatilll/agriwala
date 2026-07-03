from fastapi import FastAPI, UploadFile, File # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from fastapi.staticfiles import StaticFiles # type: ignore
import sqlite3
import shutil
import json
import os
import uuid
import requests
from datetime import datetime
from fastapi import Request # type: ignore

app = FastAPI()

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- CASHFREE ----------------
CASHFREE_APP_ID = os.getenv("CASHFREE_APP_ID")
CASHFREE_SECRET_KEY = os.getenv("CASHFREE_SECRET_KEY")

CASHFREE_URL = "https://api.cashfree.com/pg/orders"


# ---------------- STORAGE ----------------

DATA_DIR = "/var/data"

os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "kisan_mart.db")

IMAGE_DIR = os.path.join(DATA_DIR, "images")

os.makedirs(IMAGE_DIR, exist_ok=True)

app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

# ---------------- DB ----------------

def get_conn():
    return sqlite3.connect(
        DB_PATH,
        timeout=10,
        check_same_thread=False
    )

def init_db():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("PRAGMA journal_mode=WAL;")

    # PRODUCTS
    cursor.execute("""
CREATE TABLE IF NOT EXISTS products(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    price INTEGER,
    category TEXT,
    description TEXT,
    image TEXT,
    image2 TEXT,
    image3 TEXT,
    image4 TEXT,
                   
    price100 INTEGER,
    price250 INTEGER,
    price500 INTEGER,
    price1000 INTEGER,   
                              
    discount INTEGER DEFAULT 0,
                   
    cod INTEGER DEFAULT 1
)
""")

    try:
        cursor.execute("""
        ALTER TABLE products
        ADD COLUMN discount INTEGER DEFAULT 0
        """)
    except:
        pass

    try:
        cursor.execute("""
        ALTER TABLE products
        ADD COLUMN price100 INTEGER
        """)
    except:
        pass

    try:
        cursor.execute("""
        ALTER TABLE products
        ADD COLUMN price250 INTEGER
        """)
    except:
        pass

    try:
        cursor.execute("""
        ALTER TABLE products
        ADD COLUMN price500 INTEGER
        """)
    except:
        pass

    try:
        cursor.execute("""
        ALTER TABLE products
        ADD COLUMN price1000 INTEGER
        """)
    except:
        pass

    try:
        cursor.execute("""
        ALTER TABLE products
        ADD COLUMN cod INTEGER DEFAULT 1
        """)
    except:
        pass

    try:
        cursor.execute("""
        ALTER TABLE products
        ADD COLUMN rating REAL DEFAULT 5
        """)
    except:
        pass

    try:
        cursor.execute("""
        ALTER TABLE products
        ADD COLUMN reviews INTEGER DEFAULT 0
        """)
    except:
        pass

    # ORDERS

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        mobile TEXT,
        location TEXT,
        house TEXT,
        area TEXT,
        city TEXT,
        state TEXT,
        pincode TEXT,
        landmark TEXT,
        items TEXT,
        total INTEGER,
        payment_id TEXT,
        payment_status TEXT,
        status TEXT,
        created_at TEXT,
        referral TEXT,
        myRef TEXT,
        discount INTEGER
    )
    """)

    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN house TEXT")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN area TEXT")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN city TEXT")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN state TEXT")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN pincode TEXT")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN landmark TEXT")
    except:
        pass

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pending_orders(
     order_id TEXT PRIMARY KEY,
       order_data TEXT
           )
                 """)

    cursor.execute("""
CREATE TABLE IF NOT EXISTS reviews(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    name TEXT,
    stars INTEGER,
    review TEXT,
    created_at TEXT
)
""")

    # REFERRALS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS referrals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref TEXT UNIQUE,
        count INTEGER
    )
    """)

    # REWARDS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rewards(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref TEXT UNIQUE,
        reward TEXT,
        status TEXT
    )
    """)

    # REFERRAL LOGS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS referral_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer TEXT,
        referred_user TEXT,
        order_id INTEGER,
        status TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- IMAGE UPLOAD ----------------

@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):

    import time

    filename = f"{int(time.time())}_{file.filename}"

    path = os.path.join(IMAGE_DIR, filename)

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    url = f"https://agriwala.onrender.com/images/{filename}"

    return {
        "image": url
    }

# ---------------- PRODUCTS ----------------

@app.get("/products")
def get_products():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    rows = cursor.fetchall()

    products = []

    for r in rows:

        # Average Rating
        cursor.execute(
            "SELECT ROUND(AVG(stars),1), COUNT(*) FROM reviews WHERE product_id=?",
            (r[0],)
        )

        review = cursor.fetchone()

        rating = review[0] if review[0] else 5
        reviews = review[1] if review[1] else 0

        products.append({
            "id": r[0],
            "name": r[1],
            "price": r[2],
            "category": r[3],
            "description": r[4],
            "image": r[5],
            "image2": r[6],
            "image3": r[7],
            "image4": r[8],
            "price100": r[9],
            "price250": r[10],
            "price500": r[11],
            "price1000": r[12],
            "discount": r[13],
            "cod": bool(r[14]),
            "rating": rating,
            "reviews": reviews
        })

    conn.close()

    return products

@app.post("/add-product")
def add_product(data: dict):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO products (name,price,category,description,image,image2,image3,image4,price100,price250,price500,price1000,cod) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
         data.get("name"),
        data.get("price"),
        data.get("category"),
        data.get("description"),
        data.get("image"),
        data.get("image2"),
        data.get("image3"),
        data.get("image4"),
        data.get("price100"),
        data.get("price250"),
        data.get("price500"),
        data.get("price1000"),
        1 if data.get("cod") else 0

        )
    )

    conn.commit()
    conn.close()

    return {
        "message": "Product added"
    }

@app.delete("/delete-product/{id}")
def delete_product(id: int):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM products WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return {
        "message": "Deleted"
    }

@app.post("/update-discount")
def update_discount(data: dict):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE products
        SET discount=?
        WHERE id=?
        """,
        (
            data.get("discount"),
            data.get("id")
        )
    )

    conn.commit()
    conn.close()

    return {
        "message": "Discount Updated Successfully"
    }

# ---------------- CREATE PAYMENT ----------------

@app.post("/create-payment")
def create_payment(data: dict):

    amount = data.get("amount")
    name = data.get("name")
    mobile = data.get("mobile")

    order_id = "ORDER_" + str(uuid.uuid4())[:8]

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO pending_orders(order_id, order_data) VALUES(?, ?)",
        (
            order_id,
            json.dumps(data)
        )
    )

    conn.commit()
    conn.close()

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-client-id": CASHFREE_APP_ID,
        "x-client-secret": CASHFREE_SECRET_KEY,
        "x-api-version": "2023-08-01"
    }

    payload = {
        "order_id": order_id,
        "order_amount": amount,
        "order_currency": "INR",

        "customer_details": {
            "customer_id": "USER_" + mobile,
            "customer_name": name,
            "customer_phone": mobile
        },

        "order_meta": {
            "return_url": "https://krushicom.com"
        }
    }

    response = requests.post(
        CASHFREE_URL,
        json=payload,
        headers=headers
    )

    result = response.json()

    print(result)

    if "payment_session_id" in result:

        return {
            "payment_session_id": result["payment_session_id"],
            "order_id": order_id
        }

    return {
        "error": result
    }

# ---------------- PLACE ORDER ----------------

@app.post("/order")
def place_order(data: dict):

    conn = get_conn()
    cursor = conn.cursor()

    farmer = data.get("farmer") or {}
    name = farmer.get("name") or data.get("name")
    mobile = farmer.get("mobile") or data.get("mobile")
    location = farmer.get("location") or data.get("location")
    house = farmer.get("house", "")
    area = farmer.get("area", "")
    city = farmer.get("city", "")
    state = farmer.get("state", "")
    pincode = farmer.get("pincode", "")
    landmark = farmer.get("landmark", "")

    if not mobile:
        return {"error": "Mobile missing"}

    items = json.dumps(data.get("items", []))

    total = data.get("total", 0)

    payment_id = data.get("payment_id", "")

    payment_status = data.get("payment_status", "PENDING")

    referral = data.get("referral", "")

    myRef = data.get("myRef", "")

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    discount = data.get("discount", 0)

    # SAVE ORDER

    cursor.execute("""

    INSERT INTO orders(

    name,
    mobile,
    location,

    house,
    area,
    city,
    state,
    pincode,
    landmark,

    items,
    total,
    payment_id,
    payment_status,
    status,
    created_at,
    referral,
    myRef,
    discount

)

VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)

    """, (

        (

    name,
    mobile,
    location,

    house,
    area,
    city,
    state,
    pincode,
    landmark,

    items,
    total,
    payment_id,
    payment_status,
    "Pending",
    created_at,
    referral,
    myRef,
    discount

)
    ))

    order_id = cursor.lastrowid

    # REFERRAL SAVE

    if referral and referral != myRef:

        cursor.execute("""

        INSERT INTO referral_logs(

            referrer,
            referred_user,
            order_id,
            status

        )

        VALUES(?,?,?,?)

        """, (

            referral,
            mobile,
            order_id,
            "Pending"

        ))

        # REFERRAL COUNT

        cursor.execute(
            "SELECT count FROM referrals WHERE ref=?",
            (referral,)
        )

        row = cursor.fetchone()

        if row:

            new_count = row[0] + 1

            cursor.execute(
                "UPDATE referrals SET count=? WHERE ref=?",
                (new_count, referral)
            )

        else:

            new_count = 1

            cursor.execute(
                "INSERT INTO referrals(ref,count) VALUES(?,?)",
                (referral, 1)
            )

        # AUTO REWARD

        if new_count == 10:

            cursor.execute(
                "SELECT * FROM rewards WHERE ref=?",
                (referral,)
            )

            reward_exist = cursor.fetchone()

            if not reward_exist:

                cursor.execute("""

                INSERT INTO rewards(
                    ref,
                    reward,
                    status
                )

                VALUES(?,?,?)

                """, (

                    referral,
                    "FREE_PRODUCT",
                    "pending"

                ))

    conn.commit()
    conn.close()

    return {
        "message": "Order placed"
    }

@app.post("/add-review")
def add_review(data: dict):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO reviews(
        product_id,
        name,
        stars,
        review,
        created_at
    )
    VALUES(?,?,?,?,?)
    """,(
        data.get("product_id"),
        data.get("name"),
        data.get("stars"),
        data.get("review"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return {"message":"Review Added"}

@app.get("/reviews/{product_id}")
def get_reviews(product_id: int):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT name, stars, review, created_at
    FROM reviews
    WHERE product_id=?
    ORDER BY id DESC
    """, (product_id,))

    rows = cursor.fetchall()

    conn.close()

    data = []

    for r in rows:
        data.append({
            "name": r[0],
            "stars": r[1],
            "review": r[2],
            "date": r[3]
        })

    return data

# ---------------- GET ORDERS ----------------
@app.get("/orders")
def get_orders():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders ORDER BY id DESC")

    rows = cursor.fetchall()

    orders = []

    for r in rows:

        orders.append({

    "id": r[0],
    "name": r[1],
    "mobile": r[2],
    "location": r[3],

    "house": r[4],
    "area": r[5],
    "city": r[6],
    "state": r[7],
    "pincode": r[8],
    "landmark": r[9],

    "items": json.loads(r[10]) if r[10] else [],
    "total": r[11],
    "payment_id": r[12],
    "payment_status": r[13],
    "status": r[14],
    "date": r[15],
    "referral": r[16],
    "myRef": r[17],
    "discount": r[18]

})

    conn.close()

    return orders

# ---------------- UPDATE ORDER ----------------

@app.put("/update-order/{id}")
def update_order(id: int, data: dict):

    conn = get_conn()
    cursor = conn.cursor()

    status = data.get("status")

    cursor.execute(
        "UPDATE orders SET status=? WHERE id=?",
        (status, id)
    )

    # REFERRAL SUCCESS

    if status == "Delivered":

        cursor.execute("""

        UPDATE referral_logs

        SET status='Success'

        WHERE order_id=?

        """, (id,))

    conn.commit()
    conn.close()

    return {
        "message": "Updated"
    }

# ---------------- TRACK ----------------

@app.get("/track/{mobile}")
def track(mobile: str):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""

    SELECT status

    FROM orders

    WHERE mobile=?

    ORDER BY id DESC

    LIMIT 1

    """, (mobile,))

    row = cursor.fetchone()

    conn.close()

    if row:

        return {
            "status": row[0]
        }

    return {
        "status": "No order found"
    }

# ---------------- REWARD ----------------

@app.get("/reward/{ref}")
def get_reward(ref: str):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT reward,status FROM rewards WHERE ref=?",
        (ref,)
    )

    row = cursor.fetchone()

    conn.close()

    if row:

        return {
            "reward": row[0],
            "status": row[1]
        }

    return {
        "reward": None
    }

# ---------------- WALLET ----------------

wallet = {}

@app.get("/wallet/{ref}")
def get_wallet(ref: str):

    return {
        "balance": wallet.get(ref, 0)
    }

# ---------------- USER REFERRALS ----------------

@app.get("/user/referrals/{ref}")
def user_referrals(ref: str):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""

    SELECT referred_user, order_id, status

    FROM referral_logs

    WHERE referrer=?

    ORDER BY id DESC

    """, (ref,))

    rows = cursor.fetchall()

    data = []

    for r in rows:

        data.append({

            "user": r[0],
            "order": r[1],
            "status": r[2]

        })

    conn.close()

    return data

# ---------------- ADMIN REFERRALS ----------------

@app.get("/admin/referrals")
def all_referrals():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT ref,count FROM referrals ORDER BY count DESC"
    )

    rows = cursor.fetchall()

    data = []

    for r in rows:

        data.append({

            "ref": r[0],
            "count": r[1]

        })

    conn.close()

    return data

# ---------------- ADMIN REFERRAL DETAILS ----------------

@app.get("/admin/referral-details")
def referral_details():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""

    SELECT
    referrer,
    referred_user,
    order_id,
    status

    FROM referral_logs

    ORDER BY id DESC

    """)

    rows = cursor.fetchall()

    data = []

    for r in rows:

        data.append({

            "referrer": r[0],
            "user": r[1],
            "order": r[2],
            "status": r[3]

        })

    conn.close()

    return data

# ---------------- APPROVE REWARD ----------------

@app.post("/admin/approve")
def approve_reward(data: dict):

    conn = get_conn()
    cursor = conn.cursor()

    ref = data.get("ref")

    cursor.execute(
        "UPDATE rewards SET status='approved' WHERE ref=?",
        (ref,)
    )

    conn.commit()
    conn.close()

    return {
        "message": "Reward Approved"
    }

# ---------------- CUSTOM REWARD ----------------

@app.post("/admin/custom-reward")
def custom_reward(data: dict):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""

    INSERT OR REPLACE INTO rewards(
        ref,
        reward,
        status
    )

    VALUES(?,?,?)

    """, (

        data.get("ref"),
        data.get("reward"),
        "approved"

    ))

    conn.commit()
    conn.close()

    return {
        "message": "Reward Given"
    }

@app.post("/cashfree-webhook")
async def cashfree_webhook(request: Request):
    data = await request.json()

    print("WEBHOOK RECEIVED")
    print(data)

    if data.get("type") == "PAYMENT_SUCCESS_WEBHOOK":

        order_id = data["data"]["order"]["order_id"]

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT order_data FROM pending_orders WHERE order_id=?",
            (order_id,)
        )

        row = cursor.fetchone()

        if row:
            print("PENDING ORDER FOUND")

            order_data = json.loads(row[0])

            farmer = order_data.get("farmer", {})
            items = json.dumps(order_data.get("items", []))

            cursor.execute("""

           INSERT INTO orders(

    name,
    mobile,
    location,
    house,
    area,
    city,
    state,
    pincode,
    landmark,
    items,
    total,
    payment_id,
    payment_status,
    status,
    created_at,
    referral,
    myRef,
    discount

)

VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)

            """, (

                (

    order_data.get("name"),
    order_data.get("mobile"),
    order_data.get("location"),

    order_data.get("house"),
    order_data.get("area"),
    order_data.get("city"),
    order_data.get("state"),
    order_data.get("pincode"),
    order_data.get("landmark"),

    items,
    order_data.get("amount", 0),

    data["data"]["payment"]["cf_payment_id"],

    "PAID",
    "Pending",

    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

    order_data.get("referral", ""),
    order_data.get("myRef", ""),
    order_data.get("discount", 0)

)

            ))

            cursor.execute(
                "DELETE FROM pending_orders WHERE order_id=?",
                (order_id,)
            )

            conn.commit()

            print("ORDER SAVED FROM WEBHOOK")

        conn.close()

    return {"status": "ok"}

@app.get("/test")
def test():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(products)")

    rows = cursor.fetchall()

    conn.close()

    return rows

