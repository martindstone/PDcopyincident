import sys
import os
from flask import Flask, request, render_template, url_for, redirect, session, Response
import json
import requests
import traceback
import time

import pd

# import http.client as http_client
# http_client.HTTPConnection.debuglevel = 1

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or os.urandom(20)

@app.route('/copyincident', methods=['POST'])
def copyincident():
	token = request.args.get('token')
	if token == None:
		print("no token in request")
		return "ok"

	print(f"token is {token}")

	body = request.get_json()
	if body == None:
		print("no JSON body")
		return "ok"

	try:
		for message in body['messages']:
			# print(json.dumps(message, indent=4))
			event = message['event']
			print(f"event is {event}")
			if event != 'incident.custom':
				continue
			user_id = message['log_entries'][0]['agent']['id']
			user = pd.request(api_key=token, endpoint=f"users/{user_id}")
			from_email = user['user']['email']

			incident_id = message['incident']['id']
			incident = pd.request(api_key=token, endpoint=f"incidents/{incident_id}")
			incident_notes = pd.fetch(api_key=token, endpoint=f"incidents/{incident_id}/notes")
			incident_alerts = pd.fetch(api_key=token, endpoint=f"incidents/{incident_id}/alerts")

			del incident["incident"]["id"]
			incident["incident"]["status"] = "triggered"
			incident["incident"]["title"] = f"Copy of {incident['incident']['title']}"
			del incident["incident"]["assignments"]
			del incident["incident"]["incident_key"]

			incident_post_result = pd.request(api_key=token, endpoint="incidents", method="POST", data=incident, addheaders={"From": from_email})
			print(incident_post_result)
			new_incident_id = incident_post_result["incident"]["id"]

			for alert in incident_alerts:
				alert_id = alert["id"]
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
				print(alert_add_result)
	except Exception as e:
		traceback.print_exc()

	r = "ok"
	return r
