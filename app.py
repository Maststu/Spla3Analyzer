import json
from pprint import pprint
import pymongo
import my_s3s
from collections import Counter
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
            
        else:
            my_s3s.set_language()

            return render_template("login.html",url=my_s3s.iksm.get_nintendo_url(my_s3s.A_VERSION,my_s3s.APP_USER_AGENT))

    return render_template("home.html")

@app.route("/logout",methods=["GET","POST"])
def logout():
    if my_s3s.SESSION_TOKEN =="" or my_s3s.GTOKEN == "" or my_s3s.BULLETTOKEN == "":
        return render_template("home.html")
    else:
        if request.method  == 'POST':
            
            #config.txtの内容をクリア
            
            with open('config.txt','r+')as f:
                f.truncate(0)
            
            # #game_col.delete_many({})
            # print(my_s3s.SESSION_TOKEN)
            
    
    return render_template("logout.html")


    
@app.route("/show_winrate",methods=["GET","POST"])
def show_winrate():
    df = game_col.find().sort("playedTime",-1)
    
    if request.method == 'POST':
        weapon=request.form['weapon']
    else:
        weapon =request.args.get('weapon','all')
    
        
    return render_template("show_winrate.html",df=df,weapon=weapon)

@app.route("/show_winrate_stage",methods=["GET","POST"])
def show_winrate_stage():
    df = game_col.find().sort("playedTime",-1)
    
    if request.method == 'POST':
        weapon=request.form['weapon']
    else:
        weapon =request.args.get('weapon','all')
    
        
    return render_template("show_winrate_stage.html",df=df,weapon=weapon)

@app.route('/name_search',methods=["GET","POST"])
def name_search():
    ids = Counter()
    if request.method == 'POST':
        if request.form.get('reset'):
            username = request.args.get('username', '')
        else:
            username = request.form['username']
        
    else:
        print("GET")
        
        username = request.args.get('username', 'noname')
    
    df = game_col.find({}).sort("playedTime",-1)

    return render_template("name_search.html", ids=ids, df=df, username=username)




@app.route('/config',methods=["POST"])
def config():
    return request.form.get('user')
    

@app.route("/show_json",methods=["GET","POST"])
def show_json():
    
    if game_col.find_one is None:
        if my_s3s.SESSION_TOKEN == "":

            return redirect('login')
        my_s3s.set_language()

        my_s3s.fetch_json("ink",separate=True, exportall=True, specific=True, skipprefetch=True)

    if request.method == 'POST':
        if my_s3s.SESSION_TOKEN == "":

            return redirect('login')
        if request.form.get('update'):
            my_s3s.set_language()

            my_s3s.fetch_json("ink",separate=True, exportall=True, specific=True, skipprefetch=True)
            df = game_col.find("").sort("playedTime",-1)
        elif request.form.get('mode'):
            mode = request.form['mode']
            if mode == "ALL":
                df = game_col.find("").sort("playedTime",-1)
            else:
                df = game_col.find({"vsMode.mode":mode}).sort("playedTime",-1)
           
        else:
            return "Not Found"
        
    else:
        df = game_col.find().sort("playedTime",-1)
    
    return render_template("show_json.html",df=df)




@app.route('/compatibility',methods=["GET","POST"])
def compatibility():
    
    df = game_col.find().sort("playedTime",-1)

    if request.method == 'POST':
        username = request.form['username']
    else:
        username = request.args.get('username', 'noname')
    return render_template("compatibility.html", df=df, username=username)

@app.route('/trend_weapon',methods=["GET","POST"])
def trend_weapon():
    
    df = game_col.find().sort("playedTime",-1)
    
    if request.method == 'POST':
        mode = request.form['mode']
        search_type = request.form['search_type']
    else:
        mode = request.args.get('mode', 'ALL')
        search_type = request.args.get('search_type', 'strongest')
    return render_template("trend_weapon.html", df=df, mode=mode,search_type=search_type)