from flask import Flask, render_template, request, redirect, session, g, url_for, flash
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secret123'

# ----------------- DB CONNECTION -----------------
def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host="localhost",
            user="Muhammad",
            password="muhammad0149",
            database="database_db"
        )
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# ----------------- AUTH -----------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        db = get_db()
        cursor = db.cursor(dictionary=True)

        if role == 'user':
            cursor.execute("SELECT * FROM USER WHERE UEmail=%s AND UPassword=%s", (email, password))
        else:
            cursor.execute("SELECT * FROM ADMIN_LOGIN WHERE Email=%s AND Password=%s", (email, password))

        user = cursor.fetchone()
        cursor.close()

        if user:
            session['user_id'] = user['UID'] if role == 'user' else user['AID']
            session['role'] = role
            return redirect('/dashboard')
        else:
            flash("Invalid credentials. Please try again.", "danger")
            return redirect('/login')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()
        data = (
            request.form['name'], request.form['email'], request.form['password'],
            request.form['contact']
        )
        cursor.execute("""
            INSERT INTO USER (UName, UEmail, UPassword, UContact)
            VALUES (%s, %s, %s, %s)
        """, data)
        db.commit()
        cursor.close()
        flash("Registration successful. Please log in.", "success")
        return redirect('/login')
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ----------------- DASHBOARD -----------------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if session['role'] == 'user':
        search_query = request.args.get('search', '').strip()
        filter_by = request.args.get('filter_by', 'PName')
        sort_by = request.args.get('sort_by', '')

        if search_query:
            if filter_by == 'CCategory':
                query = """
                    SELECT P.* FROM PRODUCT P
                    JOIN COMPANY C ON P.CID = C.CID
                    WHERE C.CCategory LIKE %s
                """
                params = (f"%{search_query}%",)
            else:
                query = """
                    SELECT * FROM PRODUCT
                    WHERE PName LIKE %s OR AName LIKE %s OR PDescription LIKE %s
                """
                params = (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%")
        else:
            query = "SELECT * FROM PRODUCT"
            params = ()

        cursor.execute(query, params)
        products = cursor.fetchall()
        cursor.close()

        for p in products:
            aprice = float(p.get('APrice') or 0)
            duty = float(p.get('Duty') or 0)
            transport = float(p.get('Transport') or 0)
            gst = float(p.get('GST') or 0)
            gst_amount = aprice * gst / 100
            p['UPrice'] = round(aprice + duty + transport + gst_amount, 2)

        if sort_by == 'price_asc':
            products.sort(key=lambda x: x['UPrice'])
        elif sort_by == 'price_desc':
            products.sort(key=lambda x: x['UPrice'], reverse=True)
        elif sort_by == 'name_asc':
            products.sort(key=lambda x: x['PName'].lower())
        elif sort_by == 'name_desc':
            products.sort(key=lambda x: x['PName'].lower(), reverse=True)

        return render_template('user_dashboard.html', products=products)

    else:
        cursor.execute("""
        SELECT A.AID, U.UName, U.UContact, A.UAddress,
               P.PName, P.AName, P.APrice, P.UPrice, 
               C.CAddress, C.CContact,
               A.OrderTime, A.Status
        FROM ADMIN A
        JOIN USER U ON A.UID = U.UID
        JOIN PRODUCT P ON A.PID = P.PID
        JOIN COMPANY C ON P.CID = C.CID
        WHERE A.Status != 'Completed'
        ORDER BY A.AID ASC
    """)
    orders = cursor.fetchall()
    cursor.close()
    return render_template('admin_dashboard.html', orders=orders)


@app.route('/admin/companies')
def admin_companies():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM COMPANY")
    companies = cursor.fetchall()
    cursor.close()
    return render_template("company_manage.html", companies=companies)

@app.route('/admin/products')
def admin_products():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM PRODUCT")
    products = cursor.fetchall()
    cursor.close()
    return render_template("product_manage.html", products=products)

@app.route('/admin/history')
def view_order_history_admin():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT H.HAID, U.UName, P.PName, H.Quantity, H.OrderDate, H.CompletionTime, H.PaymentMethod
        FROM ORDER_HISTORY H
        JOIN USER U ON H.UID = U.UID
        JOIN PRODUCT P ON H.PID = P.PID
        ORDER BY H.CompletionTime DESC
    """)
    history = cursor.fetchall()
    cursor.close()
    return render_template("order_history_admin.html", history=history)

@app.route('/company/add', methods=['GET', 'POST'])
def add_company():
    if request.method == 'POST':
        data = (
            request.form['CName'], request.form['CAddress'], request.form['CCountry'],
            request.form['CContact'], request.form['CYear'], request.form['CCategory'],
            request.form['CDescription']
        )
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO COMPANY (CName, CAddress, CCountry, CContact, CYear, CCategory, CDescription)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, data)
        db.commit()
        flash("Company added.", "success")
        return redirect('/admin/companies')
    return render_template('company_form.html', action='Add')

@app.route('/company/edit/<int:cid>', methods=['GET', 'POST'])
def edit_company(cid):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        data = (
            request.form['CName'], request.form['CAddress'], request.form['CCountry'],
            request.form['CContact'], request.form['CYear'], request.form['CCategory'],
            request.form['CDescription'], cid
        )
        cursor.execute("""
            UPDATE COMPANY SET CName=%s, CAddress=%s, CCountry=%s, CContact=%s,
            CYear=%s, CCategory=%s, CDescription=%s WHERE CID=%s
        """, data)
        db.commit()
        flash("Company updated.", "success")
        return redirect('/admin/companies')
    cursor.execute("SELECT * FROM COMPANY WHERE CID = %s", (cid,))
    company = cursor.fetchone()
    cursor.close()
    return render_template('company_form.html', action='Edit', company=company)

@app.route('/company/delete/<int:cid>')
def delete_company(cid):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM PRODUCT WHERE CID = %s", (cid,))
    count = cursor.fetchone()[0]
    if count > 0:
        flash("Cannot delete: Products are linked to this company.", "danger")
    else:
        cursor.execute("DELETE FROM COMPANY WHERE CID = %s", (cid,))
        db.commit()
        flash("Company deleted.", "success")
    cursor.close()
    return redirect('/admin/companies')

@app.route('/product/add', methods=['GET', 'POST'])
def add_product():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        try:
            aprice = float(request.form['APrice'])
            duty = float(request.form['Duty'] or 0.0)
            transport = float(request.form['Transport'] or 0.0)
            gst = float(request.form['GST'] or 0.0)
            gst_amount = aprice * gst / 100
            uprice = round(aprice + gst_amount + duty + transport, 2)
            data = (
                request.form['PName'], request.form['AName'],
                request.form['PDescription'], request.form['PImage'],
                aprice, uprice, duty, transport, gst,
                request.form['CID']
            )
            cursor.execute("""
                INSERT INTO PRODUCT (PName, AName, PDescription, PImage, APrice, UPrice, Duty, Transport, GST, CID)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, data)
            db.commit()
            flash("Product added!", "success")
            return redirect('/admin/products')
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
    cursor.execute("SELECT CID, CName FROM COMPANY")
    companies = cursor.fetchall()
    cursor.close()
    return render_template('product_form.html', action='Add', companies=companies)

