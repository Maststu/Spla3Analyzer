#!/usr/bin/env python
# s3s (ↄ) 2022 eli fessler (frozenpandaman), clovervidia
# Based on splatnet2statink (ↄ) 2017-2022 eli fessler (frozenpandaman), clovervidia
# https://github.com/frozenpandaman/s3s
# License: GPLv3

import argparse
import base64
import datetime
import json
import os
import pickle
import re
import shutil
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from subprocess import call

import iksm
import msgpack
import pymongo
import requests
import utils
from packaging import version
from collections import Counter

A_VERSION = "0.2.3"

DEBUG = False

os.system("") # ANSI escape setup
if sys.version_info[1] >= 7: # only works on python 3.7+
	sys.stdout.reconfigure(encoding='utf-8') # note: please stop using git bash

# CONFIG.TXT CREATION
if getattr(sys, 'frozen', False): # place config.txt in same directory as script (bundled or not)
	app_path = os.path.dirname(sys.executable)
elif __file__:
	app_path = os.path.dirname(__file__)
config_path = os.path.join(app_path, "config.txt")

try:
	config_file = open(config_path, "r")
	CONFIG_DATA = json.load(config_file)
	config_file.close()
except (IOError, ValueError):
	print("Generating new config file.")
	CONFIG_DATA = {"api_key": "", "acc_loc": "", "gtoken": "", "bullettoken": "", "session_token": "", "f_gen": "https://api.imink.app/f"}
	config_file = open(config_path, "w")
	config_file.seek(0)
	config_file.write(json.dumps(CONFIG_DATA, indent=4, sort_keys=False, separators=(',', ': ')))
	config_file.close()
	config_file = open(config_path, "r")
	CONFIG_DATA = json.load(config_file)
	config_file.close()

# SET GLOBALS
API_KEY       = CONFIG_DATA["api_key"]       # for stat.ink
USER_LANG     = CONFIG_DATA["acc_loc"][:5]   # user input
USER_COUNTRY  = CONFIG_DATA["acc_loc"][-2:]  # nintendo account info
GTOKEN        = CONFIG_DATA["gtoken"]        # for accessing splatnet - base64 json web token
BULLETTOKEN   = CONFIG_DATA["bullettoken"]   # for accessing splatnet - base64
SESSION_TOKEN = CONFIG_DATA["session_token"] # for nintendo login
F_GEN_URL     = CONFIG_DATA["f_gen"]         # endpoint for generating f (imink API by default)

thread_pool = ThreadPoolExecutor(max_workers=2)

# SET HTTP HEADERS
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Linux; Android 11; Pixel 5) ' \
						'AppleWebKit/537.36 (KHTML, like Gecko) ' \
						'Chrome/94.0.4606.61 Mobile Safari/537.36'
APP_USER_AGENT = str(CONFIG_DATA.get("app_user_agent", DEFAULT_USER_AGENT))

#database
myclient = pymongo.MongoClient("mongodb://localhost:27017/")
Spladb = myclient["Spla3db"]
game_col = Spladb["Game"]
playtime = Counter()

def write_config(tokens):
	'''Writes config file and updates the global variables.'''

	config_file = open(config_path, "w")
	config_file.seek(0)
	config_file.write(json.dumps(tokens, indent=4, sort_keys=False, separators=(',', ': ')))
	config_file.close()

	config_file = open(config_path, "r")
	CONFIG_DATA = json.load(config_file)

	global API_KEY
	API_KEY = CONFIG_DATA["api_key"]
	global USER_LANG
	USER_LANG = CONFIG_DATA["acc_loc"][:5]
	global USER_COUNTRY
	USER_COUNTRY = CONFIG_DATA["acc_loc"][-2:]
	global GTOKEN
	GTOKEN = CONFIG_DATA["gtoken"]
	global BULLETTOKEN
	BULLETTOKEN = CONFIG_DATA["bullettoken"]
	global SESSION_TOKEN
	SESSION_TOKEN = CONFIG_DATA["session_token"]

	config_file.close()


def headbutt(forcelang=None):
	'''Returns a (dynamic!) header used for GraphQL requests.'''

	if forcelang:
		lang    = forcelang
		country = forcelang[-2:]
	else:
		lang    = USER_LANG
		country = USER_COUNTRY

	graphql_head = {
		'Authorization':    f'Bearer {BULLETTOKEN}', # update every time it's called with current global var
		'Accept-Language':  lang,
		'User-Agent':       APP_USER_AGENT,
		'X-Web-View-Ver':   iksm.get_web_view_ver(),
		'Content-Type':     'application/json',
		'Accept':           '*/*',
		'Origin':           iksm.SPLATNET3_URL,
		'X-Requested-With': 'com.nintendo.znca',
		'Referer':          f'{iksm.SPLATNET3_URL}?lang={lang}&na_country={country}&na_lang={lang}',
		'Accept-Encoding':  'gzip, deflate'
	}
	return graphql_head


