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


from flask import Flask, request, session, Response

import logging
from functools import wraps
import  pprint
import json 
import random
import string

from twilio import twiml
from twilio.rest import TwilioRestClient



# Create app
app = Flask(__name__)

# Setup Flask-Mail


app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'super-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://postgres@localhost/sms-app'

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
app.config['MAIL_PASSWORD'] = '07cb77nesh'
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



# # Create a user to test with
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
    # print current_user
    if current_user.temp_pass == True:
        db.session.query(User).filter_by(id = current_user.id).update({'temp_pass': (False)})
        db.session.commit()
        return render_template('security/change_password.html', change_password_form = ChangePasswordForm())
    else: 
        return render_template('index.html')
    # return current_user

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


@app.route("/sms", methods=["GET","POST"])
def get_text():
    from flask import Flask, request, session, Response
    from twilio import twiml
    from twilio.rest import TwilioRestClient

    SECRET_KEY = "u092i3049034"

    app = Flask(__name__)
    app.config.from_object(__name__)

    # Find these values at https://twilio.com/user/account
    account_sid = "ACaaaadf1975e4dcc6dde6d42ddda6743e"
    auth_token = "8b17826f30ea9747c8a3c381e198b196"
    client = TwilioRestClient(account_sid, auth_token)

    TWILIO_NUMBER="+13474078862"

    team_leads_contact = db.session.query(User).join(User.roles).filter(Role.name=="teamlead").all()
    state_leader = db.session.query(User).join(User.roles).filter(Role.name=="statelead").all()
    team_lead = db.session.query(User).join(User.roles).filter(Role.name=="teamlead").all()
    reg_lead = db.session.query(User).join(User.roles).filter(Role.name=="regional").all()
    
    response = twiml.Response()
    inbound_msg_body = request.form.get("Body")
    inbound_msg_from = request.form.get("From")
    menu = "Press 1 to report an emergency \n Press 2 to report an emergency \n"

    # response_msg = "Yo, %s" %(callers[inbound_msg_from])

    # response.message(response_msg)
    
    activate_session=session.get("activate_session")
    menu_session=session.get("menu_session")
    last_name_session = session.get("last_name_session")
    is_active = session.get("is_active")
    # session.pop("activate_session")

    if menu_session == True:
        if inbound_msg_body == "1":
            message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
                                                  body="Emergency support logged. Standby.")
            session.pop("menu_session")

    # ACTIVATE SESSION BEGINS HERE!
    elif (inbound_msg_body[:9].lower()).replace(" ","") == "activate":
        try:
            user = User.query.filter(User.phone_number== inbound_msg_from).one()
            active = user.on_shift
            if active == True:
                message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
                                     body="You are already active")
            else:
                db.session.query(User).filter(User.phone_number == inbound_msg_from).update({"on_shift":(True)})
                db.session.commit()
                message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
                                     body="You've been activated")
        except:
            message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
                                         body="What is your first name?")
            activate_session = True
            session["activate_session"] = activate_session
    
    elif activate_session == True:
        a = []
        user_first_name = inbound_msg_body.replace(" ","")
        
        user_phone = inbound_msg_from
        activate_last_name_session = True
        a.append(user_first_name)
        session["last_name_session"] = a
        message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
                                          body="What is your Last name")
        print len(session["last_name_session"])
        session.pop("activate_session")

    elif last_name_session:
        if len(last_name_session) == 1:
            print "*****SESION RAN"
            user_last_name = inbound_msg_body
            user_first_name = session["last_name_session"][0]
            user_phone = inbound_msg_from
            new_users = User(first_name=user_first_name, 
                    last_name=user_last_name, 
                    phone_number=user_phone,
                    on_shift=True)
            db.session.add(new_users)
            db.session.commit()
            message = client.messages.create(to=inbound_msg_from, 
                                             from_=TWILIO_NUMBER,
                                             body="You are now active")
            session.pop("last_name_session")
            session["is_active"] = True

    elif (inbound_msg_body[:11].lower()).replace(" ","") == "deactivate":
        try:
            user = User.query.filter(User.phone_number== inbound_msg_from).one()
            active = user.on_shift
            if active == True:
                db.session.query(User).filter(User.phone_number == inbound_msg_from).update({"on_shift":(False)})
                db.session.commit()
                message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
                                     body="Good Bye")
            else:
                message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
                                     body="You're not active.")

        except:
            message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
                                     body="This number is not registered in our system")

    elif inbound_msg_body[:5].lower()=="menu":
        message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
                                                  body=menu)
        menu_session = session.get("menu_session")
        print menu_session
        menu_session = True
        session["menu_session"] = menu_session

        # session.pop("menu_session")
        # message = client.messages.create(to=number, from_=TWILIO_NUMBER,body=["Respond with 1: if you are in trouble."])

    elif inbound_msg_body[:2].lower()=="tl":
        team_leads_contact = db.session.query(User).join(User.roles).filter(Role.name=="teamlead").all()
        # for number in leads_numbers:
        #     if inbound_msg_from != number:
        #         message = client.messages.create(to=number, from_=TWILIO_NUMBER,
        #                                           body="%s: %s" %(team_leads[inbound_msg_from],inbound_msg_body))
    else:
        user = db.session.query(User).filter(User.phone_number == inbound_msg_from).one()
        team_members = db.session.query(User).filter(User.van == user.van).all()
        for x in team_members:
            print x.phone_number
            if inbound_msg_from != x.phone_number:
                message = client.messages.create(to=x.phone_number, from_=TWILIO_NUMBER,
                                                    body="%s: %s" %(user.first_name,inbound_msg_body))

        # # team_numbers = "team_%s_numbers"%(team_number)
        # for number in team_numbers[team_number-1]:
        #     if inbound_msg_from != number:
        #         print inbound_msg_body
        #         message = client.messages.create(to=number, from_=TWILIO_NUMBER,
        #                                           body="%s: %s" %(callers[inbound_msg_from]["Name"],inbound_msg_body))
        # return "Done"
    return "Done"

if __name__ == '__main__':
    app.run(debug=True)
