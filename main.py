import os
from typing import List
from dotenv import load_dotenv
load_dotenv()

MY_EMAIL = os.environ['MY_EMAIL']
MY_PASSWORD = os.environ['MY_PASSWORD']
print(MY_EMAIL, MY_PASSWORD)
SECRET_KEY = os.environ['SECRET_KEY']
SQLALCHEMY_DATABASE_URI = os.environ['SQLALCHEMY_DATABASE_URI']

from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Text, ForeignKey

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, EmailField, IntegerField
from wtforms.validators import DataRequired # pip install email-validator
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor, CKEditorField
from flask_gravatar import Gravatar
from datetime import date

import smtplib

class RegisterForm(FlaskForm):
    email = EmailField(label='Email', validators=[DataRequired()])
    password = PasswordField(label='Password', validators=[DataRequired()])
    name = StringField(label='Name', validators=[DataRequired()])
    submit = SubmitField(label='SIGN ME UP!')
    
class LoginForm(FlaskForm):
    email = EmailField(label='Email', validators=[DataRequired()])
    password = PasswordField(label='Password', validators=[DataRequired()])
    submit = SubmitField(label='LET ME IN!')

class PostForm(FlaskForm):
    title = StringField(label='Blog Post Title', validators=[DataRequired()])
    subtitle = StringField(label='Subtitle', validators=[DataRequired()])
    image_url = StringField(label='Blog Image URL',
                            validators=[DataRequired()])
    body = CKEditorField(label='Blog Content', validators=[DataRequired()])
    submit = SubmitField(label='Submit Post')

class CommentForm(FlaskForm):
    body = CKEditorField(label='Comment', validators=[DataRequired()])
    submit = SubmitField(label='Submit Comment')


app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
ckeditor = CKEditor(app)
Bootstrap5(app)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
# Create the extension
db = SQLAlchemy(model_class=Base)
# initialise the app with the extension
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


# CREATE USER TABLE
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(250))
    name: Mapped[str] = mapped_column(String(100))    
    posts: Mapped[List["Post"]] = relationship('Post', back_populates='author')
    comments: Mapped[List["Comment"]] = relationship('Comment', back_populates='author')
        

# CREATE POST TABLE
class Post(db.Model):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'))
    author: Mapped["User"] = relationship('User', back_populates='posts')
    title: Mapped[str] = mapped_column(
        String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[float] = mapped_column(String(250), nullable=False)
    comments: Mapped[List["Comment"]] = relationship('Comment', back_populates='post')
        
        
# CREATE COMMENT TABLE
class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'))
    author: Mapped["User"] = relationship('User', back_populates='comments')
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey('posts.id'))
    post: Mapped["Post"] = relationship('Post', back_populates='comments')
    body: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[float] = mapped_column(String(250), nullable=False)
    

# For adding profile images to the comment section
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


# Create table schema in the database. Requires application context.
with app.app_context():
    db.create_all()


@app.route('/')
def get_all_posts():
    # READ ALL RECORDS
    # Construct a query to select from the database. Returns the rows in the database
    result = db.session.execute(db.select(Post).order_by(Post.date))
    # Use .scalars() to get the elements rather than entire rows from the database
    all_posts = result.scalars().all()
    return render_template("index.html", logged_in=current_user.is_authenticated, posts=all_posts, user=current_user)
    # return render_template("secrets.html", name=current_user.name, logged_in=True)


@app.route('/register', methods=["GET", "POST"])
def register():
    register_form = RegisterForm()
    if register_form.validate_on_submit():
        
        email = register_form.email.data
        result = db.session.execute(db.select(User).where(User.email == email))

        # Note, email in db is unique so will only have one result.
        user = result.scalar()
        if user:
            # User already exists
            flash("You've already signed up with that email, log in instead!", category="error")
            return redirect(url_for('login'))

        hash_and_salted_password = generate_password_hash(
            register_form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=register_form.email.data,
            password=hash_and_salted_password,
            name=register_form.name.data,
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("get_all_posts"))

    return render_template("register.html", logged_in=current_user.is_authenticated, register_form=register_form)