def prefetch_checks(printout=False):
	'''Queries the SplatNet 3 homepage to check if our gtoken & bulletToken are still valid and regenerates them if not.'''

	if printout:
		print("Validating your tokens...", end='\r')

	iksm.get_web_view_ver() # setup

	if SESSION_TOKEN == "" or GTOKEN == "" or BULLETTOKEN == "":
		gen_new_tokens("blank")
	

	sha = utils.translate_rid["HomeQuery"]
	test = requests.post(utils.GRAPHQL_URL, data=utils.gen_graphql_body(sha), headers=headbutt(), cookies=dict(_gtoken=GTOKEN))
	if test.status_code != 200:
		if printout:
			print("\n")
		gen_new_tokens("expiry")
	else:
		if printout:
			print("Validating your tokens... done.\n")



def gen_new_tokens(reason, force=False, user_url=""):
	'''Attempts to generate new tokens when the saved ones have expired.'''
	
	manual_entry = False
	if force != True: # unless we force our way through
		if reason == "blank":
			print("Blank token(s).          ")
		elif reason == "expiry":
			print("The stored tokens have expired.")
		else:
			print("Cannot access SplatNet 3 without having played online.")
			sys.exit(0)

	if SESSION_TOKEN == "":
		print("Please log in to your Nintendo Account to obtain your session_token.")
		new_token = iksm.log_in(A_VERSION, APP_USER_AGENT,user_url)
		if new_token is None:
			print("There was a problem logging you in. Please try again later.")
		elif new_token == "skip":
			manual_entry = True
		else:
			print("\nWrote session_token to config.txt.")
		CONFIG_DATA["session_token"] = new_token
		write_config(CONFIG_DATA)
	elif SESSION_TOKEN == "skip":
		manual_entry = True

	if manual_entry: # no session_token ever gets stored
		print("\nYou have opted against automatic token generation and must manually input your tokens.\n")
		new_gtoken, new_bullettoken = iksm.enter_tokens()
		acc_lang = "en-US" # overwritten by user setting
		acc_country = "US"
		print("Using `US` for country by default. This can be changed in config.txt.")
	else:
	
		new_gtoken, acc_name, acc_lang, acc_country = iksm.get_gtoken(F_GEN_URL, SESSION_TOKEN, A_VERSION)
		new_bullettoken = iksm.get_bullet(new_gtoken, APP_USER_AGENT, acc_lang, acc_country)
	CONFIG_DATA["gtoken"] = new_gtoken # valid for 6 hours
	CONFIG_DATA["bullettoken"] = new_bullettoken # valid for 2 hours

	global USER_LANG
	if acc_lang != USER_LANG:
		acc_lang = USER_LANG
	CONFIG_DATA["acc_loc"] = f"{acc_lang}|{acc_country}"

	write_config(CONFIG_DATA)

	if new_bullettoken == "":
		print("Wrote gtoken to config.txt, but could not generate bulletToken.")
		print("Is SplatNet 3 undergoing maintenance?")
		sys.exit(1)
	if manual_entry:
		print("Wrote tokens to config.txt.\n") # and updates acc_country if necessary...
	else:
		print(f"Wrote tokens for {acc_name} to config.txt.\n")


