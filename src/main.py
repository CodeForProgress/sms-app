from flask import Flask, render_template, request, url_for, redirect, flash, session, Response
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy

from flask_security import Security, SQLAlchemyUserDatastore, UserMixin, RoleMixin, login_required, current_user, roles_required
from flask_security.forms import RegisterForm, LoginForm, ChangePasswordForm
from flask.ext.security.utils import encrypt_password, verify_and_update_password, verify_password

from wtforms import StringField, Form, BooleanField, StringField, PasswordField, validators
from wtforms.validators import Required, InputRequired

from twilio import twiml
from twilio.rest import TwilioRestClient

from datetime import datetime
from functools import wraps

import psycopg2
import string
import random
import bcrypt
import logging
import json 
import random
import string


# Create app
app = Flask(__name__)
app.config.from_pyfile('settings/config.py')

mail = Mail(app)

# Create database connection object
db = SQLAlchemy(app)

# Define models
roles_users = db.Table('roles_users',
        db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
        db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))

vans = db.Table('vans',
        db.Column('van_leader_id', db.Integer, db.ForeignKey('user.id')),
        db.Column('van_member_id', db.Integer, db.ForeignKey('user.id')))

twilio_users = db.Table('twilio_users',
        db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
        db.Column('twilio_id', db.Integer(), db.ForeignKey('twilio.id')))

class ExtendedRegisterForm(RegisterForm):
    first_name = StringField('First Name', [Required()])
    last_name = StringField('Last Name', [Required()])
    phone_number = StringField('Phone Number', [Required()])

class Twilio(db.Model):
    id = db.Column(db.Integer(), primary_key=True)
    account_sid = db.Column(db.String(255))
    auth_token = db.Column(db.String(255))
    twilio_number = db.Column(db.String(255))
    state_number = db.Column(db.String(255))
    is_active = db.Column(db.Boolean())


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
    region = db.Column(db.String(255))
    van = db.Column(db.String(255))
    twilio_accounts = db.relationship('Twilio', secondary=twilio_users,backref=db.backref('users', lazy='dynamic'))
    state_number = db.Column(db.String(255))
    password = db.Column(db.String(255))
    temp_pass = db.Column(db.String(255))
    on_shift = db.Column(db.Boolean())
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
    van_confirmed = db.Column(db.Boolean())
    roles = db.relationship('Role', secondary=roles_users,backref=db.backref('users', lazy='dynamic'))
    van_teams = db.relationship('User', 
                               secondary=vans, 
                               primaryjoin=(vans.c.van_leader_id == id), 
                               secondaryjoin=(vans.c.van_member_id == id), 
                               backref=db.backref('vans', lazy='dynamic'), 
                               lazy='dynamic')

    def add_to_van(self, user):
        self.van_teams.append(user)
        return self

    def remove_from_van(self, user):
        self.van_teams.remove(user)
        return self

