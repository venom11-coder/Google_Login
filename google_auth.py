from flask import Flask, url_for, session, redirect, jsonify, request
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import requests
from zoneinfo import ZoneInfo
import httpx
import json
from authlib.integrations.flask_client import OAuth
import os
from dotenv import load_dotenv
from sqlalchemy import Text, Column, Integer,DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from flask_cors import CORS
from datetime import datetime, timedelta, timezone

load_dotenv()

api_key = os.getenv("api_key")
# uses flask to communicate
# creates a flask object

app = Flask(__name__)


# ⚠️ Only for localhost testing — REMOVE THIS in production!

CORS(app, supports_credentials=True)

MAP_API_KEY = os.getenv("MAP_API_KEY")

url= "aiintegrationdb-production.up.railway.app"

#url_timezone = "web-production-2504b.up.railway.app/timezone"

SCOPES = ['https://www.googleapis.com/auth/calendar']



#VERY IMPORTANT LINE TO FORCE GOOGLE TO GENERATE HTTPS REQUEST!!!!!
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)



# Use Flask's default secure cookie-based session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = True  # Because Railway uses HTTPS




base= declarative_base()

DATABASE_URL= os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

class Calendar(base):
    __tablename__ = 'Calendar'
    client_id_google = Column(Text, primary_key=True)
    token_google = Column(Text)
    app_user_id = Column(Text)
    client_secret_google = Column(Text)
    scope_google = Column(Text)
    Time = Column(DateTime, default=datetime.utcnow)

class User(base):
   __tablename__= 'User'
   user_id = Column(Text,primary_key=True)
   email_id= Column(Text)
   full_name= Column(Text)
   first_name= Column(Text)
   last_name= Column(Text)
   Time= Column(DateTime, default=datetime.utcnow)
   
base.metadata.create_all(engine)

# create the client id, secret and url and also flask secret pwd
# used port 5000 for local testing
appconf= {
    "OAUTH2_CLIENT_ID": os.getenv("OAUTH2_CLIENT_ID") ,
    "OAUTH2_CLIENT_SECRET":os.getenv("OAUTH2_CLIENT_SECRET"),
    "OAUTH2_META_URL": os.getenv("OAUTH2_META_URL"),
    "FLASK_SECRET": os.getenv("FLASK_SECRET"),
    

}

# configures the app with the credentials

app.config.update(appconf)
app.secret_key = app.config["FLASK_SECRET"]
oAuth = OAuth(app)


# registers with all the credentaisl
oAuth.register("Fittergem",
               client_id= app.config.get("OAUTH2_CLIENT_ID"),
               client_secret= app.config.get("OAUTH2_CLIENT_SECRET"),
               server_metadata_url = app.config.get("OAUTH2_META_URL"),
               client_kwargs= {"scope": "openid https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/calendar" ,
               
               }
               )



@app.route("/")
def home():
    db = SessionLocal()
    user_id= session.get("user_id")
    
    if not user_id:
       return redirect(url_for("googleLogin"))
    user_exist = db.query(User).filter(User.user_id==user_id).first()
    if user_exist is not None:
          return """
<html>
  <body style="font-family: sans-serif; text-align: center; margin-top: 50px;">
    <h2>Login successful!</h2>
    <p>You can now return to the Fittergem app.</p>
    <script>
      setTimeout(function() {
        window.close();
      }, 1000);
    </script>
  </body>
</html>
"""

    else:
        return redirect(url_for("googleLogin", external=True))

@app.route("/google-login")
def googleLogin():
    redirect_uri = url_for("googleCallback", _external=True, _scheme="https")
    return oAuth.Fittergem.authorize_redirect(redirect_uri)

@app.route("/check-login-session")
def check_login_session():
    user_id = session.get("user_id")
    if user_id:
        return jsonify({"status": "logged_in", "user_id": user_id})
    return jsonify({"status": "not_logged_in"})