def fetch_json(which, separate=False, exportall=False, specific=False, numbers_only=False, printout=False, skipprefetch=False):
	'''Returns results JSON from SplatNet 3, including a combined dictionary for battles + SR jobs if requested.'''


	prefetch_checks(printout)
	
	
	ink_list, salmon_list = [], []
	parent_files = []

	queries = []
	if which == "both" or which == "ink":
		if specific in (True, "regular"):
			queries.append("RegularBattleHistoriesQuery")
		if specific in (True, "anarchy"):
			queries.append("BankaraBattleHistoriesQuery")
		if specific in (True, "x"):
			queries.append("XBattleHistoriesQuery")
		if specific in (True, "private") and not utils.custom_key_exists("ignore_private", CONFIG_DATA):
			queries.append("PrivateBattleHistoriesQuery")
		else:
			if DEBUG:
				print("* not specific, just looking at latest")
			queries.append("LatestBattleHistoriesQuery")
	else:
		queries.append(None)
	if which in ("both", "salmon"):
		queries.append("CoopHistoryQuery")
	else:
		queries.append(None)

	needs_sorted = False # https://ygdp.yale.edu/phenomena/needs-washed :D
	

	#print(json.dumps(query1_resp,sort_keys=True, indent=4))
	
	for sha in queries:
		if sha is not None:
			if DEBUG:
				print(f"* making query1 to {sha}")
			lang = 'en-US' if sha == "CoopHistoryQuery" else None
			sha = utils.translate_rid[sha]
			battle_ids, job_ids = [], []
			#試合のidを含むjsonファイル
			query1 = requests.post(utils.GRAPHQL_URL,
				data=utils.gen_graphql_body(sha),
				headers=headbutt(forcelang=lang),
				cookies=dict(_gtoken=GTOKEN))
			query1_resp = json.loads(query1.text)
		

			#swim()
			
			# ink battles - latest 50 of any type
			if "latestBattleHistories" in query1_resp["data"]:
				for battle_group in query1_resp["data"]["latestBattleHistories"]["historyGroups"]["nodes"]:
					for battle in battle_group["historyDetails"]["nodes"]:
						if game_col.find_one({"id":battle["id"]}) is None:
							battle_ids.append(battle["id"]) # don't filter out private battles here - do that in post_result()

			# ink battles - latest 50 turf war
			elif "regularBattleHistories" in query1_resp["data"]:
				needs_sorted = True
				for battle_group in query1_resp["data"]["regularBattleHistories"]["historyGroups"]["nodes"]:
					for battle in battle_group["historyDetails"]["nodes"]:
						

						if game_col.find_one({"id":battle["id"]}) is None:
							battle_ids.append(battle["id"]) # don't filter out private battles here - do that in post_result()
			# ink battles - latest 50 anarchy battles
			elif "bankaraBattleHistories" in query1_resp["data"]:
				needs_sorted = True
				for battle_group in query1_resp["data"]["bankaraBattleHistories"]["historyGroups"]["nodes"]:
					for battle in battle_group["historyDetails"]["nodes"]:
						if game_col.find_one({"id":battle["id"]}) is None:
							battle_ids.append(battle["id"]) # don't filter out private battles here - do that in post_result()
			# ink battles - latest 50 x battles
			elif "xBattleHistories" in query1_resp["data"]:
				needs_sorted = True
				for battle_group in query1_resp["data"]["xBattleHistories"]["historyGroups"]["nodes"]:
					for battle in battle_group["historyDetails"]["nodes"]:
						if game_col.find_one({"id":battle["id"]}) is None:
							battle_ids.append(battle["id"]) # don't filter out private battles here - do that in post_result()
			# ink battles - latest 50 private battles
			elif "privateBattleHistories" in query1_resp["data"] \
			and not utils.custom_key_exists("ignore_private", CONFIG_DATA):
				needs_sorted = True
				for battle_group in query1_resp["data"]["privateBattleHistories"]["historyGroups"]["nodes"]:
					for battle in battle_group["historyDetails"]["nodes"]:
						if game_col.find_one({"id":battle["id"]}) is None:
							battle_ids.append(battle["id"]) # don't filter out private battles here - do that in post_result()

			# salmon run jobs - latest 50
			elif "coopResult" in query1_resp["data"]:
				for shift in query1_resp["data"]["coopResult"]["historyGroups"]["nodes"]:
					for job in shift["historyDetails"]["nodes"]:
						job_ids.append(job["id"])

			if numbers_only:
				ink_list.extend(battle_ids)
				salmon_list.extend(job_ids)
			else: # ALL DATA - TAKES A LONG TIME
				thread_pool.map(fetch_detailed_result, [True]*len(battle_ids), battle_ids)
				#thread_pool.map(fetch_detailed_result, [False]*len(job_ids), job_ids)

				
			parent_files.append(query1_resp)
		else: # sha = None (we don't want to get the specified result type)
			pass

		



def fetch_detailed_result(is_vs_history, history_id):
	'''Helper function for fetch_json().'''
	
	sha = "VsHistoryDetailQuery" if is_vs_history else "CoopHistoryDetailQuery"
	varname = "vsResultId" if is_vs_history else "coopHistoryDetailId"
	lang = None if is_vs_history else 'en-US'

	query2 = requests.post(utils.GRAPHQL_URL,
		data=utils.gen_graphql_body(utils.translate_rid[sha], varname, history_id),
		headers=headbutt(forcelang=lang),
		cookies=dict(_gtoken=GTOKEN))
	query2_resp = json.loads(query2.text)
	query2_hist = query2_resp["data"]["vsHistoryDetail"]
	
	print("new_insert")
	game_col.insert_one(query2_hist)
	print(query2_hist["playedTime"])



	return query2_resp


