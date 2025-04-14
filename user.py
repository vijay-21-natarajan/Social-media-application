from flask import Flask, request, jsonify, render_template, redirect, url_for, session,flash
#from flask_socketio import SocketIO, send, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
#from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email_validator import validate_email, EmailNotValidError
import os
from werkzeug.utils import secure_filename
import logging
import requests 
import openai

#from flask_sqlalchemy import BaseQuery

app = Flask(__name__, template_folder="templates")

# Configuration for PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:21DCjxwhijil98ihj@localhost/social_media'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'  # Required for session handling

UPLOAD_FOLDER = 'static/uploads'  # Directory for profile picture uploads
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

logging.basicConfig(level=logging.DEBUG) 
openai.api_key = "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"

db = SQLAlchemy(app)
#migrate = Migrate(app, db)
#socketio = SocketIO(app)
# Define the User model
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    profile_picture = db.Column(db.String(300), default="uploads/default_profile.png")
    bio = db.Column(db.String(500), default="")
    notifications_enabled = db.Column(db.Boolean, default=True)
    private_account = db.Column(db.Boolean, default=False)
    close_friends = db.Column(db.Text, default="")  # Store close friends as comma-separated usernames
    
    # Relationship for messages
    sent_messages = db.relationship(
        'Message',
        foreign_keys='Message.sender_id',
        backref='sender',
        lazy='dynamic'
    )
    received_messages = db.relationship(
        'Message',
        foreign_keys='Message.recipient_id',
        backref='recipient',
        lazy='dynamic'
    )

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "profile_picture": self.profile_picture,
            "bio": self.bio,
            "notifications_enabled": self.notifications_enabled,
            "private_account": self.private_account,
            "close_friends": self.close_friends.split(',') if self.close_friends else []

        }


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "text": self.text,
            "sender": self.sender.username if self.sender else None,
            "recipient": self.recipient.username if self.recipient else None
        }
