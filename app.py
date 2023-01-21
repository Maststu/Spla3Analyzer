import json
from pprint import pprint
import pymongo
import my_s3s
from flask import (Flask, current_app, g, redirect, render_template, request,
                    url_for) 

app = Flask(__name__)
myclient = pymongo.MongoClient("mongodb://localhost:27017/")
Spladb = myclient["Spla3db"]
game_col = Spladb["Game"]
@app.route("/")
def Home():
    #database
    
    return render_template("home.html")


@app.route("/login",methods=["GET","POST"])
def login():
    
    if my_s3s.SESSION_TOKEN =="" or my_s3s.GTOKEN == "" or my_s3s.BULLETTOKEN == "":
        if request.method == 'POST':
            my_s3s.iksm.get_web_view_ver()
            
            my_s3s.gen_new_tokens("blank",user_url=request.form['password'])
            #my_s3s.prefetch_checks(False)
            return render_template("home.html")
        else:
            my_s3s.set_language()

            return render_template("login.html",url=my_s3s.iksm.get_nintendo_url(my_s3s.A_VERSION,my_s3s.APP_USER_AGENT))

    return "Hello"
    
@app.route("/show_winrate",methods=["GET","POST"])
def show_winrate():
    df = game_col.find().sort("playedTime",-1)
    
    if request.method == 'POST':
        weapon=request.form['weapon']
    else:
        weapon =request.args.get('weapon','all')
        
        
    return render_template("show_winrate.html",df=df,weapon=weapon)

@app.route('/name_search',methods=["GET","POST"])
def name_search():
    with open('./templates/results.json') as f:
        df = json.load(f)
    
    if request.method == 'POST':
        username = request.form['username']
    else:
        username = request.args.get('username', 'noname')
    
    df = game_col.find().sort("playedTime",-1)

    return render_template("name_search.html", df=df, username=username)




@app.route('/config',methods=["POST"])
def config():
    return request.form.get('user')
    

@app.route("/show_json",methods=["GET","POST"])
def show_json():
    

    if request.method == 'POST':
        if my_s3s.SESSION_TOKEN == "":

            return redirect('login')
        my_s3s.set_language()

        my_s3s.fetch_json("ink",separate=True, exportall=True, specific=True, skipprefetch=True)

    df = game_col.find().sort("playedTime",-1)
    return render_template("show_json.html",df=df)

@app.route("/show_all_json")
def show_all_json():
    with open('./templates/all.json') as f:
        df = json.load(f)

    df_player = df['data']['vsHistoryDetail']['myTeam']['players']
    
    return render_template("show_all_json.html",df=df_player)
    return "hello"



@app.route('/compatibility',methods=["GET","POST"])
def compatibility():
    with open('./templates/results.json') as f:
        df = json.load(f)

    if request.method == 'POST':
        username = request.form['username']
    else:
        username = request.args.get('username', 'noname')
    return render_template("compatibility.html", df=df, username=username)