@app.route("/signin-google")
def googleCallback():
    try:
        token = oAuth.Fittergem.authorize_access_token()
        access_token = token["access_token"]

        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        response = requests.get("https://www.googleapis.com/oauth2/v1/userinfo", headers=headers)
        user_info = response.json()

        google_id = user_info["id"]
        session["user_id"] = google_id
        email_id = user_info["email"]
        full_name = user_info["name"]
        first_name = user_info["given_name"]
        last_name = user_info["family_name"]

        db = SessionLocal()
        user_exist = db.query(User).filter(User.user_id == google_id, User.email_id == email_id).first()

        if not user_exist:
            new_user = User(
                user_id=google_id,
                email_id=email_id,
                full_name=full_name,
                first_name=first_name,
                last_name=last_name
            )
            db.add(new_user)
            db.commit()

        return redirect("/calendar-access")







    except Exception as e:
        print("Error during callback:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/logout")
async def logout():
    session.clear()
    return redirect("/")

@app.route("/check-login")
def check_login():
    email = request.args.get("email")
    if not email:
        return jsonify({"error": "Missing email"}), 400

    db = SessionLocal()
    user = db.query(User).filter(User.email_id == email).first()

    if user:
        return jsonify({"status": "logged_in", "user_id": user.user_id})
    else:
        return jsonify({"status": "not_logged_in"})


 # used to get all user events and send it to chatgpt along with the prompt to store it
@app.route("/google-Calendar")
def Calendar_Integration():
 msg = request.args.get("msg")
 if msg:
    # Rebuild GPT prompt with that message instead of just the event list
    user_input = {
        "user_id": session.get("user_id"),
        "message": msg
    }
    response = httpx.post(f"https://{url}/chat", json=user_input, timeout=40.0)
    # You can now apply the returned GPT plan (if JSON) automatically

 user_id = session["user_id"]
 
 db=SessionLocal()
 user_exist = db.query(Calendar).filter(Calendar.client_id_google==user_id).first()
 
 if user_exist is None:
    session["pending_message"] = "fetch_schedule"
    return redirect("/calendar-access")
 
 
 data=json.loads(user_exist.token_google)
 
 if user_exist is not None:
  fe_id = user_exist.app_user_id
  creds=  Credentials.from_authorized_user_info(data, SCOPES)
 service = build("calendar", "v3", credentials=creds)

 if creds.expired and creds.refresh_token:
    creds.refresh(Request())
    
    user_exist.token_google = creds.to_json()
    db.commit()

   

    data = json.loads(user_exist.token_google)
    timezone_id = data.get("timezone", "America/Toronto")


     # detects time in EST but needs to be changed as per the user
 time = datetime.now(ZoneInfo(timezone_id)).replace(hour=0,minute=0,second=0,microsecond=0)
       
     # starts from today to next seven days
 all_events =[]
 for i in range(0,7):
       est_start = time + timedelta(days=i)
       est_end = time + timedelta(days=i + 1)
      
       # sends the query to Calendar in UTC
       time_min = est_start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
       time_max = est_end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

       # sends query
       events_result = service.events().list(
        calendarId="primary",
        timeMin= time_min ,
        timeMax= time_max ,
        singleEvents=True,
        orderBy="startTime"
       ).execute()


       events = events_result.get("items", [])
       lines = []

       data =  request.json if request.is_json else {}

    

      

       if not events:
        print("No upcoming events found in google calendar in the next 7 days.")
        #prompt = ("if no events found. Do not assume the user is free. When recommending workouts, diet changes, or other plans, do not assume full availability. Instead, ask the user about their preferred or available time slots before making detailed suggestions. Just reply with 'noted'.")
       else:
        print("Upcoming events:")
        for event in events:
            event_detail = {
            "start" : event["start"].get("dateTime", event["start"].get("date")) ,
            "end" : event["end"].get("dateTime") ,
            "summary": event.get("summary")
            
            }
            all_events.append(event_detail)
        
        for event in all_events:
            summary = event["summary"]
            start = event["start"]
            end = event["end"]
            formatted = f"Event: {summary}\nStart: {start}\nEnd: {end}"
            lines.append(formatted)

 schedule_string = "\n\n".join(lines)
 messages = f"{schedule_string}"
 
 user_input = {
         
 "user_id": fe_id ,
 "message": messages
  }
     
 with httpx.Client() as client:
        response =   client.post(f"https://{url}/chat", json=user_input, timeout=40.0)
        return jsonify(status="user Calendar accessed!")
 