class Emergency(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    msg = db.Column(db.String(1000))
    time = db.Column(db.DateTime())
    phone_number = db.Column(db.String(15))

class Password_Change_Form(Form):
    current_password = PasswordField('Current Password', [validators.DataRequired()])
    new_password = PasswordField('New Password',[validators.DataRequired(),validators.EqualTo('confirm', message='Passwords must match')])
    password_confirm = PasswordField('Confirm Password')

class Twilio_Account_Form(Form):
    account_sid = StringField('Account SID', [validators.required(), validators.length(max=50)])
    auth_token = StringField('Auth Token', [validators.required(), validators.length(max=50)])
    twilio_number = StringField('Twilio Number', [validators.required(), validators.length(max=50)])


# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore, register_form=ExtendedRegisterForm)


# Twilio Account Info
twilio = db.session.query(Twilio).filter(Twilio.is_active==True).first()

ACCOUNT_SID = twilio.account_sid
AUTH_TOKEN = twilio.auth_token
TWILIO_NUMBER = twilio.twilio_number

client = TwilioRestClient(ACCOUNT_SID, AUTH_TOKEN)


# Create a user to test with
# @app.before_first_request
# def create_user():
#     db.create_all()
#     x =encrypt_password('password')
#     user_datastore.create_user(email='ronesha@codeforprogress.org', password=x, temp_pass=x)
#     db.session.commit()
# db.create_all()

# Random Password Generator 
def id_generator(size=10, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.SystemRandom().choice(chars) for _ in range(size))

# Views
@app.route('/', methods=["POST", "GET"])
@login_required
def home():
    password_form = Password_Change_Form(request.form)
    if request.method == 'POST':
        if verify_password(password_form.current_password.data, current_user.password):
            db.session.query(User).filter(User.id == current_user.id).update({"password":encrypt_password(password_form.new_password.data)})
            db.session.commit()

            return redirect(url_for('home'))

    regional_leads = db.session.query(User).join(User.roles).filter(Role.name == 'regional').all()
    team_leads = db.session.query(User).join(User.roles).filter(Role.name == 'teamlead').all()

    if current_user.temp_pass == current_user.password:
        password_reset = True
    else: 
        password_reset = False

    if current_user.roles[0] == "teamlead":
        return redirect(url_for('team_confirmation'))
        
    return render_template('index.html', password_form= password_form,regional_leads=regional_leads, password_reset=password_reset, team_leads=team_leads)

@app.route('/logout')
def logout():
    logout()
    return render_template('index.html')

@app.route('/addRegional', methods=['GET', 'POST'])
@roles_required('state')
def addRegional():
    if request.method == "POST":
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phone_number = request.form['phone_number']
        region = request.form['region']

        phone_number = "+1" + phone_number
        password = id_generator()
        state_number = id_generator()

        new_user = User(first_name = first_name, 
            last_name = last_name, 
            email = email, 
            phone_number=phone_number, 
            region = region,
            password = encrypt_password(id_generator()), 
            state_number = state_number,
            active = True, 
            temp_pass = password
            )
        new_role = db.session.query(Role).filter_by(name = 'regional').first()
        new_user.roles.append(new_role)

        message = Message("Confirm Your Account", recipients=[email])
        message.body = """Dear %s %s, \n\n
        You've been registered as a Regional Supervisor by %s %s. \n\n
        Please login to your account at %s using the password here: %s. \n\n
        Thank you. """ %(first_name, last_name, current_user.first_name, current_user.last_name, URL, password) 
        mail.send(message)

        try:
            db.session.add(new_user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("The user you entered is already active in our system.")
            return redirect(url_for('home')) 

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
            region = current_user.region
            phone_number = "+1" + phone_number
            
            password = id_generator()
            state_number = id_generator()

            new_user = User(first_name = first_name, 
                last_name = last_name, 
                email = email, 
                phone_number=phone_number, 
                password = password, 
                region = region,
                state_number = state_number,
                active = True,
                temp_pass = password
                )
            new_role = db.session.query(Role).filter_by(name = 'teamlead').first()
            new_user.roles.append(new_role)
            try:
                db.session.add(new_user)

                message = Message("Confirm Your Account", recipients=[email])
                message.body = """Dear %s %s, \n\n
                You've been registered as a Team Leader by %s %s. \n\n
                Please login to your account at %s using the password here: %s. \n\n
                Thank you. """ %(first_name, last_name, current_user.first_name, current_user.last_name, URL, password) 
                mail.send(message)

                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("The user you entered is already active in our system.")
                return redirect(url_for('home')) 
            
            flash("You've successfully added %s %s as a Team Leader." %(first_name, last_name))
            return redirect(url_for('addTeamLeader'))
        return render_template('teamlead.html')

    else:
        flash("You do not have permission to view this resource.")
        redirect(url_for('home'))
    

@app.route('/addTeamMember', methods=['GET', 'POST'])
def addTeamMember():

    if current_user.roles[0].name == "state" or current_user.roles[0] == "regional" or current_user.roles[0] == "teamlead":
        if request.method == "POST":
            first_name = request.form['first_name']
            last_name = request.form['last_name']   
            phone_number = request.form['phone_number']
            region = current_user.region

            phone_number = "+1" + phone_number
            state_number = id_generator()
            
            new_user = User(first_name = first_name, 
                last_name = last_name, 
                phone_number=phone_number, 
                region = region,
                state_number = state_number,
                active = True,
                on_shift = False
                )
            new_role = db.session.query(Role).filter_by(name = 'member').first()
            new_user.roles.append(new_role)

            try:
                db.session.add(new_user)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("The user you entered is already active in our system.")
                return redirect(url_for('home')) 
            
            flash("You've successfully added %s %s as a Team Member." %(first_name, last_name))
            return redirect(url_for('addTeamMember'))
        return render_template('teammember.html')
    else:
        flash("You do not have permission to view this resource.")
        return redirect(url_for('home'))

@app.route('/assignments', methods=['GET', 'POST'])
@roles_required('regional')
def van_assignments():
    team_leaders = db.session.query(User).join(User.roles).filter(Role.name == 'teamlead').all()
    if request.method == 'POST':
        team_lead_id = request.form['team_leaders']
        van_number = request.form['van_number']
        vanspaces = request.form['vanspaces']
        vanspaces = int(vanspaces)

        team_lead = db.session.query(User).join(User.roles).filter(User.id == team_lead_id).first()
        team_lead.van = van_number
        db.session.commit() 

        team_region = team_lead.region
        flash("You've added %s %s as a new team leader." %(team_lead.first_name, team_lead.last_name))
        return redirect(url_for('team_van_assignments', team_region = team_region, team_lead_id = team_lead_id, van_number = van_number, vanspaces = vanspaces))
    return render_template('assignments.html', team_leaders = team_leaders)


@app.route('/<team_region>/teamassignments/<team_lead_id>/no<van_number>/<vanspaces>', methods =['GET', 'POST'])
@roles_required('regional')
def team_van_assignments(team_region, team_lead_id, van_number, vanspaces):
    team_members = db.session.query(User).join(User.roles).filter(Role.name == 'member').filter(User.region == team_region).all()
    vanspaces = int(vanspaces)
   
    if request.method == "POST":
        new_team_leader = db.session.query(User).filter_by(id = team_lead_id).first()
        for x in range(vanspaces):
            team_member_id = request.form['team_member_' + str(x)]
            new_team_member = db.session.query(User).filter_by(id=team_member_id).first()
            new_team_member.van = van_number
            new_team_member.van_confirmed = False
            assign_to_van = new_team_leader.add_to_van(new_team_member)
            db.session.add(assign_to_van)
            db.session.commit()

        return redirect(url_for('home'))
    return render_template('teamassignments.html', team_members = team_members, vanspaces = vanspaces)


@app.route('/teamconfirmation', methods=['GET', 'POST'])
@roles_required('teamlead')
def team_confirmation():
    team_members = db.session.query(User).join(User.roles).filter(Role.name == 'member').filter(User.van == current_user.van).all()

    if team_members:
        if request.method == "POST":
            for x in team_members:
                team_member_id = x.id  
                team_member = db.session.query(User).filter_by(id=team_member_id).first()   
                team_member_confirmed = request.form['confirmed_' + str(x.id)]
                if team_member_confirmed != "True":
                    team_member.van = None
                    team_member.van_confirmed = False 
                else: 
                    team_member.van_confirmed = True
                db.session.commit()
            flash ("You've confirmed your team. Thanks!")
            return redirect(url_for('home'))
    else:
        flash("There are no team members to confirm.")
        return redirect(url_for('home'))
    return render_template('teamconfirmation.html', team_members = team_members)

@app.route('/regions')
@roles_required('state')
def region_overview():
    regional_leaders = db.session.query(User).join(User.roles).filter(Role.name == 'regional').all()

    return render_template('regional_overview.html', regional_leaders = regional_leaders)

@app.route('/regions/<region_id>')
@roles_required('state')
def region_details(region_id):
    regional_leader = db.session.query(User).join(User.roles).filter(Role.name == 'regional').filter(region == region_id).first()
    team_leaders = db.session.query(User).join(User.roles).filter(Role.name == 'teamlead').filter(region == region_id).all()

    return render_template('regional_details.html', regional_leader = regional_leader, team_leaders = team_leaders)

@app.route('/teams')
@login_required
def teams_overview():
    
    return render_template('team_overview.html')


@app.route('/messages')
@login_required
def messages_overview():
    
    return render_template('messages_overview.html')

@app.route('/alerts')
@login_required
def alerts_overview():
    alerts = db.session.query(Emergency).all()

    return render_template('alerts_overview.html',alerts=alerts)

@app.route('/account', methods=["POST", "GET"])
@login_required
def account_overview():
    form = Twilio_Account_Form(request.form)
    if request.method == 'POST':
        twilio = Twilio(account_sid = form.account_sid.data,
            auth_token = form.auth_token.data,
            twilio_number = form.twilio_number.data
            )
        db.session.add(twilio)
        db.session.commit()

        twilio = db.session.query(Twilio).filter(Twilio.account_sid==form.account_sid.data).first()
        user = db.session.query(User).filter(id == current_user.id).first()

        current_user.twilio_accounts.append(twilio)
        db.session.commit()

    return render_template('account_overview.html', form=form)


@app.route('/add_state', methods=["POST", "GET"])
@login_required
def add_state():
    if request.method == "POST": 
        if current_user.email != 'naeem@codeforprogress.org':
            return redirect(url_for('home'))
        else: 
            email = request.form['email']
            first_name = request.form['first_name']
            last_name = request.form['last_name']

            password = id_generator()
            state_number = id_generator()

            new_user = User(first_name = first_name, 
                last_name = last_name, 
                email=email,
                password=password, 
                state_number = state_number,
                active = True,
                on_shift = False,
                temp_pass = True,
                )
            new_role = db.session.query(Role).filter_by(name = 'state').first()
            new_user.roles.append(new_role)

            try:
                db.session.add(new_user)
                message = Message("Confirm Your Account", recipients=[email])
                message.body = """Dear %s %s, \n\n
                You've been registered as a Team Leader by %s %s. \n\n
                Please login to your account at %s using the password here: %s. \n\n
                Thank you. """ %(first_name, last_name, current_user.first_name, current_user.last_name, URL, password) 
                mail.send(message)

                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("The user you entered is already active in our system.")
                return redirect(url_for('add_state')) 



    if current_user.email != 'naeem@codeforprogress.org':
        return redirect(url_for('home'))
    else: 
        return render_template('add_state.html')

def get_teamleads_by_region(region):
    x = db.session.query(User).filter(User.region==region, User.on_shift==True).join(User.roles).filter(Role.name=="teamlead").all()
    return x

def get_users_by_role(role):
    x = db.session.query(User).filter(User.on_shift==True).join(User.roles).filter(Role.name==role).all()
    return x 

def get_team_members(region, van):
    team_members = db.session.query(User).filter(User.region==region, User.van==van).join(User.roles).filter(Role.name=='member').all()
    return team_members

def get_caller_role(phone_number):
    caller = db.session.query(Role).join(User.roles).filter(User.phone_number==phone_number).first()
    return caller.name

def get_teamlead(region, van):
    teamlead = db.session.query(User).filter(User.region==region, User.van==van, User.on_shift==True).join(User.roles).filter(Role.name=="teamlead").first()
    return teamlead

def get_team(region, van):
    team = db.session.query(User).filter(User.region==region, User.van==van, User.on_shift==True).all()
    return team

def get_region(region):
    region = db.session.query(User).filter(User.region==region,User.on_shift==True).join(User.roles).filter((Role.name=='member') | (Role.name=='teamlead')).all()
    return region

def get_state():
    state = db.session.query(User).filter(User.on_shift==True).join(User.roles).filter((Role.name=='regional') | (Role.name=='member') | (Role.name=='teamlead')).all()
    return state
def get_caller_by_phone_number(phone_number):
    caller = db.session.query(User).filter(User.phone_number==phone_number).first()
    return caller



@app.route("/sms", methods=["GET","POST"])
def get_text():

    team_leads = get_users_by_role('teamlead')
    state_leads = get_users_by_role('teamlead')
    regional_leads = get_teamleads_by_region("1")

    # Gets all members from database
    member = db.session.query(User).join(User.roles).filter(Role.name=="member").all()
    response = twiml.Response()

    # Save inbound number and message
    inbound_msg_body = request.form.get("Body")
    inbound_msg_from = request.form.get("From")

    # Menu /// Incomplete
    menu = "Press 1 to report an emergency \n Press 2 to report an emergency \n"
    
    # Gets callers role from the database
    # inc_msg_user_role = db.session.query(Role).join(User.roles).filter(User.phone_number==inbound_msg_from).first()
    # inc_msg_user_role = inc_msg_user_role.name
    
    # Gets caller's van number 
    # inc_msg_van = db.session.query(User).join(User.roles).filter(User.phone_number==inbound_msg_from).first()
    # inc_msg_van = inc_msg_van.van

    # Gets sessions 
    activate_session=session.get("activate_session")
    activation_step=session.get("activation_step")

    menu_session=session.get("menu_session")
    last_name_session = session.get("last_name_session")
    is_active = session.get("is_active")
    emergency = session.get("emergency_session")
    add_van = session.get("add_van_session")
   
    # session.pop("add_van_session")
    # session.pop("menu_session")
    # session.pop("activate_session")
   
   # Checks if the menu session is true and handles the responses

   # ========================================= #
   # ======= Emergencies and Alerts ========== #
   # ========================================= #

    menu = ["Press 1 for an emergency health care, residential, vehicle accident.",
            "Press 2 for a natural disaster tornadoes, thuderstorms, hailsotrms, extreme cold weather.",
            "Press 3 if violence or gunshot erupts.",
            "Press 4 for an accident or structual failure fire, building collapse, toll or bridge/tunnel accident.",
            "Press 5 for an utility incidents power outage, winter storms, severe cold/exposure."]

    if inbound_msg_body.replace(' ', '').lower()[:10]=="emergency":
        for x in menu:
            client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,body=x)
        session['emergency_session'] = True

    elif emergency: 
        print "Runs"
        if inbound_msg_body.replace(' ', '')[:2] == "1":
            user = get_caller_by_phone_number(inbound_msg_from)
            team = get_region(user.region)
            for x in team:
                emergency_message = "emergency health care, residential, vehicle accident"
                if inbound_msg_from != x.phone_number:
                    message = client.messages.create(to=x.phone_number, 
                        from_=TWILIO_NUMBER, body="%s: Has issued an emergency alert due to an emergency health care, residential, vehicle accident\nPhone Number: %s" %(user.first_name, user.phone_number))
        
        elif inbound_msg_body.replace(' ', '')[:2] == "2":
            user = get_caller_by_phone_number(inbound_msg_from)
            team = get_region(user.region)
            for x in team:
                emergency_message = "natural disaster tornadoes, thuderstorms, hailsotrms, extreme cold weather"
                if inbound_msg_from != x.phone_number:
                    message = client.messages.create(to=x.phone_number, 
                        from_=TWILIO_NUMBER, body="%s: Has issued an emergency alert due to a natural disaster tornadoes, thuderstorms, hailsotrms, extreme cold weather. \nPhone Number: %s" %(user.first_name, user.phone_number))



        
        elif inbound_msg_body.replace(' ', '')[:2] == "3":
            user = get_caller_by_phone_number(inbound_msg_from)
            team = get_region(user.region)
            for x in team:
                emergency_message = "violence or gunshot erupts"
                if inbound_msg_from != x.phone_number:
                    message = client.messages.create(to=x.phone_number, 
                        from_=TWILIO_NUMBER, body="%s: Has issued an emergency alert due to an eruption of violence or gunshots\nPhone Number: %s" %(user.first_name, user.phone_number))


        elif inbound_msg_body.replace(' ', '')[:2] == "4":
            user = get_caller_by_phone_number(inbound_msg_from)
            team = get_region(user.region)
            for x in team:
                emergency_message = "accident or structual failure fire, building collapse, toll or bridge/tunnel accident"
                if inbound_msg_from != x.phone_number:
                    message = client.messages.create(to=x.phone_number, 
                        from_=TWILIO_NUMBER, body="%s: Has issued an emergency alert due to an accident or structual failure fire, building collapse, toll or bridge/tunnel accident.\nPhone Number: %s" %(user.first_name, user.phone_number))


        elif inbound_msg_body.replace(' ', '')[:2] == "5":
            user = get_caller_by_phone_number(inbound_msg_from)
            team = get_region(user.region)
            for x in team:
                emergency_message = "utility incidents power outage, winter storms, severe cold/exposure"
                if inbound_msg_from != x.phone_number:
                    message = client.messages.create(to=x.phone_number, 
                        from_=TWILIO_NUMBER, body="%s: Has issued an emergency alert due an utility incidents power outage, winter storms, severe cold/exposure.\nPhone Number: %s" %(user.first_name, user.phone_number))


        client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,body="All regional staff have been notified of you emergency and will contact you shortly.")
        new_emergency = Emergency(msg=emergency_message,time=datetime.now(),phone_number=inbound_msg_from)
        db.session.add(new_emergency)
        db.session.commit()
        session.pop("emergency_session")

    elif inbound_msg_body.lower().replace(' ', '')[:7] == "urgent":

        inbound_msg_body = inbound_msg_body.lower().replace("urgent","")
        inbound_msg_body.capitalize()

        new_emergency = Emergency(msg=inbound_msg_body,time=datetime.now(),phone_number=inbound_msg_from)
        db.session.add(new_emergency)
        db.session.commit()

        user = db.session.query(User).filter(User.phone_number == inbound_msg_from).one()
        team = get_team(user.region, user.van)
        
        for x in team:
            print x.phone_number
            if inbound_msg_from != x.phone_number:
                message = client.messages.create(to=x.phone_number, from_=TWILIO_NUMBER,body="%s: URGENT %s" %(user.first_name,inbound_msg_body))



    # =========================================== #
    # ================ ACTIVATE ================= #
    # =========================================== #

    # If the caller text "Activate", a response will be sent         
    elif inbound_msg_body.lower().replace(" ","")[:9] == "activate":
        try:
            # Queries the User table 
            user = User.query.filter(User.phone_number == inbound_msg_from).one()
            on_shift = user.on_shift

            # If user has already activate their number of the shift we'll send a welcome messase
            if on_shift == True:
                client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,body="Welcome back!")

            # Else if the caller is in the DB, but 'on_shift' is False, we'll will update the callers 
            # status in the database to True and welcome them caller and ask for their Van Number  
            else:
                db.session.query(User).filter(User.phone_number == inbound_msg_from).update({"on_shift":(True)})
                db.session.commit()
                client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,body="You've been activated, what is your van number?")

                # Creates an 'add_van_session'
                session.get("add_van_session")
                session['add_van_session'] = True

        # If python throws an error, the caller's number isn't in our database and we begin the text-based registration 
        except:
            client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,body="What is your first name?")

            #starts activate session
            session["activate_session"] = True
            session['activation_step'] = 1 




    # The callers first name response is handled
    elif activate_session:
        if activation_step == 1:

            #the msg received after the first name will be used as their first name
            user_first_name = inbound_msg_body.replace(" ","")
            first_name = [user_first_name] 

            session["last_name_session"] = first_name

            message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,body="What is your Last name")
            session['activation_step'] = 2


        # The callers first name response is handled
        elif activation_step == 2:
            
            last_name = inbound_msg_body
            last_name_session.append(last_name)
        
            # Sends confromation text
            client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,body="What is your FOUR digit van number? ")
            session["is_active"] = True
            session['activation_step'] = 3

        elif activation_step == 3: 
            region = inbound_msg_body.replace(' ','').lower()[:2]
            van = inbound_msg_body.replace(' ','').lower()[-2:]
            new_users = User(first_name=last_name_session[0], 
                             last_name=last_name_session[1], 
                             phone_number=inbound_msg_from,
                             van = van,
                             region = region,
                             on_shift=True)

            new_role = db.session.query(Role).filter_by(name="member").first()
            new_users.roles.append(new_role)
            db.session.add(new_users)
            db.session.commit()

            # Sends confromation text
            message = client.messages.create(to=inbound_msg_from,from_=TWILIO_NUMBER,body="You are now active")

            session.pop('activation_step')
            session.pop('activate_session')
            session.pop('last_name_session')

    

    # =========================================== #
    #  ============== DEACTIVATE ================ #
    # =========================================== #

    elif inbound_msg_body.lower().replace(" ","")[:11] == "deactivate":
        try:
            user = User.query.filter(User.phone_number== inbound_msg_from).one()
            if user.on_shift == True:
                db.session.query(User).filter(User.phone_number == inbound_msg_from).update({"on_shift":(False)})
                db.session.query(User).filter(User.phone_number == inbound_msg_from).update({"van":(0)})
                db.session.commit()
                client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,body="Good Bye")
            else:
                message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,body="You're not active.")
        except:
            message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,body="This number is not registered in our system") 




    # ============================================ #
    # ========== TEAM LEADS MESSASING ============ #
    # ============================================ #

    elif (inbound_msg_body[:3].lower()).replace(" ","") == "tl":
        if get_caller_role(inbound_msg_from) == 'member':
            sender = get_caller_by_phone_number(inbound_msg_from)
            teamlead = get_teamlead(sender.region, sender.van)
            client.messages.create(to=teamlead.phone_number, from_=TWILIO_NUMBER,body=inbound_msg_body)

        elif get_caller_role(inbound_msg_from) == 'teamlead':
            teamleaders = get_teamleads_by_region(user.region)

            for leads in teamleaders:
                if leads.phone_number != inbound_msg_from:
                    client.messages.create(to=leads.phone_number, from_=TWILIO_NUMBER,body=inbound_msg_body)


    # ============================================= #
    # ======== Regional Leader Messaging ========== #
    # ============================================= #

        elif get_caller_role(inbound_msg_from) == 'regional':
            user = db.session.query(User).filter(User.phone_number == inbound_msg_from).one()
            team_leads = get_teamleads_by_region(user.region)
            for x in team_leads:
                client.messages.create(to=x.phone_number, from_=TWILIO_NUMBER,body="%s: %s" %(user.first_name,inbound_msg_body))




    # elif add_van == True:
    #     print "got to add van script"
    #     try:
    #         db.session.query(User).filter(User.phone_number==inbound_msg_from).update({'van':int(inbound_msg_body)})
    #         db.session.commit()
    #         session.pop("add_van_session")
    #     except:
    #         message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
    #                                  body="Please provide us with the correct van number")
    #         session[add_van]= True            
    

    # elif inbound_msg_body[:7].lower().replace(" ","") == "roster" and inc_msg_user_role == "teamlead":
    #     roster = db.session.query(User).filter(User.van==inc_msg_van).filter(User.on_shift==True).all()
    #     roster_list = []
    #     for x in roster:
    #         print roster_list.append(x.first_name)
    #     message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,body=("You're current van members are %s"%roster_list))

    #     message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,body=menu)
    #     menu_session = session.get("menu_session")
        
    #     message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,body=["What is your emergency?"])
    #     session["menu_session"] = "save emergency"

    # elif menu_session == "save emergency":
    #     new_emergency = Emergency(msg=inbound_msg_body,time=datetime.now(),phone_number=inbound_msg_from)
    #     db.session.add(new_emergency)
    #     db.session.commit()
    #     session.pop("menu_session")
   
    else:
        if get_caller_role(inbound_msg_from) == 'state':
            user = get_caller_role(inbound_msg_from)
            team = get_state()
            for x in team:
                print x.phone_number
                if inbound_msg_from != x.phone_number:
                    message = client.messages.create(to=x.phone_number, from_=TWILIO_NUMBER,body="%s: %s" %(user.first_name,inbound_msg_body))

        elif get_caller_role(inbound_msg_from) == 'regional':
            user = get_caller_by_phone_number(inbound_msg_from)
            team = get_region(user.region)
            for x in team:
                print x.phone_number
                if inbound_msg_from != x.phone_number:
                    message = client.messages.create(to=x.phone_number, from_=TWILIO_NUMBER,body="%s: %s" %(user.first_name,inbound_msg_body))

        else:
            user = db.session.query(User).filter(User.phone_number == inbound_msg_from).one()
            team = get_team(user.region, user.van)
            for x in team:
                if inbound_msg_from != x.phone_number:
                    message = client.messages.create(to=x.phone_number, from_=TWILIO_NUMBER,body="%s: %s" %(user.first_name,inbound_msg_body))
    return "Done"

if __name__ == '__main__':
    app.run(debug=True)
