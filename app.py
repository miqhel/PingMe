from flask import Flask, flash, request, render_template, redirect, session, send_from_directory, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql.expression import func
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message, Mail
import os

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
#mail config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'Cesca1Mul@gmail.com'   # replace or use env var
app.config['MAIL_PASSWORD'] = 'rpqg ctjg vdru zsli'      # replace or use env var
app.config["MAIL_DEBUG"] = True
app.config["ALLOWED_EXTENSIONS"] = [".jpg", ".png", ".jpeg", ".gif", ".mp4", 'mov', 'webm']
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["SECRET_KEY"] = "replace_with_env_secret"

db = SQLAlchemy(app)
mail = Mail(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    profile_pic = db.Column(db.String(200), nullable=True)
    likes = db.relationship("Like", backref="user")
    posts = db.relationship("Post", backref="user")
    comments = db.relationship("Comment", backref="user")
    followers = db.relationship(
    "Follow",
    foreign_keys="Follow.followed_id",
    backref="followed",
    lazy="dynamic"
)

following = db.relationship(
    "Follow",
    foreign_keys="Follow.follower_id",
    backref="follower",
    lazy="dynamic"
)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    attachment = db.Column(db.String(200), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    likes = db.relationship("Like", backref="post")
    comments = db.relationship("Comment", backref="post")


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)    
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    

@app.route('/')
def index():
    if "user_id" not in session:
        posts = Post.query.order_by(func.random()).all()
        return render_template("index.html", posts=posts)

    posts = Post.query.order_by(Post.id.desc()).all()
    return render_template("index.html", posts=posts, Follow=Follow, user = session["user_id"])

@app.route("/likes/<int:post_id>", methods=["POST"])
def like(post_id):
    if "user_id" not in session:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Please login!"}), 401
        flash("Please login!", "warning")
        return redirect(url_for("login"))

    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=session["user_id"], post_id=post_id).first()
    liked = False

    if like:
        db.session.delete(like)
    else:
        new_like = Like(user_id=session["user_id"], post_id=post_id)
        db.session.add(new_like)
        liked = True

    db.session.commit()

    # If AJAX, return JSON instead of redirect
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "liked": liked,
            "like_count": len(post.likes)
        })

    return redirect(url_for("index"))


@app.route("/comment/<int:post_id>", methods=["POST"])
def comment(post_id):
    if "user_id" not in session:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Please login!"}), 401
        flash("Please login to comment!", "warning")
        return redirect(url_for("login"))

    content = request.form.get("content")
    if not content or content.strip() == "":
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Comment cannot be empty!"}), 400
        flash("Comment cannot be empty!", "error")
        return redirect(url_for("index"))

    post = Post.query.get_or_404(post_id)
    new_comment = Comment(
        content=content,
        post_id=post.id,
        user_id=session["user_id"]
    )
    db.session.add(new_comment)
    db.session.commit()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "success": True,
            "comment": {
                "username": new_comment.user.username,
                "content": new_comment.content
            },
            "comment_count": len(post.comments)
        })

    flash("Comment added successfully!", "success")
    return redirect(url_for("index"))


@app.route("/follow/<int:post_id>", methods=["POST"])
def follow(post_id):
    if "user_id" not in session:
        flash("Please login", "warning")
        return redirect(url_for("login"))

    post = Post.query.get_or_404(post_id)
    author = post.user

    follow = Follow.query.filter_by(
        follower_id=session["user_id"],
        followed_id=author.id
    ).first()

    if follow:
        db.session.delete(follow)
        flash(f"You unfollowed {author.username}", "info")
    else:
        new_follow = Follow(follower_id=session["user_id"], followed_id=author.id)
        db.session.add(new_follow)
        flash(f"You are now following {author.username}!", "success")

    db.session.commit()
    return redirect(url_for("index"))

        


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        files = request.files.get("profile_pic")

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash("Username or email already exists.", "error")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)
        filename = None
        try:
            if files and files.filename != "":
                extension = os.path.splitext(files.filename)[1].lower()
                if extension not in app.config["ALLOWED_EXTENSIONS"]:
                    flash("Invalid file type for profile picture.", "error")
                    return redirect(url_for("register"))
                filename = secure_filename(files.filename)
                files.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            else:
                filename = None
        except Exception as e:
            flash(f"File upload error: {str(e)}", "error")
            return redirect(url_for("register"))            
        new_user = User(username=username, email=email, password=hashed_password, profile_pic=filename)
        db.session.add(new_user)
        db.session.commit()
        try:
            msg = Message("Welcome to Our Platform", sender="Cesca1Mul@gmail.com", recipients=[email])
            msg.body = f"Hello {username},\n\nWelcome to our platform! We're glad to have you here.\n\nBest,\nThe Team"
            mail.send(msg)
        except Exception as e:
            flash(f"Error sending email: {str(e)}", "error")

        flash("Registration successful! Please check your email.", "success")
        return redirect(url_for("login"))
    
    return render_template("register.html")