@app.route("/calendar-access")
def Calendaraccess():
    frontend_user_id = request.args.get("user_id")
   
    session["pending_message"] = "fetch_schedule"  # ✅ Save the intent
    return oAuth.Fittergem.authorize_redirect(
    redirect_uri=url_for("Calendarstore", _external=True),
    state=frontend_user_id,  # ✅ store user id here
    access_type="offline",
    prompt="consent"
)

@app.route("/calendar-token-store", methods=["POST"])
def store_token_with_timezone():
    db = SessionLocal()
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"error": "User not logged in"}), 403

    data = request.get_json()
    timezone = data.get("timezone")

    if not timezone:
        return jsonify({"error": "Timezone missing"}), 400

    user_token = db.query(Calendar).filter(Calendar.client_id_google == user_id).first()
    if not user_token:
        return jsonify({"error": "No token found for user"}), 404

    token_data = json.loads(user_token.token_google)
    token_data["timezone"] = timezone
    user_token.token_google = json.dumps(token_data)

    db.commit()
    return jsonify({"status": "Timezone saved ✅"})



@app.route("/Calendar-info-store", methods=['GET', 'POST'])
def Calendarstore():
    frontend_user_id = request.args.get("state")

    print("Calendar-info-store endpoint called!")
    try:
     db = SessionLocal()
     token = oAuth.Fittergem.authorize_access_token()

     print("Calendar-info-store authorization completed!")

   
    
     creds_info = {
        "token": token["access_token"],
        "refresh_token": token.get("refresh_token"),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": app.config["OAUTH2_CLIENT_ID"],
        "client_secret": app.config["OAUTH2_CLIENT_SECRET"],
        "scopes": SCOPES,
        
        
     }

     access_token = token["access_token"]
     uinfo = requests.get(
     "https://www.googleapis.com/oauth2/v1/userinfo",
     headers={"Authorization": f"Bearer {access_token}"}
     ).json()
     google_id = uinfo["id"]  
     new_user = Calendar(
        client_id_google=google_id,
        token_google=json.dumps(creds_info),
        app_user_id=frontend_user_id,   
        scope_google=token.get("scope"),
        client_secret_google=app.config["OAUTH2_CLIENT_SECRET"]
     )
     print("user info stored in db!")

     db.merge(new_user)
     db.commit()
    finally:
     db.close()

    # ✅ Check if we had intent to fetch calendar immediately
    pending = session.pop("pending_message", None)
    if pending == "fetch_schedule":
      try:
        user_id = google_id
        db = SessionLocal()
        user_exist = db.query(Calendar).filter(Calendar.client_id_google == user_id).first()

        if not user_exist:
            raise Exception("No calendar token found")

        data = json.loads(user_exist.token_google)
        creds = Credentials.from_authorized_user_info(data, SCOPES)
        service = build("calendar", "v3", credentials=creds)

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            user_exist.token_google = creds.to_json()
            db.commit()

        timezone_id = data.get("timezone", "America/Toronto")

        # Get events
        time = datetime.now(ZoneInfo(timezone_id)).replace(hour=0, minute=0, second=0, microsecond=0)
        all_events = []

        for i in range(7):
            est_start = time + timedelta(days=i)
            est_end = time + timedelta(days=i + 1)
            time_min = est_start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            time_max = est_end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

            events_result = service.events().list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime"
            ).execute()

            events = events_result.get("items", [])
            for event in events:
                event_detail = {
                    "start": event["start"].get("dateTime", event["start"].get("date")),
                    "end": event["end"].get("dateTime"),
                    "summary": event.get("summary")
                }
                all_events.append(event_detail)

        lines = []
        for event in all_events:
            formatted = f"Event: {event['summary']}\nStart: {event['start']}\nEnd: {event['end']}"
            lines.append(formatted)

        schedule_string = "\n\n".join(lines)

        if not lines:
            prompt = (
                "if no events found. Do not assume the user is free. "
                "When recommending workouts, diet changes, or other plans, do not assume full availability. "
                "Instead, ask the user about their preferred or available time slots before making detailed suggestions. "
            )
        else:
            prompt = (
                "The following is a 7-day Google Calendar schedule. Summarize when the user is busy..."
                # ⬆️ Keep your original prompt
            )

        messages = f"{prompt}\n\n{schedule_string}"






        # ✅ Send to GPT
        user_input = {
            "user_id": frontend_user_id,  # very important
            "events": messages
        }

        response = httpx.post(f"https://{url}/user-calendar-data-store", json=user_input, timeout=40.0)

        print("✅ GPT calendar response:", response.text)

      except Exception as e:
        print("❌ Error sending calendar to GPT:", e)


    return """
    <html>
      <body style="font-family: sans-serif; text-align: center; margin-top: 50px;">
        <h2>Calendar Connected!</h2>
        <p>Your schedule has been processed. You may now return to the Fittergem app.</p>
        <script>
          setTimeout(function() {
            window.close();
          }, 1000);
        </script>
      </body>
    </html>
    """


