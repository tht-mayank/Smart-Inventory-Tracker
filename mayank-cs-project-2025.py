                                    #Smart Inventory Tracker For Local Businesses

import mysql.connector                    
from datetime import datetime
from calendar import monthrange

            #MySQL connection

def connect_db():
    """Return a new MySQL connection using the credentials you confirmed."""
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="write_password_here",      #use your MySQL Password here
        database="business_db",   #database 'business_db' must already exist on MySQL server
        ssl_disabled=True #Only needed on Ubuntu/Linux systems to prevent SSL connection errors for local MySQL
    )

            #Initialize Tables

def initialize_tables():
    """Create inventory,orders and sales tables if they don't exist"""
    db= connect_db()
    cursor= db.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        item_id INT AUTO_INCREMENT PRIMARY KEY,
        item_name VARCHAR(100),
        price FLOAT,
        cost_price FLOAT,
        stock INT DEFAULT 0
    )
    """)

            #Create orders(order header)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id INT AUTO_INCREMENT PRIMARY KEY,
        order_date DATE,
        total_amount FLOAT
    )
    """)
           #Create sales(order details)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        sale_id INT AUTO_INCREMENT PRIMARY KEY,
        order_id INT,
        item_id INT,
        quantity INT,
        sale_price FLOAT,
        FOREIGN KEY(order_id) REFERENCES orders(order_id),
        FOREIGN KEY(item_id) REFERENCES inventory(item_id)
    )
    """)
    db.commit()
    cursor.close()
    db.close()

           #inventory Management
    
def add_inventory_item():
    db =connect_db()
    cursor= db.cursor()
    item_name= input("Enter item name: ").strip()
    try:
        price =float(input("Enter selling price: "))
        cost =float(input("Enter cost price: "))
        stock= int(input("Enter initial stock quantity: "))
    except ValueError:
        print("Invalid numeric input for price/cost/stock.")
        cursor.close()
        db.close()
        return
    try:
        #Check duplicate name (case-insensitive)
        cursor.execute("SELECT item_id FROM inventory WHERE LOWER(item_name) = LOWER(%s)", (item_name,))
        if cursor.fetchone():
            print("Item with this name already exists.")
        else:
            cursor.execute(
                "INSERT INTO inventory (item_name, price, cost_price, stock) VALUES (%s,%s,%s,%s)",
                (item_name, price, cost, stock)
            )
            db.commit()
            print("Item added successfully.")
    except mysql.connector.Error as err:
        db.rollback()
        print(f"Database error: {err}")
    finally:
        cursor.close()
        db.close()
        
def restock_item():
    """Increase stock quantity for an existing inventory item."""
    db =connect_db()
    cursor= db.cursor()
    cursor.execute("SELECT item_id, item_name, stock FROM inventory ORDER BY item_id")
    items=cursor.fetchall()
    if not items:
        print("No items in inventory to restock. Add items first.")
        cursor.close()
        db.close()
        return

    print("\n--- Current Stock Levels ---")
    for iid, name, stock in items:
        print(f"{iid}. {name:<20} | Current Stock: {stock}")

    try:
        item_id= int(input("\nEnter the Item ID to restock: "))
        cursor.execute("SELECT item_name, stock FROM inventory WHERE item_id = %s",(item_id,))
        item= cursor.fetchone()
        if not item:
            print("Invalid Item ID.")
            cursor.close()
            db.close()
            return

        item_name, current_stock =item
        qty= int(input(f"Enter quantity to add to {item_name} (current stock {current_stock}): "))
        if qty <=0:
            print("Quantity must be positive.")
            cursor.close()
            db.close()
            return

        cursor.execute("UPDATE inventory SET stock = stock + %s WHERE item_id = %s",(qty, item_id))
        db.commit()
        print(f"Stock for '{item_name}' updated successfully. New stock: {current_stock + qty}")
    except ValueError:
        print("Invalid input. Please enter numeric values.")
    except mysql.connector.Error as err:
        db.rollback()
        print(f"Database error: {err}")
    finally:
        cursor.close()
        db.close()

def view_inventory():
    """Print Inventory and return a mapping {item_id: (item_name, price, cost_price)}"""
    db=connect_db()
    cursor=db.cursor()
    cursor.execute("SELECT item_id, item_name, price, cost_price, stock FROM inventory ORDER BY item_id")
    items = cursor.fetchall()
    print("\n--- Inventory ---")
    if not items:
        print("Inventory is empty. Add items first.")
        cursor.close()
        db.close()
        return None
    inventory_map ={}
    for item in items:
        iid,name,price,cost,stock =item
        print(f"{iid}. {name:<20} - ₹{price:.2f} | Stock: {stock}")
        inventory_map[iid]= (name,float(price),float(cost),int(stock))
    cursor.close()
    db.close()
    return inventory_map

                   #Place Order
def place_order():
    inventory=view_inventory()
    if not inventory:
        return
    db=connect_db()
    cursor=db.cursor()
    order_items=[]
    order_total=0.0
    print("\nEnter order details (Enter 'done' when finished):")
    while True:
        try:
            item_id_input=input("Enter item ID to order (or 'done'): ").strip()
            if item_id_input.lower() =='done':
                break
            item_id= int(item_id_input)
            if item_id not in inventory:
                print("Invalid item ID. Please choose from the inventory.")
                continue
            item_name, item_price, item_cost, item_stock = inventory[item_id]
            quantity = int(input(f"Enter quantity for {item_name} (₹{item_price:.2f} each): "))
            if quantity<= 0:
                print("Quantity must be a positive number.")
                continue
            if quantity >item_stock:
                print(f"Not enough stock for {item_name}. Only {item_stock} left.")
                continue
            order_items.append((item_id, quantity, item_price))
            order_total += quantity * item_price
            print(f"Added {quantity} x {item_name}. Current total: ₹{order_total:.2f}")
        except ValueError:
            print("Invalid input. Please enter numbers for ID and quantity.")
        except Exception as e:
            print(f"An error occurred: {e}")
            break

    if not order_items:
        print("No items added to the order.")
        cursor.close()
        db.close()
        return

    today=datetime.now().date()
    try:
        #Insert order header
        cursor.execute("INSERT INTO orders (order_date, total_amount) VALUES (%s, %s)", (today, order_total))
        #Get order id of the last inserted row. Using SELECT MAX(order_id)
        cursor.execute("SELECT MAX(order_id) FROM orders")
        order_id =cursor.fetchone()[0]

        #Insert each sale row explicitly
        insert_sales_query= "INSERT INTO sales (order_id, item_id, quantity, sale_price) VALUES (%s, %s, %s, %s)"
        for item_id, quantity, price in order_items:
            cursor.execute(insert_sales_query, (order_id, item_id, quantity, price))
                    # Reduce stock for each item sold
        for item_id, quantity, price in order_items:
            cursor.execute("UPDATE inventory SET stock = stock - %s WHERE item_id = %s", (quantity, item_id))
        db.commit()
        print(f"\nOrder #{order_id} placed successfully! Total: ₹{order_total:.2f}")
    except mysql.connector.Error as err:
        db.rollback()
        print(f"Database error: {err}")
    finally:
        cursor.close()
        db.close()

                        #Reporting/Profit Calculation
        
def calculate_sales_profit(period_type='day',period_value=None):
    
    """
    Uses SQL JOINs and aggregation to compute:
      - qty sold per item
      - total sales (revenue) per item
      - profit per item (using cost_price from inventory)
    period_type: 'day' | 'month' | 'year'
    period_value: date object (for day), date object (first of month) for month, date object (year) for year
    """
    
    db =connect_db()
    cursor=db.cursor()
    base_query= """
    SELECT
        m.item_name,
        SUM(s.quantity) AS qty,
        SUM(s.quantity * s.sale_price) AS revenue,
        SUM(s.quantity * (s.sale_price - m.cost_price)) AS profit
    FROM sales s
    JOIN inventory m ON s.item_id = m.item_id
    JOIN orders o ON s.order_id = o.order_id
    """
    try:
        if period_type =='day':
            query =base_query + " WHERE o.order_date = %s GROUP BY m.item_id"
            cursor.execute(query, (period_value,))
        elif period_type =='month':
            query=base_query + " WHERE MONTH(o.order_date) = %s AND YEAR(o.order_date) = %s GROUP BY m.item_id"
            cursor.execute(query, (period_value.month, period_value.year))
        elif period_type =='year':
            query = base_query +" WHERE YEAR(o.order_date) = %s GROUP BY m.item_id"
            cursor.execute(query,(period_value.year,))
        else:
            print("Invalid period type.")
            cursor.close()
            db.close()
            return

        rows =cursor.fetchall()
        print("\nItem | Qty Sold | Sales ₹ | Profit ₹")
        total_sales =total_profit =0.0
        for r in rows:
            name =r[0]
            qty =int(r[1] or 0)
            rev =float(r[2] or 0.0)
            prof =float(r[3] or 0.0)
            print(f"{name:<15} | {qty:<8} | {rev:<8.2f} | {prof:<8.2f}")
            total_sales += rev
            total_profit += prof
        print("-" * 40)
        print(f"TOTAL SALES: ₹{total_sales:.2f}")
        print(f"TOTAL PROFIT: ₹{total_profit:.2f}")
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
    finally:
        cursor.close()
        db.close()

                 #Helper: Top selling items
        
def get_top_selling_items(period_type, period_value, db_cursor):
    base_query = """
    SELECT
        m.item_name,
        SUM(s.quantity) AS total_quantity
    FROM sales s
    JOIN inventory m ON s.item_id = m.item_id
    JOIN orders o ON s.order_id = o.order_id
    """
    try:
        if period_type=='day':
            query =base_query +"WHERE o.order_date = %s GROUP BY m.item_id ORDER BY total_quantity DESC LIMIT 3"
            db_cursor.execute(query,(period_value,))
        elif period_type =='month':
            query = base_query +" WHERE MONTH(o.order_date) = %s AND YEAR(o.order_date) = %s GROUP BY m.item_id ORDER BY total_quantity DESC LIMIT 3"
            db_cursor.execute(query,(period_value.month, period_value.year))
        elif period_type =='year':
            query = base_query + "WHERE YEAR(o.order_date) = %s GROUP BY m.item_id ORDER BY total_quantity DESC LIMIT 3"
            db_cursor.execute(query, (period_value.year,))
        else:
            return []
        return db_cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return []

                      #View Order History & Analysis
    
def view_order_history():
    print("\n--- Order History & Analysis ---")
    period_type =input("View history for 'day','month',or 'year'? ").lower()
    period_value =None
    date_str =""

    if period_type =='day':
        date_str = input("Enter date (YYYY-MM-DD): ")
        try:
            period_value =datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            print("Invalid date format.Use YYYY-MM-DD.")
            return
    elif period_type =='month':
        date_str = input("Enter month (YYYY-MM): ")
        try:
            period_value = datetime.strptime(date_str,'%Y-%m').date()
        except ValueError:
            print("Invalid month format.Use YYYY-MM.")
            return
    elif period_type =='year':
        date_str =input("Enter year (YYYY): ")
        try:
            period_value = datetime.strptime(date_str,'%Y').date()
        except ValueError:
            print("Invalid year format.Use YYYY.")
            return
    else:
        print("Invalid period type.")
        return

    db =connect_db()
    cursor =db.cursor()

    # Fetch total sales and total profit for the period
    profit_query ="""
    SELECT
        SUM(s.quantity * s.sale_price) AS total_sales,
        SUM(s.quantity * (s.sale_price - m.cost_price)) AS total_profit
    FROM sales s
    JOIN inventory m ON s.item_id = m.item_id
    JOIN orders o ON s.order_id = o.order_id
    """
    try:
        if period_type =='day':
            where_clause="WHERE o.order_date = %s"
            params =(period_value,)
        elif period_type=='month':
            where_clause ="WHERE MONTH(o.order_date) = %s AND YEAR(o.order_date) = %s"
            params =(period_value.month, period_value.year)
        else:  #year
            where_clause ="WHERE YEAR(o.order_date) = %s"
            params =(period_value.year,)
        cursor.execute(profit_query + where_clause, params)
        sales_data= cursor.fetchone()
        total_sales= sales_data[0] if sales_data and sales_data[0] is not None else 0.0
        total_profit =sales_data[1] if sales_data and sales_data[1] is not None else 0.0

        #Top 3 selling
        top_items =get_top_selling_items(period_type, period_value, cursor)

        #Header
        print("\n" + "=" * 50)
        print(f"--- Analysis for {period_type.upper()} ({date_str}) ---")
        print(f"TOTAL REVENUE: ₹{total_sales:.2f}")
        print(f"**TOTAL NET PROFIT: ₹{total_profit:.2f}**")
        print("=" * 50)

        #Top items
        print("\n--- Top 3 Selling Items (by Quantity) ---")
        if top_items:
            for i, (item_name, quantity) in enumerate(top_items):
                print(f"{i+1}. {item_name} (Sold: {quantity})")
        else:
            print("No sales data available for this period.")
        print("-" * 50)

        #Detailed order breakdown
        base_query_details = """
        SELECT
            o.order_id,
            o.order_date,
            m.item_name,
            s.quantity,
            s.sale_price,
            (s.quantity * s.sale_price) AS line_total,
            o.total_amount
        FROM orders o
        JOIN sales s ON o.order_id = s.order_id
        JOIN inventory m ON s.item_id = m.item_id
        """
        query_details= base_query_details + where_clause + " ORDER BY o.order_id, o.order_date"
        cursor.execute(query_details, params)
        rows =cursor.fetchall()

        print("\n--- Detailed Order Breakdown ---")
        if not rows:
            cursor.close()
            db.close()
            return
        current_order_id= -1
        prev_order_total =0.0
        for row in rows:
            order_id, order_date, item_name,quantity, sale_price, line_total, total_from_order_table =row
            if order_id !=current_order_id:
                if current_order_id != -1:
                    print("-" * 40)
                    print(f"| {'':<50} | **Order Total:** | **₹{prev_order_total:.2f}** |")
                    print("=" * 80)
                print(f"\nOrder ID: {order_id} | Date: {order_date}")
                print("Item Name | Qty | Price/Item | Line Total")
                current_order_id =order_id
                prev_order_total= total_from_order_table
            print(f"{item_name:<18} | {quantity:<3} | ₹{sale_price:<9.2f} | ₹{line_total:<10.2f}")

        #Print last order total
        if current_order_id != -1:
            print("-" * 40)
            print(f"| {'':<50} | **Order Total:** | **₹{prev_order_total:.2f}** |")
        print("=" * 80)

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
    finally:
        cursor.close()
        db.close()

             #Export Report (writes a plain text CSV-format file WITHOUT using csv module)
def export_report_csv(period_type='day', date_value=None):
    """
    Exports query result rows into a file smart_report_{period_type}_{date}.csv
    Does not import/use the csv module - uses plain file writing to avoid CSV library.
    """
    db= connect_db()
    cursor= db.cursor()
    base_query = """
    SELECT
        o.order_id,
        o.order_date,
        m.item_name,
        s.quantity,
        s.sale_price,
        m.cost_price,
        (s.sale_price - m.cost_price) AS profit_per_item,
        (s.quantity * s.sale_price) AS revenue
    FROM orders o
    JOIN sales s ON o.order_id = s.order_id
    JOIN inventory m ON s.item_id = m.item_id
    """
    try:
        if period_type =='day':
            where_clause = "WHERE o.order_date = %s"
            params = (date_value,)
            filename_date_part = date_value.strftime('%Y-%m-%d')
        elif period_type =='month':
            where_clause = " WHERE MONTH(o.order_date) = %s AND YEAR(o.order_date) = %s"
            params = (date_value.month, date_value.year)
            filename_date_part = date_value.strftime('%Y_%m')
        elif period_type =='year':
            where_clause ="WHERE YEAR(o.order_date) = %s"
            params=(date_value.year,)
            filename_date_part = date_value.strftime('%Y')
        else:
            print("Invalid period type for export.")
            cursor.close()
            db.close()
            return

        query =base_query + where_clause + " ORDER BY o.order_id, o.order_date"
        cursor.execute(query, params)
        rows =cursor.fetchall()

        filename = f"smart_report_{period_type}_{filename_date_part}.csv"
        #Write file manually without csv module (comma-separated values)
        with open(filename, mode='w', encoding='utf-8', newline='') as f:
            header ="Order ID,Sale Date,Item Name,Quantity,Selling Price (per item),Cost Price (per item),Profit per Item,Line Revenue\n"
            f.write(header)
            for r in rows:
                order_id =r[0]
                order_date =r[1].isoformat() if isinstance(r[1], datetime) or hasattr(r[1], "isoformat") else str(r[1])
                item_name= str(r[2])
                qty= int(r[3])
                sale_price =float(r[4])
                cost_price=float(r[5])
                profit_per_item= float(r[6]) if r[6] is not None else sale_price - cost_price
                revenue = float(r[7])
                #Escape commas in item_name by wrapping in double quotes if necessary
                if ',' in item_name or '"' in item_name:
                    safe_name= '"' + item_name.replace('"', '""') + '"'
                else:
                    safe_name =item_name
                line= f"{order_id},{order_date},{safe_name},{qty},{sale_price:.2f},{cost_price:.2f},{profit_per_item:.2f},{revenue:.2f}\n"
                f.write(line)
        print(f"CSV report saved as {filename}")
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
    finally:
        cursor.close()
        db.close()
        
def predictive_restock():
    
    """
    Analyzes past 7 days' sales and predicts which items are likely to need restocking soon.
    Uses actual stock levels from menu table.
    """
    
    db=connect_db()
    cursor=db.cursor()

    print("\n--- Predictive Restock Analysis ---")

    try:
        # Fetch average daily sales in the last 7 days
        query ="""
        SELECT 
            m.item_name,
            m.stock,
            SUM(s.quantity)/7 AS avg_daily_sales
        FROM sales s
        JOIN inventory m ON s.item_id = m.item_id
        JOIN orders o ON s.order_id = o.order_id
        WHERE o.order_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        GROUP BY m.item_id
        """
        cursor.execute(query)
        rows=cursor.fetchall()

        if not rows:
            print("No recent sales data available for prediction.")
            cursor.close()
            db.close()
            return

        print(f"\n{'Item Name':<20} | {'Stock':<6} | {'Avg Daily Sales':<15} | {'Predicted Days Left':<18} | Status")
        print("-" * 80)
        for item_name, stock, avg_sales in rows:
            avg_sales =avg_sales or 0
            if avg_sales == 0:
                days_left= "∞"
                status= "Stable"
            else:
                days_left= stock/avg_sales
                status ="Low" if days_left < 5 else "OK"
            print(f"{item_name:<20} | {stock:<6} | {avg_sales:<15.2f} | {days_left:<18} | {status}")
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
    finally:
        cursor.close()
        db.close()

# ---------- Predictive Restock Analysis ----------

def predictive_restock():
    
    """
    Analyzes past 7 days' sales and predicts which items are likely to need restocking soon.
    Uses a simple moving average model to estimate demand.
    """
    
    db =connect_db()
    cursor =db.cursor()

    print("\n--- Predictive Restock Analysis ---")

    try:
        # Fetch average quantity sold per day for each item in the last 7 days
        query = """
        SELECT 
            m.item_name,
            SUM(s.quantity) / 7 AS avg_daily_sales
        FROM sales s
        JOIN inventory m ON s.item_id = m.item_id
        JOIN orders o ON s.order_id = o.order_id
        WHERE o.order_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        GROUP BY m.item_id
        """
        cursor.execute(query)
        rows =cursor.fetchall()

        if not rows:
            print("Not enough recent data for prediction (no sales in last 7 days).")
            cursor.close()
            db.close()
            return

        # Assume each item currently has a default stock of 50 units (virtual assumption)
        assumed_stock = 50
        print(f"\n{'Item Name':<20} | {'Avg Daily Sales':<15} | {'Predicted Days Left':<18} | Status")
        print("-" * 70)
        for item_name, avg_sales in rows:
            if avg_sales == 0:
                days_left = "∞"
                status = "Stable"
            else:
                days_left = assumed_stock / avg_sales
                status = "Low" if days_left < 5 else "OK"
            print(f"{item_name:<20} | {avg_sales:<15.2f} | {days_left:<18} | {status}")

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
    finally:
        cursor.close()
        db.close()

                #End of period helpers
        
def end_day():
    today= datetime.now().date()
    print("\n--- Day Report till now ---")
    calculate_sales_profit('day',today)
    
def end_month():
    today = datetime.now()
    #Use first day of current month as representative month value
    first_of_month = datetime(today.year,today.month, 1).date()
    print("\n--- Month Report till now ---")
    calculate_sales_profit('month',first_of_month)

def end_year():
    today= datetime.now()
    first_of_year=datetime(today.year,1,1).date()
    print("\n--- End of Year Report ---")
    calculate_sales_profit('year',first_of_year)
    
                    #Main UI
    
def main():
    initialize_tables()
    while True:
        print("\n=== Smart Inventory Tracker ===")
        print("1. Add inventory Item")
        print("2. View inventory")
        print("3. Place Order (Multi-Item)")
        print("4. View Order History / Details")
        print("5. Predictive Restock Analysis")
        print("6. Restock Item (Add Stock)")
        print("-" * 25)
        print("7. Daily Sales & Profit Report")
        print("8. Monthly Sales & Profit Report")
        print("9. Yearly Sales & Profit Report")
        print("10. Exit")

        choice = input("\nEnter your choice (1–10): ").strip()

        if choice == '1':
            add_inventory_item()
        elif choice == '2':
            view_inventory()
        elif choice == '3':
            place_order()
        elif choice == '4':
            view_order_history()
        elif choice == '5':
            predictive_restock()
        elif choice == '6':
            restock_item()
        elif choice == '7':
            today = datetime.now().date()
            export_report_csv('day', today)
        elif choice == '8':
            today = datetime.now().date()
            export_report_csv('month', today)
        elif choice == '9':
            today = datetime.now().date()
            export_report_csv('year',today)
        elif choice == '10':
            print("\nExiting Smart Inventory Tracker... Have a great day!")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 10.")

if __name__ =="__main__":
    main()

#Author: Mayank M Gautam | Created for CBSE Class 12 Project (2025)
