from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os

print(os.path.abspath("expenses.db"))
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

app.secret_key = "supersecretkey"

from flask import jsonify
import sqlite3

@app.route("/expenses")
def get_expenses():
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("SELECT amount, category FROM expenses")
    rows = cursor.fetchall()

    conn.close()

    data = []
    for row in rows:
        data.append({
            "amount": row[0],
            "category": row[1]
        })

    return jsonify(data)
# Create database and table
def init_db():
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Expenses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            user_id INTEGER,
            recurring INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Budget table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budget (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL
        )
    """)

    cursor.execute("""
        INSERT INTO budget (amount)
        SELECT 5000
        WHERE NOT EXISTS (SELECT 1 FROM budget)
    """)

    conn.commit()
    conn.close()


# Initialize database
init_db()


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        conn = sqlite3.connect("expenses.db")
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password)
            )
            conn.commit()
        except sqlite3.IntegrityError:
           return "Username already exists"

        conn.close()
        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        print("Entered:", username, password)
        conn = sqlite3.connect("expenses.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        print("User from DB:", user)
        conn.close()

        if user and check_password_hash(user[2], password):
            print("Stored password:", user[2])
            session["user_id"] = user[0]
            return redirect("/")
        else:
            return "Invalid credentials"

    return render_template("login.html")
 
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect("/login")

@app.route("/set_budget", methods=["POST"])
def set_budget():
    if "user_id" not in session:
        return redirect("/login")

    new_budget = request.form["budget"]

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    # Check if budget already exists
    cursor.execute("SELECT * FROM budget")
    existing = cursor.fetchone()

    if existing:
        cursor.execute("UPDATE budget SET amount=?", (new_budget,))
    else:
        cursor.execute("INSERT INTO budget (amount) VALUES (?)", (new_budget,))

    conn.commit()
    conn.close()

    return redirect("/")

@app.route("/", methods=["GET", "POST"])
def home():
    if "user_id" not in session:
        return redirect("/login")
    category_filter = request.args.get("category")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    if request.method == "POST":
        title = request.form["title"]
        amount = request.form["amount"]
        category = request.form["category"]
        date = request.form["date"]
        print("RAW FORM:", request.form)
        recurring = 1 if request.form.get("recurring") else 0
        print("Recurring value:", recurring)

        cursor.execute(
    "INSERT INTO expenses (title, amount, category, date, user_id, recurring) VALUES (?, ?, ?, ?, ?, ?)",
    (title, amount, category, date, session["user_id"], recurring)
)
        conn.commit()
        return redirect("/")
        
    def add_monthly_recurring_expenses(user_id):
      import datetime
      today = datetime.date.today()
      current_month = today.strftime("%Y-%m")

      cursor.execute("""
      SELECT title, amount, category, date, user_id
      FROM expenses
      WHERE recurring = 1 AND user_id=?
      """, (session["user_id"],))

       # Get all recurring expenses
      recurring_expenses = cursor.fetchall()

       # Prepare date info
      new_date = today.strftime("%Y-%m-%d")
      current_month = today.strftime("%Y-%m")

      # Fetch all expenses for this month for all users at once
      cursor.execute("""
       SELECT title, user_id FROM expenses
       WHERE strftime('%Y-%m', date)=?
       """, (current_month,))
      existing_expenses = set(cursor.fetchall())  # set of (title, user_id) tuples

# Loop through recurring expenses and insert only if not present
      for exp in recurring_expenses:
       title, amount, category, old_date, user_id = exp

       if (title, user_id) not in existing_expenses:
          cursor.execute("""
            INSERT INTO expenses (title, amount, category, date, user_id, recurring)
            VALUES (?, ?, ?, ?, ?, 1)
          """, (title, amount, category, new_date, user_id))
          existing_expenses.add((title, user_id))  # update set to avoid duplicates

    conn.commit()
    conn.commit()

    query = "SELECT id, title, amount, category, date, recurring FROM expenses WHERE user_id=?"
    params = [session["user_id"]]

    if category_filter:
     query += " AND category = ?"
     params.append(category_filter)

    if start_date:
     query += " AND date >= ?"
     params.append(start_date)

    if end_date:
     query += " AND date <= ?"
     params.append(end_date)

    cursor.execute(query, params)
    expenses = cursor.fetchall()

    query = """
    SELECT category, SUM(amount)
    FROM expenses
    WHERE user_id = ?
