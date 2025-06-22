from flask import Flask, url_for, session, redirect, jsonify

import requests
import json
from authlib.integrations.flask_client import OAuth
import os
from dotenv import load_dotenv
from sqlalchemy import Text, Column, Integer,DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

load_dotenv()

# uses flask to communicate
# creates a flask object

app = Flask(__name__)

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
               client_kwargs= {"scope": "openid https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email" ,
               
               }
               )



@app.route("/")
def home():
    user= session.get("user")
    if not user:
       return redirect(url_for("googleLogin"))
    else:    
     token = session.get("user")
     access_token = token["access_token"]

     headers = {
     "Authorization": f"Bearer {access_token}"
      }

     response= requests.get("https://www.googleapis.com/oauth2/v1/userinfo", headers=headers)
     user_info = response.json()
     google_id = user_info["id"]
     email_id = user_info["email"]
     full_name = user_info["name"]
     first_name = user_info["given_name"]
     last_name = user_info["family_name"]



     return json.dumps(user_info, indent=4)

@app.route("/google-login")
def googleLogin():
    redirect_uri = url_for("googleCallback", _external=True)
    print(redirect_uri)
    return oAuth.Fittergem.authorize_redirect(redirect_uri)


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

        return jsonify({
            "user_id": google_id,
            "email": email_id,
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name
        })

    except Exception as e:
        print("Error during callback:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")





if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
