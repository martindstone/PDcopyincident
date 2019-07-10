import sys
import os
from flask import Flask, request, render_template, url_for, redirect, session, Response
import json
import requests
import traceback
import time
from threading import Thread

import pd

# import http.client as http_client
# http_client.HTTPConnection.debuglevel = 1

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or os.urandom(20)

def process_alerts(token, from_email, incident_id, new_incident_id):
	incident_alerts = pd.fetch(api_key=token, endpoint=f"incidents/{incident_id}/alerts")
	for alert in incident_alerts:
		alert_id = alert["id"]
		move_alert(token, from_email, incident_id, alert_id, new_incident_id)

def move_alert(token, from_email, incident_id, alert_id, new_incident_id):
	alert_add_data = {
		"alert": {
			"type": "alert",
			"incident": {
				"type": "incident_reference", 
				"id": new_incident_id
			}
		}
	}
	alert_add_result = pd.request(
		api_key=token, 
		endpoint=f"incidents/{incident_id}/alerts/{alert_id}",
		method="PUT", 
		data=alert_add_data,
		addheaders={"From": from_email}
	)
	# print(alert_add_result)

def email_for_user_id(token, user_id):
	user = pd.request(api_key=token, endpoint=f"users/{user_id}")
	return user['user']['email']

def process_notes(token, incident_id, new_incident_id):
	incident_notes = pd.fetch(api_key=token, endpoint=f"incidents/{incident_id}/notes")
	incident_notes.reverse()
	for note in incident_notes:
		note_add_data = {
			"note": {
				"content": f"{note['content']} ({note['created_at']})"
			}
		}
		note_add_result = pd.request(
			api_key=token,
			endpoint=f"incidents/{new_incident_id}/notes",
			method="POST",
			data=note_add_data,
			addheaders={"From": email_for_user_id(token, note["user"]["id"])}
		)
		# print(note_add_result)

@app.route('/copyincident', methods=['POST'])
def copyincident():
	token = request.args.get('token')
	if token == None:
		print("no token in request")
		return "ok"

	body = request.get_json()
	if body == None:
		print("no JSON body")
		return "ok"

	try:
		incident_url = body["messages"][0]["incident"]["html_url"]
		message = body["messages"][0]
		event = message['event']
		if event != 'incident.custom':
			print(f"Event is {event}, doing nothing")
			return "ok"
		user_id = message['log_entries'][0]['agent']['id']
		user = pd.request(api_key=token, endpoint=f"users/{user_id}")
		from_email = user['user']['email']

		incident_id = message['incident']['id']
		incident = pd.request(api_key=token, endpoint=f"incidents/{incident_id}")

		del incident["incident"]["id"]
		incident["incident"]["status"] = "triggered"
		incident["incident"]["title"] = f"Copy of {incident['incident']['title']}"
		del incident["incident"]["assignments"]
		del incident["incident"]["incident_key"]

		incident_post_result = pd.request(api_key=token, endpoint="incidents", method="POST", data=incident, addheaders={"From": from_email})
		new_incident_id = incident_post_result["incident"]["id"]
		print(f"Copied incident {incident_url} to {new_incident_id}")

		alerts_thread = Thread(target=process_alerts, args=(token, from_email, incident_id, new_incident_id))
		alerts_thread.start()
		print(f"started thread for incident alerts on {new_incident_id}")
		notes_thread = Thread(target=process_notes, args=(token, incident_id, new_incident_id))
		notes_thread.start()
		print(f"started thread for incident notes on {new_incident_id}")

	except Exception as e:
		traceback.print_exc()

	r = "ok"
	return r