"""
    params = [session["user_id"]]
    if category_filter:
     query += " AND category = ?"
     params.append(category_filter)

    if start_date:
     query += " AND date >= ?"
     params.append(start_date)

    if end_date:
     query += " AND date <= ?"
     params.append(end_date)

    query += " GROUP BY category"

    cursor.execute(query, params)
    category_data = cursor.fetchall()

    categories = [row[0] for row in category_data]
    amounts = [float(row[1]) for row in category_data if row[1] is not None]

    cursor.execute("""
    SELECT date, SUM(amount) as total
    FROM expenses
    WHERE user_id=?
    GROUP BY date
    ORDER BY total DESC
    LIMIT 1
""", (session["user_id"],))

    result = cursor.fetchone()

    if result:
      highest_day = result[0]
      highest_amount = result[1]
    else:
     highest_day = None
     highest_amount = 0

     cursor.execute("""
    SELECT category, SUM(amount) as total
    FROM expenses
    WHERE user_id=?
    GROUP BY category
    ORDER BY total DESC
    LIMIT 1
""", (session["user_id"],))

    result = cursor.fetchone()
 
    if result:
     top_category = result[0]
     top_category_amount = result[1]
    else:
     top_category = None
     top_category_amount = 0

  
    cursor.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id=?",
        (session["user_id"],)
    )
    total_spent = cursor.fetchone()[0] or 0

   
    cursor.execute("""
        SELECT SUM(amount) FROM expenses
        WHERE user_id=? AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
    """, (session["user_id"],))
    monthly_spent = cursor.fetchone()[0] or 0

    cursor.execute("SELECT amount FROM budget LIMIT 1")
    result = cursor.fetchone()
    budget = result[0] if result else 0

    overspent = monthly_spent > budget

    cursor.execute("""
    SELECT date, SUM(amount)
    FROM expenses
    WHERE user_id=? 
    AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
    GROUP BY date
    ORDER BY date
""", (session["user_id"],))
    monthly_data = cursor.fetchall()

    months = [row[0] for row in monthly_data]
    monthly_totals = [float(row[1]) for row in monthly_data if row[1] is not None]
 
    return render_template(
        "index.html",
        expenses=expenses,
        total_spent=total_spent,
        monthly_spent=monthly_spent,
        budget=budget,
        overspent=overspent,
        categories=categories,
        amounts=amounts,
        months=months,
        monthly_totals=monthly_totals,
        highest_day=highest_day,
        highest_amount=highest_amount,
        top_category=top_category,
        top_category_amount=top_category_amount
    )
    


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_expense(id):
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    if request.method == "POST":
        title = request.form["title"]
        amount = request.form["amount"]
        category = request.form["category"]
        date = request.form["date"]

        # ✅ UPDATE instead of INSERT
        cursor.execute("""
            UPDATE expenses
            SET title=?, amount=?, category=?, date=?
            WHERE id=? AND user_id=?
        """, (title, amount, category, date, id, session["user_id"]))

        conn.commit()
        conn.close()
        return redirect("/")

    # GET request: show the edit form
    cursor.execute("SELECT * FROM expenses WHERE id=? AND user_id=?", (id, session["user_id"]))
    expense = cursor.fetchone()
    conn.close()

    return render_template("edit.html", expense=expense)

    return render_template("edit.html", expense=expense)


@app.route("/delete/<int:id>", methods=["POST"])
def delete_expense(id):
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute(
    "DELETE FROM expenses WHERE id=? AND user_id=?",
    (id, session["user_id"])
)
    conn.commit()
    conn.close()
    return redirect("/")

from flask import Response
import csv
@app.route("/export")
def export():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT title, amount, category, date
        FROM expenses
        WHERE user_id=?
    """, (session["user_id"],))

    data = cursor.fetchall()
    conn.close()

    def generate():
        yield "Title,Amount,Category,Date\n"
        for row in data:
            yield f"{row[0]},{row[1]},{row[2]},{row[3]}\n"

    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=expenses.csv"})


if __name__ == "__main__":
    app.run(debug=True)