class Content(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    file_path = db.Column(db.String(300), nullable=True)
    url = db.Column(db.String(300), nullable=True)
    description = db.Column(db.String(500), nullable=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

with app.app_context(): 
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/debug_session', methods=['GET'])
def debug_session():
    user_id = session.get('user_id')
    return jsonify({"user_id": user_id})

# Utility function to send a confirmation email using SendGrid
def send_email(receiver_email, subject, body):
    sender_email = "vijay211104@gmail.com"
    password = "gimr zpgt vofw wsve" 
    if not sender_email or not password:
        raise Exception("Email credentials are not set in environment variables.")
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        print("Email sent successfully!")
    except smtplib.SMTPAuthenticationError:
        print("Authentication error. Check your email and password.")
        raise
    except Exception as e:
        print(f"Error occurred: {e}")
        raise

# Route for signup
@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({"error": "All fields are required!"}), 400

    try:
        # Validate email
        valid = validate_email(email)
        email = valid.email
    except EmailNotValidError as e:
        return jsonify({"error": f"Invalid email address: {str(e)}"}), 400

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({"error": "Username or email already exists!"}), 409

    hashed_password = generate_password_hash(password)
    new_user = User(username=username, email=email, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    # Set session for the new user
    session['user_id'] = new_user.id

    # Send email notification
    subject = "Signup Confirmation"
    body = f"Welcome {username},\n\nThank you for signing up. You can now log in and use our services.\n\nBest Regards,\nSOC Team"
    try:
        send_email(email, subject, body)
        flash("Signup Successful! Confirmation Email Sent", "success")
    except Exception as e:
        print(f"Email sending failed: {e}")
        flash("Signup Successful! But email confirmation failed.", "warning")

    return redirect(url_for('edit_profile', user_id=new_user.id))  # Redirect to profile page


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({"error": "Invalid username or password!"}), 401

    session['user_id'] = user.id
    return redirect(url_for('homepage'))  # Redirect to homepage

@app.route('/profile/<int:user_id>', methods=['GET', 'POST'])
def get_profile(user_id):
    user = db.session.get(User, user_id)  # Updated to use Session.get
    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == 'POST':
        bio = request.form.get('bio')
        if bio:
            user.bio = bio

        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            user.profile_picture = file_path

        db.session.commit()
        return redirect(url_for('homepage'))

    return render_template('profile.html', user=user.to_dict(), user_id=user_id)

@app.route('/profile/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_profile(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == 'POST':
        bio = request.form.get('bio')
        website = request.form.get('website')
        gender = request.form.get('gender')
        show_suggestions = request.form.get('showSuggestions', 'off') == 'on'

        if bio:
            user.bio = bio
        if website:
            user.website = website
        if gender:
            user.gender = gender
        user.show_suggestions = show_suggestions

        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            user.profile_picture = file_path

        db.session.commit()
        return redirect(url_for('get_profile', user_id=user.id))

    return render_template('edit.html', user=user.to_dict())

    
@app.route('/homepage', methods=['GET'])
def homepage():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('index'))

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return render_template('homepage.html', user=user.to_dict())


# Get user settings
# Main Settings Page
@app.route('/settings/<int:user_id>')
def settings_main(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return render_template('settings.html', user=user.to_dict())

# Routes for other settings pages
@app.route('/settings/account', methods=['GET', 'PUT'])
def settings_account():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == 'GET':
        return render_template('account.html', user=user.to_dict())
    elif request.method == 'PUT':
        data = request.json
        username = data.get('username', user.username)
        email = data.get('email', user.email)
        if User.query.filter(User.id != user_id, (User.username == username) | (User.email == email)).first():
            return jsonify({"error": "Username or email already exists!"}), 409
        user.username = username
        user.email = email
        db.session.commit()
        return jsonify({"message": "Account settings updated successfully"})


@app.route('/settings/appearance', methods=['GET', 'PUT'])
def settings_appearance():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == 'GET':
        return render_template('appearance.html', user=user.to_dict())
    elif request.method == 'PUT':
        # Handle appearance settings update logic here
        return jsonify({"message": "Appearance settings updated successfully"})


@app.route('/settings/privacy', methods=['GET', 'PUT'])
def settings_privacy():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == 'GET':
        return render_template('privacy.html', user=user.to_dict())
    elif request.method == 'PUT':
        data = request.json
        user.private_account = data.get('private_account', user.private_account)
        db.session.commit()
        return jsonify({"message": "Privacy settings updated successfully"})


@app.route('/settings/notifications', methods=['GET', 'PUT'])
def settings_notifications():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == 'GET':
        return render_template('notifications.html', user=user.to_dict())
    elif request.method == 'PUT':
        data = request.json
        user.notifications_enabled = data.get('notifications_enabled', user.notifications_enabled)
        db.session.commit()
        return jsonify({"message": "Notification settings updated successfully"})


@app.route('/settings/friendship', methods=['GET', 'PUT'])
def settings_friendship():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == 'GET':
        return render_template('friendship.html', user=user.to_dict())
    elif request.method == 'PUT':
        data = request.json
        user.close_friends = ','.join(data.get('close_friends', user.close_friends.split(',')))
        db.session.commit()
        return jsonify({"message": "Friendship settings updated successfully"})


@app.route('/settings/linked_accounts', methods=['GET', 'PUT'])
def settings_linked_accounts():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == 'GET':
        return render_template('linked_accounts.html', user=user.to_dict())
    elif request.method == 'PUT':
        # Handle linked accounts update logic here
        return jsonify({"message": "Linked accounts updated successfully"})


@app.route('/settings/advertising_preferences', methods=['GET', 'PUT'])
def settings_advertising_preferences():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == 'GET':
        return render_template('advertising_preferences.html', user=user.to_dict())
    elif request.method == 'PUT':
        # Handle advertising preferences update logic here
        return jsonify({"message": "Advertising preferences updated successfully"})


@app.route('/settings/activity_settings', methods=['GET', 'PUT'])
def settings_activity_settings():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == 'GET':
        return render_template('activity_settings.html', user=user.to_dict())
    elif request.method == 'PUT':
        # Handle activity settings update logic here
        return jsonify({"message": "Activity settings updated successfully"})


@app.route('/settings/help_support', methods=['GET'])
def settings_help_support():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return render_template('help_support.html', user=user.to_dict())


@app.route('/settings/advanced_options', methods=['GET'])
def settings_advanced_options():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return render_template('advanced_options.html', user=user.to_dict())


@app.route('/settings/experiment_settings', methods=['GET'])
def settings_experiment_settings():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return render_template('experiment_settings.html', user=user.to_dict())

@app.route('/settings/content', methods=['GET', 'PUT'])
def settings_content():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == 'GET':
        # Render the content settings page
        return render_template('content.html', user=user.to_dict())

    elif request.method == 'PUT':
        # Example: Handle content visibility updates
        data = request.json
        content_visibility = data.get('content_visibility')  # Example field
        if content_visibility:
            # Save the content visibility setting (assuming such a field exists in your User model)
            user.content_visibility = content_visibility
            db.session.commit()

        return jsonify({"message": "Content settings updated successfully"})

@app.route('/settings/security', methods=['GET', 'PUT'])
def settings_security():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == 'GET':
        # Render the security settings page
        return render_template('security.html', user=user.to_dict())

    elif request.method == 'PUT':
        # Example: Handle updates to security settings
        data = request.json
        two_factor_enabled = data.get('two_factor_enabled')  # Example field
        if two_factor_enabled is not None:
            # Save the two-factor authentication setting (assuming such a field exists in your User model)
            user.two_factor_enabled = two_factor_enabled
            db.session.commit()

        return jsonify({"message": "Security settings updated successfully"})

@app.route('/api/fetch_posts', methods=['GET'])
def fetch_posts():
    # Fetch posts from JSONPlaceholder API
    try:
        response = requests.get('https://dummyjson.com/posts')
        response.raise_for_status()
        posts = response.json()

        # Return the fetched posts
        return jsonify(posts[:10])  # Limit to 10 posts for simplicity
    except requests.RequestException as e:
        logging.error(f"Error fetching posts: {e}")
        return jsonify({"error": "Failed to fetch posts"}), 500

@app.route('/api/trending', methods=['GET'])
def get_trending():
    trending_topics = [
        {"name": "#Coolie", "postsCount": "23.1K"},
        {"name": "#NagpurViolence", "postsCount": "50.5K"},
        {"name": "#Paytm", "postsCount": "19.2K"}
    ]
    return jsonify(trending_topics)

@app.route('/explore', methods=['GET'])
def explore_page():
    return render_template('explore.html')

@app.route('/api/search-users', methods=['GET'])
def search_users():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify([])  # Return an empty list if no query is provided

    # Perform case-insensitive search for users by username or email
    users = User.query.filter(
        User.username.ilike(f'%{query}%') | User.email.ilike(f'%{query}%')
    ).all()

    # Convert the results to dictionaries
    user_data = [{'id': user.id, 'username': user.username, 'email': user.email} for user in users]
    return jsonify(user_data)


@app.route('/users', methods=['GET'])
def get_users():
    query = request.args.get('username', '').strip()
    if query:
        users = User.query.filter(User.username.ilike(f'%{query}%')).all()
    else:
        users = User.query.all()
    return jsonify([{"id": user.id, "username": user.username} for user in users])

@app.route('/current-user', methods=['GET'])
def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"id": user.id, "username": user.username, "email": user.email})

@app.route('/messages/<int:recipient_id>', methods=['GET', 'POST'])
def messages(recipient_id):
    logged_in_user_id = session.get('user_id')
    if not logged_in_user_id:
        return jsonify({"error": "User not logged in"}), 401

    if request.method == 'POST':
        text = request.json.get('message_text', '').strip()
        if text:
            new_message = Message(
                sender_id=logged_in_user_id,
                recipient_id=recipient_id,
                text=text
            )
            db.session.add(new_message)
            db.session.commit()
            return jsonify({"success": True}), 201

    messages = Message.query.filter(
        ((Message.sender_id == logged_in_user_id) & (Message.recipient_id == recipient_id)) |
        ((Message.sender_id == recipient_id) & (Message.recipient_id == logged_in_user_id))
    ).order_by(Message.timestamp).all()

    return jsonify([{
        "sender_id": msg.sender_id,
        "recipient_id": msg.recipient_id,
        "text": msg.text,
        "timestamp": msg.timestamp.isoformat()
    } for msg in messages])


@app.route('/messages/', methods=['GET', 'POST'])
def new():
    return render_template('m_c.html')

@app.route('/api/posts', methods=['GET'])
def api_posts():
    try:
        # Fetch images from Picsum API
        response = requests.get('https://picsum.photos/v2/list?page=2&limit=100')
        response.raise_for_status()
        picsum_data = response.json()

        # Format the posts data
        posts = []
        for idx, pic in enumerate(picsum_data):
            posts.append({
                "id": idx + 1,
                "title": f"Photo by {pic['author']}",
                "body": "A beautiful random image from Picsum.",
                "img": f"{pic['download_url']}?w=100&h=100",
                "tags": ["nature", "random", "picsum"],  # Example tags
                "reactions": {"likes": idx % 100 + 1}  # Example reaction count
            })

        # Return formatted posts as JSON
        return jsonify({"posts": posts})

    except requests.RequestException as e:
        return jsonify({"error": "Failed to fetch posts from Picsum API", "details": str(e)}), 500

@app.route('/upload-content', methods=['POST'])
def upload_content():
    user_id = request.form.get('user_id')
    description = request.form.get('description', '')

    if 'file' in request.files:
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            new_content = Content(user_id=user_id, file_path=file_path, description=description)
            db.session.add(new_content)
            db.session.commit()
            return jsonify({"message": "File uploaded successfully!"}), 201

    if 'url' in request.form:
        url = request.form['url']
        new_content = Content(user_id=user_id, url=url, description=description)
        db.session.add(new_content)
        db.session.commit()
        return jsonify({"message": "URL added successfully!"}), 201

    return jsonify({"error": "No valid file or URL provided."}), 400

@app.route('/content', methods=['GET'])
def get_content():
    contents = Content.query.all()
    return jsonify([{
        "id": content.id,
        "user_id": content.user_id,
        "file_path": content.file_path,
        "url": content.url,
        "description": content.description
    } for content in contents])

@app.route('/upload-content', methods=['GET'])
def upload_content_page():
    return render_template('upload_content.html') 

@app.route('/api/user-content/<int:user_id>', methods=['GET'])
def get_user_content(user_id):
    """Fetch all content for a specific user."""
    content = Content.query.filter_by(user_id=user_id).all()
    return jsonify([
        {"id": item.id, "file_path": item.file_path, "url": item.url, "description": item.description}
        for item in content
    ])

@app.route('/api/all-content', methods=['GET'])
def get_all_content():
    """Fetch all content for the homepage."""
    content = Content.query.all()
    return jsonify([
        {"id": item.id, "file_path": item.file_path, "url": item.url, "description": item.description}
        for item in content
    ])

@app.route('/api/delete-content/<int:post_id>', methods=['DELETE'])
def delete_content(post_id):
    content = Content.query.get(post_id)
    if content:
        db.session.delete(content)
        db.session.commit()
        return jsonify({'message': 'Post deleted successfully'}), 200
    else:
        return jsonify({'error': 'Post not found'}), 404

@app.route('/api/mutual-suggestions', methods=['GET'])
def mutual_suggestions():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    # Check if database is empty (no users other than current user)
    total_users = User.query.count()
    if total_users <= 1:
        try:
            sample_users = [
                User(
                    username='alice',
                    email='alice@example.com',
                    password=generate_password_hash('pass123'),
                    close_friends='bob,carol',
                    profile_picture='static/uploads/default_profile.png'
                ),
                User(
                    username='bob',
                    email='bob@example.com',
                    password=generate_password_hash('pass123'),
                    close_friends='alice,carol,dave',
                    profile_picture='static/uploads/default_profile.png'
                ),
                User(
                    username='carol',
                    email='carol@example.com',
                    password=generate_password_hash('pass123'),
                    close_friends='alice,bob',
                    profile_picture='static/uploads/default_profile.png'
                ),
                User(
                    username='dave',
                    email='dave@example.com',
                    password=generate_password_hash('pass123'),
                    close_friends='bob',
                    profile_picture='static/uploads/default_profile.png'
                ),
                User(
                    username='eve',
                    email='eve@example.com',
                    password=generate_password_hash('pass123'),
                    close_friends='carol',
                    profile_picture='static/uploads/default_profile.png'
                ),
            ]

            db.session.bulk_save_objects(sample_users)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Failed to seed users: {str(e)}"}), 500

    current_user = User.query.get(user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    current_user_friends = set(current_user.close_friends.split(',')) if current_user.close_friends else set()

    suggestions = []

    all_users = User.query.filter(User.id != user_id).all()
    for user in all_users:
        other_user_friends = set(user.close_friends.split(',')) if user.close_friends else set()
        mutuals = current_user_friends & other_user_friends

        if mutuals:
            suggestions.append({
                "id": user.id,
                "username": user.username,
                "mutual_count": len(mutuals),
                "mutual_friends": list(mutuals),
                "profile_picture": user.profile_picture
            })

    # Sort by number of mutual friends (descending)
    suggestions.sort(key=lambda x: x["mutual_count"], reverse=True)

    return jsonify(suggestions)


if __name__ == '__main__':
    # Set your SendGrid API key as an environment variable
    os.environ['SENDGRID_API_KEY'] = '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'  # Replace with your actual API key
    #socketio.run(app, debug=True)
    app.run(debug=True)