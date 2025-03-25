from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, flash, session
from flask_mail import Mail, Message
import sqlite3
from flask_socketio import SocketIO
from datetime import datetime
import pika
import threading
import ssl
import os
import cv2
import json


# Flask app setup
app = Flask(__name__, template_folder='../../', static_folder='../../assets')
app.config['UPLOAD_FOLDER'] = '../../assets/uploads/'  # Directory to store uploaded images
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
app.secret_key = '950007397@@$!&itl&^*^' # Required for session management
socketio = SocketIO(app)

VIDEO_PATH = os.path.join(os.path.dirname(__file__), '../Model/video.mp4')

# Flask-Mail Configuration (Replace with your details)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'itlcontact0101@gmail.com'  # Admin's email (sender)
app.config['MAIL_PASSWORD'] = 'olzs qgki gqbw mgqr'  # Use app password for security
app.config['MAIL_DEFAULT_SENDER'] = 'info@iyarkaitechlab.com'

mail = Mail(app)

# Database setup

conn = sqlite3.connect("databases.db")
cursor = conn.cursor()

cursor.execute("""
            CREATE TABLE IF NOT EXISTS adminusers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user' )
             """)

cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user')
             """)

cursor.execute("""
            CREATE TABLE IF NOT EXISTS mushroomusers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user')
             """)

cursor.execute("""
            CREATE TABLE IF NOT EXISTS poultryusers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user')
             """)

cursor.execute("""
    CREATE TABLE IF NOT EXISTS banana_user_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullname TEXT NOT NULL,
        about TEXT NOT NULL,
        company TEXT NOT NULL,
        job TEXT NOT NULL,
        country TEXT NOT NULL,
        address TEXT NOT NULL,
        phone INT,
        email TEXT NOT NULL UNIQUE,
        twitter_profile TEXT NOT NULL,
        facebook_profile TEXT NOT NULL,
        instagram_profile TEXT NOT NULL,
        linkedin_profile TEXT NOT NULL,
        profile_image TEXT,
        role TEXT NOT NULL DEFAULT 'user'
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS mushroom_user_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullname TEXT NOT NULL,
        about TEXT NOT NULL,
        company TEXT NOT NULL,
        job TEXT NOT NULL,
        country TEXT NOT NULL,
        address TEXT NOT NULL,
        phone INT,
        email TEXT NOT NULL UNIQUE,
        twitter_profile TEXT NOT NULL,
        facebook_profile TEXT NOT NULL,
        instagram_profile TEXT NOT NULL,
        linkedin_profile TEXT NOT NULL,
        profile_image TEXT,
        role TEXT NOT NULL DEFAULT 'user'
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS poultry_user_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullname TEXT NOT NULL,
        about TEXT NOT NULL,
        company TEXT NOT NULL,
        job TEXT NOT NULL,
        country TEXT NOT NULL,
        address TEXT NOT NULL,
        phone INT,
        email TEXT NOT NULL UNIQUE,
        twitter_profile TEXT NOT NULL,
        facebook_profile TEXT NOT NULL,
        instagram_profile TEXT NOT NULL,
        linkedin_profile TEXT NOT NULL,
        profile_image TEXT,
        role TEXT NOT NULL DEFAULT 'user'
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullname TEXT NOT NULL,
        about TEXT NOT NULL,
        company TEXT NOT NULL,
        job TEXT NOT NULL,
        country TEXT NOT NULL,
        address TEXT NOT NULL,
        phone INT,
        email TEXT NOT NULL UNIQUE,
        twitter_profile TEXT NOT NULL,
        facebook_profile TEXT NOT NULL,
        instagram_profile TEXT NOT NULL,
        linkedin_profile TEXT NOT NULL,
        profile_image TEXT,
        role TEXT )