@app.route("/Calendar-update" , methods=['POST'])
def Calendar_update():
   
   
   db = SessionLocal()
   
   
   data_event= request.get_json()
  

   user= db.query(Calendar).filter(Calendar.client_id_google==session["user_id"]).first()
   if not user:
     return redirect("/calendar-access")
   
   data= json.loads(user.token_google)

   creds = Credentials.from_authorized_user_info(data, SCOPES)

   service = build("calendar", "v3", credentials=creds)
   if not creds.valid or not creds:
      if creds and creds.expired and creds.refresh_token:
         creds.refresh(Request())


   event_ids =[]

   if "events" not in data_event or not isinstance(data_event["events"], list):
      return jsonify({"error": "Invalid format: 'events' should be a list"}), 400

   for each_event in data_event["events"]:
     Calendar_event = {
        
        "summary" :  each_event["summary"] ,
        "description": each_event["event"] ,
       "start" : {
          "dateTime": each_event["time_start"] ,
          "timeZone": each_event["timeZone"]
           
        } ,
        "end" : {
           
        "dateTime": each_event["time_end"] ,
        "timeZone": each_event["timeZone"]
        }

        
     }
     new_schedule = service.events().insert(calendarId="primary", body=Calendar_event).execute()
     event_ids.append(new_schedule["id"])



   return jsonify({"status": "Events created", "event_ids": event_ids})

@app.route("/Calendar-delete", methods=['POST'])
def Calendar_event_delete():
   db = SessionLocal()
   
   
   data_event= request.get_json()
  

   user= db.query(Calendar).filter(Calendar.client_id_google==session["user_id"]).first()
   if not user:
     return redirect("/calendar-access")
   
   data= json.loads(user.token_google)

   creds = Credentials.from_authorized_user_info(data, SCOPES)

   service = build("calendar", "v3", credentials=creds)
   if not creds.valid or not creds:
      if creds and creds.expired and creds.refresh_token:
         creds.refresh(Request())
    
   
   # Add this after data_event = request.get_json()
   user_summary = data_event.get("summary")
   date = data_event.get("date")  # 'YYYY-MM-DD'
   timeZone = data_event.get("timeZone", "America/New_York")

   
   start_of_day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=ZoneInfo(timeZone))
   end_of_day = start_of_day + timedelta(days=1)

   time_min = start_of_day.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
   time_max = end_of_day.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

   events_result = service.events().list(
    calendarId="primary",
    timeMin=time_min,
    timeMax=time_max,
    singleEvents=True,
    orderBy="startTime"
    ).execute()
   try:
    events = events_result.get("items", []) 
    for event in events:
     if event.get("summary") == user_summary:
        # Optionally also match time if needed
        # Delete event
   
       service.events().delete(calendarId="primary", eventId=event["id"]).execute()
       return jsonify({"status": "Event deleted", "event_id": event["id"]})
   except Exception as e:
       return jsonify({"status": "Delete failed", "error": str(e)}), 500

# starts flask
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)