@app.route('/product/edit/<int:pid>', methods=['GET', 'POST'])
def edit_product(pid):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        try:
            aprice = float(request.form['APrice'])
            duty = float(request.form['Duty'] or 0.0)
            transport = float(request.form['Transport'] or 0.0)
            gst = float(request.form['GST'] or 0.0)
            gst_amount = aprice * gst / 100
            uprice = round(aprice + gst_amount + duty + transport, 2)
            data = (
                request.form['PName'], request.form['AName'],
                request.form['PDescription'], request.form['PImage'],
                aprice, uprice, duty, transport, gst,
                request.form['CID'], pid
            )
            cursor.execute("""
                UPDATE PRODUCT SET PName=%s, AName=%s, PDescription=%s, PImage=%s,
                APrice=%s, UPrice=%s, Duty=%s, Transport=%s, GST=%s, CID=%s WHERE PID=%s
            """, data)
            db.commit()
            flash("Product updated.", "success")
            return redirect('/admin/products')
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
    cursor.execute("SELECT * FROM PRODUCT WHERE PID = %s", (pid,))
    product = cursor.fetchone()
    cursor.execute("SELECT CID, CName FROM COMPANY")
    companies = cursor.fetchall()
    cursor.close()
    return render_template('product_form.html', action='Edit', product=product, companies=companies)

@app.route('/product/delete/<int:pid>')
def delete_product(pid):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM PRODUCT WHERE PID = %s", (pid,))
    db.commit()
    cursor.close()
    flash("Product deleted.", "success")
    return redirect('/admin/products')