""")

conn.commit()
conn.close() 

# Define databases for different products
DATABASES = {
    "BananaQueue": "product1_banana_data.db",
    "MushroomQueue": "product2_mushroom_data.db",
    "PoultryQueue": "product3_poultry_data.db"
}

# Initialize separate databases manually
def init_db():
    for db_name in DATABASES.values():
        connection = sqlite3.connect(db_name)
        cursor = connection.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            id TEXT NOT NULL,
            temperature REAL,
            humidity REAL,
            th REAL,
            timestamp TEXT NOT NULL,
            PRIMARY KEY (id, timestamp)
        )
        ''')
        connection.commit()
        connection.close()

# Save data to the respective database
def save_to_database(data, db_name):
    connection = sqlite3.connect(db_name)
    cursor = connection.cursor()

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
        INSERT INTO sensor_data (id, temperature, humidity, th, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (data['ID'], data['TEMP'], data['HUM'], data['TH'], timestamp))

    connection.commit()
    connection.close()

# Process messages and store in the correct database
def process_message(body, db_name):
    try:
        message = json.loads(body)
        required_keys = {'TEMP', 'HUM', 'TH', 'ID'}

        if not all(key in message for key in required_keys):
            missing_keys = required_keys - message.keys()
            print(f"Incomplete data in message: {message}, missing keys: {missing_keys}")
            return

        data = {
            'ID': message['ID'],
            'TEMP': float(message['TEMP']),
            'HUM': float(message['HUM']),
            'TH': float(message['TH']),
        }

        save_to_database(data, db_name)

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error decoding or processing message: {body}, error: {e}")

# RabbitMQ Consumer function for a specific queue
def consume_queue(queue_name, db_name):
    cloudamqp_url = 'amqps://uhbvmhoj:u76Em_OYzjlBXtV3Zw0K4MeGEI4XHEFu@hawk.rmq.cloudamqp.com/uhbvmhoj'
    params = pika.URLParameters(cloudamqp_url)

    try:
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)

        def callback(ch, method, properties, body):
            print(f"Received message from {queue_name}: {body}")
            process_message(body, db_name)

        print(f"Listening on queue: {queue_name} for {db_name}")
        channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
        channel.start_consuming()

    except pika.exceptions.AMQPConnectionError as e:
        print(f"RabbitMQ connection error for {queue_name}: {e}")
    except Exception as e:
        print(f"Error in queue {queue_name}: {e}")

# Start multiple consumers in separate threads
def main():
    # Manually initialize all databases
    init_db()

    # Start a thread for each queue
    for queue_name, db_name in DATABASES.items():
        thread = threading.Thread(target=consume_queue, args=(queue_name, db_name), daemon=True)
        thread.start()

# Call main() here to start RabbitMQ consumers
main()

# Function to generate video frames
def gen():
    if not os.path.exists(VIDEO_PATH):
        raise FileNotFoundError(f"Video file not found at {VIDEO_PATH}")

    cap = cv2.VideoCapture(VIDEO_PATH)
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    finally:
        cap.release()
        print("Video capture released.")
        
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Flask routes
# Registration route
@app.route('/')
def home():
    return render_template('alldevice.html')

@app.route('/mushroomlogin')
def mushroomhome():
    return render_template('mushroom-login.html')

@app.route('/poultrylogin')
def poultryhome():
    return render_template('poultry-login.html')

@app.route('/bananalogin')
def bananahome():
    return render_template('login.html')

@app.route('/adminhome')
def adminhome():
    return render_template('admin-login.html')

@app.route('/adminregister', methods=['GET', 'POST'])
def adminregister():
    if request.method == 'POST':
        try:
            fullname = request.form['fullname']
            email = request.form['email']
            username = request.form['username']
            password = request.form['password']
            role = 'user'
            conn = sqlite3.connect("databases.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO adminusers (fullname, email, username, password, role) VALUES (?, ?, ?, ?, ?)",
                               (fullname, email, username, password, role))
            conn.commit()
            flash("Registration successful. Please log in.", "success")
            
        except sqlite3.IntegrityError:
            flash("Username or email already exists. Please try again.", "danger")

            
        finally:
            conn.close() 
            return redirect(url_for('adminlogin'))   
    return render_template('admin-register.html')

# Login route

@app.route('/adminlogin', methods=['GET', 'POST'])
def adminlogin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect("databases.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM adminusers WHERE username = ? AND password = ?", (username, password)
        )
        data = cursor.fetchone()
        conn.close()

        if data:
            session['username'] = data["username"]
            session['role'] = data["role"]  # Store role in session

            if data["role"] == 'admin':
                '''flash("Login successful as admin.", "success")'''
                return redirect(url_for('admin_dashboard'))
            else:
                flash("You are logged in as a user. Admin access required.", "danger")
                return redirect(url_for('adminlogin'))  # Replace this with a user-specific route if available
        else:
            flash("Invalid username or password", "danger")

    return render_template('admin-login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            fullname = request.form['fullname']
            email = request.form['email']
            username = request.form['username']
            password = request.form['password']
            role = 'user'
            conn = sqlite3.connect("databases.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (fullname, email, username, password, role) VALUES (?, ?, ?, ?, ?)",
                               (fullname, email, username, password, role))
            conn.commit()
            flash("Registration successful. Please log in.", "success")
            
        except sqlite3.IntegrityError:
            flash("Username or email already exists. Please try again.", "danger")

            
        finally:
            conn.close()
            return redirect(url_for('bananahome'))    
            
    return render_template('register.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect("databases.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?", (username, password)
        )
        data = cursor.fetchone()
        conn.close()

        if data:
            session['username'] = data["username"]
            session['role'] = data["role"]  # Store role in session
            '''flash("Login successful.", "success")'''

            # Redirect based on role
            if data["role"] == 'users':
                '''flash("Login successful as user.", "success")'''
                return redirect(url_for('user_dashboard'))
            else:
                flash("You are not logged in as a user. Admin access required.", "danger")
                return redirect(url_for('login'))  # Replace this with a user-specific route if available
        else:
            flash("Invalid username or password", "danger")

    return render_template('login.html')

# mushroom login and registration

@app.route('/mushroomregister', methods=['GET', 'POST'])
def mushroomregister():
    if request.method == 'POST':
        try:
            fullname = request.form['fullname']
            email = request.form['email']
            username = request.form['username']
            password = request.form['password']
            role = 'user'
            conn = sqlite3.connect("databases.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO mushroomusers (fullname, email, username, password, role) VALUES (?, ?, ?, ?, ?)",
                               (fullname, email, username, password, role))
            conn.commit()
            flash("Registration successful. Please log in.", "success")
            
        except sqlite3.IntegrityError:
            flash("Username or email already exists. Please try again.", "danger")

            
        finally:
            conn.close()
            return redirect(url_for('mushroomhome'))    
            
    return render_template('mushroom-register.html')

# Login route
@app.route('/mushroomlogin', methods=['GET', 'POST'])
def mushroomlogin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect("databases.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM mushroomusers WHERE username = ? AND password = ?", (username, password)
        )
        data = cursor.fetchone()
        conn.close()

        if data:
            session['username'] = data["username"]
            session['role'] = data["role"]  # Store role in session
            '''flash("Login successful.", "success")'''

            if data["role"] == 'users':
                '''flash("Login successful as user.", "success")'''
                return redirect(url_for('mushroom_user_dashboard'))
            else:
                flash("You are not logged in as a user. Admin access required.", "danger")
                return redirect(url_for('mushroomlogin'))  # Replace this with a user-specific route if available
        else:
            flash("Invalid username or password", "danger")

    return render_template('mushroom-login.html')

# poultry login and registration

@app.route('/poultryregister', methods=['GET', 'POST'])
def poultryregister():
    if request.method == 'POST':
        try:
            fullname = request.form['fullname']
            email = request.form['email']
            username = request.form['username']
            password = request.form['password']
            role = 'user'
            conn = sqlite3.connect("databases.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO poultryusers (fullname, email, username, password, role) VALUES (?, ?, ?, ?, ?)",
                               (fullname, email, username, password, role))
            conn.commit()
            flash("Registration successful. Please log in.", "success")
            
        except sqlite3.IntegrityError:
            flash("Username or email already exists. Please try again.", "danger")

            
        finally:
            conn.close()
            return redirect(url_for('poultryhome'))    
            
    return render_template('poultry-register.html')

# Login route
@app.route('/poultrylogin', methods=['GET', 'POST'])
def poultrylogin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect("databases.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM poultryusers WHERE username = ? AND password = ?", (username, password)
        )
        data = cursor.fetchone()
        conn.close()

        if data:
            session['username'] = data["username"]
            session['role'] = data["role"]  # Store role in session
            '''flash("Login successful.", "success")'''

            # Redirect based on role
            if data["role"] == 'users':
                '''flash("Login successful as user.", "success")'''
                return redirect(url_for('poultry_user_dashboard'))
            else:
                flash("You are not logged in as a user. Admin access required.", "danger")
                return redirect(url_for('poultrylogin'))  # Replace this with a user-specific route if available
        else:
            flash("Invalid username or password", "danger")

    return render_template('poultry-login.html')

# Dashboard route (protected)

# Admin dashboard
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'username' in session and session.get('role') == 'admin':
        conn = sqlite3.connect("databases.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        user = cursor.execute("SELECT * FROM admin_profile WHERE role = 'admin'").fetchone()
        conn.close()

        if not user:
            flash("No user profile found.", "danger")
            user = {"fullname": "N/A", "job": "N/A"}

        # Render the admin dashboard
        return render_template('Adminindex.html', admin_profile=user)
    else:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('adminhome'))




# User dashboard - banana
@app.route('/user_dashboard')
def user_dashboard():
    if 'role' in session and session['role'] == 'users':
        # Global variables to store the latest sensor values
        latest_sensor_values = {
            "temperature": 0,  # Default value
            "humidity": 0,     # Default value
            "co2": 0,          # Default value
            "ammonia": 0,      # Default value
            "other": 0         # Default value
        }

        # RabbitMQ connection details
        rabbitmq_url = "amqps://uhbvmhoj:u76Em_OYzjlBXtV3Zw0K4MeGEI4XHEFu@hawk.rmq.cloudamqp.com/uhbvmhoj"
        queue_name = "BananaQueue"
        topic = "1001C/DATA"

        # Consumer function to read sensor values from RabbitMQ
        def consume_sensor_data():
            params = pika.URLParameters(rabbitmq_url)

            try:
                connection = pika.BlockingConnection(params)
                channel = connection.channel()

                # Declare and bind the queue
                channel.queue_declare(queue=queue_name, durable=True)
                channel.queue_bind(exchange="amq.topic", queue=queue_name, routing_key=topic)

                # Callback function for processing messages
                def callback(ch, method, properties, body):
                    nonlocal latest_sensor_values
                    try:
                        message = json.loads(body.decode())
                        
                        # Update variables only if data is present
                        if 'TEMP' in message and message['TEMP'] != "":
                            latest_sensor_values["temperature"] = float(message['TEMP'])
                        if 'HUM' in message and message['HUM'] != "":
                            latest_sensor_values["humidity"] = float(message['HUM'])
                        if 'R1' in message and message['R1'] != "":
                            latest_sensor_values["co2"] = float(message['R1'])
                        if 'R2' in message and message['R2'] != "":
                            latest_sensor_values["ammonia"] = round(float(message['R2']))
                        if 'R3' in message and message['R3'] != "":
                            latest_sensor_values["other"] = round(float(message['R3']))

                        print(f"Received data - Temperature: {latest_sensor_values['temperature']}°C, "
                              f"Humidity: {latest_sensor_values['humidity']}%, CO2: {latest_sensor_values['co2']} ppm, "
                              f"Ammonia: {latest_sensor_values['ammonia']}%, Other: {latest_sensor_values['other']}")

                        # Emit updated data to clients via Socket.IO
                        socketio.emit('update_data', latest_sensor_values)
                    except Exception as e:
                        print(f"Error processing message: {e}")

                # Start consuming messages
                channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
                print(f"Subscribed to topic: {topic}")
                channel.start_consuming()
            except Exception as e:
                print(f"An error occurred while consuming messages: {e}")

        # Start the consumer in a separate thread if not already running
        threading.Thread(target=consume_sensor_data, daemon=True).start()

        # Retrieve user profile from database
        conn = sqlite3.connect("databases.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        user = cursor.execute("SELECT * FROM banana_user_profile WHERE role = 'user'").fetchone()
        conn.close()

        if not user:
            flash("No user profile found.", "danger")
            user = {"fullname": "N/A", "job": "N/A"}

        # Render the user dashboard
        return render_template('index.html', banana_user_profile=user, sensor_values=latest_sensor_values)
    else:
        flash("Access denied. Users only.", "danger")
        return redirect(url_for('bananahome'))
        
# User dashboard - mushroom
@app.route('/mushroom_user_dashboard')
def mushroom_user_dashboard():
    if 'role' in session and session['role'] == 'users':
        # Global variables for mushroom sensor values
        mushroom_sensor_values = {
            "temperature": 0,  # Default value
            "humidity": 0,     # Default value
            "co2": 0,          # Default value
            "ammonia": 0,      # Default value
            "other": 0         # Default value
        }

        # RabbitMQ connection details for mushroom
        rabbitmq_url = "amqps://uhbvmhoj:u76Em_OYzjlBXtV3Zw0K4MeGEI4XHEFu@hawk.rmq.cloudamqp.com/uhbvmhoj"
        queue_name = "MushroomQueue"
        topic = "1001H/DATA"

        # Consumer function for mushroom sensor data
        def consume_mushroom_data():
            params = pika.URLParameters(rabbitmq_url)

            try:
                connection = pika.BlockingConnection(params)
                channel = connection.channel()

                # Declare and bind the queue
                channel.queue_declare(queue=queue_name, durable=True)
                channel.queue_bind(exchange="amq.topic", queue=queue_name, routing_key=topic)

                # Callback function for processing messages
                def callback(ch, method, properties, body):
                    nonlocal mushroom_sensor_values
                    try:
                        message = json.loads(body.decode())

                        # Update variables only if data is present
                        if 'TEMP' in message and message['TEMP'] != "":
                            mushroom_sensor_values["temperature"] = float(message['TEMP'])
                        if 'HUM' in message and message['HUM'] != "":
                            mushroom_sensor_values["humidity"] = float(message['HUM'])
                        if 'R1' in message and message['R1'] != "":
                            mushroom_sensor_values["co2"] = float(message['R1'])
                        if 'R2' in message and message['R2'] != "":
                            mushroom_sensor_values["ammonia"] = round(float(message['R2']))
                        if 'R3' in message and message['R3'] != "":
                            mushroom_sensor_values["other"] = round(float(message['R3']))

                        print(f"Received mushroom data - Temperature: {mushroom_sensor_values['temperature']}°C, "
                              f"Humidity: {mushroom_sensor_values['humidity']}%, CO2: {mushroom_sensor_values['co2']} ppm, "
                              f"Ammonia: {mushroom_sensor_values['ammonia']}%, Other: {mushroom_sensor_values['other']}")

                        # Emit updated data to clients via Socket.IO
                        socketio.emit('update_mushroom_data', mushroom_sensor_values)
                    except Exception as e:
                        print(f"Error processing mushroom message: {e}")

                # Start consuming messages
                channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
                print(f"Subscribed to mushroom topic: {topic}")
                channel.start_consuming()
            except Exception as e:
                print(f"An error occurred while consuming mushroom messages: {e}")

        # Start the consumer in a separate thread if not already running
        threading.Thread(target=consume_mushroom_data, daemon=True).start()

        # Retrieve user profile from database
        conn = sqlite3.connect("databases.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        user = cursor.execute("SELECT * FROM mushroom_user_profile WHERE role = 'user'").fetchone()
        conn.close()

        if not user:
            flash("No user profile found.", "danger")
            user = {"fullname": "N/A", "job": "N/A"}

        # Render the mushroom dashboard
        return render_template('1001H.html', mushroom_user_profile=user, sensor_values=mushroom_sensor_values)
    else:
        flash("Access denied. Users only.", "danger")
        return redirect(url_for('mushroomhome'))


# User dashboard - poultry
@app.route('/poultry_user_dashboard')
def poultry_user_dashboard():
    if 'role' in session and session['role'] == 'users':
        # Global variables for poultry sensor values
        poultry_sensor_values = {
            "temperature": 0,  # Default value
            "humidity": 0,     # Default value
            "co2": 0,          # Default value
            "ammonia": 0,      # Default value
            "other": 0         # Default value
        }

        # RabbitMQ connection details for poultry
        rabbitmq_url = "amqps://uhbvmhoj:u76Em_OYzjlBXtV3Zw0K4MeGEI4XHEFu@hawk.rmq.cloudamqp.com/uhbvmhoj"
        queue_name = "PoultryQueue"
        topic = "1001A/DATA"

        # Consumer function for poultry sensor data
        def consume_poultry_data():
            params = pika.URLParameters(rabbitmq_url)

            try:
                connection = pika.BlockingConnection(params)
                channel = connection.channel()

                # Declare and bind the queue
                channel.queue_declare(queue=queue_name, durable=True)
                channel.queue_bind(exchange="amq.topic", queue=queue_name, routing_key=topic)

                # Callback function for processing messages
                def callback(ch, method, properties, body):
                    nonlocal poultry_sensor_values
                    try:
                        message = json.loads(body.decode())

                        # Update variables only if data is present
                        if 'TEMP' in message and message['TEMP'] != "":
                            poultry_sensor_values["temperature"] = float(message['TEMP'])
                        if 'HUM' in message and message['HUM'] != "":
                            poultry_sensor_values["humidity"] = float(message['HUM'])
                        if 'R1' in message and message['R1'] != "":
                            poultry_sensor_values["co2"] = float(message['R1'])
                        if 'R2' in message and message['R2'] != "":
                            poultry_sensor_values["ammonia"] = round(float(message['R2']))
                        if 'R3' in message and message['R3'] != "":
                            poultry_sensor_values["other"] = round(float(message['R3']))

                        print(f"Received poultry data - Temperature: {poultry_sensor_values['temperature']}°C, "
                              f"Humidity: {poultry_sensor_values['humidity']}%, CO2: {poultry_sensor_values['co2']} ppm, "
                              f"Ammonia: {poultry_sensor_values['ammonia']}%, Other: {poultry_sensor_values['other']}")

                        # Emit updated data to clients via Socket.IO
                        socketio.emit('update_poultry_data', poultry_sensor_values)
                    except Exception as e:
                        print(f"Error processing poultry message: {e}")

                # Start consuming messages
                channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
                print(f"Subscribed to poultry topic: {topic}")
                channel.start_consuming()
            except Exception as e:
                print(f"An error occurred while consuming poultry messages: {e}")

        # Start the consumer in a separate thread if not already running
        threading.Thread(target=consume_poultry_data, daemon=True).start()

        # Retrieve user profile from database
        conn = sqlite3.connect("databases.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        user = cursor.execute("SELECT * FROM poultry_user_profile WHERE role = 'user'").fetchone()
        conn.close()

        if not user:
            flash("No user profile found.", "danger")
            user = {"fullname": "N/A", "job": "N/A"}

        # Render the poultry dashboard
        return render_template('1001A.html', poultry_user_profile=user, sensor_values=poultry_sensor_values)
    else:
        flash("Access denied. Users only.", "danger")
        return redirect(url_for('poultryhome'))



# Logout route

def clear_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.route('/adminlogout')
def adminlogout():
    session.clear()  # Clear session data
    flash("You have been logged out.", "logout")
    response = redirect(url_for('adminhome'))
    return clear_cache(response)

@app.route('/mushroomlogout')
def mushroomlogout():
    session.clear()  # Clear session data
    flash("You have been logged out.", "logout")
    response = redirect(url_for('mushroomhome'))
    return clear_cache(response)

@app.route('/poultrylogout')
def poultrylogout():
    session.clear()  # Clear session data
    flash("You have been logged out.", "logout")
    response = redirect(url_for('poultryhome'))
    return clear_cache(response)

@app.route('/bananalogout')
def bananalogout():
    session.clear()  # Clear session data
    flash("You have been logged out.", "logout")
    response = redirect(url_for('bananahome'))
    return clear_cache(response)

@app.route('/1001C.html')
def deviceC():
    return render_template('index.html')

@app.route('/1001A.html', methods=['GET'])
def deviceA():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM poultry_user_profile WHERE role = 'user'").fetchone()
    conn.close()

    if not user:
        flash("No user profile found.", "danger")
        user = {"fullname": "N/A", "job": "N/A"}
    return render_template('1001A.html', poultry_user_profile=user)

@app.route('/1001H.html', methods=['GET'])
def deviceH():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM mushroom_user_profile WHERE role = 'user'").fetchone()
    conn.close()

    if not user:
        flash("No user profile found.", "danger")
        user = {"fullname": "N/A", "job": "N/A"}
    return render_template('1001H.html', mushroom_user_profile=user)

@app.route('/1001I.html')
def deviceI():
    return render_template('1001I.html')

@app.route('/1001J.html')
def deviceJ():
    return render_template('1001J.html')

@app.route('/terms.html')
def terms():
    return render_template('terms.html')

@app.route('/Adminindex.html')
def Adminindex():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM admin_profile WHERE role = 'admin'").fetchone()
    conn.close()

    if not user:
        flash("No admin profile found.", "danger")
        user = {}

    return render_template('Adminindex.html', admin_profile=user)

@app.route('/admin-profile.html', methods=['GET', 'POST'])
def adminprofile():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    

    if request.method == 'POST':
        try:
            fullname = request.form['fullName']
            about = request.form['about']
            company = request.form['company']
            job = request.form['job']
            country = request.form['country']
            address = request.form['address']
            phone = request.form['phone']
            email = request.form['email']
            twitter_profile = request.form['twitter']
            facebook_profile = request.form['facebook']
            instagram_profile = request.form['instagram']
            linkedin_profile = request.form['linkedin']

            # Handle file upload
            profile_image = request.files.get('profileImage')
            image_path = None
            if profile_image and profile_image.filename:
                # Save the image file
                upload_folder = '../../assets/uploads/admin_pic/'
                image_filename = os.path.join(upload_folder, profile_image.filename)
                profile_image.save(image_filename)
                image_path = image_filename

            # Update the database with profile data and image path
            cursor.execute("""
                UPDATE admin_profile
                SET fullname = ?, about = ?, company = ?, job = ?, country = ?, address = ?, phone = ?, 
                    email = ?, twitter_profile = ?, facebook_profile = ?, instagram_profile = ?, linkedin_profile = ?, 
                    profile_image = COALESCE(?, profile_image)
                WHERE role = 'admin'
            """, (fullname, about, company, job, country, address, phone, email, twitter_profile,
                  facebook_profile, instagram_profile, linkedin_profile, image_path))
            conn.commit()
            flash('Profile updated successfully!', 'success')
        except sqlite3.Error as e:
            flash(f'An error occurred: {e}', 'danger')
        finally:
            conn.close()
        return redirect(url_for('adminprofile'))

    # Handle GET request
    user = cursor.execute("SELECT * FROM admin_profile WHERE role = 'admin'").fetchone()
    conn.close()

    if not user:
        flash("No admin profile found.", "danger")
        user = {}

    return render_template('admin-profile.html', admin_profile=user)

@app.route('/remove-profile-image-a', methods=['GET'])
def remove_profile_image_a():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row  # Enable dictionary-style row access
    cursor = conn.cursor()

    # Fetch the current profile image path
    cursor.execute("SELECT profile_image FROM admin_profile WHERE role = 'admin'")
    result = cursor.fetchone()

    if result and result['profile_image']:
        image_path = result['profile_image']

        # Remove the file if it exists
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
                print(f"Deleted image: {image_path}")
        except Exception as e:
            print(f"Error deleting image: {e}")

        # Update the database to set profile_image to NULL
        cursor.execute("UPDATE admin_profile SET profile_image = NULL WHERE role = 'admin'")
        conn.commit()

    conn.close()

    flash("Profile image removed successfully!", "success")
    return redirect(url_for('adminprofile'))

# Route to handle password change
@app.route('/change-password-a', methods=['POST'])
def change_password_a():
    current_password = request.form.get('password')
    new_password = request.form.get('newpassword')
    renew_password = request.form.get('renewpassword')

    # Connect to database
    conn = sqlite3.connect("databases.db")
    cursor = conn.cursor()

    # Fetch current user password (assuming user with id 1 for example)
    cursor.execute("SELECT password FROM adminusers WHERE role = 'admin'")
    result = cursor.fetchone()

    if not result:
        flash("User not found!", "danger")
        conn.close()
        return redirect(url_for('adminprofile'))

    stored_password = result[0]

    # Verify current password
    if current_password != stored_password:
        flash("Current password is incorrect!", "danger")
        conn.close()
        return redirect(url_for('adminprofile'))

    # Check if new password and re-entered password match
    if new_password != renew_password:
        flash("New passwords do not match!", "danger")
        conn.close()
        return redirect(url_for('adminprofile'))

    # Update the password in the database
    cursor.execute("UPDATE adminusers SET password = ? WHERE role = 'admin'", (new_password,))
    conn.commit()
    conn.close()

    flash("Password changed successfully!", "success")
    return redirect(url_for('adminprofile'))


@app.route('/admin-contact.html')
def admincontact():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM admin_profile WHERE role = 'admin'").fetchone()
    conn.close()

    if not user:
        flash("No user profile found.", "danger")
        user = {}
    return render_template('admin-contact.html', admin_profile=user)

@app.route('/admin-faq.html')
def adminfaq():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM admin_profile WHERE role = 'admin'").fetchone()
    conn.close()

    if not user:
        flash("No user profile found.", "danger")
        user = {}
    return render_template('admin-faq.html', admin_profile=user)

@app.route('/index.html', methods=['GET'])
def Error():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM banana_user_profile WHERE role = 'user'").fetchone()
    conn.close()

    if not user:
        flash("No user profile found.", "danger")
        user = {"fullname": "N/A", "job": "N/A"}
    return render_template('index.html', banana_user_profile=user) 

@app.route('/users-profile.html', methods=['GET', 'POST'])
def user_profile():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            fullname = request.form['fullName']
            about = request.form['about']
            company = request.form['company']
            job = request.form['job']
            country = request.form['country']
            address = request.form['address']
            phone = request.form['phone']
            email = request.form['email']
            twitter_profile = request.form['twitter']
            facebook_profile = request.form['facebook']
            instagram_profile = request.form['instagram']
            linkedin_profile = request.form['linkedin']

            # Handle file upload
            profile_image = request.files.get('profileImage')
            image_path = None
            if profile_image and profile_image.filename:
                # Save the image file
                upload_folder = '../../assets/uploads/banana_user/'
                image_filename = os.path.join(upload_folder, profile_image.filename)
                profile_image.save(image_filename)
                image_path = image_filename

            # Update the database with profile data and image path
            cursor.execute("""
                UPDATE banana_user_profile
                SET fullname = ?, about = ?, company = ?, job = ?, country = ?, address = ?, phone = ?, 
                    email = ?, twitter_profile = ?, facebook_profile = ?, instagram_profile = ?, linkedin_profile = ?, 
                    profile_image = COALESCE(?, profile_image)
                WHERE role = 'user'
            """, (fullname, about, company, job, country, address, phone, email, twitter_profile,
                  facebook_profile, instagram_profile, linkedin_profile, image_path))
            conn.commit()
            flash('Profile updated successfully!', 'success')
        except sqlite3.Error as e:
            flash(f'An error occurred: {e}', 'danger')
        finally:
            conn.close()
        return redirect(url_for('user_profile'))

    # Handle GET request
    user = cursor.execute("SELECT * FROM banana_user_profile WHERE role = 'user'").fetchone()
    conn.close()

    if not user:
        flash("No user profile found.", "danger")
        user = {}

    return render_template('users-profile.html', banana_user_profile=user)

@app.route('/remove-profile-image', methods=['GET'])
def remove_profile_image():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row  # Enable dictionary-style row access
    cursor = conn.cursor()

    # Fetch the current profile image path
    cursor.execute("SELECT profile_image FROM banana_user_profile WHERE role = 'user'")
    result = cursor.fetchone()

    if result and result['profile_image']:
        image_path = result['profile_image']

        # Remove the file if it exists
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
                print(f"Deleted image: {image_path}")
        except Exception as e:
            print(f"Error deleting image: {e}")

        # Update the database to set profile_image to NULL
        cursor.execute("UPDATE banana_user_profile SET profile_image = NULL WHERE role = 'user'")
        conn.commit()

    conn.close()

    flash("Profile image removed successfully!", "success")
    return redirect(url_for('user_profile'))

# Route to handle password change
@app.route('/change-password', methods=['POST'])
def change_password():
    current_password = request.form.get('password')
    new_password = request.form.get('newpassword')
    renew_password = request.form.get('renewpassword')

    # Connect to database
    conn = sqlite3.connect("databases.db")
    cursor = conn.cursor()

    # Fetch current user password (assuming user with id 1 for example)
    cursor.execute("SELECT password FROM users WHERE role = 'user'")
    result = cursor.fetchone()

    if not result:
        flash("User not found!", "danger")
        conn.close()
        return redirect(url_for('user_profile'))

    stored_password = result[0]

    # Verify current password
    if current_password != stored_password:
        flash("Current password is incorrect!", "danger")
        conn.close()
        return redirect(url_for('user_profile'))

    # Check if new password and re-entered password match
    if new_password != renew_password:
        flash("New passwords do not match!", "danger")
        conn.close()
        return redirect(url_for('user_profile'))

    # Update the password in the database
    cursor.execute("UPDATE users SET password = ? WHERE role = 'user'", (new_password,))
    conn.commit()
    conn.close()

    flash("Password changed successfully!", "success")
    return redirect(url_for('user_profile'))

@app.route('/pages-contact.html', methods=['GET'])
def contact():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM banana_user_profile WHERE role = 'user'").fetchone()
    conn.close()

    if not user:
        flash("No user profile found.", "danger")
        user = {}
    return render_template('pages-contact.html', banana_user_profile=user)

@app.route('/pages-faq.html', methods=['GET'])
def faq():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM banana_user_profile WHERE role = 'user'").fetchone()
    conn.close()

    if not user:
        flash("No user profile found.", "danger")
        user = {}
    return render_template('pages-faq.html', banana_user_profile=user)

# admin

@app.route('/send_email_a', methods=['POST'])
def send_email_a():
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message_content = request.form.get('message')

        if not all([name, email, subject, message_content]):
            flash('All fields are required!', 'danger')
            return redirect(url_for('adminprofile'))

        # Send email to admin
        admin_email = "harilearnings13@gmail.com"  # Replace with admin's email
        msg = Message(subject=f"Contact Form: {subject}",
                      recipients=[admin_email])
        msg.body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message_content}"

        mail.send(msg)
        flash('Your message has been sent successfully!', 'success')
        return redirect(url_for('adminprofile'))

    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('adminprofile'))

# banana

@app.route('/send_email', methods=['POST'])
def send_email():
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message_content = request.form.get('message')

        if not all([name, email, subject, message_content]):
            flash('All fields are required!', 'danger')
            return redirect(url_for('user_profile'))

        # Send email to admin
        admin_email = "harilearnings13@gmail.com"  # Replace with admin's email
        msg = Message(subject=f"Contact Form: {subject}",
                      recipients=[admin_email])
        msg.body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message_content}"

        mail.send(msg)
        flash('Your message has been sent successfully!', 'success')
        return redirect(url_for('user_profile'))

    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('user_profile'))

# mushroom

@app.route('/sendd_email', methods=['POST'])
def sendd_email():
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message_content = request.form.get('message')

        if not all([name, email, subject, message_content]):
            flash('All fields are required!', 'danger')
            return redirect(url_for('mushroomuserprofile'))

        # Send email to admin
        admin_email = "harilearnings13@gmail.com"  # Replace with admin's email
        msg = Message(subject=f"Contact Form: {subject}",
                      recipients=[admin_email])
        msg.body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message_content}"

        mail.send(msg)
        flash('Your message has been sent successfully!', 'success')
        return redirect(url_for('mushroomuserprofile'))

    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('mushroomuserprofile'))

# poultry

@app.route('/senddd_email', methods=['POST'])
def senddd_email():
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message_content = request.form.get('message')

        if not all([name, email, subject, message_content]):
            flash('All fields are required!', 'danger')
            return redirect(url_for('poultryuserprofile'))

        # Send email to admin
        admin_email = "harilearnings13@gmail.com"  # Replace with admin's email
        msg = Message(subject=f"Contact Form: {subject}",
                      recipients=[admin_email])
        msg.body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message_content}"

        mail.send(msg)
        flash('Your message has been sent successfully!', 'success')
        return redirect(url_for('poultryuserprofile'))

    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('poultryuserprofile'))


@app.route('/mushroom-user-profile.html', methods=['GET', 'POST'])
def mushroomuserprofile():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            fullname = request.form['fullName']
            about = request.form['about']
            company = request.form['company']
            job = request.form['job']
            country = request.form['country']
            address = request.form['address']
            phone = request.form['phone']
            email = request.form['email']
            twitter_profile = request.form['twitter']
            facebook_profile = request.form['facebook']
            instagram_profile = request.form['instagram']
            linkedin_profile = request.form['linkedin']

            # Handle file upload
            
            profile_image = request.files.get('profileImage')
            image_path = None
            if profile_image and profile_image.filename:
                # Save the image file
                upload_folder = '../../assets/uploads/mushroom_user/'
                image_filename = os.path.join(upload_folder, profile_image.filename)
                profile_image.save(image_filename)
                image_path = image_filename

            # Update the database with profile data and image path
            cursor.execute("""
                UPDATE mushroom_user_profile
                SET fullname = ?, about = ?, company = ?, job = ?, country = ?, address = ?, phone = ?, 
                    email = ?, twitter_profile = ?, facebook_profile = ?, instagram_profile = ?, linkedin_profile = ?, 
                    profile_image = COALESCE(?, profile_image)
                WHERE role = 'user'
            """, (fullname, about, company, job, country, address, phone, email, twitter_profile,
                  facebook_profile, instagram_profile, linkedin_profile, image_path))
            conn.commit()
            flash('Profile updated successfully!', 'success')
        except sqlite3.Error as e:
            flash(f'An error occurred: {e}', 'danger')
        finally:
            conn.close()
        return redirect(url_for('mushroomuserprofile'))

    # Handle GET request
    user = cursor.execute("SELECT * FROM mushroom_user_profile WHERE role = 'user'").fetchone()
    conn.close()

    if not user:
        flash("No user profile found.", "danger")
        user = {}

    return render_template('mushroom-user-profile.html', mushroom_user_profile=user)

@app.route('/removee-profilee-image', methods=['GET'])
def removee_profilee_image():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row  # Enable dictionary-style row access
    cursor = conn.cursor()

    # Fetch the current profile image path
    cursor.execute("SELECT profile_image FROM mushroom_user_profile WHERE role = 'user'")
    result = cursor.fetchone()

    if result and result['profile_image']:
        image_path = result['profile_image']

        # Remove the file if it exists
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
                print(f"Deleted image: {image_path}")
        except Exception as e:
            print(f"Error deleting image: {e}")

        # Update the database to set profile_image to NULL
        cursor.execute("UPDATE mushroom_user_profile SET profile_image = NULL WHERE role = 'user'")
        conn.commit()

    conn.close()

    flash("Profile image removed successfully!", "success")
    return redirect(url_for('mushroomuserprofile'))

# Route to handle password change
@app.route('/changee-passwordd', methods=['POST'])
def changee_passwordd():
    current_password = request.form.get('password')
    new_password = request.form.get('newpassword')
    renew_password = request.form.get('renewpassword')

    # Connect to database
    conn = sqlite3.connect("databases.db")
    cursor = conn.cursor()

    # Fetch current user password (assuming user with id 1 for example)
    cursor.execute("SELECT password FROM mushroomusers WHERE role = 'user'")
    result = cursor.fetchone()

    if not result:
        flash("User not found!", "danger")
        conn.close()
        return redirect(url_for('mushroomuserprofile'))

    stored_password = result[0]

    # Verify current password
    if current_password != stored_password:
        flash("Current password is incorrect!", "danger")
        conn.close()
        return redirect(url_for('mushroomuserprofile'))

    # Check if new password and re-entered password match
    if new_password != renew_password:
        flash("New passwords do not match!", "danger")
        conn.close()
        return redirect(url_for('mushroomuserprofile'))

    # Update the password in the database
    cursor.execute("UPDATE mushroomusers SET password = ? WHERE role = 'user'", (new_password,))
    conn.commit()
    conn.close()

    flash("Password changed successfully!", "success")
    return redirect(url_for('mushroomuserprofile'))

@app.route('/mushroom-pages-contact.html', methods=['GET'])
def mushroomcontact():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM mushroom_user_profile WHERE role = 'user'").fetchone()
    conn.close()

    if not user:
        flash("No user profile found.", "danger")
        user = {}
    return render_template('mushroom-pages-contact.html', mushroom_user_profile=user)

@app.route('/mushroom-pages-faq.html', methods=['GET'])
def mushroomcfaq():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM mushroom_user_profile WHERE role = 'user'").fetchone()
    conn.close()

    if not user:
        flash("No user profile found.", "danger")
        user = {}
    return render_template('mushroom-pages-faq.html', mushroom_user_profile=user)

@app.route('/poultry-user-profile.html', methods=['GET', 'POST'])
def poultryuserprofile():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            fullname = request.form['fullName']
            about = request.form['about']
            company = request.form['company']
            job = request.form['job']
            country = request.form['country']
            address = request.form['address']
            phone = request.form['phone']
            email = request.form['email']
            twitter_profile = request.form['twitter']
            facebook_profile = request.form['facebook']
            instagram_profile = request.form['instagram']
            linkedin_profile = request.form['linkedin']

            # Handle file upload
            profile_image = request.files.get('profileImage')
            image_path = None
            if profile_image and profile_image.filename:
                # Save the image file
                upload_folder = '../../assets/uploads/poultry_user/'
                image_filename = os.path.join(upload_folder, profile_image.filename)
                profile_image.save(image_filename)
                image_path = image_filename

            # Update the database with profile data and image path
            cursor.execute("""
                UPDATE poultry_user_profile
                SET fullname = ?, about = ?, company = ?, job = ?, country = ?, address = ?, phone = ?, 
                    email = ?, twitter_profile = ?, facebook_profile = ?, instagram_profile = ?, linkedin_profile = ?, 
                    profile_image = COALESCE(?, profile_image)
                WHERE role = 'user'
            """, (fullname, about, company, job, country, address, phone, email, twitter_profile,
                  facebook_profile, instagram_profile, linkedin_profile, image_path))
            conn.commit()
            flash('Profile updated successfully!', 'success')
        except sqlite3.Error as e:
            flash(f'An error occurred: {e}', 'danger')
        finally:
            conn.close()
        return redirect(url_for('poultryuserprofile'))

    # Handle GET request
    user = cursor.execute("SELECT * FROM poultry_user_profile WHERE role = 'user'").fetchone()
    conn.close()

    if not user:
        flash("No user profile found.", "danger")
        user = {}

    return render_template('poultry-user-profile.html', poultry_user_profile=user)

@app.route('/removeee-profileee-image', methods=['GET'])
def removeee_profileee_image():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row  # Enable dictionary-style row access
    cursor = conn.cursor()

    # Fetch the current profile image path
    cursor.execute("SELECT profile_image FROM poultry_user_profile WHERE role = 'user'")
    result = cursor.fetchone()

    if result and result['profile_image']:
        image_path = result['profile_image']

        # Remove the file if it exists
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
                print(f"Deleted image: {image_path}")
        except Exception as e:
            print(f"Error deleting image: {e}")

        # Update the database to set profile_image to NULL
        cursor.execute("UPDATE poultry_user_profile SET profile_image = NULL WHERE role = 'user'")
        conn.commit()

    conn.close()

    flash("Profile image removed successfully!", "success")
    return redirect(url_for('poultryuserprofile'))

# Route to handle password change
@app.route('/changeee-passworddd', methods=['POST'])
def changeee_passworddd():
    current_password = request.form.get('password')
    new_password = request.form.get('newpassword')
    renew_password = request.form.get('renewpassword')

    # Connect to database
    conn = sqlite3.connect("databases.db")
    cursor = conn.cursor()

    # Fetch current user password (assuming user with id 1 for example)
    cursor.execute("SELECT password FROM poultryusers WHERE role = 'user'")
    result = cursor.fetchone()

    if not result:
        flash("User not found!", "danger")
        conn.close()
        return redirect(url_for('poultryuserprofile'))

    stored_password = result[0]

    # Verify current password
    if current_password != stored_password:
        flash("Current password is incorrect!", "danger")
        conn.close()
        return redirect(url_for('poultryuserprofile'))

    # Check if new password and re-entered password match
    if new_password != renew_password:
        flash("New passwords do not match!", "danger")
        conn.close()
        return redirect(url_for('poultryuserprofile'))

    # Update the password in the database
    cursor.execute("UPDATE poultryusers SET password = ? WHERE role = 'user'", (new_password,))
    conn.commit()
    conn.close()

    flash("Password changed successfully!", "success")
    return redirect(url_for('poultryuserprofile'))

@app.route('/poultry-pages-contact.html', methods=['GET'])
def poultrycontact():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM poultry_user_profile WHERE role = 'user'").fetchone()
    conn.close()

    if not user:
        flash("No user profile found.", "danger")
        user = {}
    return render_template('poultry-pages-contact.html', poultry_user_profile=user)

@app.route('/poultry-pages-faq.html', methods=['GET'])
def poultryfaq():
    conn = sqlite3.connect("databases.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM poultry_user_profile WHERE role = 'user' ").fetchone()
    conn.close()

    if not user:
        flash("No user profile found.", "danger")
        user = {}
    return render_template('poultry-pages-faq.html', poultry_user_profile=user)

@app.route('/temperature')
def temperature():
    return jsonify({'temperature': latest_temperature})

@app.route('/humidity')
def humidity():
    return jsonify({'humidity': latest_humidity})

@app.route('/co2')
def co2():
    return jsonify({'co2': latest_co2})

@app.route('/ammonia')
def ammonia():
    return jsonify({'ammonia': latest_ammonia})

'''@app.route('/pages-error-404.html')
def  errorpages404():
    return render_template('pages-error-404.html')'''

@app.route('/other')
def other():
    return jsonify({'other': latest_other})

@app.route('/video_feed')
def video_feed():
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    # Run the app on DigitalOcean's public IP with Nginx proxy
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
