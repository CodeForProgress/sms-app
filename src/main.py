from flask import Flask, render_template, request, url_for, redirect, flash
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required, current_user, roles_required
from flask_mail import Mail, Message
from flask_security.forms import RegisterForm, LoginForm, ChangePasswordForm
from wtforms import StringField
from wtforms.validators import Required, InputRequired


import psycopg2
import string
import random


# Create app
app = Flask(__name__)

# Setup Flask-Mail


app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'super-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://localhost/sms-app'

app.config['SECURITY_REGISTERABLE'] = False 
app.config['SECURITY_RECOVERABLE'] = True 
app.config['SECURITY_CHANGEABLE'] = True 
app.config['SECURITY_CONFIRMABLE'] = False
app.config['USER_REQUIRE_INVITATION'] = True
app.config['USER_ENABLE_EMAIL'] = True
# app.config['SECURITY_PASSWORD_HASH'] = True

app.config['SECURITY_EMAIL_SUBJECT_REGISTER'] = "Welcome to Political SMS App"
app.config['SECURITY_EMAIL_SUBJECT_PASSWORD_NOTICE'] = "Your Political SMS App Password Has Changed."
app.config['SECURITY_EMAIL_SUBJECT_PASSWORD_RESET'] = "Change Your Political SMS App Password"
app.config['SECURITY_EMAIL_SUBJECT_PASSWORD_CHANGE_NOTICE'] = "Your Political SMS Password Has Been Changed"
app.config['SECURITY_EMAIL_SUBJECT_CONFIRM'] = "Confirm Your Political SMS Email"

# app.config['SECURITY_USER_IDENTITY_ATTRIBUTES'] =  ('phone_number', 'email')

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_DEBUG'] = True
app.config['MAIL_USERNAME'] = 'ronesha@codeforprogress.org'
app.config['MAIL_PASSWORD'] = '\\\\'
app.config['MAIL_DEFAULT_SENDER'] = 'ronesha@codeforprogress.org'

mail = Mail(app)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True


# Create database connection object
db = SQLAlchemy(app)

# Define models
roles_users = db.Table('roles_users',
        db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
        db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))

class ExtendedRegisterForm(RegisterForm):
    first_name = StringField('First Name', [Required()])
    last_name = StringField('Last Name', [Required()])
    phone_number = StringField('Phone Number', [Required()])

class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    phone_number = db.Column(db.String(), unique=True)
    shift = db.Column(db.String(255))
    van = db.Column(db.Integer())
    password = db.Column(db.String(255))
    temp_pass = db.Column(db.Boolean())
    on_shift = db.Column(db.Boolean())
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))

# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore, register_form=ExtendedRegisterForm)



# Create a user to test with
# @app.before_first_request
# def create_user():
#     db.create_all()
#     user_datastore.create_user(email='ronesha@codeforprogress.org', password='password')
#     db.session.commit()

#methods 
def id_generator(size=10, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.SystemRandom().choice(chars) for _ in range(size))

# Views
@app.route('/')
@login_required
def home():
    if current_user.temp_pass == True:
        db.session.query(User).filter_by(id = current_user.id).update({'temp_pass': (False)})
        db.session.commit()
        return render_template('security/change_password.html', change_password_form = ChangePasswordForm())
    else: 
        return render_template('index.html')

@app.route('/logout')
def logout():
    logout()
    return render_template('index.html')

@app.route('/addRegional', methods=['GET', 'POST'])
@roles_required('state')
def addRegional():
    print current_user.roles[0].name
    if request.method == "POST":
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phone_number = request.form['phone_number']

        password = id_generator()

        new_user = User(first_name = first_name, 
            last_name = last_name, 
            email = email, 
            phone_number=phone_number, 
            password = password, 
            active = True, 
            temp_pass = True
            )
        new_role = db.session.query(Role).filter_by(name = 'regional').first()
        new_user.roles.append(new_role)

        url = 'http://3073f486.ngrok.io'

        message = Message("Confirm Your Account", recipients=[email])
        message.body = """Dear %s %s, \n\n
        You've been registered as a Regional Supervisor by %s %s. \n\n
        Please login to your account at %s using the password here: %s. \n\n
        Thank you. """ %(first_name, last_name, current_user.first_name, current_user.last_name, url, password) 
        mail.send(message)

        db.session.add(new_user)
        db.session.commit()

        flash("You've successfully added %s %s as a regional supervisor." %(first_name, last_name))

        return redirect(url_for('addRegional'))

    return render_template('regional.html')


@app.route('/addTeamLeader', methods=['GET', 'POST'])
def addTeamLeader():

    if current_user.roles[0].name == "state" or current_user.roles[0].name == "regional":
        if request.method == "POST":
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            email = request.form['email']
            phone_number = request.form['phone_number']
            van = request.form['van']

            password = id_generator()

            new_user = User(first_name = first_name, 
                last_name = last_name, 
                email = email, 
                phone_number=phone_number, 
                van = van, 
                password = password, 
                active = True,
                temp_pass = True
                )
            new_role = db.session.query(Role).filter_by(name = 'teamlead').first()
            new_user.roles.append(new_role)
            db.session.add(new_user)

            url = 'http://3073f486.ngrok.io'

            message = Message("Confirm Your Account", recipients=[email])
            message.body = """Dear %s %s, \n\n
            You've been registered as a Team Leader by %s %s. \n\n
            Please login to your account at %s using the password here: %s. \n\n
            Thank you. """ %(first_name, last_name, current_user.first_name, current_user.last_name, url, password) 
            mail.send(message)


            db.session.commit()
            flash("You've successfully added %s %s as a Team Leader." %(first_name, last_name))
            return redirect(url_for('addTeamLeader'))
        return render_template('teamlead.html')
    else: 
        flash("You do not have permission to view this resource.")
        return redirect(url_for('home'))

@app.route('/addTeamMember', methods=['GET', 'POST'])
def addTeamMember():

    if current_user.roles[0].name == "state" or current_user.roles[0].name == "regional" or current_user.roles[0] == "teamlead":
        if request.method == "POST":
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            email = request.form['email']
            phone_number = request.form['phone_number']
            van = request.form['van']
            shift = request.form['shift']

            new_user = User(first_name = first_name, 
                last_name = last_name, 
                phone_number=phone_number, 
                van = van, 
                shift = shift,
                active = True,
                on_shift = False
                )
            new_role = db.session.query(Role).filter_by(name = 'member').first()
            new_user.roles.append(new_role)
            db.session.add(new_user)
            db.session.commit()
            flash("You've successfully added %s %s as a Team Member." %(first_name, last_name))
            return redirect(url_for('addTeamMember'))
        return render_template('teammember.html')
    else:
        flash("You do not have permission to view this resource.")
        return redirect(url_for('home'))


if __name__ == '__main__':
    app.run()