def check_for_updates():
	'''Checks the script version against the repo, reminding users to update if available.'''

	try:
		latest_script = requests.get("https://raw.githubusercontent.com/frozenpandaman/s3s/master/s3s.py")
		new_version = re.search(r'A_VERSION = "([\d.]*)"', latest_script.text).group(1)
		update_available = version.parse(new_version) > version.parse(A_VERSION)
		if update_available:
			print(f"\nThere is a new version (v{new_version}) available.", end='')
			if os.path.isdir(".git"):
				update_now = input("\nWould you like to update now? [Y/n] ")
				if update_now == "" or update_now[0].lower() == "y":
					FNULL = open(os.devnull, "w")
					call(["git", "checkout", "."], stdout=FNULL, stderr=FNULL)
					call(["git", "checkout", "master"], stdout=FNULL, stderr=FNULL)
					call(["git", "pull"], stdout=FNULL, stderr=FNULL)
					print(f"Successfully updated to v{new_version}. Please restart s3s.")
					sys.exit(0)
				else:
					print("Please update to the latest version by running " \
						'`\033[91m' + "git pull" + '\033[0m' \
						"` as soon as possible.\n")
			else: # no git directory
				print(" Visit the site below to update:\nhttps://github.com/frozenpandaman/s3s\n")
	except Exception as e: # if there's a problem connecting to github
		print('\033[3m' + "» Couldn't connect to GitHub. Please update the script manually via " \
			'`\033[91m' + "git pull" + '\033[0m' + "`." + '\033[0m' + "\n")
		# print('\033[3m' + "» While s3s is in beta, please update the script regularly via " \
		# 	'`\033[91m' + "git pull" + '\033[0m' + "`." + '\033[0m' + "\n")

def set_language():
	'''Prompts the user to set their game language.'''

	if USER_LANG == "":
		print("Default locale is en-US. Press Enter to accept, or enter your own (see readme for list).")
		language_code = ""

		if language_code == "":
			CONFIG_DATA["acc_loc"] = "JP|JP|JP" # default
			write_config(CONFIG_DATA)
			return
		else:
			language_list = [
				"de-DE", "en-GB", "en-US", "es-ES", "es-MX", "fr-CA", "fr-FR",
				"it-IT", "ja-JP", "ko-KR", "nl-NL", "ru-RU", "zh-CN", "zh-TW"
			]
			while language_code not in language_list:
				print("Invalid language code. Please try entering it again:")
				language_code = input("")
			CONFIG_DATA["acc_loc"] = f"{language_code}|US" # default to US until set by ninty
			write_config(CONFIG_DATA)
	return


def get_num_results(which):
	'''I/O for getting number of battles/jobs to upload.'''

	noun = utils.set_noun(which)
	try:
		if which == "ink": # TODO update '200' number when league released
			print("Note: 50 recent battles of each type (up to 200 total) may be uploaded by instead manually exporting data with " \
				'\033[91m' + "-o" + '\033[0m' + ".\n")
		n = int(input(f"Number of recent {noun} to upload (0-50)? "))
	except ValueError:
		print("Please enter an integer between 0 and 50. Exiting.")
		sys.exit(0)
	if n < 1:
		print("Exiting without uploading anything.")
		sys.exit(0)
	elif n > 50:
		if which == "salmon":
			print("SplatNet 3 only stores the 50 most recent jobs. Exiting.")
		elif which == "ink":
			print("\nIn this mode, s3s can only fetch the 50 most recent battles (of any type) at once. " \
				"To export & upload the 50 most recent battles of each type " \
				"(Regular, Anarchy, X, and Private) for up to 200 results total, run the script with " \
				'\033[91m' + "-o" + '\033[0m' + " and then " \
				'\033[91m' + "-i results.json overview.json" + '\033[0m' + ".")
		sys.exit(0)
	else:
		return n




class SquidProgress:
	'''Displays an animation of a squid swimming while waiting. :)'''

	def __init__(self):
		self.count = 0

	def __call__(self):
		lineend = shutil.get_terminal_size()[0] - 5 # 5 = ('>=> ' or '===>') + blank 1
		ika = '>=> ' if self.count % 2 == 0 else '===>'
		sys.stdout.write(f"\r{' '*self.count}{ika}{' '*(lineend - self.count)}")
		sys.stdout.flush()
		self.count += 1
		if self.count > lineend:
			self.count = 0

	def __del__(self):
		sys.stdout.write(f"\r{' '*(shutil.get_terminal_size()[0] - 1)}\r")
		sys.stdout.flush()



# def main():
# 	'''Main process, including I/O and setup.'''
	
# 	print('\033[93m\033[1m' + "s3s" + '\033[0m\033[93m' + f" v{A_VERSION}" + '\033[0m')
	
# 	# setup
# 	#######
# 	#check_for_updates()
# 	#check_statink_key()
# 	set_language()

# 	#set_DataBase()
# 	fetch_json("both",separate=True, exportall=True, specific=True, skipprefetch=True)
	
	
# 	#print("\nHave fun playing Splatoon 3! :) Bye!")
	
# 	sys.exit(0)

	
	
# 	thread_pool.shutdown(wait=True)


# if __name__ == "__main__":
# 	main()