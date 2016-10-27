from flask import Flask, render_template, request, url_for, redirect, flash
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required, current_user, roles_required
from flask_mail import Mail, Message
from flask_security.forms import RegisterForm, LoginForm, ChangePasswordForm
from wtforms import StringField
from wtforms.validators import Required, InputRequired
from datetime import datetime

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

vans = db.Table('vans',
    db.Column('van_leader_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('van_member_id', db.Integer, db.ForeignKey('user.id'))
)


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
    region = db.Column(db.String(255))
    van = db.Column(db.String(255))
    password = db.Column(db.String(255))
    temp_pass = db.Column(db.Boolean())
    on_shift = db.Column(db.Boolean())
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
    van_confirmed = db.Column(db.Boolean())
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))
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

# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore, register_form=ExtendedRegisterForm)

# Create a user to test with
# @app.before_first_request
# def create_user():
#     db.create_all()
#     user_datastore.create_user(email='ronesha@codeforprogress.org', password='password')
#     db.session.commit()
# db.create_all()

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
    if request.method == "POST":
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phone_number = request.form['phone_number']
        region = request.form['region']

        phone_number = "+1" + phone_number
        password = id_generator()

        new_user = User(first_name = first_name, 
            last_name = last_name, 
            email = email, 
            phone_number=phone_number, 
            region = region,
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

            new_user = User(first_name = first_name, 
                last_name = last_name, 
                email = email, 
                phone_number=phone_number, 
                password = password, 
                region = region,
                active = True,
                temp_pass = True
                )
            new_role = db.session.query(Role).filter_by(name = 'teamlead').first()
            new_user.roles.append(new_role)
            try:
                db.session.add(new_user)

                url = 'http://3073f486.ngrok.io'

                message = Message("Confirm Your Account", recipients=[email])
                message.body = """Dear %s %s, \n\n
                You've been registered as a Team Leader by %s %s. \n\n
                Please login to your account at %s using the password here: %s. \n\n
                Thank you. """ %(first_name, last_name, current_user.first_name, current_user.last_name, url, password) 
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
            
            new_user = User(first_name = first_name, 
                last_name = last_name, 
                phone_number=phone_number, 
                region = region,
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
                if team_member_confirmed == "False":
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

    team_leads_contact = db.session.query(User).join(User.roles).filter(Role.name=="team lead").all()
    # print team_leads_contact
    state_leader = db.session.query(User).join(User.roles).filter(Role.name=="state").all()
    team_lead = db.session.query(User).join(User.roles).filter(Role.name=="teamlead").all()
    # print team_lead
    
    reg_lead = db.session.query(User).join(User.roles).filter(Role.name=="regional").all()
    if len(reg_lead) >= 1:
        for x in reg_lead:
            reg_lead_numbers = []
            reg_lead_numbers.append(x.phone_number)
            print reg_lead_numbers
    else:
        print "there are no reg_lead"
    member = db.session.query(User).join(User.roles).filter(Role.name=="member").all()
    response = twiml.Response()
    inbound_msg_body = request.form.get("Body")
    inbound_msg_from = request.form.get("From")
    menu = "Press 1 to report an emergency \n Press 2 to report an emergency \n"
    
    inc_msg_user_role = db.session.query(Role).join(User.roles).filter(User.phone_number==inbound_msg_from).first()
    inc_msg_user_role = inc_msg_user_role.name
    
    inc_msg_van = db.session.query(User).join(User.roles).filter(User.phone_number==inbound_msg_from).first()
    inc_msg_van = inc_msg_van.van

    activate_session=session.get("activate_session")
    menu_session=session.get("menu_session")
    last_name_session = session.get("last_name_session")
    is_active = session.get("is_active")
    emergency = session.get("emergency_session")
    add_van = session.get("add_van_session")
    # session.pop("add_van_session")
    # session.pop("menu_session")
    # session.pop("activate_session")
    # ACTIVATE SESSION BEGINS HERE
    if menu_session == True:
        if inbound_msg_body == "1":   
            session.get("emergency_session")          
    elif inbound_msg_body[:9].lower().replace(" ","") == "activate":
        try:
            user = User.query.filter(User.phone_number == inbound_msg_from).one()
            on_shift = user.on_shift
            if on_shift == True:
                message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
                                     body="Welcome back!")
            else:
                db.session.query(User).filter(User.phone_number == inbound_msg_from).update({"on_shift":(True)})
                db.session.commit()
                message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
                                     body="You've been activated, what is your van number?")
                a = True
                session.get("add_van_session")
                session['add_van_session'] = a
                print a 
        except:
            message = client.messages.create(to=inbound_msg_from,
                                             from_=TWILIO_NUMBER,
                                             body="What is your first name?")
            #starts activate session
            activate_session = True
            session["activate_session"] = activate_session
    elif inc_msg_user_role =="teamlead" and inbound_msg_body[:3] == "tl":
        fellow_tl = db.session.query(User).join(User.roles).filter(Role.name=="teamlead").filter(User.van==inc_msg_van).all()
    elif add_van == True:
        print "got to add van script"
        try:
            db.session.query(User).filter(User.phone_number==inbound_msg_from).update({'van':int(inbound_msg_body)})
            db.session.commit()
            session.pop("add_van_session")
        except:
            message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
                                     body="Please provide us with the correct van number")
            session[add_van]= True            
    elif activate_session == True:
        a = []
        #the msg received after the first name will be used as their first name
        user_first_name = inbound_msg_body.replace(" ","")
        
        user_phone = inbound_msg_from
        #Starts session to get last name
        activate_last_name_session = True
        a.append(user_first_name)
        #takes list and saves it in session
        session["last_name_session"] = a
        message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
                                          body="What is your Last name")
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
            new_role = db.session.query(Role).filter_by(name="member").first()
            new_users.roles.append(new_role)
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
            if user.on_shift == True:
                db.session.query(User).filter(User.phone_number == inbound_msg_from).update({"on_shift":(False)})
                db.session.query(User).filter(User.phone_number == inbound_msg_from).update({"van":(0)})
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
        message = client.messages.create(to=inbound_msg_from, 
                                         from_=TWILIO_NUMBER,
                                         body=["What is your emergency?"])
        a = "save emergency"
        session["menu_session"] = a
    elif menu_session == "save emergency":
        # session["emergency_session"] = inbound_msg_body
        new_emergency = Emergency(msg=inbound_msg_body,
                                  time=datetime.now(),
                                  phone_number=inbound_msg_from)
        db.session.add(new_emergency)
        db.session.commit()
        session.pop("menu_session")
    elif (inbound_msg_body[:7].lower()) == "urgent":
        print "*****caught emergency msg"
        inbound_msg_body = inbound_msg_body.lower().replace("urgent","")
        inbound_msg_body.capitalize()
        print inbound_msg_body
        new_emergency = Emergency(msg=inbound_msg_body,
                                  time=datetime.now(),
                                  phone_number=inbound_msg_from)
        db.session.add(new_emergency)
        db.session.commit()
        user = db.session.query(User).filter(User.phone_number == inbound_msg_from).one()
        team_members = db.session.query(User).filter(User.van == user.van).all()
        
        for x in team_members:
            print x.phone_number
            if inbound_msg_from != x.phone_number:
                message = client.messages.create(to=x.phone_number, from_=TWILIO_NUMBER,
                                                    body="%s: %s" %(user.first_name,inbound_msg_body))
    elif inbound_msg_body[:7].lower().replace(" ","") == "roster" and inc_msg_user_role == "teamlead":
        roster = db.session.query(User).filter(User.van==inc_msg_van).filter(User.on_shift==True).all()
        roster_list = []
        for x in roster:
            print roster_list.append(x.first_name)
        message = client.messages.create(to=inbound_msg_from, from_=TWILIO_NUMBER,
                                     body=("You're current van members are %s"%roster_list))
    #For Regional Managers to send msgs to respective TLs & Members
    elif inbound_msg_from in reg_lead_numbers:
        if inbound_msg_body[:2].lower() == "tl":
            user = db.session.query(User).filter(User.phone_number == inbound_msg_from).one()
            print user.phone_number
            team_leads = db.session.query(User).filter(User.van == user.van).join(User.roles).filter(Role.name=="teamlead").all()
            for x in team_leads:
                print x.van
                message = client.messages.create(to=x.phone_number, from_=TWILIO_NUMBER,
                                                        body="%s: %s" %(user.first_name,inbound_msg_body))
        else:
            user = db.session.query(User).filter(User.phone_number == inbound_msg_from).one()
            team_members = db.session.query(User).filter(User.van == user.van).all()
            for x in team_members:
                print x.phone_number
                if inbound_msg_from != x.phone_number:
                    message = client.messages.create(to=x.phone_number, from_=TWILIO_NUMBER,
                                                        body="%s: %s" %(user.first_name,inbound_msg_body))
    # elif inbound_msg_body[:2].lower()=="tl":
    #     team_leads_contact = db.session.query(User).filter(team_number).join(User.roles).filter(Role.name=="teamlead").all()
    #     for number in leads_numbers:
    #         if inbound_msg_from != number:
    #             message = client.messages.create(to=number, from_=TWILIO_NUMBER,
    #                                               body="%s: %s" %(team_leads[inbound_msg_from],inbound_msg_body))
    else:
        user = db.session.query(User).filter(User.phone_number == inbound_msg_from).one()
        team_members = db.session.query(User).filter(User.van == user.van).all()
        for x in team_members:
            print x.phone_number
            if inbound_msg_from != x.phone_number:
                message = client.messages.create(to=x.phone_number, from_=TWILIO_NUMBER,
                                                    body="%s: %s" %(user.first_name,inbound_msg_body))
    return "Done"

if __name__ == '__main__':
    app.run(debug=True)
