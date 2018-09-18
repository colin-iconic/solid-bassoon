from __future__ import print_function
import sys
import pyodbc
import itertools
import pandas as pd
import numpy as np
import datetime

from threading import Thread
from operator import itemgetter
from flask import Flask
from flask import render_template
from flask import url_for
from flask import request

from flask_mail import Mail
from flask_mail import Message

app = Flask(__name__)

app.config.update(dict(
	DEBUG = False,
	MAIL_SERVER = 'smtp.gmail.com',
	MAIL_PORT = 587,
	MAIL_USE_TLS = True,
	MAIL_USE_SSL = False,
	MAIL_USERNAME = 'colin@iconicmetalgear.com',
	MAIL_PASSWORD = 'CamLock1065',
))

mail = Mail(app)

@app.route('/')
def home():
	return render_template('home.html')

@app.route('/office')
def office():
	return render_template('office.html')

@app.route('/configurator')
def configurator():
	return render_template('configurator.html')

@app.route('/pullfrom')
def pullfrom(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')

	cursor = connection.cursor()
	cursor.execute("select t1.job, t1.customer, t1.description, cast(t1.order_date as date), t1.order_quantity, t1.part_number, t1.floor_notes, t2.job, t2.order_quantity, delivery.remaining_quantity from ((select job.job, job.customer, job.description, job.order_date, job.order_quantity, job.part_number, job_operation.floor_notes, job.status from job inner join job_operation on job.job = job_operation.job where job_operation.work_center like '%pull from%' and job.status = 'active' and job_operation.status = 'o') t1 left join (select job.job, job.customer, job.description, job.order_date, job.order_quantity, job.part_number, job.status from job where job.customer = 'i-h prod' and job.status = 'active' and job.job not like '%-%' and job.part_number <> '0202') t2 on t1.part_number = t2.part_number) left join delivery on t2.job = delivery.job")

	rows = cursor.fetchall()
	head = ['Job Number', 'Customer', 'Description', 'Order Date', 'Quantity', 'Part Number', 'Notes', 'Stock Job Number', 'Order Quantity', 'Remaining Quantity']
	return render_template('generic_table.html', rows = rows, head = head, title = 'Pull From')

@app.route('/hot')
def hotlist(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("select job.priority, job.job, job.customer, job.description, cast(job.order_date as date), job.order_quantity, job.part_number, job_operation.work_center, job_operation.sequence from job inner join job_operation on job.job = job_operation.job where job.status = 'active' and job.priority < 5 and job_operation.status = 'o'")

	data = cursor.fetchall()
	jobs = []
	rows = []
	c = []
	d = []
	for a in data:
		if a[1] not in jobs:
			jobs.append(a[1])

	for a in jobs:
		centers = []
		for b in data:
			if a == b[1]:
				centers.append(b)

		centers.sort(key=itemgetter(8))
		rows.append(centers[0])

	head = ['Priority', 'Job Number', 'Customer', 'Description', 'Order Date', 'Order Quantity', 'Part Number', 'Work Center', 'Sequence']
	return render_template('generic_table.html', rows = rows, head = head, title = 'Hot List')

@app.route('/racks')
def racklist(name=None):
	class StockItem(object):
		part = ''
		usedin = []
		description = ''
		inproduction = 0
		sold = 0
		productionjobs = []
		soldjobs = []
		shipped = 0

		def __init__(self, part, usedin, description, inproduction=0, sold=0, productionjobs=[], soldjobs=[], shipped = 0):
			self.part = part
			self.usedin = usedin
			self.description = description
			self.inproduction = inproduction
			self.sold = sold
			self.productionjobs = productionjobs
			self.soldjobs = soldjobs
			self.shipped = shipped

	def make_stockitem(part, usedin, description, inproduction=0, sold=0, productionjobs=[], soldjobs=[], shipped = 0):
		stockitem = StockItem(part, usedin, description, inproduction=0, sold=0, productionjobs=[], soldjobs=[], shipped=0)
		return stockitem

	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	#Flat 70"
	flat70 = make_stockitem('1300', ['1319'], '70" Flat Headache Rack')
	cursor.execute("select job.job as job from job where job.job not like '%-%' and job.customer like 'I-H PROD' and job.part_number = '{0}' and job.status = 'active'".format(flat70.part))

	pjobs = cursor.fetchall()

	flat70.productionjobs = [x.job for x in pjobs]

	cursor.execute("select sum(job.order_quantity) as qty from job where job.job in ('{0}')".format("', '".join(flat70.productionjobs)))
	prodqty = cursor.fetchall()
	flat70.inproduction = prodqty[0][0] or 0

	cursor.execute("select job.job as job from job where job.job not like '%-%' and job.customer not like 'I-H PROD' and job.part_number in ('{0}', '{1}') and job.status = 'active'".format(flat70.part, "', '".join(flat70.usedin)))
	sjobs = cursor.fetchall()
	flat70.soldjobs = [x.job for x in sjobs]

	cursor.execute("select sum(job.order_quantity) as qty from job where job.job in ('{0}')".format("', '".join(flat70.soldjobs)))
	soldqty = cursor.fetchall()
	flat70.sold = soldqty[0][0] or 0

	cursor.execute("select sum(shipped_quantity) as shipped from job where job.job in ('{0}')".format("', '".join(flat70.productionjobs)))
	shipped = cursor.fetchall()
	flat70.shipped = shipped[0][0] or 0

	#Jailbar 70"
	jb70 = make_stockitem('1364', ['1351', '1352', '1352', '1322'], '70" Jailbar Headache Rack')
	cursor.execute("select job.job as job from job where job.job not like '%-%' and job.customer like 'I-H PROD' and job.part_number = '{0}' and job.status = 'active'".format(jb70.part))
	pjobs = cursor.fetchall()
	jb70.productionjobs = [x.job for x in pjobs]

	cursor.execute("select sum(job.order_quantity) as qty from job where job.job in ('{0}')".format("', '".join(jb70.productionjobs)))
	prodqty = cursor.fetchall()
	jb70.inproduction = prodqty[0][0] or 0

	cursor.execute("select job.job as job from job where job.job not like '%-%' and job.customer not like 'I-H PROD' and job.part_number in ('{0}', '{1}') and job.status = 'active'".format(jb70.part, "', '".join(jb70.usedin)))
	sjobs = cursor.fetchall()
	jb70.soldjobs = [x.job for x in sjobs]

	cursor.execute("select sum(job.order_quantity) as qty from job where job.job in ('{0}')".format("', '".join(jb70.soldjobs)))
	soldqty = cursor.fetchall()
	jb70.sold = soldqty[0][0] or 0

	cursor.execute("select sum(shipped_quantity) as shipped from job where job.job in ('{0}')".format("', '".join(jb70.productionjobs)))
	shipped = cursor.fetchall()
	jb70.shipped = shipped[0][0] or 0

	#Flat 76"
	flat76 = make_stockitem('1301', ['1320', '1353', '1362'], '76" Flat Headache Rack')
	cursor.execute("select job.job as job from job where job.job not like '%-%' and job.customer like 'I-H PROD' and job.part_number = '{0}' and job.status = 'active'".format(flat76.part))
	pjobs = cursor.fetchall()
	flat76.productionjobs = [x.job for x in pjobs]

	cursor.execute("select sum(job.order_quantity) as qty from job where job.job in ('{0}')".format("', '".join(flat76.productionjobs)))
	prodqty = cursor.fetchall()
	flat76.inproduction = prodqty[0][0] or 0

	cursor.execute("select job.job as job from job where job.job not like '%-%' and job.customer not like 'I-H PROD' and job.part_number in ('{0}', '{1}') and job.status = 'active'".format(flat76.part, "', '".join(flat76.usedin)))
	sjobs = cursor.fetchall()
	flat76.soldjobs = [x.job for x in sjobs]

	cursor.execute("select sum(job.order_quantity) as qty from job where job.job in ('{0}')".format("', '".join(flat76.soldjobs)))
	soldqty = cursor.fetchall()
	flat76.sold = soldqty[0][0] or 0

	cursor.execute("select sum(shipped_quantity) as shipped from job where job.job in ('{0}')".format("', '".join(flat76.productionjobs)))
	shipped = cursor.fetchall()
	flat76.shipped = shipped[0][0] or 0

	#Jailbar 76"
	jb76 = make_stockitem('1365', ['1323', '1355', '1356', '1357'], '76" Jailbar Headache Rack')
	cursor.execute("select job.job as job from job where job.job not like '%-%' and job.customer like 'I-H PROD' and job.part_number = '{0}' and job.status = 'active'".format(jb76.part))
	pjobs = cursor.fetchall()
	jb76.productionjobs = [x.job for x in pjobs]

	cursor.execute("select sum(job.order_quantity) as qty from job where job.job in ('{0}')".format("', '".join(jb76.productionjobs)))
	prodqty = cursor.fetchall()
	jb76.inproduction = prodqty[0][0] or 0

	cursor.execute("select job.job as job from job where job.job not like '%-%' and job.customer not like 'I-H PROD' and job.part_number in ('{0}', '{1}') and job.status = 'active'".format(jb76.part, "', '".join(jb76.usedin)))
	sjobs = cursor.fetchall()
	jb76.soldjobs = [x.job for x in sjobs]

	cursor.execute("select sum(job.order_quantity) as qty from job where job.job in ('{0}')".format("', '".join(jb76.soldjobs)))
	soldqty = cursor.fetchall()
	jb76.sold = soldqty[0][0] or 0

	cursor.execute("select sum(shipped_quantity) as shipped from job where job.job in ('{0}')".format("', '".join(jb76.productionjobs)))
	shipped = cursor.fetchall()
	jb76.shipped = shipped[0][0] or 0

	#Flat 86"
	flat86 = make_stockitem('1302', ['1321'], '86" Flat Headache Rack')
	cursor.execute("select job.job as job from job where job.job not like '%-%' and job.customer like 'I-H PROD' and job.part_number = '{0}' and job.status = 'active'".format(flat86.part))
	pjobs = cursor.fetchall()
	flat86.productionjobs = [x.job for x in pjobs]

	cursor.execute("select sum(job.order_quantity) as qty from job where job.job in ('{0}')".format("', '".join(flat86.productionjobs)))
	prodqty = cursor.fetchall()
	flat86.inproduction = prodqty[0][0] or 0

	cursor.execute("select job.job as job from job where job.job not like '%-%' and job.customer not like 'I-H PROD' and job.part_number in ('{0}', '{1}') and job.status = 'active'".format(flat86.part, "', '".join(flat86.usedin)))
	sjobs = cursor.fetchall()
	flat86.soldjobs = [x.job for x in sjobs]

	cursor.execute("select sum(job.order_quantity) as qty from job where job.job in ('{0}')".format("', '".join(flat86.soldjobs)))
	soldqty = cursor.fetchall()
	flat86.sold = soldqty[0][0] or 0

	cursor.execute("select sum(shipped_quantity) as shipped from job where job.job in ('{0}')".format("', '".join(flat86.productionjobs)))
	shipped = cursor.fetchall()
	flat86.shipped = shipped[0][0] or 0

	#Jailbar 86"
	jb86 = make_stockitem('1366', ['1324','1359','1360','1361'], '86" Jailbar Headache Rack')
	cursor.execute("select job.job as job from job where job.job not like '%-%' and job.customer like 'I-H PROD' and job.part_number = '{0}' and job.status = 'active'".format(jb86.part))
	pjobs = cursor.fetchall()
	jb86.productionjobs = [x.job for x in pjobs]

	cursor.execute("select sum(job.order_quantity) as qty from job where job.job in ('{0}')".format("', '".join(jb86.productionjobs)))
	prodqty = cursor.fetchall()
	jb86.inproduction = prodqty[0][0] or 0

	cursor.execute("select job.job as job from job where job.job not like '%-%' and job.customer not like 'I-H PROD' and job.part_number in ('{0}', '{1}') and job.status = 'active'".format(jb86.part, "', '".join(jb86.usedin)))
	sjobs = cursor.fetchall()
	jb86.soldjobs = [x.job for x in sjobs]

	cursor.execute("select sum(job.order_quantity) as qty from job where job.job in ('{0}')".format("', '".join(jb86.soldjobs)))
	soldqty = cursor.fetchall()
	jb86.sold = soldqty[0][0] or 0

	cursor.execute("select sum(shipped_quantity) as shipped from job where job.job in ('{0}')".format("', '".join(jb86.productionjobs)))
	shipped = cursor.fetchall()
	jb86.shipped = shipped[0][0] or 0

	cursor.execute("select job.job from job where job.description like '%headache%' and job.part_number like '%0202%' and job.status = 'active' and job.job not like '%-s%' and job.job not like '%-ncr%'")

	custom_racks = cursor.fetchall()

	custom_racks = [list(x) for x in custom_racks]

	rackssold = [flat70.soldjobs, jb70.soldjobs, flat76.soldjobs, jb76.soldjobs, flat86.soldjobs, jb86.soldjobs] + custom_racks
	cursor.execute("select job.description as description, job.part_number as partnumber, job.job as job, job.customer as customer, job.order_quantity as orderquantity, cast(job.order_date as date) as orderdate, cast(delivery.promised_date as date) as promiseddate, job.note_text from (job inner join delivery on job.job = delivery.job)  where job.job in ('{0}')".format("', '".join(list(itertools.chain.from_iterable(rackssold)))))
	sold = cursor.fetchall()

	racksstock = [flat70.productionjobs, jb70.productionjobs, flat76.productionjobs, jb76.productionjobs, flat86.productionjobs, jb86.productionjobs]

	tank30 = {'part': 1396}
	tank50 = {'part': 1397}
	tank70 = {'part': 1398}

	tanks = [tank30, tank50, tank70]

	for tank in tanks:
		cursor.execute("select description from material where material = '" + str(tank['part']) + "'")
		desc = cursor.fetchall()
		tank['description'] = desc[0][0]

		cursor.execute("select sum(job.order_quantity) from job where job.customer = 'I-H PROD' and job.status = 'active' and job.part_number = '" + str(tank['part']) + "'")
		tprod = cursor.fetchall()
		try:
			tank['production'] = tprod[0][0]
		except IndexError:
			tank['production'] = 0

		cursor.execute("select on_hand_qty from material_location where location_id = 'SHOP' and material = '" + str(tank['part']) + "'")
		tstock = cursor.fetchall()
		try:
			tank['stock'] = int(tstock[0][0])
		except IndexError:
			tank['stock'] = 0

	stocklist = []
	for rack in racksstock:
		for job in rack:
			stockitem = []
			cursor.execute("select description as description, part_number as partnumber, job as job, customer as customer, order_quantity as orderquantity, cast(order_date as date) as orderdate from job where job.job in ('" + job + "')")
			stock = list(cursor.fetchall()[0])
			cursor.execute("select sum(shipped_quantity) as shipped from job where job.job in ('" + job + "')")
			stock.append(list(cursor.fetchall()[0])[0])
			stocklist.append(stock)

	return render_template('rackinventory.html', data = [flat70, jb70, flat76, jb76, flat86, jb86], tanks = tanks, sold = sold, stock = stocklist, head = ['Description','Part Number','Job', 'Customer', 'Quantity', 'Order Date', 'Shipped Quantity'], title = 'Headache Rack Production Tracker')

@app.route('/onthego') #active jobs with values
def onthego(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("SELECT job.job, job.customer, job.part_number, job.description, job.order_quantity, job.total_price from job where job.status = 'Active' and job.job not like '%-%'")

	rows = cursor.fetchall()

	cursor.execute("SELECT sum(job.total_price) from job where job.status = 'Active' and job.job not like '%-%'")

	total = cursor.fetchall()

	head = ['Job Number', 'Customer', 'Part Number', 'Description', 'Order Quantity', 'Total Price', total[0][0]]
	return render_template('generic_table.html', rows = rows, head = head, title = 'Pull From')

@app.route('/job/<job>')
def jobs(job):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	joblist = [x.strip() for x in job.split(',')]

	rows = []
	for each in joblist:
		try:
			cursor.execute("select job.priority, job.job, job.customer, job.description, cast(job.order_date as date), job.order_quantity, job.part_number, job.note_text from job inner join job_operation on job.job = job_operation.job where job.job = '"+ each +"'")
		except:
			continue
		data = cursor.fetchall()
		data = [list(x) for x in data]
		jobs = []

		for a in data:
			if a[1] not in jobs:
				jobs.append(a[1])

		for a in jobs:
			cursor.execute("select work_center, sequence, status from job_operation where job = '"+a+"'")
			centers = cursor.fetchall()
			centers = [list(x) for x in centers]

			c = []
			for x in centers:
				if x[2] == 'O':
					c.append(x)

			if c == []:
				c.append(['COMPLETE', 0])
			c.sort(key=itemgetter(1))

			data[0].insert(7, c[0][0])
			rows.append(data[0])

	head = ['Priority', 'Job Number', 'Customer', 'Description', 'Order Date', 'Order Quantity', 'Part Number', 'Work Center', 'Note Text']
	return render_template('jobs_list.html', rows = rows, head = head, title = 'Job List')

@app.route('/report/boxes') #boxes ordered since January 1 2018
def boxes(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("SELECT job, customer, order_quantity, part_number, description, cast(order_date as date) from job where (description like 'thandle%' or description like 'camlock%') and job not like '%-%' and customer not like 'I-H%' and order_date > '1/1/2018 12:00:00 AM'")

	camlocks = cursor.fetchall()

	cursor.execute("SELECT sum(order_quantity) from job where (description like 'thandle%' or description like 'camlock%') and job not like '%-%' and customer not like 'I-H%' and order_date > '1/1/2018 12:00:00 AM'")

	total = cursor.fetchall()
	total = total[0]

	head = ['Job', 'Customer', 'Order Quantity', 'Part Number', 'Description', 'Order Date']
	return render_template('generic_table.html', rows = camlocks, head = head, title = 'Tool Boxes', body = 'Total: ' + str(total[0]))

@app.route('/report/bigmth') #bigmouths ordered since January 1 2018
def bigmth(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("SELECT job, customer, order_quantity, part_number, description, cast(order_date as date) from job where description like '%big mth%' and job not like '%-%' and customer not like 'I-H%' and order_date > '1/1/2018 12:00:00 AM'")

	camlocks = cursor.fetchall()

	cursor.execute("SELECT sum(order_quantity) from job where description like '%big mth%' and job not like '%-%' and customer not like 'I-H%' and order_date > '1/1/2018 12:00:00 AM'")

	total = cursor.fetchall()
	total = total[0]

	head = ['Job', 'Customer', 'Order Quantity', 'Part Number', 'Description', 'Order Date']
	return render_template('generic_table.html', rows = camlocks, head = head, title = 'Big Mouths', body = 'Total: ' + str(total[0]))

@app.route('/report/c_tax') #customer tax codes
def c_tax(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("SELECT CUSTOMER.CUSTOMER, address.phone, ADDRESS.CITY, ADDRESS.STATE, ADDRESS.COUNTRY, CUSTOMER.TAX_CODE FROM CUSTOMER INNER JOIN ADDRESS ON CUSTOMER.CUSTOMER = ADDRESS.CUSTOMER")

	info = cursor.fetchall()

	head = ['Customer', 'Phone Number', 'City', 'State', 'Country', 'Tax Code']
	return render_template('generic_table.html', rows = info, head = head, title = 'Customer Tax Code')

@app.route('/report/wip') #number of jobs and value in progress (after laser)
def wip(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("select job from job where status = 'active' and customer = 'I-H PROD'")
	jlist = cursor.fetchall()

	job_nums = []
	for job in jlist:
		job_nums.append(job[0])

	in_progress = []
	for job in job_nums:
		cursor.execute("select job_operation.work_center from job inner join job_operation on job.job = job_operation.job where job_operation.status = 'c' and job.job = '"+job+"'")
		operations = cursor.fetchall()
		if len(operations) > 3:
			in_progress.append(job)

	cursor.execute("select order_quantity, material.selling_price from (job inner join material on job.part_number = material.material) where job.job in ('" + "', '".join(in_progress) + "')")
	info = cursor.fetchall()
	info = [list(x) for x in info]
	for job in info:
		if not job[1]:
			job[1] = 0
		order_total = job[0] * job[1]
		job.append(order_total)

	total_stock = sum([x[2] for x in info])

	#===============================================
	cursor.execute("select job from job where status = 'active' and customer <> 'I-H PROD'")
	jlist = cursor.fetchall()

	job_nums = []
	for job in jlist:
		job_nums.append(job[0])

	in_progress = []
	for job in job_nums:
		cursor.execute("select job_operation.work_center from job inner join job_operation on job.job = job_operation.job where job_operation.status = 'c' and job.job = '"+job+"'")
		operations = cursor.fetchall()
		if len(operations) > 3:
			in_progress.append(job)

	cursor.execute("select sum(order_quantity) from job where job.job in ('" + "', '".join(in_progress) + "')")

	cursor.execute("select sum(total_price) from job where job.job in ('" + "', '".join(in_progress) + "')")
	cvalue = cursor.fetchall()[0][0]

	#==============================================
	pull_froms = []
	for job in job_nums:
		cursor.execute("select job.job from job inner join job_operation on job.job = job_operation.job where job_operation.work_center = 'PULL FROM' and job_operation.status = 'o' and job.job = '"+job+"'")
		pulls = cursor.fetchall()
		if pulls:
			pull_froms.append(job)

	cursor.execute("select sum(total_price) from job where job.job in ('" + "', '".join(pull_froms) + "')")
	pvalue = cursor.fetchall()[0][0]
	info = [[total_stock, cvalue, pvalue]]
	total_value = float(cvalue) + total_stock
	head = ['I-H Prod', 'Customer', 'Pull Froms']
	return render_template('generic_table.html', rows = info, head = head, title = 'Work In Progress', body = ["", "Value of jobs on the floor, does not include 'Pull From' jobs under Customer.", "Total job value: $" + str(total_value)])

@app.route('/report/routing_changes')
def routing_changes(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("SELECT CHANGE_HISTORY.CHANGED_BY, CHANGE_HISTORY.CHANGE_DATE, CHANGE_HISTORY.OLD_TEXT, CHANGE_HISTORY.NEW_TEXT, CHANGE_HISTORY.WC_VENDOR, CHANGE_HISTORY.JOB, JOB.CUSTOMER, JOB.DESCRIPTION, JOB.PART_NUMBER, JOB.ORDER_QUANTITY FROM (CHANGE_HISTORY INNER JOIN JOB ON CHANGE_HISTORY.JOB = JOB.JOB) WHERE CHANGE_HISTORY.CHANGE_DATE > DATEADD(DAY, DATEDIFF(DAY, 0, getDate() - 30), 0) AND CHANGE_HISTORY.CHANGE_TYPE = 14")

	info = cursor.fetchall()

	head = ['Changed By', 'Change Date', 'Old', 'New', 'Work Center', 'Job', 'Customer', 'Description', 'Part Number', 'Order Quantity']
	return render_template('generic_table.html', rows = info, head = head, title = 'Daily Routing Changes')

@app.route("/chart/weekly_s&o")
def wso():
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	now = str(datetime.datetime.now().date())

	cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.Total_Price FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' order by job.order_date desc")

	data = cursor.fetchall()

	data_wk1 = []
	for each in data:
		each[1] = each[1].isocalendar()[:-1]
		data_wk1.append(each[1:])

	df1 = pd.DataFrame(data_wk1, columns=['week', 'price'])

	table1 = pd.pivot_table(df1, values='price', columns='week', aggfunc=np.sum)

	week_order = list(table1)

	values_order1 = table1.values.tolist()

	cursor.execute("SELECT cast(packlist_header.packlist_date as date), packlist_detail.unit_price, packlist_detail.quantity, job.customer FROM (packlist_header inner join packlist_detail on packlist_header.packlist = packlist_detail.packlist) inner join job on packlist_detail.job = job.job WHERE Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%' AND packlist_header.packlist_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' order by packlist_header.packlist_date desc")

	data = cursor.fetchall()

	data_wk2 = []
	for each in data:
		each[0] = each[0].isocalendar()[:-1]
		price = round(each[1] * each[2], 2)
		data_wk2.append([each[0], price])

	df2 = pd.DataFrame(data_wk2, columns=['week', 'price'])

	table2 = pd.pivot_table(df2, values='price', columns='week', aggfunc=np.sum)

	values_order2 = table2.values.tolist()

	avg_order = round(sum(values_order1[0])/len(values_order1[0]),2)
	avg_ship = round(sum(values_order2[0])/len(values_order2[0]),2)
	so_diff = avg_order - avg_ship
	averages = "Average Orders: " + str(avg_order) + " | Average Shipments: " + str(avg_ship) + " | Order Surplus: " + str(so_diff)
	title = 'Past Year Shipped & Ordered Totals'
	legend = ['', 'Weekly Order Totals', 'Weekly Shipment Totals']
	caption = averages
	values = [values_order1[0], values_order2[0]]
	return render_template('chart.html', values=values, labels=week_order, legend=legend, title=title, caption=caption)

@app.route('/report/pos') #Active jobs grouped by PO with routing
def pos(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("select distinct job.customer_po from job where job.status = 'active' and job.job not like '%-%' and job.customer not like 'I-H PROD'")

	purchase_orders = cursor.fetchall()
	purchase_orders = [x[0] for x in purchase_orders]

	po_list = []

	for o in purchase_orders[1:]:
		cursor.execute("select job.job from job where job.customer_po = '" + o + "'")
		job_numbers = cursor.fetchall()
		job_numbers = [x[0] for x in job_numbers]

		job_list = []
		for job in job_numbers:
			cursor.execute("select order_quantity, part_number, description, customer from job where job = '" + job + "'")
			job_details = cursor.fetchall()
			job_details = [list(x) for x in job_details]

			cursor.execute("select work_center, sequence from job_operation where status = 'o' and job = '" + job + "'")
			work_centers = cursor.fetchall()
			work_centers = [list(x) for x in work_centers]
			work_centers.sort(key=itemgetter(1))
			if not work_centers:
				work_centers = [['COMPLETE']]

			cursor.execute("select cast(promised_date as date) from delivery where job = '" + job + "'")
			promised_date = cursor.fetchall()
			promised_date = [list(x) for x in promised_date]
			if not promised_date:
				promised_date = [[datetime.date(3000, 1, 1)]]

			try:
				job_list.append([job]+job_details[0]+promised_date[0]+[work_centers[0][0]])
			except IndexError as error:
				print([job])
				print(job_details[0])
				print(promised_date[0])
				print(work_centers)

			job_list.sort(key=itemgetter(5))
		po_list.append([job_list[0][4], o, job_list[0][5], job_list])
		po_list.sort(key=itemgetter(2))

	return render_template('pos.html', po_list=po_list)

@app.route("/chart/weekly_items")
def wk_items():
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("SELECT cast(job.order_date as date), job.order_quantity FROM job WHERE job.customer Not Like '%I-H%' AND (Job.Order_Date > Dateadd(Month, Datediff(Month, 0, DATEADD(d, -365, current_timestamp)), 0)) AND (Job.Job Not Like '%-%') and job.part_number in ('1100', '1101', '1102', '1103', '1104', '1105', '1106', '1107', '1108', '1109', '1110', '1111', '1112', '1113', '1114', '1115', '1116', '1117', '1118', '1119', '1120', '1121', '1122', '1123', '1150', '1151', '1152', '1153', '1154', '1155', '1156', '1157', '1158', '1159', '1160', '1161', '1162', '1163', '1164', '1165', '1166', '1167', '1168', '1169', '1170', '1171', '1172', '1173', '1174', '1175', '1500', '1501', '1502', '1503', '1504', '1505', '1506', '1507', '1508', '1509', '1510', '1511', '1512', '1513', '1514', '1515', '1516', '1517', '1518', '1519', '1520', '1521', '1522', '1523', '1524', '1525', '1526', '1527') order by job.order_date")

	data = cursor.fetchall()
	data_wk = []
	for each in data:
		each[0] = each[0].isocalendar()[1]
		data_wk.append([each[0], each[1]])

	df = pd.DataFrame(data_wk, columns=['week', 'quantity'])

	table = pd.pivot_table(df, values='quantity', columns='week', aggfunc=np.sum)

	week_order1 = []
	for x in range(52):
		week_order1.append((x + data_wk[0][0]) % 52)

	values_order1 = []
	for x in range(52):
		try:
			values_order1.append(table.values.tolist()[0][week_order1[x]])
		except IndexError:
			values_order1.append([0])

	#==============
	items = [str(x) for x in list(range(1000, 1025))]
	for e in range(1050, 1077):
		items.append(str(e))

	items = str(items)[1:-1]
	cursor.execute("SELECT cast(job.order_date as date), job.order_quantity FROM job WHERE job.customer Not Like '%I-H%' AND (Job.Order_Date > Dateadd(Month, Datediff(Month, 0, DATEADD(d, -365, current_timestamp)), 0)) AND (Job.Job Not Like '%-%') and job.part_number in (" + items + ") order by job.order_date")

	data = cursor.fetchall()
	data_wk = []
	for each in data:
		each[0] = each[0].isocalendar()[1]
		data_wk.append([each[0], each[1]])

	df = pd.DataFrame(data_wk, columns=['week', 'quantity'])

	table = pd.pivot_table(df, values='quantity', columns='week', aggfunc=np.sum)

	week_order2 = []
	for x in range(52):
		week_order2.append((x + data_wk[0][0]) % 52)

	values_order2 = []
	for x in range(52):
		try:
			values_order2.append(table.values.tolist()[0][week_order2[x]])
		except IndexError:
			values_order2.append([0])
	title = 'Past Year Ordered Totals'
	legend = ['Null', 'T-Handle Boxes']
	caption = 'Weekly Order Totals'
	labels = []
	for x in week_order1[1:]:
		if x > data_wk[0][0]:
			labels.append(datetime.datetime.strptime(str(datetime.datetime.now().year - 1) + '-W' + str(x) + '-0', "%Y-W%W-%w").date())
		else:
			labels.append(datetime.datetime.strptime(str(datetime.datetime.now().year) + '-W' + str(x) + '-0', "%Y-W%W-%w").date())
	values = [values_order1[1:], values_order2[1:]]
	return render_template('chart.html', values=[values], labels=labels, legend=legend, title=title, caption=caption)

@app.route('/report/pricing') #Iconic Item Prices
def pricing(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	items = [str(x) for x in list(range(1000, 4500))]

	cursor.execute("SELECT material.material, material.selling_price, price_break.minimum_qty from (material left join price_break on material.material = price_break.material) where material.material in (" + str(items)[1:-1]+")")

	rows = cursor.fetchall()

	head = ['Material', 'Price', 'Minimum Quantity']
	return render_template('generic_table.html', rows = rows, head = head, title = 'Pricing')

@app.route('/report/weld_stubs/priority') #Job Stubs for Welding Scheduling
def weld_stubs_priority(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("select job.job from job where status = 'active'")
	job_numbers = cursor.fetchall()
	job_numbers = [x[0] for x in job_numbers]

	job_list = []
	for job in job_numbers:
		cursor.execute("select customer, customer_po, description, order_quantity, priority from job where job = '" + job + "'")
		job_details = cursor.fetchall()
		job_details = [list(x) for x in job_details]

		cursor.execute("select work_center, sequence, est_run_hrs from job_operation where status = 'o' and job = '" + job + "'")
		work_centers = cursor.fetchall()
		work_centers = [list(x) for x in work_centers]

		work_centers.sort(key=itemgetter(1))
		if not work_centers:
			work_centers = [['NONE']]
		if work_centers[0][0] != 'WELDING':
			continue
		else:
			job_details = job_details[0] + work_centers[0]

		cursor.execute("select cast(promised_date as date) from delivery where job = '" + job + "'")
		promised_date = cursor.fetchall()
		promised_date = [list(x) for x in promised_date]
		if not promised_date:
			promised_date = [[datetime.date(3000, 1, 1)]]

		try:
			job_list.append([job]+job_details+promised_date[0])
		except IndexError as error:
			print([job])
			print(job_details[0])
			print(promised_date[0])
			print(work_centers)

	job_list.sort(key=itemgetter(5,9))
	head = ['Job', 'Customer', 'Customer PO', 'Description', 'Order Quantity', 'Run Hours']
	return render_template('job_stub.html', rows = job_list, head = head)

@app.route('/report/weld_stubs/all') #Job Stubs for Welding Scheduling
def weld_stubs_all(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("select job.job from job where status = 'active'")
	job_numbers = cursor.fetchall()
	job_numbers = [x[0] for x in job_numbers]

	job_list = []
	for job in job_numbers:
		cursor.execute("select customer, customer_po, description, order_quantity, priority from job where job = '" + job + "'")
		job_details = cursor.fetchall()
		job_details = [list(x) for x in job_details]

		cursor.execute("select work_center, sequence, est_run_hrs from job_operation where status = 'o' and job = '" + job + "'")
		work_centers = cursor.fetchall()
		work_centers = [list(x) for x in work_centers]

		work_centers.sort(key=itemgetter(1))
		if not work_centers:
			work_centers = [['NONE']]

		job_details = job_details[0] + work_centers[0]

		cursor.execute("select cast(promised_date as date) from delivery where job = '" + job + "'")
		promised_date = cursor.fetchall()
		promised_date = [list(x) for x in promised_date]
		if not promised_date:
			promised_date = [[datetime.date(3000, 1, 1)]]

		try:
			job_list.append([job]+job_details+promised_date[0])
		except IndexError as error:
			print([job])
			print(job_details[0])
			print(promised_date[0])
			print(work_centers)

	job_list.sort(key=itemgetter(0))
	head = ['Job', 'Customer', 'Customer PO', 'Description', 'Order Quantity', 'Run Hours']
	return render_template('job_stub.html', rows = job_list, head = head)

@app.route('/report/weld_stubs/hot') #Job Stubs for Welding Scheduling
def weld_stubs_hot(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("select job.job from job where status = 'active' and priority > 5")
	job_numbers = cursor.fetchall()
	job_numbers = [x[0] for x in job_numbers]

	job_list = []
	for job in job_numbers:
		cursor.execute("select customer, customer_po, description, order_quantity, priority from job where job = '" + job + "'")
		job_details = cursor.fetchall()
		job_details = [list(x) for x in job_details]

		cursor.execute("select work_center, sequence, est_run_hrs from job_operation where status = 'o' and job = '" + job + "'")
		work_centers = cursor.fetchall()
		work_centers = [list(x) for x in work_centers]

		work_centers.sort(key=itemgetter(1))
		if not work_centers:
			work_centers = [['NONE']]

		job_details = job_details[0] + work_centers[0]

		cursor.execute("select cast(promised_date as date) from delivery where job = '" + job + "'")
		promised_date = cursor.fetchall()
		promised_date = [list(x) for x in promised_date]
		if not promised_date:
			promised_date = [[datetime.date(3000, 1, 1)]]

		try:
			job_list.append([job]+job_details+promised_date[0])
		except IndexError as error:
			print([job])
			print(job_details[0])
			print(promised_date[0])
			print(work_centers)

	job_list.sort(key=itemgetter(0))
	head = ['Job', 'Customer', 'Customer PO', 'Description', 'Order Quantity', 'Run Hours']
	return render_template('job_stub.html', rows = job_list, head = head)

@app.route('/report/active_orders') #Total Values For Work In Progress
def active_orders(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	#stock job totals
	cursor.execute("select job.job, job.part_number, job.order_quantity, material.selling_price, job.note_text from (job left join material on job.part_number = material.material) where job.status = 'active' and job.customer = 'I-H PROD' and job.job not like '%-%'")
	stock_jobs = cursor.fetchall()

	stock_jobs = [list(x) for x in stock_jobs]

	no_value_jobs = []

	for job in stock_jobs:
		if not job[3]:
			job[3] = 0
		job_value = job[2] * job[3]
		job.append(job_value)
		if not job[4]:
			job[4] = ''

	stock_wip = sum([x[5] for x in stock_jobs])
	stock_wip_count = len(stock_jobs)

	#customer job totals
	cursor.execute("select job.job, job.part_number, job.order_quantity, job.total_price, job.note_text from job where job.status = 'active' and job.customer not like 'I-H%' and job.job not like '%-%'")
	customer_jobs = cursor.fetchall()

	customer_jobs = [list(x) for x in customer_jobs]

	for job in customer_jobs:
		if not job[3]:
			job[3] = 0
			no_value_jobs.append(job)
		job_value = float(job[3])
		job.append(job_value)
		if not job[4]:
			job[4] = ''

	customer_wip = sum([x[5] for x in customer_jobs])
	customer_wip_count = len(customer_jobs)

	info = [[stock_wip, stock_wip_count, customer_wip, customer_wip_count, sum([stock_wip, customer_wip])]]
	head = ['Stock Job Total', 'Stock Job Count', 'Customer Job Total', 'Customer Job Count', 'Total Value']
	return render_template('generic_table.html', rows = info, head = head, title = 'Value in Production', body = ['Jobs with No Value:'] + [x[0] + ' - ' + x[4] for x in no_value_jobs])

@app.route('/report/sm_sheets') #Total smooth sheets with tape
def sm_sheets(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("select sum(po_detail.order_quantity) from po_detail inner join po_header on po_detail.po = po_header.po where po_header.order_date > Dateadd(year, -1, getdate()) and po_detail.vendor_reference = '54588619'")

	data = cursor.fetchall()

	return render_template('generic_table.html', rows = data, head = ['total sheets'], title = 'smooth taped sheets ordered')

@app.route("/chart/weekly_s&o&po")
def wsop():
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	now = str(datetime.datetime.now().date())

	cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.Total_Price FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' order by job.order_date desc")

	data = cursor.fetchall()

	data_wk1 = []
	weeks = [x for x in range(1,53)]
	for each in data:
		each[1] = each[1].isocalendar()[:-1]
		try:
			weeks.remove(each[0][1])
		except ValueError:
			pass
		data_wk1.append(each[1:])

	for wk in weeks:
		n = datetime.datetime.now().isocalendar()[1]
		if n < wk:
			yr = datetime.datetime.now().year - 1
		else:
			yr = datetime.datetime.now().year
		data_wk1.append([(yr, wk), 0])

	df1 = pd.DataFrame(data_wk1, columns=['week', 'price'])

	table1 = pd.pivot_table(df1, values='price', columns='week', aggfunc=np.sum)

	week_order = list(table1)

	values_order1 = table1.values.tolist()
	values_order1 = [float(x) for x in values_order1[0]]
	i = len(values_order1)
	d1 = pd.DataFrame({
	'week' : [float(x) for x in range(1,i+1)],
	'value' : values_order1
	})
	values_trend1 = np.polyfit(d1.week, d1.value, 1)
	r_x1, r_y1 = zip(*((i, i*values_trend1[0] + values_trend1[1]) for i in d1.week))

	cursor.execute("SELECT cast(packlist_header.packlist_date as date), packlist_detail.unit_price, packlist_detail.quantity, job.customer FROM (packlist_header inner join packlist_detail on packlist_header.packlist = packlist_detail.packlist) inner join job on packlist_detail.job = job.job WHERE Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%' AND packlist_header.packlist_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' order by packlist_header.packlist_date desc")

	data = cursor.fetchall()

	data_wk2 = []
	weeks = [x for x in range(1,53)]
	for each in data:
		each[0] = each[0].isocalendar()[:-1]
		try:
			weeks.remove(each[0][1])
		except ValueError:
			pass
		price = round(each[1] * each[2], 2)
		data_wk2.append([each[0], price])

	for wk in weeks:
		n = datetime.datetime.now().isocalendar()[1]
		if n < wk:
			yr = datetime.datetime.now().year - 1
		else:
			yr = datetime.datetime.now().year
		data_wk2.append([(yr, wk), 0])

	df2 = pd.DataFrame(data_wk2, columns=['week', 'price'])

	table2 = pd.pivot_table(df2, values='price', columns='week', aggfunc=np.sum)

	values_order2 = table2.values.tolist()
	values_order2 = [float(x) for x in values_order2[0]]
	i = len(values_order2)
	d2 = pd.DataFrame({
	'week' : [float(x) for x in range(1,i+1)],
	'value' : values_order2
	})
	values_trend2 = np.polyfit(d2.week, d2.value, 1)
	r_x2, r_y2 = zip(*((i, i*values_trend2[0] + values_trend2[1]) for i in d2.week))

	cursor.execute("SELECT cast(po_header.order_date as date), po_detail.order_quantity, po_detail.unit_cost, po_header.trade_currency from po_header inner join po_detail on po_header.po = po_detail.po where po_header.status not like 'unissued' and po_header.order_date > Dateadd(year, -1, getdate()) order by po_header.order_date desc")

	data = cursor.fetchall()

	data_wk3 = []
	weeks = [x for x in range(1,53)]
	for each in data:
		each[0] = each[0].isocalendar()[:-1]
		try:
			weeks.remove(each[0][1])
		except ValueError:
			pass
		if each[3] == 1:
			cost = each[2] * 1.3
		else:
			cost = each[2]
		price = round(each[1] * cost, 2)
		data_wk3.append([each[0], price])

	for wk in weeks:
		n = datetime.datetime.now().isocalendar()[1]
		if n < wk:
			yr = datetime.datetime.now().year - 1
		else:
			yr = datetime.datetime.now().year
		data_wk3.append([(yr, wk), 0])

	df3 = pd.DataFrame(data_wk3, columns=['week', 'price'])

	table3 = pd.pivot_table(df3, values='price', columns='week', aggfunc=np.sum)

	values_order3 = table3.values.tolist()
	values_order3 = [float(x) for x in values_order3[0]]
	i = len(values_order3)

	d3 = pd.DataFrame({
	'week' : [float(x) for x in range(1,i+1)],
	'value' : values_order3
	})
	values_trend3 = np.polyfit(d3.week, d3.value, 1)
	r_x3, r_y3 = zip(*((i, i*values_trend3[0] + values_trend3[1]) for i in d3.week))

	avg_order = round(sum(values_order1)/len(values_order1),2)
	avg_ship = round(sum(values_order2)/len(values_order2),2)
	so_diff = avg_order - avg_ship
	avg_po = round(sum(values_order3)/len(values_order3),2)
	averages = "Average PO Value: " + str(avg_po) + " | Average Orders: " + str(avg_order) + " | Average Shipments: " + str(avg_ship) + " | Order Surplus: " + str(so_diff)
	title = 'Past Year Shipped & Ordered & PO Totals'
	legend = ['','Orders Trend', 'Weekly Order Totals', 'Shipment Trend', 'Weekly Shipment Totals', 'PO Trend', 'Weekly PO Value Total']
	caption = [averages, "Order totals calculated from total price of customer orders totaled each week. Shipment totals calculated from Packing List values totaled each week. PO totals calculated from the value of POs issued totaled each week."]
	values = [r_y1, values_order1, r_y2, values_order2, r_y3, values_order3]
	return render_template('chart.html', values=values, labels=week_order, legend=legend, title=title, caption=caption)

@app.route("/chart/parts_charts")
def parts_charts():
	part_number = request.args.get('part', default = '%', type = str)
	print(part_number)

	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	now = str(datetime.datetime.now().date())

	if part_number == 'boxes':
		cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.order_quantity FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' and (job.description like 'thandle%' or job.description like 'camlock%') and job.part_number not like '0202' order by job.order_date desc")

	elif part_number == 'thandle':
		cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.order_quantity FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' and job.description like 'thandle%' and job.part_number not like '0202' order by job.order_date desc")

	elif part_number == 'camlock':
		cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.order_quantity FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' and job.description like 'camlock%' and job.part_number not like '0202' order by job.order_date desc")

	elif part_number == 'racks':
		cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.order_quantity FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' and job.description like '%headache%' and job.part_number not like '0202' order by job.order_date desc")

	else:
		cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.order_quantity FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' and job.part_number like '" + part_number + "' order by job.order_date desc")

	data = cursor.fetchall()
	print(data[0])
	data_wk1 = []
	weeks = [x for x in range(1,53)]
	for each in data:
		each[1] = each[1].isocalendar()[:-1]
		try:
			weeks.remove(each[0][1])
		except ValueError:
			pass
		data_wk1.append(each[1:])

	for wk in weeks:
		n = datetime.datetime.now().isocalendar()[1]
		if n < wk:
			yr = datetime.datetime.now().year - 1
		else:
			yr = datetime.datetime.now().year
		data_wk1.append([(yr, wk), 0])

	df1 = pd.DataFrame(data_wk1, columns=['week', 'quantity'])

	table1 = pd.pivot_table(df1, values='quantity', columns='week', aggfunc=np.sum)

	week_order = list(table1)

	values_order1 = table1.values.tolist()
	values_order1 = [float(x) for x in values_order1[0]]
	i = len(values_order1)
	d1 = pd.DataFrame({
	'week' : [float(x) for x in range(1,i+1)],
	'quantity' : values_order1
	})
	values_trend1 = np.polyfit(d1.week, d1.quantity, 1)
	r_x1, r_y1 = zip(*((i, i*values_trend1[0] + values_trend1[1]) for i in d1.week))

	title = 'Past Year '+part_number.capitalize()+' Ordered Totals'
	legend = ['','Orders Trend', 'Weekly Order Totals']
	caption = 'Does not include: I-H Prod, custom products, saw jobs, or NCRs'
	values = [r_y1, values_order1]
	return render_template('item_chart.html', values=values, labels=week_order, legend=legend, title=title, caption=caption)

@app.route("/chart/parts_charts", methods=['POST'])
def parts_charts_post():
	text = request.form['part']
	part_number = text

	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	now = str(datetime.datetime.now().date())

	if part_number == 'boxes':
		cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.order_quantity FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' and (job.description like 'thandle%' or job.description like 'camlock%') and job.part_number not like '0202' order by job.order_date desc")

	elif part_number == 'thandle':
		cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.order_quantity FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' and job.description like 'thandle%' and job.part_number not like '0202' order by job.order_date desc")

	elif part_number == 'camlock':
		cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.order_quantity FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' and job.description like 'camlock%' and job.part_number not like '0202' order by job.order_date desc")

	elif part_number == 'racks':
		cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.order_quantity FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' and job.description like '%headache%' and job.part_number not like '0202' order by job.order_date desc")

	elif part_number == 'bigmth':
		cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.order_quantity FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' and job.description like '%big mth%' and job.part_number not like '0202' order by job.order_date desc")

	else:
		cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.order_quantity FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' and job.part_number like '" + part_number + "' order by job.order_date desc")

	data = cursor.fetchall()
	print(data[0])
	data_wk1 = []
	weeks = [x for x in range(1,53)]
	for each in data:
		each[1] = each[1].isocalendar()[:-1]
		try:
			weeks.remove(each[0][1])
		except ValueError:
			pass
		data_wk1.append(each[1:])

	for wk in weeks:
		n = datetime.datetime.now().isocalendar()[1]
		if n < wk:
			yr = datetime.datetime.now().year - 1
		else:
			yr = datetime.datetime.now().year
		data_wk1.append([(yr, wk), 0])

	df1 = pd.DataFrame(data_wk1, columns=['week', 'quantity'])

	table1 = pd.pivot_table(df1, values='quantity', columns='week', aggfunc=np.sum)

	week_order = list(table1)

	values_order1 = table1.values.tolist()
	values_order1 = [float(x) for x in values_order1[0]]
	i = len(values_order1)
	d1 = pd.DataFrame({
	'week' : [float(x) for x in range(1,i+1)],
	'quantity' : values_order1
	})
	values_trend1 = np.polyfit(d1.week, d1.quantity, 1)
	r_x1, r_y1 = zip(*((i, i*values_trend1[0] + values_trend1[1]) for i in d1.week))

	title = 'Past Year '+part_number.capitalize()+' Ordered Totals'
	legend = ['','Orders Trend', 'Weekly Order Totals']
	caption = 'Does not include: I-H Prod, custom products, saw jobs, or NCRs'
	values = [r_y1, values_order1]
	return render_template('item_chart.html', values=values, labels=week_order, legend=legend, title=title, caption=caption)

@app.route('/update_mailer') #Send Email for each Routing Update
def update_mailer(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	with open('change_history', 'r') as data_file:
		last_change = data_file.read()

	pos = ["GGAT 007"]

	for po in pos:
		cursor.execute("select job from job where customer_po = '" + po + "'")
		jobs = [list(x) for x in cursor.fetchall()]

	for job in jobs:
		cursor.execute("SELECT CHANGE_HISTORY.CHANGED_BY, CHANGE_HISTORY.CHANGE_DATE, CHANGE_HISTORY.OLD_TEXT, CHANGE_HISTORY.NEW_TEXT, CHANGE_HISTORY.WC_VENDOR, CHANGE_HISTORY.JOB, JOB.CUSTOMER, JOB.DESCRIPTION, JOB.PART_NUMBER, JOB.ORDER_QUANTITY FROM (CHANGE_HISTORY INNER JOIN JOB ON CHANGE_HISTORY.JOB = JOB.JOB) WHERE CHANGE_HISTORY.CHANGE_DATE > convert(Datetime, '" + last_change[:-3] + "', 101) AND CHANGE_HISTORY.CHANGE_TYPE = 14 and job.job = '" + job[0] + "' order by change_history.change_date desc")
		#===========================================
		data = cursor.fetchall()

		if data:
			msg = Message("Job " + data[0][5] + " for " + data[0][6] + " updated!",
						  sender="colin@iconicmetalgear.com",
						  recipients=["colin@iconicmetalgear.com", "jason@iconicmetalgear.com"])

			msg.html = "<h2>Status Update</h2><br /><p>The " + data[0][4] + " step for this job was changed from " + data[0][2] + " to " + data[0][3] + " by " + data[0][0] +"</p>"

			mail.send(msg)

			with open('change_history', 'w') as data_file:
				data_file.write(str(data[0][1]))
		else:
			data = ['Nothing to update']

	return render_template('mailer.html', head = ['Sending Updates...'], title = 'Update Mailer', update = data[0])

@app.route("/chart/weekly_sopo_6mo")
def wsop_6mo():
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	now = str(datetime.datetime.now().date())

	cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.Total_Price FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(minute, -262800, getdate()) AND Job.Job Not Like '%-%' order by job.order_date desc")

	data = cursor.fetchall()

	data_wk1 = []
	weeks = [x for x in range(1,26)]
	for each in data:
		each[1] = each[1].isocalendar()[:-1]
		try:
			weeks.remove(each[0][1])
		except ValueError:
			pass
		data_wk1.append(each[1:])

	#for wk in weeks:
	#	n = datetime.datetime.now().isocalendar()[1]
	#	if n < wk:
	#		yr = datetime.datetime.now().year - 1
	#	else:
	#		yr = datetime.datetime.now().year
	#	data_wk1.append([(yr, wk), 0])

	df1 = pd.DataFrame(data_wk1, columns=['week', 'price'])

	table1 = pd.pivot_table(df1, values='price', columns='week', aggfunc=np.sum)

	week_order = list(table1)

	values_order1 = table1.values.tolist()
	values_order1 = [float(x) for x in values_order1[0]]
	i = len(values_order1)
	d1 = pd.DataFrame({
	'week' : [float(x) for x in range(1,i+1)],
	'value' : values_order1
	})
	values_trend1 = np.polyfit(d1.week, d1.value, 1)
	r_x1, r_y1 = zip(*((i, i*values_trend1[0] + values_trend1[1]) for i in d1.week))

	cursor.execute("SELECT cast(packlist_header.packlist_date as date), packlist_detail.unit_price, packlist_detail.quantity, job.customer FROM (packlist_header inner join packlist_detail on packlist_header.packlist = packlist_detail.packlist) inner join job on packlist_detail.job = job.job WHERE Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%' AND packlist_header.packlist_date > Dateadd(minute, -262800, getdate()) AND Job.Job Not Like '%-%' order by packlist_header.packlist_date desc")

	data = cursor.fetchall()

	data_wk2 = []
	weeks = [x for x in range(1,26)]
	for each in data:
		each[0] = each[0].isocalendar()[:-1]
		try:
			weeks.remove(each[0][1])
		except ValueError:
			pass
		price = round(each[1] * each[2], 2)
		data_wk2.append([each[0], price])

	#for wk in weeks:
	#	n = datetime.datetime.now().isocalendar()[1]
	#	if n < wk:
	#		yr = datetime.datetime.now().year - 1
	#	else:
	#		yr = datetime.datetime.now().year
	#	data_wk2.append([(yr, wk), 0])

	df2 = pd.DataFrame(data_wk2, columns=['week', 'price'])

	table2 = pd.pivot_table(df2, values='price', columns='week', aggfunc=np.sum)

	values_order2 = table2.values.tolist()
	values_order2 = [float(x) for x in values_order2[0]]
	i = len(values_order2)
	d2 = pd.DataFrame({
	'week' : [float(x) for x in range(1,i+1)],
	'value' : values_order2
	})
	values_trend2 = np.polyfit(d2.week, d2.value, 1)
	r_x2, r_y2 = zip(*((i, i*values_trend2[0] + values_trend2[1]) for i in d2.week))

	cursor.execute("SELECT cast(po_header.order_date as date), po_detail.order_quantity, po_detail.unit_cost, po_header.trade_currency from po_header inner join po_detail on po_header.po = po_detail.po where po_header.status not like 'unissued' and po_header.order_date > Dateadd(minute, -262800, getdate()) order by po_header.order_date desc")

	data = cursor.fetchall()

	data_wk3 = []
	weeks = [x for x in range(1,26)]
	for each in data:
		each[0] = each[0].isocalendar()[:-1]
		try:
			weeks.remove(each[0][1])
		except ValueError:
			pass
		if each[3] == 1:
			cost = each[2] * 1.3
		else:
			cost = each[2]
		price = round(each[1] * cost, 2)
		data_wk3.append([each[0], price])

	#for wk in weeks:
	#	n = datetime.datetime.now().isocalendar()[1]
	#	if n < wk:
	#		yr = datetime.datetime.now().year - 1
	#	else:
	#		yr = datetime.datetime.now().year
	#	data_wk3.append([(yr, wk), 0])

	df3 = pd.DataFrame(data_wk3, columns=['week', 'price'])

	table3 = pd.pivot_table(df3, values='price', columns='week', aggfunc=np.sum)

	values_order3 = table3.values.tolist()
	values_order3 = [float(x) for x in values_order3[0]]
	i = len(values_order3)

	d3 = pd.DataFrame({
	'week' : [float(x) for x in range(1,i+1)],
	'value' : values_order3
	})
	values_trend3 = np.polyfit(d3.week, d3.value, 1)
	r_x3, r_y3 = zip(*((i, i*values_trend3[0] + values_trend3[1]) for i in d3.week))

	avg_order = round(sum(values_order1)/len(values_order1),2)
	avg_ship = round(sum(values_order2)/len(values_order2),2)
	so_diff = avg_order - avg_ship
	avg_po = round(sum(values_order3)/len(values_order3),2)
	averages = "Average PO Value: " + str(avg_po) + " | Average Orders: " + str(avg_order) + " | Average Shipments: " + str(avg_ship) + " | Order Surplus: " + str(so_diff)
	title = 'Past Year Shipped & Ordered & PO Totals'
	legend = ['','Orders Trend', 'Weekly Order Totals', 'Shipment Trend', 'Weekly Shipment Totals', 'PO Trend', 'Weekly PO Value Total']
	caption = [averages, "Order totals calculated from total price of customer orders totaled each week. Shipment totals calculated from Packing List values totaled each week. PO totals calculated from the value of POs issued totaled each week."]
	values = [r_y1, values_order1, r_y2, values_order2, r_y3, values_order3]
	return render_template('chart.html', values=values, labels=week_order, legend=legend, title=title, caption=caption)

@app.route("/reminder")
def daimler_reminder():
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')

	cursor = connection.cursor()

	cursor.execute("select distinct customer_po from job where customer like 'DAIMLER' and status = 'active' and job not like '%-%'")

	purchase_orders = [list(x) for x in cursor.fetchall()]

	po_list = []
	for po in purchase_orders:
		cursor.execute("select job from job where status = 'active' and job not like '%-%' and customer like 'DAIMLER' and customer_po like '" + po[0] + "'")

		jobs = [list(x) for x in cursor.fetchall()]
		j = []
		for job in jobs:
			cursor.execute("select work_center, sequence from job_operation where status = 'o' and job = '" + job[0] + "'")

			centers = [list(x) for x in cursor.fetchall()]
			centers.sort(key=itemgetter(1))

			cursor.execute("select promised_date from delivery where job = '" + job[0] + "'")
			promised = [list(x) for x in cursor.fetchall()]
			if not promised:
				promised = datetime.date(1900, 1, 1)
			else:
				promised = promised[0][0]

			j.append([job[0], promised, centers[0][0]])

		po_list.append([po[0], j])

	msg = Message("Daimler - Daily Update",
		sender="colin@iconicmetalgear.com",
		recipients=["colin@iconicmetalgear.com", "jason@iconicmetalgear.com"])

	msg.html = render_template('mailer.html', po_list = po_list)
	mail.send(msg)

	return render_template('mailer.html', po_list = po_list)

@app.route("/report/part")
def part_status():
	try:
		text = request.args['part']
	except:
		text = ''

	part_number = text

	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("select description from material where material = '" + part_number + "'")
	try:
		description = cursor.fetchall()[0][0]
	except:
		return render_template('part_status.html', title="No Part Found")

	cursor.execute("select selling_price, price_unit_conv from material where material = '" + part_number + "'")
	data = cursor.fetchall()
	part_price = list(data)[0][0]
	c = list(data)[0][1]
	if c == 1.0:
		part_currency = 'CAD'
	elif not c:
		part_currency = ''
	else:
		part_currency = 'USD'

	cursor.execute("select cast(on_hand_qty as int) from material_location where material = '" + part_number + "' and location_id = 'SHOP'")
	data = cursor.fetchall()
	if data:
		stock_quantity = list(data)[0][0]
	else:
		stock_quantity = 0

	cursor.execute("select cast(on_hand_qty as int) from material_location where material = '" + part_number + "' and location_id = 'BUFFALO'")
	data = cursor.fetchall()
	if data:
		buffalo_quantity = list(data)[0][0]
	else:
		buffalo_quantity = 0


	cursor.execute("select job.job, delivery.remaining_quantity, job.customer, delivery.promised_date as date from job left join delivery on job.job = delivery.job where job.part_number = '" + part_number + "' and job.status = 'active' and job.job not like '%-%' and job.customer not like 'I-H%'")
	customer_jobs = [list(x) for x in cursor.fetchall()]

	pull_from_list = []
	make_list = []
	ship_list = []

	for job in customer_jobs:
		cursor.execute("select count(sequence) from job_operation where job = '" + str(job[0]) + "'")
		operation_count = cursor.fetchall()[0][0]

		if operation_count > 2:
			make_list.append(job)

		if operation_count == 2:
			pull_from_list.append(job)

		if operation_count == 1:
			ship_list.append(job)

	cursor.execute("select job, order_quantity from job where part_number = '" + part_number + "' and job.status = 'active' and job.job not like '%-%' and job.customer like 'I-H PROD'")
	stock_jobs = [list(x) for x in cursor.fetchall()]

	for job in stock_jobs:
		cursor.execute("select work_center, sequence from job_operation where status = 'o' and job = '" + job[0] + "'")

		centers = [list(x) for x in cursor.fetchall()]
		centers.sort(key=itemgetter(1))

		job.append(centers[0][0])

	stock_in_production = 0
	for each in stock_jobs:
		stock_in_production += each[1]

	total_pull_from = 0
	for each in pull_from_list:
		total_pull_from += each[1]

	total_ship = 0
	for each in ship_list:
		total_ship += each[1]

	title = part_number.capitalize() + ' Stock Status'

	available = stock_quantity + stock_in_production - total_pull_from - total_ship

	return render_template('part_status.html', title=title, description = description, part_price = part_price, part_currency = part_currency, available = available, stock_quantity = stock_quantity, buffalo_quantity = buffalo_quantity, stock_in_production = stock_in_production, total_pull_from = total_pull_from, make_list = make_list, pull_from_list = pull_from_list, stock_jobs = stock_jobs, ship_list = ship_list)

@app.route('/report/daily_progress')
def daily_progress(name=None):
	if request.args.get('next'):
		day = request.args.get('next')
		day = datetime.datetime.strptime(day, "%m/%d/%Y").date() + datetime.timedelta(days=1)
		day = day.strftime('%m/%d/%Y')
	elif request.args.get('prev'):
		day = request.args.get('prev')
		day = datetime.datetime.strptime(day, "%m/%d/%Y").date() - datetime.timedelta(days=1)
		day = day.strftime('%m/%d/%Y')
	elif request.args.get('date'):
		day = request.args.get('date')
	else:
		day = datetime.datetime.now().strftime('%m/%d/%Y')

	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()
	work_center_jobs = {}
	for work_center in [['SCHEDULE', 'LASER'], ['LASER', 'TOYOKOKI'], ['TOYOKOKI', 'WELDING'], ['WELDING', 'SHOP']]:
		cursor.execute("select change_history.job, cast(change_history.change_date as date), job.customer, job.part_number, job.order_quantity, job.note_text from change_history left join job on change_history.job = job.job where change_history.change_date between '" + day + " 00:00:00.00' and '" + day + " 23:59:59.99' and change_history.wc_vendor = '" + work_center[0] + "' and change_history.change_type = 14 and job.status = 'active'")
		work_center_in = [list(x) for x in cursor.fetchall()]
		work_center_jobs[work_center[1]] = {}
		work_center_jobs[work_center[1]]['wc_in'] = work_center_in

		cursor.execute("select change_history.job, cast(change_history.change_date as date), job.customer, job.part_number, job.order_quantity, job.note_text from change_history left join job on change_history.job = job.job where change_history.change_date between '" + day + " 00:00:00.00' and '" + day + " 23:59:59.99' and change_history.wc_vendor = '" + work_center[1] + "' and change_history.change_type = 14")
		work_center_out = [list(x) for x in cursor.fetchall()]
		work_center_jobs[work_center[1]]['wc_out'] = work_center_out

	head = ['job', 'date', 'customer', 'description', 'part number', 'quantity']
	return render_template('flow.html', day = day, work_center_jobs = work_center_jobs, head = head, title = 'Daily Routing Changes')

@app.route('/report/ship_list')
def ship_list(name=None):
	if request.args.get('po'):
		po_number = request.args.get('po')
		po_number = [x.strip() for x in po_number.split(',')]
	else:
		return render_template('ship_list.html', title = 'No Jobs Match PO Number', checklist = [{'customer': None}])
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	jobs = []
	for p in po_number:
		cursor.execute("select job from job where customer_po = '" + p + "'")
		j = [list(x)[0] for x in cursor.fetchall()]
		jobs.extend(j)

	checklist = []

	for job in jobs:
		cursor.execute("select customer, part_number, order_quantity, description from job where job = '" + job + "'")
		data = [list(x) for x in cursor.fetchall()]
		checklist.append({'job': job, 'customer': data[0][0], 'part number': data[0][1], 'quantity': data[0][2], 'description': data[0][3]})

	head = ['job', 'customer', 'description', 'part number', 'quantity']
	return render_template('ship_list.html', head = head, title = 'Shipping Checklist', po_number = po_number, checklist = checklist)

@app.route('/analytics')
def analytics(name=None):
	connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
	cursor = connection.cursor()

	cursor.execute("select order_date, total_price from job where total_price <> 0 and customer not like 'I-H%' and job not like '%-%'")
	data = [list(x) for x in cursor.fetchall()]
	data = [{'date': x[0].date(), 'price': x[1]} for x in data]

	data = pd.DataFrame(data)
	data = data.set_index('date')

	weekly_data = data['price'].resample('W', how='sum')

	return render_template('analytics.html', data = weekly_data)

if __name__ == '__main__':
	app.run()