@app.route("/login", methods=["POST","GET"])
def login():
    if request.method == "POST":
        username=request.form.get("username")
        password=request.form.get("password")

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username
            flash("Login successful","success")
            return redirect(url_for("dashboard"))
        flash("user not found!","warning")
        return redirect(url_for("login"))
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = User.query.filter_by(id = session["user_id"]).first()
    posts = Post.query.filter_by(user_id=session["user_id"]).all()
    followers = (
    db.session.query(User)
    .join(Follow, User.id == Follow.follower_id)
    .filter(Follow.followed_id == session["user_id"])
    .all()
)


    return render_template("dashboard.html", user=user, username=session["username"], posts=posts, followers=followers)

@app.route("/create_post", methods=["POST","GET"])
def create_post():
    if "user_id" in session:
        if request.method == "POST":
            content = request.form.get("content")
            files = request.files.get("attachment")
            filename = None
            try:
                if files and files.filename != "":
                    extension = os.path.splitext(files.filename)[1].lower()
                    if extension not in app.config["ALLOWED_EXTENSIONS"]:
                        flash("File type not supported")
                        return redirect(url_for("create_post"))
                    filename = secure_filename(files.filename)
                    files.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                else:
                    filename = None
            except Exception as e:
                flash(f"File upload error: {str(e)}", "error")
                return redirect(url_for("create_post"))   
            new_post = Post(content=content, attachment = filename, user_id = session["user_id"])  
            db.session.add(new_post)
            db.session.commit()          
            flash("Posted Successfully!","success")
            return redirect(url_for("dashboard"))
        return render_template("create_post.html")
    flash("Please Login!","warning")
    return redirect(url_for("login"))

@app.route("/user/<int:user_id>")
def user_profile(user_id):
    user = User.query.get_or_404(user_id)
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.id.desc()).all()
    is_following = False
    if "user_id" in session:
        is_following = Follow.query.filter_by(follower_id=session["user_id"], followed_id=user.id).first() is not None
    return render_template("user_profile.html", user=user, posts=posts, is_following=is_following, Follow=Follow)

@app.route("/search_api")
def search_api():
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify([])

    results = User.query.filter(User.username.ilike(f"%{query}%")).all()

    # Return id, username, and optionally profile_pic for dropdown
    return jsonify([
        {
            "id": user.id,
            "username": user.username,
            "profile_pic": user.profile_pic  # can be null
        } 
        for user in results
    ])




@app.route("/<int:id>/edit", methods=["GET", "POST"])
def edit_post(id):
    if "user_id" not in session:
        flash("Please login first!", "warning")
        return redirect(url_for("login"))


    post = Post.query.get_or_404(id)

    # Ensure only the owner can edit
    if post.user_id != session["user_id"]:
        flash("You are not authorized to edit this post.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        post.content = request.form.get("content")

        # Check if a new attachment was uploaded
        if "attachment" in request.files:
            file = request.files["attachment"]
            if file and file.filename != "":
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)

                # Replace old attachment (optional: delete old file)
                post.attachment = filename

        db.session.commit()
        flash("Post updated 🎉", "success")
        return redirect(url_for("dashboard"))

    return render_template("edit_post.html", post=post)




@app.route("/<int:id>/delete", methods=["POST"])
def delete_post(id):
    if "user_id" in session:
        post = Post.query.filter_by(id=id).first()
        db.session.delete(post)
        db.session.commit()
        flash("Post Deleted!","success")
        return redirect(url_for("index"))
    flash("Please Login!","warning")
    return redirect(url_for("login"))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]   


@app.route("/logout")
def logout():
    if "user_id" in session:
        session.clear()
        flash("Logout succesful!","success")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))  # Render assigns a port
    app.run(host="0.0.0.0", port=port)    