@app.route("/complete_order", methods=["POST"])
def complete_order():
    if session.get('role') != 'admin':
        return redirect("/login")

    aid = request.form['aid']
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch order details
    cursor.execute("""
    SELECT A.AID, A.UID, A.PID, A.Quantity, A.OrderDate, A.PaymentMethod, A.UAddress,
           U.UName, U.UContact,
           P.PName, P.UPrice
    FROM ADMIN A
    JOIN USER U ON A.UID = U.UID
    JOIN PRODUCT P ON A.PID = P.PID
    WHERE A.AID = %s
""", (aid,))
    order = cursor.fetchone()

    if not order:
        flash("Order not found.", "danger")
        return redirect("/dashboard")

    # Insert into ORDER_HISTORY
    cursor.execute("""
        INSERT INTO ORDER_HISTORY (HAID, UID, PID, Quantity, OrderDate, Status, PaymentMethod, CompletionTime)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        order['AID'], order['UID'], order['PID'], order['Quantity'],
        order['OrderDate'], "Completed", order['PaymentMethod'],
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ))

    # Remove from current orders
    cursor.execute("DELETE FROM ADMIN WHERE AID = %s", (aid,))
    db.commit()
    cursor.close()

    # Store invoice in session
    session['last_order'] = {
        "OrderID": order['AID'],
        "CustomerName": order['UName'],
        "CustomerAddress": order['UAddress'],
        "CustomerContact": order['UContact'],
        "ProductName": order['PName'],
        "UnitPrice": order['UPrice'],
        "Quantity": order['Quantity'],
        "TotalAmount": round(order['UPrice'] * order['Quantity'], 2),
        "OrderDate": order['OrderDate'],
        "PaymentMethod": order['PaymentMethod'],
        "CompletionTime": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    flash("Order marked as completed. Invoice ready.", "success")
    return redirect("/invoice")

@app.route("/invoice")
def invoice():
    if 'last_order' not in session:
        flash("No invoice to show.", "danger")
        return redirect('/dashboard')

    return render_template("invoice.html", order=session['last_order'], now=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@app.route("/print_invoice", methods=["POST"])
def print_invoice():
    if request.form.get("confirm") == "yes":
        return redirect('/invoice')
    session.pop('last_order', None)
    return redirect('/dashboard')

# ----------------- CART FUNCTIONALITY -----------------
@app.route('/cart/add', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        flash("Please login to add items to cart.", "danger")
        return redirect('/login')

    pid = request.form['product_id']
    uid = session['user_id']

    db = get_db()
    cursor = db.cursor()

    # Check if already in cart
    cursor.execute("SELECT * FROM CART WHERE UID = %s AND PID = %s", (uid, pid))
    existing = cursor.fetchone()
    if existing:
        flash("Product already in cart.", "info")
    else:
        cursor.execute("INSERT INTO CART (UID, PID, Quantity) VALUES (%s, %s, %s)", (uid, pid, 1))
        db.commit()
        flash("Product added to cart.", "success")

    cursor.close()
    return redirect('/dashboard')

@app.route('/cart/checkout_form')
def cart_checkout_form():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('checkout_form.html')  # You must create this file

@app.route('/cart')
def view_cart():
    if 'user_id' not in session:
        return redirect('/login')

    uid = session['user_id']
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT C.CartID, P.PName, P.UPrice, C.Quantity, P.PImage
        FROM CART C
        JOIN PRODUCT P ON C.PID = P.PID
        WHERE C.UID = %s
    """, (uid,))
    cart_items = cursor.fetchall()
    cursor.close()

    return render_template('cart.html', cart=cart_items)

@app.route('/cart/checkout', methods=['POST'])
def checkout_cart():
    if 'user_id' not in session:
        return redirect('/login')

    address = request.form['address']
    payment_method = request.form['payment_method']
    uid = session['user_id']
    order_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT PID, Quantity FROM CART WHERE UID = %s", (uid,))
    items = cursor.fetchall()

    for item in items:
        cursor.execute("""
    INSERT INTO ADMIN (UID, PID, Quantity, OrderDate, Status, PaymentMethod, UAddress)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
""", (uid, item[0], item[1], order_time, "Pending", payment_method, address))


    cursor.execute("DELETE FROM CART WHERE UID = %s", (uid,))
    db.commit()
    cursor.close()

    flash("Checkout successful. Orders placed!", "success")
    return redirect('/my_orders')


# ----------------- MY ORDERS -----------------

@app.route("/my_orders")
def my_orders():
    if 'user_id' not in session or session['role'] != 'user':
        return redirect('/login')

    db = get_db()
    cursor = db.cursor(dictionary=True)
    uid = session['user_id']

    cursor.execute("""
        SELECT P.PName, P.UPrice, A.PaymentMethod, A.OrderTime, A.Status
        FROM ADMIN A
        JOIN PRODUCT P ON A.PID = P.PID
        WHERE A.UID = %s
    """, (uid,))
    pending_orders = cursor.fetchall()

    cursor.execute("""
        SELECT P.PName, P.UPrice, H.PaymentMethod, H.OrderDate AS OrderTime, H.Status
        FROM ORDER_HISTORY H
        JOIN PRODUCT P ON H.PID = P.PID
        WHERE H.UID = %s
    """, (uid,))
    completed_orders = cursor.fetchall()

    all_orders = pending_orders + completed_orders
    all_orders.sort(key=lambda x: x['OrderTime'], reverse=True)
    cursor.close()

    return render_template("my_orders.html", orders=all_orders)

# ----------------- KEEP EXISTING PRODUCT/ADMIN/COMPANY ROUTES -----------------
# Not removed or changed — already working in your last version

# ----------------- RUN APP -----------------
if __name__ == '__main__':
    app.run(debug=True)
