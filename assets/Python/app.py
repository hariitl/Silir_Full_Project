from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, flash, session
import sqlite3
from flask_socketio import SocketIO
import pika
import threading
import ssl
import os
import cv2
import json

# Flask app setup
app = Flask(__name__, template_folder='../../', static_folder='../../assets')
app.secret_key = '950007397@$' # Required for session management
socketio = SocketIO(app)

VIDEO_PATH = os.path.join(os.path.dirname(__file__), '../Model/video.mp4')

# Database setup

conn = sqlite3.connect("databases.db")
conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user')
             """)
conn.close()

conn = sqlite3.connect("databases.db")
conn.execute("""
            CREATE TABLE IF NOT EXISTS mushroomusers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user')
             """)
conn.close()

conn = sqlite3.connect("databases.db")
conn.execute("""
            CREATE TABLE IF NOT EXISTS poultryusers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user')
             """)
conn.close()


# Global variables to store the latest sensor values
latest_temperature = 0  # Default value
latest_humidity = 0     # Default value
latest_co2 = 0          # Default value
latest_ammonia = 0      # Default value
latest_other = 0        # Default value

# RabbitMQ connection details
rabbitmq_url = "amqps://uhbvmhoj:u76Em_OYzjlBXtV3Zw0K4MeGEI4XHEFu@hawk.rmq.cloudamqp.com/uhbvmhoj"
queue_name = "Testing2"
topic = "1001C/DATA"

# Consumer function to read sensor values from RabbitMQ
def consume_sensor_data():
    global latest_temperature, latest_humidity, latest_co2, latest_ammonia, latest_other
    params = pika.URLParameters(rabbitmq_url)

    try:
        connection = pika.BlockingConnection(params)
        channel = connection.channel()

        # Declare and bind the queue
        channel.queue_declare(queue=queue_name, durable=True)
        channel.queue_bind(exchange="amq.topic", queue=queue_name, routing_key=topic)

        # Callback function for processing messages
        def callback(ch, method, properties, body):
            global latest_temperature, latest_humidity, latest_co2, latest_ammonia, latest_other

            try:
                message = json.loads(body.decode())
                
                # Update variables only if data is present
                if 'TEMP' in message and message['TEMP'] != "":
                    latest_temperature = float(message['TEMP'])
                if 'HUM' in message and message['HUM'] != "":
                    latest_humidity = float(message['HUM'])
                if 'R1' in message and message['R1'] != "":
                    latest_co2 = float(message['R1'])
                if 'R2' in message and message['R2'] != "":
                    latest_ammonia = round(float(message['R2']))
                if 'R3' in message and message['R3'] != "":
                    latest_other = round(float(message['R3']))

                print(f"Received data - Temperature: {latest_temperature}°C, "
                      f"Humidity: {latest_humidity}%, CO2: {latest_co2} ppm, "
                      f"Ammonia: {latest_ammonia}%, Other: {latest_other}")
                

                # Emit updated data to clients via Socket.IO
                socketio.emit('update_data', {
                    'temperature': latest_temperature,
                    'humidity': latest_humidity,
                    'co2': latest_co2,
                    'ammonia': latest_ammonia,
                    'other': latest_other,
                   # 'timestamp': datetime.utcnow().isoformat()
                })
            except ValueError as e:
                print(f"Error processing message: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")

        # Start consuming messages
        channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
        print(f"Subscribed to topic: {topic}")
        channel.start_consuming()
    except pika.exceptions.AMQPConnectionError as e:
        print("Error: Could not connect to RabbitMQ server.", e)
    except Exception as e:
        print("An error occurred while consuming messages:", e)

# Start the consumer in a separate thread
threading.Thread(target=consume_sensor_data, daemon=True).start()

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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            fullname = request.form['fullname']
            email = request.form['email']
            username = request.form['username']
            password = request.form['password']
            role = request.form.get('role', 'user')
            conn = sqlite3.connect("databases.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (fullname, email, username, password, role) VALUES (?, ?, ?, ?, ?)",
                               (fullname, email, username, password, role))
            conn.commit()
            flash("Registration successful. Please log in.", "success")
            
        except sqlite3.IntegrityError:
            flash("Username or email already exists. Please try again.", "danger")

            
        finally:
            return redirect(url_for('bananahome'))    
            conn.close()
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

        if data:
            session['username'] = data["username"]
            session['role'] = data["role"]  # Store role in session
            flash("Login successful.", "success")

            # Redirect based on role
            if data["role"] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
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
            role = request.form.get('role', 'user')
            conn = sqlite3.connect("databases.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO mushroomusers (fullname, email, username, password, role) VALUES (?, ?, ?, ?, ?)",
                               (fullname, email, username, password, role))
            conn.commit()
            flash("Registration successful. Please log in.", "success")
            
        except sqlite3.IntegrityError:
            flash("Username or email already exists. Please try again.", "danger")

            
        finally:
            return redirect(url_for('mushroomhome'))    
            conn.close()
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

        if data:
            session['username'] = data["username"]
            session['role'] = data["role"]  # Store role in session
            flash("Login successful.", "success")

            # Redirect based on role
            if data["role"] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('mushroom_user_dashboard'))
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
            role = request.form.get('role', 'user')
            conn = sqlite3.connect("databases.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO poultryusers (fullname, email, username, password, role) VALUES (?, ?, ?, ?, ?)",
                               (fullname, email, username, password, role))
            conn.commit()
            flash("Registration successful. Please log in.", "success")
            
        except sqlite3.IntegrityError:
            flash("Username or email already exists. Please try again.", "danger")

            
        finally:
            return redirect(url_for('poultryhome'))    
            conn.close()
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

        if data:
            session['username'] = data["username"]
            session['role'] = data["role"]  # Store role in session
            flash("Login successful.", "success")

            # Redirect based on role
            if data["role"] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('poultry_user_dashboard'))
        else:
            flash("Invalid username or password", "danger")

    return render_template('poultry-login.html')

# Dashboard route (protected)

# Admin dashboard
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'role' in session and session['role'] == 'admin':
        return render_template('Adminindex.html')
    else:
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('home'))

# User dashboard - banana
@app.route('/user_dashboard')
def user_dashboard():
    if 'role' in session and session['role'] == 'user':
        return render_template('index.html')
    else:
        flash("Access denied. Users only.", "danger")
        return redirect(url_for('bananahome'))

# User dashboard - mushroom
@app.route('/mushroom_user_dashboard')
def mushroom_user_dashboard():
    if 'role' in session and session['role'] == 'user':
        return render_template('1001H.html')
    else:
        flash("Access denied. Users only.", "danger")
        return redirect(url_for('mushroomhome'))

# User dashboard - poultry
@app.route('/poultry_user_dashboard')
def poultry_user_dashboard():
    if 'role' in session and session['role'] == 'user':
        return render_template('1001A.html')
    else:
        flash("Access denied. Users only.", "danger")
        return redirect(url_for('poultryhome'))

# Logout route

@app.route('/adminlogout')
def adminlogout():
    session.clear()  # Clear session data
    flash("You have been logged out.", "logout")
    return redirect(url_for('home'))

@app.route('/mushroomlogout')
def mushroomlogout():
    session.clear()  # Clear session data
    flash("You have been logged out.", "logout")
    return redirect(url_for('mushroomhome'))

@app.route('/poultrylogout')
def poultrylogout():
    session.clear()  # Clear session data
    flash("You have been logged out.", "logout")
    return redirect(url_for('poultryhome'))

@app.route('/bananalogout')
def bananalogout():
    session.clear()  # Clear session data
    flash("You have been logged out.", "logout")
    return redirect(url_for('bananahome'))

@app.route('/1001C.html')
def deviceC():
    return render_template('index.html')

@app.route('/1001A.html')
def deviceA():
    return render_template('1001A.html')

@app.route('/1001H.html')
def deviceH():
    return render_template('1001H.html')

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
def adminindex():
    return render_template('Adminindex.html')

@app.route('/admin-profile.html')
def adminprofile():
    return render_template('admin-profile.html')

@app.route('/admin-contact.html')
def admincontact():
    return render_template('/admin-contact.html')

@app.route('/admin-faq.html')
def adminfaq():
    return render_template('admin-faq.html')

@app.route('/index.html')
def Error():
    return render_template('index.html') 

@app.route('/users-profile.html')
def profile():
    return render_template('users-profile.html')

@app.route('/pages-contact.html')
def contact():
    return render_template('pages-contact.html')

@app.route('/pages-faq.html')
def faq():
    return render_template('pages-faq.html')

@app.route('/mushroom-user-profile.html')
def mushroomuserprofile():
    return render_template('mushroom-user-profile.html')

@app.route('/mushroom-pages-contact.html')
def mushroomcontact():
    return render_template('mushroom-pages-contact.html')

@app.route('/mushroom-pages-faq.html')
def mushroomcfaq():
    return render_template('mushroom-pages-faq.html')

@app.route('/poultry-user-profile.html')
def poultryuserprofile():
    return render_template('poultry-user-profile.html')

@app.route('/poultry-pages-contact.html')
def poultrycontact():
    return render_template('poultry-pages-contact.html')

@app.route('/poultry-pages-faq.html')
def poultryfaq():
    return render_template('poultry-pages-faq.html')

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