@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        
        email = login_form.email.data
        password = login_form.password.data

        result = db.session.execute(db.select(User).where(User.email == email))
        user = result.scalar()
        # Email doesn't exist or password incorrect.
        if not user:
            flash("That email does not exist, please try again.", "error")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.', 'error')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))

    return render_template("login.html", logged_in=current_user.is_authenticated, login_form=login_form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def get_post(post_id):
    requested_post = db.get_or_404(Post, post_id)
    add_comment_form = CommentForm()
    if add_comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.", 'error')
            return redirect(url_for("login"))
        
        add_comment(requested_post, add_comment_form)
        flash("Your comment has been added.")
    return render_template("post.html", logged_in=current_user.is_authenticated, post=requested_post, user=current_user, add_comment_form=add_comment_form)


def add_comment(post, form):
    new_comment = Comment(
        author_id=current_user.id,
        author=current_user,
        post_id=post.id,
        post=post,
        body=form.body.data,
        date=date.today().strftime("%B %d, %Y"))
    db.session.add(new_comment)
    db.session.commit()
    return redirect(url_for('get_post',  post_id=post.id))


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_post():
    add_post_form = PostForm()
    if add_post_form.validate_on_submit():
        new_post = Post(
            title=add_post_form.title.data,
            subtitle=add_post_form.subtitle.data,
            author_id=current_user.id,
            author=current_user,
            image_url=add_post_form.image_url.data,
            body=add_post_form.body.data,
            date=date.today().strftime("%B %d, %Y"))
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('get_all_posts'))
    return render_template("update.html", logged_in=current_user.is_authenticated, add_form=add_post_form)


@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
@login_required
def edit_post(post_id):
    post_to_update = db.get_or_404(Post, post_id)
    edit_post_form = PostForm(
        title=post_to_update.title,
        subtitle=post_to_update.subtitle,
        image_url=post_to_update.image_url,
        body=post_to_update.body)
    
    if edit_post_form.validate_on_submit():
        # UPDATE RECORD
        post_to_update.subtitle = edit_post_form.subtitle.data
        post_to_update.image_url = edit_post_form.image_url.data
        post_to_update.body = edit_post_form.body.data
        # post_to_update.date=date.today().strftime("%B %d, %Y")
        db.session.commit()
        return redirect(url_for('get_post', post_id=post_to_update.id))
    
    return render_template("update.html", logged_in=current_user.is_authenticated, edit_form=edit_post_form)


@app.route("/delete")
@login_required
def delete_post():
    post_id = request.args.get('post_id')

    # DELETE A RECORD BY ID
    post_to_delete = db.get_or_404(Post, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route('/about')
def about():
    return render_template("about.html", logged_in=current_user.is_authenticated)


@app.route('/contact', methods=["GET", "POST"])
def contact():
    if request.method == 'POST':
        data = request.form
        send_email(data['name'], data['email'], data['phone'], data['message'])
        return render_template("contact.html", msg_sent=True)
    return render_template("contact.html", logged_in=current_user.is_authenticated, msg_sent=False)


def send_email(name, email, phone, message):
    with smtplib.SMTP("smtp.gmail.com") as connection:
        connection.starttls()
        connection.login(MY_EMAIL, MY_PASSWORD)
        connection.sendmail(
            from_addr=MY_EMAIL,
            to_addrs=MY_EMAIL,
            msg=f"Subject:New Message\n\nName: {name}\nEmail: {email}\nPhone: {phone}\nMessage:{message}"
        )


if __name__ == "__main__":
    app.run(debug=False)
    # app.run(debug=True, host="localhost", port="5000")
    # app.run(debug=True, host='0.0.0.0'). # I can immediately view the results on the mobile phone. ;)
