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

CASHFREE_URL=CASHFREE_URL = "https://api.cashfree.com/pg/orders"

# ---------------- FOLDERS ----------------

if not os.path.exists("images"):
    os.makedirs("images")

app.mount("/images", StaticFiles(directory="images"), name="images")

# ---------------- DB ----------------

def get_conn():
    return sqlite3.connect(
        "kisan_mart.db",
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
        image TEXT
    )
    """)

    # ORDERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        mobile TEXT,
        location TEXT,
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

    path = f"images/{filename}"

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

        products.append({
            "id": r[0],
            "name": r[1],
            "price": r[2],
            "category": r[3],
            "image": r[4]
        })

    conn.close()

    return products

@app.post("/add-product")
def add_product(data: dict):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO products (name,price,category,image) VALUES (?,?,?,?)",
        (
            data.get("name"),
            data.get("price"),
            data.get("category"),
            data.get("image")
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

# ---------------- CREATE PAYMENT ----------------

@app.post("/create-payment")
def create_payment(data: dict):

    amount = data.get("amount")
    name = data.get("name")
    mobile = data.get("mobile")

    order_id = "ORDER_" + str(uuid.uuid4())[:8]

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
            "return_url": "https://agriwala-1.onrender.com"
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

    farmer = data.get("farmer")

    if not farmer:
        return {"error": "Farmer missing"}

    name = farmer.get("name")
    mobile = farmer.get("mobile")
    location = farmer.get("location")

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

    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)

    """, (

        name,
        mobile,
        location,
        items,
        total,
        payment_id,
        payment_status,
        "Pending",
        created_at,
        referral,
        myRef,
        discount

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
            "items": json.loads(r[4]),
            "total": r[5],
            "payment_id": r[6],
            "payment_status": r[7],
            "status": r[8],
            "date": r[9],
            "referral": r[10],
            "myRef": r[11],
            "discount": r[12]

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