import time
import schedule
import pyodbc

from itertools import groupby
from operator import itemgetter
from flask import Flask
from flask_mail import Mail
from flask_mail import Message

app = Flask(__name__)

app.config.update(dict(
    DEBUG = True,
    MAIL_SERVER = 'smtp.gmail.com',
    MAIL_PORT = 587,
    MAIL_USE_TLS = True,
    MAIL_USE_SSL = False,
    MAIL_USERNAME = 'colin@iconicmetalgear.com',
    MAIL_PASSWORD = 'CamLock1065',
))
mail = Mail(app)

def email_reminder():
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	
	cursor = connection.cursor()
	
	cursor.execute("select distinct customer_po from job where customer like 'DAIMLER' and status = 'active' and job not like '%-%'")
	
	purchase_orders = [list(x) for x in cursor.fetchall()]
	
	po_list = []
	for po in purchase_orders:
		cursor.execute("select job from job where status = 'active' and job not like '%-%' and customer like 'DAIMLER' and customer_po like '" + po[0] + "'")
		
		jobs = [list(x) for x in cursor.fetchall()]
		
		for job in jobs:
			cursor.execute("select work_center, sequence from job_operation where status = 'o' and job = '" + job[0] + "'")
			
			centers = [list(x) for x in cursor.fetchall()]
			centers.sort(key=itemgetter(1))
			
			cursor.execute("select promised_date from delivery where job = '" + job[0] + "'")
			promised = [list(x) for x in cursor.fetchall()]
			
			po.append([job[0], promised, centers[0][0]])
		
		po_list.append(po)
	
	msg = Message("Daily Daimler Reminder",
		sender="colin@iconicmetalgear.com",
		recipients=["colin@iconicmetalgear.com"])
	
	msg.html = '\n'.join([str(x) for x in po_list])
	mail.send(msg)
	
#schedule.every().day.at("06:30").do(email_reminder)

#while True:
#	schedule.run_pending()

email_reminder()