from __future__ import print_function
import sys
import pyodbc
import itertools
import pandas as pd
import numpy as np
import datetime
import json

from threading import Thread
from operator import itemgetter
from flask import Flask
from flask import render_template
from flask import url_for
from flask import request
from decimal import Decimal
from calendar import monthrange
from flask_sqlalchemy import SQLAlchemy

from flask_mail import Mail
from flask_mail import Message

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////home/colin/dev/jb_reporter/jb_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return '<User %r>' % self.username

class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    thickness = db.Column(db.Float, nullable=False)
    sheet_x = db.Column(db.Float, nullable=False)
    sheet_y = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(80), nullable=False)
    metal = db.Column(db.String(80), nullable=False)
    finish = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(80), nullable=False)

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    po_number = db.Column(db.String(80))

class Nest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(80))
    drop_id = db.Column(db.Integer, db.ForeignKey('drop.id'))

class Drop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    drop_number = db.Column(db.String(80), nullable=False)
    location = db.Column(db.String(80))
    sheet_x = db.Column(db.Float, nullable=False)
    sheet_y = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(80), nullable=False)
    origin = db.Column(db.Integer, db.ForeignKey('nest.id'), nullable=False)

class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)


with open('gmail.txt', 'r') as f:
    gmailpass = f.readline()

app.config.update(dict(
    DEBUG = False,
    MAIL_SERVER = 'smtp.gmail.com',
    MAIL_PORT = 587,
    MAIL_USE_TLS = True,
    MAIL_USE_SSL = False,
    MAIL_USERNAME = 'no-reply@iconicmetalgear.com',
    MAIL_PASSWORD = gmailpass,
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
    cursor.execute("select t1.job, t1.customer, t1.customer_po, t1.description, cast(t1.order_date as date), t1.order_quantity, t1.part_number, t1.floor_notes, t2.job, t2.order_quantity, delivery.remaining_quantity from ((select job.job, job.customer, job.customer_po, job.description, job.order_date, job.order_quantity, job.part_number, job_operation.floor_notes, job.status from job inner join job_operation on job.job = job_operation.job where job_operation.work_center like '%pull from%' and job.status = 'active' and job_operation.status = 'o') t1 left join (select job.job, job.customer, job.description, job.order_date, job.order_quantity, job.part_number, job.status from job where job.customer = 'i-h prod' and job.status = 'active' and job.job not like '%-%' and job.part_number <> '0202') t2 on t1.part_number = t2.part_number) left join delivery on t2.job = delivery.job")

    rows = cursor.fetchall()
    head = ['Job Number', 'Customer', 'Customer PO', 'Description', 'Order Date', 'Quantity', 'Part Number', 'Notes', 'Stock Job Number', 'Order Quantity', 'Remaining Quantity']
    return render_template('pull_from.html', rows = rows, head = head, title = 'Pull From')

@app.route('/hot')
def hotlist(name=None):
    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select priority, job, customer, customer_po, description, cast(order_date as date), order_quantity, part_number from job where status = 'active' and priority < 5")
    data = [list(x) for x in cursor.fetchall()]

    for job in data:
        cursor.execute("select work_center, sequence from job_operation where job = '{0}' and job_operation.status = 'o'".format(job[1]))
        job_data = [list(x) for x in cursor.fetchall()]
        job_data.sort(key=itemgetter(1))
        try:
            job.append(job_data[0][0])
        except:
            pass

        cursor.execute("select cast(promised_date as date) from delivery where job = '{0}'".format(job[1]))
        try:
            job.append([list(x) for x in cursor.fetchall()][0][0])
        except:
            job.append(job[5])

    data.sort(key=itemgetter(0))

    head = ['Priority', 'Job Number', 'Customer', 'Customer PO', 'Description', 'Order Date', 'Promised Date', 'Order Quantity', 'Part Number', 'Work Center']
    return render_template('hot.html', rows = data, head = head, title = 'Hot List')

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
    jb70 = make_stockitem('1364', ['1329', '1351', '1352', '1352', '1322'], '70" Jailbar Headache Rack')
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
    flat76 = make_stockitem('1301', ['1320', '1330', '1353', '1362'], '76" Flat Headache Rack')
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

    cursor.execute("select job.job from job where ((job.description like '%headache%' and job.part_number like '%0202%') or (job.part_number like '6900' or job.part_number like '6910')) and job.status = 'active' and job.job not like '%-s%' and job.job not like '%-ncr%'")

    custom_racks = cursor.fetchall()

    custom_racks = [list(x) for x in custom_racks]

    rackssold = [flat70.soldjobs, jb70.soldjobs, flat76.soldjobs, jb76.soldjobs, flat86.soldjobs, jb86.soldjobs] + custom_racks
    cursor.execute("select job.description as description, job.part_number as partnumber, job.job as job, job.customer as customer, job.order_quantity as orderquantity, cast(job.order_date as date) as orderdate, cast(delivery.promised_date as date) as promiseddate, job.note_text, job.customer_po from (job inner join delivery on job.job = delivery.job)  where job.job in ('{0}')".format("', '".join(list(itertools.chain.from_iterable(rackssold)))))
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

    cursor.execute("select job, part_number, description, order_quantity, cast(order_date as date) from job where status = 'active' and part_number in ('1401', '1402', '1403', '1409', '1410', '1411')")
    trays = [list(x) for x in cursor.fetchall()]

    for part in trays:
        cursor.execute("select cast(on_hand_qty as int) from material_location where material = '" + part[1] + "' and location_id = 'SHOP'")
        try:
            stockqty = list(cursor.fetchall())[0][0]
        except:
            stockqty = 0

        part.append(stockqty)

    return render_template('rackinventory.html', data = [flat70, jb70, flat76, jb76, flat86, jb86], tanks = tanks, sold = sold, stock = stocklist, trays = trays, head = ['Description','Part Number','Job', 'Customer', 'Quantity', 'Order Date', 'Shipped Quantity'], title = 'Headache Rack Production Tracker')

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

    if ',' in job:
        joblist = [x.strip() for x in job.split(',')]
    elif '-' not in job and len(job) % 5 == 0:
        joblist = [job[i:i+5] for i in range(0, len(job), 5)]

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

            cursor.execute("select cast(promised_date as date) from delivery where job = '{0}'".format(a))
            try:
                data[0].insert(5, [list(x) for x in cursor.fetchall()][0][0])
            except:
                data[0].insert(5, 'None')

            data[0].insert(8, c[0][0])
            rows.append(data[0])

    head = ['Priority', 'Job Number', 'Customer', 'Description', 'Order Date', 'Promised Date', 'Order Quantity', 'Part Number', 'Work Center', 'Note Text']
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
    total_value = float(cvalue) + total_stock
    cursor.execute("select sum(cast(material_location.on_hand_qty as int) * material.selling_price) from material left join material_location on material.material = material_location.material where material.material not like '%[a-zA-Z]%' and len(material.material) = 4 and material.material like '[1-3]%' and cast(material_location.on_hand_qty as int) > 0 and material_location.location_id in ('BUFFALO', 'SHOP') and material.selling_price != 0")
    stock_value = cursor.fetchall()[0][0]
    info = [[total_stock, cvalue, pvalue, stock_value]]

    head = ['I-H Prod', 'Customer', 'Pull Froms', 'In Stock']
    return render_template('generic_table.html', rows = info, head = head, title = 'Work In Progress', body = "Value of jobs on the floor, does not include 'Pull From' jobs under Customer. Total job value: ${0}".format(total_value))

@app.route('/report/routing_changes')
def routing_changes(name=None):
    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("SELECT CHANGE_HISTORY.CHANGED_BY, CHANGE_HISTORY.CHANGE_DATE, CHANGE_HISTORY.OLD_TEXT, CHANGE_HISTORY.NEW_TEXT, CHANGE_HISTORY.WC_VENDOR, CHANGE_HISTORY.JOB, JOB.CUSTOMER, JOB.DESCRIPTION, JOB.PART_NUMBER, JOB.ORDER_QUANTITY FROM (CHANGE_HISTORY INNER JOIN JOB ON CHANGE_HISTORY.JOB = JOB.JOB) WHERE CHANGE_HISTORY.CHANGE_DATE > DATEADD(DAY, DATEDIFF(DAY, 0, getDate() - 30), 0) AND CHANGE_HISTORY.CHANGE_TYPE = 14")

    info = cursor.fetchall()

    head = ['Changed By', 'Change Date', 'Old', 'New', 'Work Center', 'Job', 'Customer', 'Description', 'Part Number', 'Order Quantity']
    return render_template('generic_table.html', rows = info, head = head, title = 'Daily Routing Changes')

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

    cursor.execute("SELECT cast(job.order_date as date), job.order_quantity FROM job WHERE job.customer Not Like '%I-H%' AND (Job.Order_Date > Dateadd(Month, Datediff(Month, 0, DATEADD(d, -365, current_timestamp)), 0)) AND (Job.Job Not Like '%-%') and job.part_number in ('1100', '1101', '1102', '1103', '1104', '1105', '1106', '1107', '1108', '1109', '1110', '1111', '1112', '1113', '1114', '1115', '1116', '1117', '1118', '1119', '1120', '1121', '1122', '1123', '1150', '1151', '1152', '1153', '1154', '1155', '1156', '1157', '1158', '1159', '1160', '1161', '1162', '1163', '1164', '1165', '1166', '1167', '1168', '1169', '1170', '1171', '1172', '1173', '1174', '1175', '1500', '1501', '1502', '1503', '1504', '1505', '1506', '1507', '1508', '1509', '1510', '1511', '1512', '1513', '1514', '1515', '1516', '1517', '1518', '1519', '1520', '1521', '1522', '1523', '1524', '1525', '1526', '1.34') order by job.order_date")

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

@app.route("/chart/weekly_s&o&po") # Chart with weekly totals for Shipped, Ordered, and PO values. Also lines of best fit for each.
def wsop():
    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    now = str(datetime.datetime.now().date())

    cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.Total_Price, job.trade_currency FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' order by job.order_date desc")

    data = cursor.fetchall()

    data_wk1 = []
    weeks = [x for x in range(1,53)]
    for each in data:
        each[1] = each[1].isocalendar()[:-1]
        try:
            weeks.remove(each[0][1])
        except ValueError:
            pass
        if each[3] == 2: #if currency is CAD do nothing
            pass
        elif each[3] == 1: #if currency is USD convert to CAD
            each[2] = Decimal(each[2])*Decimal(1.34)
        else:
            pass
        data_wk1.append(each[1:])

    for wk in weeks:
        n = datetime.datetime.now().isocalendar()[1]
        if n < wk:
            yr = datetime.datetime.now().year - 1
        else:
            yr = datetime.datetime.now().year
        data_wk1.append([(yr, wk), 0])

    df1 = pd.DataFrame(data_wk1, columns=['week', 'price', 'currency'])
    df1.drop(columns='currency')

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

    cursor.execute("SELECT cast(packlist_header.packlist_date as date), packlist_detail.unit_price, packlist_detail.quantity, job.customer, job.trade_currency FROM (packlist_header inner join packlist_detail on packlist_header.packlist = packlist_detail.packlist) inner join job on packlist_detail.job = job.job WHERE Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%' AND packlist_header.packlist_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' order by packlist_header.packlist_date desc")

    data = cursor.fetchall()
    data_wk2 = []
    weeks = [x for x in range(1,53)]
    for each in data:
        each[0] = each[0].isocalendar()[:-1]
        try:
            weeks.remove(each[0][1])
        except ValueError:
            pass
        if each[4] == 2: #if currency is CAD do nothing
            pass
        elif each[4] == 1: #if currency is USD convert to CAD
            each[1] = Decimal(each[1])*Decimal(1.34)
        else:
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

    cursor.execute("SELECT cast(po_header.order_date as date), po_detail.order_quantity, po_detail.unit_cost, po_header.trade_currency from po_header inner join po_detail on po_header.po = po_detail.po where po_header.status not like 'unissued' and po_detail.po not like '19981' and po_header.order_date > Dateadd(year, -1, getdate()) order by po_header.order_date desc")

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
            cost = each[2] * 1.34
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
        cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.order_quantity FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' and (job.description like '%headache%' or job.part_number like '6910') and job.part_number not like '0202' order by job.order_date desc")

    else:
        cursor.execute("SELECT Job.Job, cast(Job.Order_Date as date), Job.order_quantity FROM Job WHERE (Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%') AND CURRENT_TIMESTAMP > Job.Order_Date and job.order_date > Dateadd(year, -1, getdate()) AND Job.Job Not Like '%-%' and job.part_number like '" + part_number + "' order by job.order_date desc")

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
            if len(centers) == []:
                centers = [['COMPLETE']]

            cursor.execute("select promised_date from delivery where job = '" + job[0] + "'")
            promised = [list(x) for x in cursor.fetchall()]
            if not promised:
                promised = datetime.date(1900, 1, 1)
            else:
                promised = promised[0][0]

            cursor.execute("select order_quantity, description from job where job = '" + job[0] + "'")
            quantity = [list(x) for x in cursor.fetchall()]

            try:
                j.append([job[0], promised, centers[0][0], quantity[0][0], quantity[0][1]])
            except:
                pass

        po_list.append([po[0], j])

    msg = Message("Daimler - Daily Update",
        sender="colin@iconicmetalgear.com",
        recipients=["colin@iconicmetalgear.com", "jason@iconicmetalgear.com", "shipping@iconicmetalgear.com"])

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

    cursor.execute("select job.job, delivery.remaining_quantity from job left join delivery on job.job = delivery.job where part_number = '" + part_number + "' and job.status = 'active' and job.job not like '%-%' and job.customer like 'I-H PROD'")
    stock_jobs = [list(x) for x in cursor.fetchall()]

    for job in stock_jobs:
        cursor.execute("select work_center, sequence from job_operation where status = 'o' and job = '" + job[0] + "'")

        centers = [list(x) for x in cursor.fetchall()]
        centers.sort(key=itemgetter(1))

        job.append(centers[0][0])

    stock_in_production = 0
    for each in stock_jobs:
        try:
            stock_in_production += each[1]
        except:
            continue

    total_pull_from = 0
    for each in pull_from_list:
        cursor.execute("select count(sequence) from job_operation where job = '" + str(each[0]) + "' and status = 'o'")
        operation_count = cursor.fetchall()[0][0]
        if operation_count == 2:
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

    cursor.execute("select order_date, total_price, trade_currency from job where total_price <> 0 and customer not like 'I-H%' and job not like '%-%' and order_date > '1/1/2014 12:00:00 AM' order by Order_Date")
    query = [list(x) for x in cursor.fetchall()]
    for job in query:
        if job[2] == 2: #if currency is CAD do nothing
            pass
        elif job[2] == 1: #if currency is USD convert to CAD
            job[1] = Decimal(job[1])*Decimal(1.34)

    query = [{'date': x[0], 'price': x[1]} for x in query]

    data = pd.DataFrame(query)
    data = data.set_index(['date'])
    data = data['price'].resample('W').sum()
    data['date'] = data.index
    data = data.reset_index()
    data = data.fillna(0)
    data = data.to_dict('records')
    data = data[0:-1]
    data = query
    for e in data:
        e['date'] = e['date'].strftime('%Y-%m-%d')

    osp_data = json.dumps(data, indent=2, default=str)
    data = {'osp': osp_data}

    #get jobs shipped in last 12 months
    cursor.execute("select change_history.job, cast(change_history.change_date as date), job.part_number, job.total_price, job.trade_currency from job inner join change_history on job.job = change_history.job where wc_vendor = 'shipping' and change_date >= DATEADD(MONTH, DATEDIFF(MONTH, '19000101', GETDATE())-12, '19000101') AND change_date <  DATEADD(MONTH, DATEDIFF(MONTH, '19000101', GETDATE()), '19000101') and change_type = 14 and job.customer not like 'I-H%' and job.job not like '%-%'")

    job_list = [list(x) for x in cursor.fetchall()]
    job_list = sorted(job_list, key=itemgetter(1))

    monthly_sales = [{'month': '01', 'year': '', 'toolbox': 0, 'rack': 0, 'stepbox': 0, 'cabinets': 0, 'other': 0, '0202': 0}, {'month': '02', 'year': '', 'toolbox': 0, 'rack': 0, 'stepbox': 0, 'cabinets': 0, 'other': 0, '0202': 0}, {'month': '03', 'year': '', 'toolbox': 0, 'rack': 0, 'stepbox': 0, 'cabinets': 0, 'other': 0, '0202': 0}, {'month': '04', 'year': '', 'toolbox': 0, 'rack': 0, 'stepbox': 0, 'cabinets': 0, 'other': 0, '0202': 0}, {'month': '05', 'year': '', 'toolbox': 0, 'rack': 0, 'stepbox': 0, 'cabinets': 0, 'other': 0, '0202': 0}, {'month': '06', 'year': '', 'toolbox': 0, 'rack': 0, 'stepbox': 0, 'cabinets': 0, 'other': 0, '0202': 0}, {'month': '07', 'year': '', 'toolbox': 0, 'rack': 0, 'stepbox': 0, 'cabinets': 0, 'other': 0, '0202': 0}, {'month': '08', 'year': '', 'toolbox': 0, 'rack': 0, 'stepbox': 0, 'cabinets': 0, 'other': 0, '0202': 0}, {'month': '09', 'year': '', 'toolbox': 0, 'rack': 0, 'stepbox': 0, 'cabinets': 0, 'other': 0, '0202': 0}, {'month': '10', 'year': '', 'toolbox': 0, 'rack': 0, 'stepbox': 0, 'cabinets': 0, 'other': 0, '0202': 0}, {'month': '11', 'year': '', 'toolbox': 0, 'rack': 0, 'stepbox': 0, 'cabinets': 0, 'other': 0, '0202': 0}, {'month': '12', 'year': '', 'toolbox': 0, 'rack': 0, 'stepbox': 0, 'cabinets': 0, 'other': 0, '0202': 0}]

    for each in monthly_sales:
        each['year'] = next(item for item in job_list if item[1].strftime('%m') == each['month'])[1].strftime('%Y')

    def makeDate(item):
        d = item['year'] + '-' + item['month']
        d = datetime.datetime.strptime(d, '%Y-%m')
        return d

    monthly_sales = sorted(monthly_sales, key=makeDate)

    other_list = []

    for job in job_list:
        if job[4] == 2: #if currency is CAD do nothing
            pass
        elif job[4] == 1: #if currency is USD convert to CAD
            job[3] = Decimal(job[3])*Decimal(1.32)

        if job[2] in ['1076','1001','1002','1003','1004','1005','1006','1007','1008','1009','1010','1011','1012','1013','1014','1015','1016','1017','1018','1020','1021','1022','1023','1024','1075','1050','1051','1052','1053','1054','1055','1056','1057','1058','1059','1060','1061','1062','1063','1064','1065','1066','1067','1070','1071','1072','1073','1074','1068','1100','1101','1102','1103','1122','1104','1105','1106','1107','1108','1109','1110','1111','1112','1113','1114','1115','1116','1117','1118','1119','1120','1121','1123','1171','1172','1150','1151','1152','1153','1154','1155','1156','1157','1158','1159','1160','1161','1162','1163','1164','1165','1166','1167','1168','1169','1170','1173','1174','1175','1200','1201','1202','1215','1216','1217','1203','1204','1205','1206','1207','1208','1209','1210','1211','1212','1213','1214','6805','6566','6565','6564','6560','1801','1802','1800','1808','1804','1813','1811','1803','1812']:
            job.append('toolbox')
            next((item for item in monthly_sales if item['month'] == job[1].strftime('%m')), None)['toolbox'] += job[3]

        elif job[2] in ['1300','1301','1302','1364','1365','1366','1319','1320','1321','1322','1323','1324','1328','1329','1330','1331','1332','1333','1351','1352','1353','1355','1356','1357','1359','1360','1361','1362','1303','1304','1305','1306','1307','1308','1309','1310','1311','1312','1313','1314','1315','1317','1367','1368','1369','1370','1371','1372','1373','1318','1374','6926','6925','6910','6900','6583']:
            job.append('rack')
            next((item for item in monthly_sales if item['month'] == job[1].strftime('%m')), None)['rack'] += job[3]

        elif job[2] in ['1500','1501','1502','1503','1504','1505','1506','1507','1508','1509','1510','1511','1512','1513','1526','1.34','1514','1515','1516','1517','1518','1525','1519','1520','1521','1522','1523','1524']:
            job.append('stepbox')
            next((item for item in monthly_sales if item['month'] == job[1].strftime('%m')), None)['stepbox'] += job[3]

        elif job[2] is not None and job[2].startswith('0202'):
            job.append('0202')
            next((item for item in monthly_sales if item['month'] == job[1].strftime('%m')), None)['0202'] += job[3]

        elif job[2] is not None and len(job[2]) == 3:
            job.append('cabinets')
            next((item for item in monthly_sales if item['month'] == job[1].strftime('%m')), None)['cabinets'] += job[3]

        else:
            job.append('other')
            next((item for item in monthly_sales if item['month'] == job[1].strftime('%m')), None)['other'] += job[3]


    family_data = json.dumps(monthly_sales, indent=2, default=str)
    data['family'] = family_data

    #get jobs shipped in last 12 months
    cursor.execute("select change_history.job, cast(change_history.change_date as date), job.total_price, job.trade_currency from job inner join change_history on job.job = change_history.job where wc_vendor = 'shipping' and change_date >= DATEADD(MONTH, DATEDIFF(MONTH, '19000101', GETDATE())-12, '19000101') AND change_date <  DATEADD(MONTH, DATEDIFF(MONTH, '19000101', GETDATE()), '19000101') and change_type = 14 and job.customer not like 'I-H%' and job.job not like '%-%'")

    job_list = [list(x) for x in cursor.fetchall()]
    job_list = sorted(job_list, key=itemgetter(1))

    monthly_sales = [{'month': '01', 'year': '', 'usd': 0, 'cad': 0}, {'month': '02', 'year': '', 'usd': 0, 'cad': 0}, {'month': '03', 'year': '', 'usd': 0, 'cad': 0}, {'month': '04', 'year': '', 'usd': 0, 'cad': 0}, {'month': '05', 'year': '', 'usd': 0, 'cad': 0}, {'month': '06', 'year': '', 'usd': 0, 'cad': 0}, {'month': '07', 'year': '', 'usd': 0, 'cad': 0}, {'month': '08', 'year': '', 'usd': 0, 'cad': 0}, {'month': '09', 'year': '', 'usd': 0, 'cad': 0}, {'month': '10', 'year': '', 'usd': 0, 'cad': 0}, {'month': '11', 'year': '', 'usd': 0, 'cad': 0}, {'month': '12', 'year': '', 'usd': 0, 'cad': 0}]

    for each in monthly_sales:
        each['year'] = next(item for item in job_list if item[1].strftime('%m') == each['month'])[1].strftime('%Y')

    def makeDate(item):
        d = item['year'] + '-' + item['month']
        d = datetime.datetime.strptime(d, '%Y-%m')
        return d

    monthly_sales = sorted(monthly_sales, key=makeDate)

    for job in job_list:
        if job[3] == 2: #if currency is CAD do nothing
            next((item for item in monthly_sales if item['month'] == job[1].strftime('%m')), None)['cad'] += job[2]
        elif job[3] == 1: #if currency is USD convert to CAD
            job[2] = Decimal(job[2])*Decimal(1.32)
            next((item for item in monthly_sales if item['month'] == job[1].strftime('%m')), None)['usd'] += job[2]

    currency_data = json.dumps(monthly_sales, indent=2, default=str)
    data['currency'] = currency_data

    cursor.execute("select cast(order_date as date) from job where status like 'Active' and job not like '%-%' and customer not like '%I-H%' and order_date > '2018-07-01'")

    active_orders = [list(x)[0] for x in cursor.fetchall()]

    order_count = []

    def daterange(start_date, end_date):
        for n in range(int ((end_date - start_date).days)):
            yield start_date + datetime.timedelta(n)

    start_date = min(active_orders)
    end_date = max(active_orders)

    for single_date in daterange(start_date, end_date):
        count = sum(1 for d in active_orders if d == single_date)
        order_count.append({'date': single_date, 'count': count})

    order_count_data = json.dumps(order_count, indent=2, default=str)
    data['counts'] = order_count_data

    #Promised Date distrobution
    #Under Construction
    cursor.execute("select cast(delivery.promised_date as date) from delivery left join job on delivery.job = job.job where job.status like 'Active' and job.job not like '%-%' and job.customer not like '%I-H%' and job.est_rem_hrs > 0")

    active_orders = [list(x)[0] for x in cursor.fetchall()]

    order_count = []

    def daterange(start_date, end_date):
        for n in range(int ((end_date - start_date).days)):
            yield start_date + datetime.timedelta(n)

    start_date = min(active_orders)
    end_date = max(active_orders)

    for single_date in daterange(start_date, end_date):
        count = sum(1 for d in active_orders if d == single_date)
        order_count.append({'date': single_date, 'count': count})

    order_count_data = json.dumps(order_count, indent=2, default=str)
    data['promised_count'] = order_count_data

    #Hours of work per week

    cursor.execute("select job.job, job.est_rem_hrs, cast(delivery.promised_date as date) from delivery left join job on delivery.job = job.job where job.status = 'Active' and job.est_rem_hrs > 0")
    query = [list(x) for x in cursor.fetchall()]

    weekly_hours_data = []

    for job in query:
        if job[2] < datetime.datetime.now().date():
            job[2] = datetime.datetime.now().date()
        job.append(job[2])
        job[2] = job[2].strftime('%Y-%V')
        if not any(j['date'] == job[2] for j in weekly_hours_data):
            weekly_hours_data.append({'date': job[2], 'count': job[1], 'fdate': job[3], 'jlist': [str(job[0])]})
        else:
            for d in weekly_hours_data:
                if d['date'] == job[2]:
                    d['count'] += job[1]
                    d['jlist'].append(str(job[0]))

    weekly_hours_data.sort(key=itemgetter('date'))
    for each in weekly_hours_data:
        each['date'] = each['fdate']
        del each['fdate']

    data['weekly_hours'] = json.dumps(weekly_hours_data, indent=2, default=str)

    return render_template('analytics.html', data = data)

@app.route("/report/in_stock")
def in_stock(name=None):
    if request.args.get('category'):
        category = request.args.get('category')
    else:
        category = 'all'

    categories = {
    'camlock': [1076,1001,1002,1003,1004,1005,1006,1007,1008,1009,1010,1011,1012,1013,1014,1015,1016,1017,1018,1020,1021,1022,1023,1024,1075,1050,1051,1052,1053,1054,1055,1056,1057,1058,1059,1060,1061,1062,1063,1064,1065,1066,1067,1070,1071,1072,1073,1074,1068],
    'thandle': [1100,1101,1102,1103,1122,1104,1105,1106,1107,1108,1109,1110,1111,1112,1113,1114,1115,1116,1117,1118,1119,1120,1121,1123,1171,1172,1150,1151,1152,1153,1154,1155,1156,1157,1158,1159,1160,1161,1162,1163,1164,1165,1166,1167,1168,1169,1170,1173,1174,1175],
    'flatrack':
    [1300,1301,1302,1364,1365,1366,1319,1320,1321,1322,1323,1324,1328,1329,1330,1331,1332,1333,1351,1352,1353,1355,1356,1357,1359,1360,1361,1362],
    'enclosed':
    [1303,1304,1305,1306,1307,1308,1309,1310,1311,1312,1313,1314,1315,1317,1367,1368,1369,1370,1371,1372,1373,1318,1374],
    'topstep':
    [1500,1501,1502,1503,1504,1505,1506,1507,1508,1509,1510,1511,1512,1513,1526,1.34],
    'bigmouth':
    [1514,1515,1516,1517,1518,1525,1519,1520,1521,1522,1523,1524],
    'loadleveler':
    [1600,1601,1602,1603,1604,1605,1606,1607,1608],
    'framebox':
    [1800,1809,1810,1801,1802,1814,1807,1803,1804,1808,1811,1812,1813],
    'fifthwheel':
    [1950,1951,1954,1955]
    }

    all = []
    for each in categories.values():
        all.extend(each)

    categories['all'] = all

    toolboxes = [item for sublist in [categories['thandle'], categories['camlock']] for item in sublist]
    categories['toolbox'] = toolboxes

    racks = [item for sublist in [categories['flatrack'], categories['enclosed']] for item in sublist]
    categories['headache'] = racks

    stepboxes = [item for sublist in [categories['topstep'], categories['bigmouth']] for item in sublist]
    categories['stepbox'] = stepboxes

    class Part(object):
        number = ''
        description = ''
        price = 0
        currency = ''
        shop_stock = 0
        dc_stock = 0
        category = ''

        def __init__(self, number, description, currency, price, shop_stock, dc_stock, category):
            self.number = number
            self.description = description
            self.price = price
            self.currency = currency
            self.shop_stock = shop_stock
            self.dc_stock = dc_stock
            self.category = category

    def make_part(number, description, currency, price, shop_stock, dc_stock, category):
        part = Part(number, description, currency, price, shop_stock, dc_stock, category)
        return part

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select material, description, selling_price, price_unit_conv from material where material in ('{0}')".format("', '".join([str(x) for x in categories[category]])))
    try:
        part_data = list(cursor.fetchall())
    except:
        return render_template('in_stock.html', parts = [])

    del categories['all']
    del categories['toolbox']
    del categories['headache']
    del categories['stepbox']

    parts = []
    for each in part_data:
        c = each[3]
        if c == 1.0:
            part_currency = 'CAD'
        elif not c:
            part_currency = ''
        else:
            part_currency = 'USD'

        buffalo_quantity = 0
        cursor.execute("select cast(on_hand_qty as int) from material_location where material = '" + each[0] + "' and location_id = 'BUFFALO'")
        data = cursor.fetchall()
        if data:
            buffalo_quantity = list(data)[0][0]

        shop_quantity = 0
        cursor.execute("select cast(on_hand_qty as int) from material_location where material = '" + each[0] + "' and location_id = 'SHOP'")
        data = cursor.fetchall()
        if data:
            shop_quantity = list(data)[0][0]

        if shop_quantity == buffalo_quantity == 0:
            continue

        part_category = ''
        for c, n in categories.iteritems():
            if each[0] in [str(x) for x in n]:
                part_category = c.capitalize()

        parts.append(make_part(each[0], each[1], part_currency, each[2], shop_quantity, buffalo_quantity, part_category))

    result = []
    for each in parts:
        if each.category in [x['category'] for x in result]:
            for e in result:
                if e['category'] == each.category:
                    e['parts'].append(each)
        else:
            result.append({'category': each.category, 'parts': [each]})

    return render_template('in_stock.html', parts = result, category = category.capitalize(), data = result)

@app.route("/schedule/<sched>", methods=['GET', 'POST'])
def schedule(sched):

    class job:
        def __init__(self, job_number, part='', description='', quantity=0, order_date='', priority=5,    current_wc='', total_line_hours=0, po_number=''):
            self.job_number = job_number
            self.part = part
            self.description = description
            self.quantity = quantity
            self.order_date = order_date
            self.priority = priority
            self.current_wc = current_wc
            self.total_line_hours = total_line_hours
            self.po_number = po_number

    #get job numbers and work centers from form
    try:
        sched = request.get_json(force=True)
    except:
        sched = ''
    #get all job details
        #customer, part, description, quantity, order date, priority, current wc, total line hours, po#
    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()
    cursor.execute("select est_total_hrs from job_operation where job = '19708'")
    data = cursor.fetchall()
    return render_template('generic_table.html', rows = data, head = '', title = 'job operation')

    for wc in sched:
        for j in wc:
            #initialize instances of job class with job numbers from form
            j = job(j)
            cursor.execute("select job, part_number, description, order_quantity, order_date, priority, customer_po from job where job.job = {}".format(j.job_number))
            data = [list(x) for x in cursor.fetchall()][0]
            j.part = data[1]
            j.description = data[2]
            j.quantity = data[3]
            j.order_date = data[4]
            j.priority = data[5]
            j.po_number = data[6]

            cursor.execute("select work_center, sequence, est_total_hrs from job_operation where job = {} and job_operation.status = 'o'".format(j.job_number))
            data = [list(x) for x in cursor.fetchall()]
            data.sort(key=itemgetter(1))
            j.current_wc = data[0][0]
            j.total_line_hours = data[0][2]

        #job_operation - current_wc & total line hours

    #return work center, job lists

    #function for adding associated PO wk_items

    #function for updating status of jobs

    #function for filling work center with jobs from priority list

@app.route('/search')
def search(name=None):
    if request.args.get('search'):
        search = request.args.get('search')
        search = search.replace("'", "''")
    else:
        return render_template('search.html', rows = '', title = 'No Search Terms Entered')

    status = ''
    if request.args.get('status'):
        status = request.args.get('status')
        if status == 'all':
            status = ''

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    #get data from job
    cursor.execute("select job, customer, order_quantity, description, ext_description, customer_po, note_text, comment, cast(order_date as date), part_number, quote, sales_rep from job where (job like '%{0}%' or customer like '%{0}%' or order_quantity like '%{0}%' or description like '%{0}%' or ext_description like '%{0}%' or customer_po like '%{0}%' or note_text like '%{0}%' or comment like '%{0}%' or part_number like '%{0}%' or quote like '%{0}%' or sales_rep like '%{0}%') and status like '%{1}%'".format(search, status))

    data = {'job': [list(x) for x in cursor.fetchall()]}
    data['job_head'] = ['Job', 'Customer', 'Quantity', 'Description', 'Ext. Description', 'Customer PO', 'Note Text', 'Comment', 'Order Date', 'Part Number', 'Quote', 'Sales Rep']

    #get data from quote
    cursor.execute("select rfq.comments, rfq.contact, rfq.customer, rfq.reference, quote.description, quote.ext_description, quote.line, quote.part_number, quote.rfq, quote.quoted_by from quote inner join rfq on quote.rfq = rfq.rfq where (rfq.comments like '%{0}%' or rfq.contact like '%{0}%' or rfq.customer like '%{0}%' or rfq.reference like '%{0}%' or quote.description like '%{0}%' or quote.ext_description like '%{0}%' or quote.line like '%{0}%' or quote.part_number like '%{0}%' or quote.rfq like '%{0}%' or quote.quoted_by like '%{0}%') and quote.status like '%{1}%'".format(search, status))

    data['quote'] = [list(x) for x in cursor.fetchall()]
    data['quote_head'] = ['Comments', 'Contact', 'Customer', 'Reference', 'Description', 'Ext. Description', 'Line', 'Part Number', 'RFQ', 'Quoted By']

    #get data from PO
    cursor.execute("select po_header.comment, po_header.issued_by, po_header.po, po_header.ship_to, po_header.status, po_header.tax_code, po_header.terms, po_header.vendor, po_detail.ext_description, po_detail.gl_account, po_detail.line, po_detail.note_text, po_detail.order_quantity, po_detail.status, po_detail.unit_cost, po_detail.vendor_reference from po_header inner join po_detail on po_header.po = po_detail.po where (po_header.comment like '%{0}%' or po_header.contact like '%{0}%' or po_header.issued_by like '%{0}%' or po_header.note_text like '%{0}%' or po_header.po like '%{0}%' or po_header.ship_to like '%{0}%' or po_header.status like '%{0}%' or po_header.tax_code like '%{0}%' or po_header.terms like '%{0}%' or po_header.vendor like '%{0}%' or po_detail.ext_description like '%{0}%' or po_detail.gl_account like '%{0}%' or po_detail.line like '%{0}%' or po_detail.note_text like '%{0}%' or po_detail.order_quantity like '%{0}%' or po_detail.status like '%{0}%' or po_detail.unit_cost like '%{0}%' or po_detail.vendor_reference like '%{0}%') and po_header.status like '%{1}%'".format(search, status))

    data['po'] = [list(x) for x in cursor.fetchall()]
    data['po_head'] = ['PO Comment', 'Issued By', 'PO', 'Ship To', 'PO Status', 'Tax Code', 'Terms', 'Vendor', 'Ext. Description', 'GL Account', 'Line', 'Item Note', 'Order Quantity', 'Status', 'Unit Cost', 'Vendor Reference']

    return render_template('search.html', rows = data, title = 'Job Detail Search', search = search)

@app.route('/sql')
def sql_entry(name=None):
    if request.args.get('sql'):
        query = request.args.get('sql')
    else:
        return render_template('sql.html', rows = '', title = 'No Search Terms Entered')

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    #get data from job
    cursor.execute(query)
    data = [list(x) for x in cursor.fetchall()]

    cursor.execute("select name from sys.dm_exec_describe_first_result_set('{0}', null, 0) ;".format(query.split('where')[0]))
    head = [list(x)[0] for x in cursor.fetchall()]

    return render_template('sql.html', rows=data, head=head, title='SQL Query')

@app.route('/reports/pm_shipped')
def pm_shipped(name=None):
    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select job.job, job.total_price, job.customer, cast(change_history.change_date as date) from job inner join change_history on job.job = change_history.job where wc_vendor = 'shipping' and change_date >= '2018-04-01 00:00:00' AND change_date <  '2018-11-01 00:00:00' and change_type = 14 and job.customer not like 'I-H%' and job.job not like '%-%' and sales_rep = 'PMSALE'")

    job_list = [list(x) for x in cursor.fetchall()]
    job_list = sorted(job_list, key=itemgetter(3))

    total_sales = 0

    for job in job_list:
        total_sales += job[1]

    return render_template('generic_table.html', rows = job_list, head = ['Job', 'Total Price', 'Customer', 'Shipped Date'], title = 'PM Sales Jobs Shipped April 1 2018 - Oct 31 2018', body = 'Total Sales: {0}'.format(total_sales))

@app.route('/rep_report')
def rep_report(name=None):

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select distinct sales_rep from job")
    rep_list = [list(x)[0] for x in cursor.fetchall()]

    if request.args.get('rep'):
        rep = request.args.get('rep')
    else:
        return render_template('rep_report.html', rows = '', title = 'No Rep Selected', rep_list = rep_list)

    if request.args.get('from_date'):
        from_date = request.args.get('from_date')
    else:
        return render_template('rep_report.html', rows = '', title = 'No From Date Entered', rep_list = rep_list)

    if request.args.get('to_date'):
        to_date = request.args.get('to_date')
    else:
        return render_template('rep_report.html', rows = '', title = 'No To Date Entered', rep_list = rep_list)

    cursor.execute("select job.job, job.total_price, job.customer, cast(change_history.change_date as date) from job inner join change_history on job.job = change_history.job where wc_vendor = 'shipping' and change_date >= '{0} 00:00:00' AND change_date <  '{1} 00:00:00' and change_type = 14 and job.customer not like 'I-H%' and job.job not like '%-%' and sales_rep = '{2}'".format(from_date, to_date, rep))

    job_list = [list(x) for x in cursor.fetchall()]
    job_list = sorted(job_list, key=itemgetter(3))

    total_sales = 0

    for job in job_list:
        total_sales += job[1]

    return render_template('rep_report.html', rows = job_list, head = ['Job', 'Total Price', 'Customer', 'Shipped Date'], title = '{0} Jobs Shipped {1} - {2}'.format(rep, from_date, to_date), body = 'Total Sales: {0}'.format(total_sales), rep_list = rep_list)

@app.route("/mobile_traveler")
def mobile_traveler(name=None):
    if request.args.get('job'):
        job = request.args.get('job')
    else:
        return render_template('mobile_traveler.html', job_details = {'job': 'Enter Job'})

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select status, part_number, order_quantity, customer_po, customer, ship_to, note_text, cast(order_date as date) from job where job = '{0}'".format(job))
    data = list(cursor.fetchall())
    if not data:
        return render_template('mobile_traveler.html', job_details = {'job': 'Invalid Job - Try Again'})

    data = [list(x) for x in data][0]

    job_details = {'job': job, 'status': data[0], 'part number': data[1], 'quantity': data[2], 'customer po': data[3], 'customer': data[4], 'ship to': data[5], 'note text': data[6], 'order date': data[7]}

    try:
        cursor.execute("select name, line1, line2, city, state, zip from address where address = '{0}'".format(job_details['ship to']))
        job_details['address'] = [x for x in cursor.fetchall()][0]
    except:
        job_details['address'] = ['NA']

    cursor.execute("select cast(promised_date as date) from delivery where job = '{0}'".format(job))
    try:
        job_details['promised date'] = [list(x) for x in cursor.fetchall()][0][0]
    except:
        job_details['promised date'] = datetime.datetime.now().date().strftime('%Y-%m-%d')

    cursor.execute("select work_center, sequence from job_operation where job = '{0}' and job_operation.status = 'o'".format(job))
    data = [list(x) for x in cursor.fetchall()]
    if data == []:
        job_details['current wc'] = 'COMPLETE'
    else:
        data.sort(key=itemgetter(1))
        job_details['current wc'] = data[0][0]

    return render_template('mobile_traveler.html', job_details = job_details)

@app.route("/part_viewer")
def part_viewer(name=None):
    if request.args.get('part'):
        part = request.args.get('part')
    else:
        return render_template('part_viewer.html', rows = '', head = '', title = 'Part Viewer')

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select job, customer, customer_po, description, cast(order_date as date), order_quantity from job where part_number = '{0}' and status = 'Active'".format(part))
    data = [list(x) for x in cursor.fetchall()]
    if not data:
        cursor.execute("select job, customer, customer_po, description, cast(order_date as date), order_quantity from job where part_number like '{0}%' and status = 'Active'".format(part))
        data = [list(x) for x in cursor.fetchall()]

    for job in data:
        cursor.execute("select work_center, sequence from job_operation where job = '{0}' and job_operation.status = 'o'".format(job[0]))
        job_data = [list(x) for x in cursor.fetchall()]
        if len(job_data[0]) > 0:
            job_data.sort(key=itemgetter(1))
            job.append(job_data[0][0])
        else:
            job.append('None')

    return render_template('part_viewer.html', rows = data, head = ['Job', 'Customer', 'Customer PO', 'Description', 'Order Date', 'Order Quantity', 'Current WC'], title = 'Part Viewer - {0}'.format(part))

@app.route("/po_viewer")
def po_viewer(name=None):
    if request.args.get('po'):
        po = request.args.get('po')
    else:
        return render_template('po_viewer.html', rows = '', head = '', title = 'PO Viewer')

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select job, customer, customer_po, part_number, description, cast(order_date as date), order_quantity from job where customer_po = '{0}' and status = 'Active'".format(po))
    data = [list(x) for x in cursor.fetchall()]
    if not data:
        cursor.execute("select job, customer, customer_po, part_number, description, cast(order_date as date), order_quantity from job where customer_po like '{0}%' and status = 'Active'".format(po))
        data = [list(x) for x in cursor.fetchall()]

    for job in data:
        cursor.execute("select work_center, sequence from job_operation where job = '{0}' and job_operation.status = 'o'".format(job[0]))
        job_data = [list(x) for x in cursor.fetchall()]
        job_data.sort(key=itemgetter(1))
        job.append(job_data[0][0])

    return render_template('po_viewer.html', rows = data, head = ['Job', 'Customer', 'Customer PO', 'Part Number', 'Description', 'Order Date', 'Order Quantity', 'Current WC'], title = 'PO Viewer')

@app.route("/customer_jobs")
def customer_jobs(name=None):
    if request.args.get('customer'):
        customer = request.args.get('customer')
    else:
        return render_template('customer_jobs.html', rows = '', head = '', title = 'Customer Jobs')

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select job.job, job.customer, job.customer_po, job.part_number, job.description, cast(job.order_date as date), cast(delivery.promised_date as date), job.order_quantity, job.ship_to from job left join delivery on job.job = delivery.job where job.customer = '{0}' and job.status = 'Active'".format(customer))
    data = [list(x) for x in cursor.fetchall()]
    if not data:
        cursor.execute("select job.job, job.customer, job.customer_po, job.part_number, job.description, cast(job.order_date as date), cast(delivery.promised_date as date), job.order_quantity, job.ship_to from job left join delivery on job.job = delivery.job where job.customer like '{0}%' and job.status = 'Active'".format(customer))
        data = [list(x) for x in cursor.fetchall()]

    for job in data:
        cursor.execute("select work_center, sequence from job_operation where job = '{0}' and job_operation.status = 'o'".format(job[0]))
        job_data = [list(x) for x in cursor.fetchall()]
        job_data.sort(key=itemgetter(1))
        try:
            job.append(job_data[0][0])
        except:
            job.append('NA')

        try:
            cursor.execute("select name from address where address = '{0}'".format(job[8]))
            job_ship = [x for x in cursor.fetchall()][0]
            job.append(job_ship[0])
        except:
            job.append('NA')
        del job[8]

    return render_template('customer_jobs.html', rows = data, head = ['Job', 'Customer', 'Customer PO', 'Ship To', 'Part Number', 'Description', 'Order Date', 'Promised Date', 'Order Quantity', 'Current WC'], title = 'Customer Jobs')

@app.route("/saw_packages")
def saw_packages(name=None):

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select job.job, job.part_number from job inner join job_operation on job.job = job_operation.job where job.status = 'Active' and job.make_quantity > 0 and job.job not like '%-%' and job_operation.work_center = 'DESIGN' and job_operation.status = 'c'")
    data = [list(x) for x in cursor.fetchall()]

    cursor.execute("select job, status, total_price from job where job like '%-S%'")
    saw_jobs = [list(x) for x in cursor.fetchall()]

    need_saw = []

    for job in data:
        if job[1] in [
                '103','1203','1204','1209','1300','1301','1302','1303','1304',
                '1307','1308','1310','1312','1315','1317','1320','1322','1352',
                '1364','1365','1366','1367',
                '1368','1369','1370','1371','1372','1373','1374','1396','1397',
                '1398','1400','1404','1414','1415','1417','1433','1529',
                '1603','1705','1800','1801',
                '1802','1803','1809','1810','1811','1813','227','3002','3004',
                '3006','3011','3013','3017','3018','3019','3024','3027','3028',
                '303','3033','3037','3039','306','6004','6018','6031','6059',
                '6450','6535','6579','6580','6581','6583','6592','6595','6845',
                '6858','6859','6925','6926','6930','6932'
                ]:
            need_saw.append(job)

    for job in need_saw:
        for sjob in saw_jobs:
            if job[0] == sjob[0][:-2]:
                if sjob[1] == 'Active':
                    job.extend(['At Saw', sjob[2]])
                else:
                    job.extend(['Saw Complete', sjob[2]])

    for job in need_saw:
        if len(job) == 2:
            job.extend(['Missing Saw', 0])

    return render_template('saw_packages.html', rows = need_saw, title = 'Saw Packages')

@app.route("/ncr_report")
def ncr_report(name=None):

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select cast(order_date as date), customer_po, customer, note_text, total_price, job, part_number from job where job like '%-NCR%'")
    data = [list(x) for x in cursor.fetchall()]

    totals = {'7': 0, '30': 0, '60': 0, '90': 0, '120': 0, '240': 0, '365': 0, '730': 0}
    for each in data:
        try:
            ncr_note = each[3].split('=')
            each[3] = ncr_note[-1]
        except:
            each[3] = 'None'

        try:
            cursor.execute("select work_center from job_operation where job = '{0}' order by sequence".format(each[5]))
            wc = [list(x) for x in cursor.fetchall()][-1][0]
            each.append(wc)
        except:
            each.append('None')

        if each[7] == 'None' or each[7] == 'DESIGN':
            each[4] = 0

        else:
            each[4] = 200

        now = datetime.datetime.now().date()

        if now-datetime.timedelta(days=7) <= each[0] <= now:
            totals['7'] += each[4]

        if now-datetime.timedelta(days=30) <= each[0] <= now:
            totals['30'] += each[4]

        if now-datetime.timedelta(days=60) <= each[0] <= now:
            totals['60'] += each[4]

        if now-datetime.timedelta(days=90) <= each[0] <= now:
            totals['90'] += each[4]

        if now-datetime.timedelta(days=120) <= each[0] <= now:
            totals['120'] += each[4]

        if now-datetime.timedelta(days=240) <= each[0] <= now:
            totals['240'] += each[4]

        if now-datetime.timedelta(days=365) <= each[0] <= now:
            totals['365'] += each[4]

        if now-datetime.timedelta(days=730) <= each[0] <= now:
            totals['730'] += each[4]


    return render_template('ncr_report.html', rows = data, head = ['Order Date', 'Customer PO', 'Customer', 'Note Text', 'Total Price', 'Job', 'Part Number', 'Work Center'], title = 'NCR Report', totals = totals)

@app.route('/job_price/<job>')
def jobs_price(job):
    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    if ',' in job:
        joblist = [x.strip() for x in job.split(',')]
    elif '-' not in job and len(job) % 5 == 0:
        joblist = [job[i:i+5] for i in range(0, len(job), 5)]

    rows = []
    for each in joblist:
        try:
            cursor.execute("select job, total_price, trade_currency from job where job = '"+ each +"'")
        except:
            continue
        data = [list(x) for x in cursor.fetchall()]
        rows.append(data[0])

    for job in rows:
        if job[2] == 1:
            job[1] = float(job[1])*float(1.3)
            job[2] = 'USD'
        elif job[2] == 2:
            job[2] = 'CAD'

    head = ['Job', 'Order Total', 'Currency']
    return render_template('generic_table.html', rows = rows, head = head, title = 'Job List')

@app.route('/reports/quotes/<length>')
def quotes_length(length):
    if not length:
        length = 21;

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select quote.quote, quote.quoted_by, quote.part_number, quote.status, quote.rfq, rfq.customer, rfq.sales_rep, cast(rfq.quote_date as date), rfq.reference, rfq.trade_currency from quote inner join rfq on quote.rfq = rfq.rfq where rfq.quote_date > DATEADD(DAY, DATEDIFF(DAY, 0, getDate() - {0}), 0)".format(length))
    data = [list(x) for x in cursor.fetchall()]

    for quote in data:
        try:
            cursor.execute("select quote_qty, total_price from quote_qty where quote like '%{0}%'".format(quote[0]))
            quote_data = [list(x) for x in cursor.fetchall()][0]
        except:
            quote_data = [0, 0]
            pass
        quote.extend(quote_data)

        if quote[9] == 2: #if currency is CAD do nothing
            pass
        elif quote[9] == 1: #if currency is USD convert to CAD
            quote[11] = Decimal(quote[11])*Decimal(1.3)

    quotes = {'quotes_per_week': 1, 'total_value': 0, 'total_win': 0, 'customers': [], 'customer_counts': {}, 'customer_total': {}, 'customer_wins': {}}

    for quote in data:
        quotes['quotes_per_week'] += 1
        quotes['total_value'] += quote[11]

        if quote[3] == 'Won':
            quotes['total_win'] += 1

        if quote[5] not in quotes['customers']:
            quotes['customers'].append(quote[5])
            quotes['customer_counts'][quote[5]] = 1
            quotes['customer_total'][quote[5]] = quote[11]
            if quote[3] == 'Won':
                quotes['customer_wins'][quote[5]] = 1
            else:
                quotes['customer_wins'][quote[5]] = 0
        else:
            quotes['customer_counts'][quote[5]] += 1
            quotes['customer_total'][quote[5]] += quote[11]
            if quote[3] == 'Won':
                quotes['customer_wins'][quote[5]] += 1

    cursor.execute("select quote.quote, quote.rfq, cast(rfq.quote_date as date), rfq.trade_currency, quote.status from quote inner join rfq on quote.rfq = rfq.rfq where rfq.quote_date > DATEADD(DAY, DATEDIFF(DAY, 0, getDate() - 365), 0)")
    data = [list(x) for x in cursor.fetchall()]

    quote_data = []
    for quote in data:
        quote.append(0)

        if quote[3] == 2: #if currency is CAD do nothing
            pass
        elif quote[3] == 1: #if currency is USD convert to CAD
            quote[5] = Decimal(quote[5])*Decimal(1.3)

        if quote[4] == 'Won':
            quote[4] = 1
        else:
            quote[4] = 0

        quote_data.append({'date': quote[2].strftime('%Y-%m-%d'), 'total_price': quote[5], 'status': quote[4]})

    data_json = json.dumps(quote_data, indent=2, default=str)
    chart_data = {'weekly_quotes': data_json}

    head = ['Customer', '# of Quotes', '$ Quoted', '% of Total $', 'Win %']
    return render_template('quotes.html', quotes = quotes, head = head, length = length, title = 'Quotes', chart_data = chart_data)

@app.route('/reports/customer_quotes/<cust>/<length>')
def customer_quotes(cust, length):
    if not length:
        length = 60

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select quote.quote, quote.quoted_by, quote.part_number, quote.status, quote.rfq, rfq.customer, rfq.sales_rep, cast(rfq.quote_date as date), rfq.reference, rfq.trade_currency from quote inner join rfq on quote.rfq = rfq.rfq where rfq.quote_date > DATEADD(DAY, DATEDIFF(DAY, 0, getDate() - {0}), 0) and rfq.customer = '{1}'".format(length, cust))
    data = [list(x) for x in cursor.fetchall()]

    for quote in data:
        try:
            cursor.execute("select quote_qty, total_price from quote_qty where quote like '%{0}%'".format(quote[0]))
            quote_data = [list(x) for x in cursor.fetchall()][0]
        except:
            quote_data = [0, 0]
            pass
        quote.extend(quote_data)

        if quote[9] == 2: #if currency is CAD do nothing
            pass
        elif quote[9] == 1: #if currency is USD convert to CAD
            quote[11] = Decimal(quote[11])*Decimal(1.3)

    quotes = {'quotes_per_week': 1, 'total_value': 0, 'total_win': 0, 'customers': [], 'customer_counts': {}, 'customer_total': {}, 'customer_wins': {}, 'quotes': []}

    for quote in data:
        quotes['quotes_per_week'] += 1
        quotes['total_value'] += quote[11]

        if quote[3] == 'Won':
            quotes['total_win'] += 1

        if quote[5] not in quotes['customers']:
            quotes['customers'].append(quote[5])
            quotes['customer_counts'][quote[5]] = 1
            quotes['customer_total'][quote[5]] = quote[11]
            if quote[3] == 'Won':
                quotes['customer_wins'][quote[5]] = 1
            else:
                quotes['customer_wins'][quote[5]] = 0
        else:
            quotes['customer_counts'][quote[5]] += 1
            quotes['customer_total'][quote[5]] += quote[11]
            if quote[3] == 'Won':
                quotes['customer_wins'][quote[5]] += 1

        quotes['quotes'].append({'part_number': quote[2], 'quantity': quote[10], 'total_price': Decimal(quote[11]), 'quote': quote[4], 'status': quote[3], 'quoted_by': quote[1], 'date': quote[7], 'reference': quote[8]})

    cursor.execute("select quote.quote, quote.rfq, cast(rfq.quote_date as date), rfq.trade_currency, quote.status from quote inner join rfq on quote.rfq = rfq.rfq where rfq.quote_date > DATEADD(DAY, DATEDIFF(DAY, 0, getDate() - 365), 0) and rfq.customer = '{0}'".format(cust))
    data = [list(x) for x in cursor.fetchall()]

    quote_data = []
    for quote in data:
        quote.append(0)

        if quote[3] == 2: #if currency is CAD do nothing
            pass
        elif quote[3] == 1: #if currency is USD convert to CAD
            quote[5] = Decimal(quote[5])*Decimal(1.3)

        if quote[4] == 'Won':
            quote[4] = 1
        else:
            quote[4] = 0

        quote_data.append({'date': quote[2].strftime('%Y-%m-%d'), 'total_price': quote[5], 'status': quote[4]})

    data_json = json.dumps(quote_data, indent=2, default=str)
    chart_data = {'weekly_quotes': data_json}

    head = ['Quote', 'Date', 'Reference', 'Part Number', 'Quantity', 'Total Price', 'Status']
    return render_template('customer_quotes.html', customer = cust, quotes = quotes, head = head, length = length, title = '{0} Quotes'.format(cust), chart_data = chart_data)

@app.route('/reports/part_quotes/<part>/<length>')
def part_quotes(part, length):
    if not length:
        length = 60;

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select quote.quote, quote.quoted_by, quote.part_number, quote.status, quote.rfq, rfq.customer, rfq.sales_rep, cast(rfq.quote_date as date), rfq.reference, rfq.trade_currency from quote inner join rfq on quote.rfq = rfq.rfq where rfq.quote_date > DATEADD(DAY, DATEDIFF(DAY, 0, getDate() - {0}), 0) and quote.part_number = '{1}'".format(length, part))
    data = [list(x) for x in cursor.fetchall()]

    for quote in data:
        try:
            cursor.execute("select quote_qty, total_price from quote_qty where quote like '%{0}%'".format(quote[0]))
            quote_data = [list(x) for x in cursor.fetchall()][0]
        except:
            quote_data = [0, 0]
            pass
        quote.extend(quote_data)

        if quote[9] == 2: #if currency is CAD do nothing
            pass
        elif quote[9] == 1: #if currency is USD convert to CAD
            quote[11] = Decimal(quote[11])*Decimal(1.3)

    quotes = {'quotes_per_week': 1, 'total_value': 0, 'total_win': 0, 'customers': [], 'customer_counts': {}, 'customer_total': {}, 'customer_wins': {}, 'quotes': []}

    for quote in data:
        quotes['quotes_per_week'] += quote[10]
        quotes['total_value'] += quote[11]

        if quote[3] == 'Won':
            quotes['total_win'] += quote[10]

        if quote[5] not in quotes['customers']:
            quotes['customers'].append(quote[5])
            quotes['customer_counts'][quote[5]] = 1
            quotes['customer_total'][quote[5]] = quote[11]
            if quote[3] == 'Won':
                quotes['customer_wins'][quote[5]] = 1
            else:
                quotes['customer_wins'][quote[5]] = 0
        else:
            quotes['customer_counts'][quote[5]] += 1
            quotes['customer_total'][quote[5]] += quote[11]
            if quote[3] == 'Won':
                quotes['customer_wins'][quote[5]] += 1

        quotes['quotes'].append({'part_number': quote[2], 'quantity': quote[10], 'total_price': Decimal(quote[11]), 'quote': quote[4], 'status': quote[3], 'quoted_by': quote[1], 'date': quote[7], 'reference': quote[8]})

    cursor.execute("select quote.quote, quote.rfq, cast(rfq.quote_date as date), rfq.trade_currency, quote.status from quote inner join rfq on quote.rfq = rfq.rfq where rfq.quote_date > DATEADD(DAY, DATEDIFF(DAY, 0, getDate() - 365), 0) and quote.part_number = '{0}'".format(part))
    data = [list(x) for x in cursor.fetchall()]

    quote_data = []
    for quote in data:
        quote.append(0)

        if quote[3] == 2: #if currency is CAD do nothing
            pass
        elif quote[3] == 1: #if currency is USD convert to CAD
            quote[5] = Decimal(quote[5])*Decimal(1.3)

        if quote[4] == 'Won':
            quote[4] = 1
        else:
            quote[4] = 0

        quote_data.append({'date': quote[2].strftime('%Y-%m-%d'), 'total_price': quote[5], 'status': quote[4]})

    data_json = json.dumps(quote_data, indent=2, default=str)
    chart_data = {'weekly_quotes': data_json}

    head = ['Quote', 'Date', 'Reference', 'Part Number', 'Quantity', 'Total Price', 'Status']
    return render_template('parts_quotes.html', customer = part, quotes = quotes, head = head, length = length, title = '{0} Quotes'.format(part), chart_data = chart_data)

@app.route("/job_progress")
def job_progress(name=None):
    if request.args.get('job'):
        job = request.args.get('job')
    else:
        return render_template('job_progress.html', job_details = {'job': 'Enter Job'})

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select status, part_number, order_quantity, customer_po, customer, ship_to, note_text, cast(order_date as date) from job where job = '{0}'".format(job))
    data = list(cursor.fetchall())
    if not data:
        return render_template('mobile_traveler.html', job_details = {'job': 'Invalid Job - Try Again'})

    data = [list(x) for x in data][0]

    job_details = {'job': job, 'status': data[0], 'part number': data[1], 'quantity': data[2], 'customer po': data[3], 'customer': data[4], 'ship to': data[5], 'note text': data[6], 'order date': data[7]}

    cursor.execute("select name, line1, line2, city, state, zip from address where address = '{0}'".format(job_details['ship to']))
    job_details['address'] = [x for x in cursor.fetchall()][0]

    cursor.execute("select cast(promised_date as date) from delivery where job = '{0}'".format(job))
    try:
        job_details['promised date'] = [list(x) for x in cursor.fetchall()][0][0]
    except:
        job_details['promised date'] = datetime.datetime.now().date().strftime('%Y-%m-%d')

    cursor.execute("select work_center, sequence from job_operation where job = '{0}' and job_operation.status = 'o'".format(job))
    data = [list(x) for x in cursor.fetchall()]
    if data == []:
        job_details['current wc'] = 'COMPLETE'
        progress = 9
    else:
        data.sort(key=itemgetter(1))
        job_details['current wc'] = data[0][0]
        if data[0][1] < 4:
            progress = 0
        else:
            progress = data[0][1]

    return render_template('job_progress.html', job_details = job_details, progress = progress)

@app.route('/shipping_list')
def shippinglist(name=None):
    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select priority, job, customer, customer_po, description, cast(order_date as date), order_quantity, part_number from job where status = 'active' and part_number not in ('1900', '1906', '1907')")
    data = [list(x) for x in cursor.fetchall()]

    shipping = []
    for job in data:
        cursor.execute("select work_center, sequence from job_operation where job = '{0}' and job_operation.status = 'o'".format(job[1]))
        job_data = [list(x) for x in cursor.fetchall()]
        job_data.sort(key=itemgetter(1))
        try:
            if job_data[0][0] == 'SHIPPING':
                job.append(job_data[0][0])
                shipping.append(job)
        except:
            continue

        job.append(' ')

    shipping.sort(key=itemgetter(0,5))

    head = ['Priority', 'Job Number', 'Customer', 'Customer PO', 'Description', 'Order Date', 'Order Quantity', 'Part Number', 'Work Center']
    return render_template('hot.html', rows = shipping, head = head, title = 'Shipping List')

@app.route("/update_mailer")
def update_mailer():
    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')

    cursor = connection.cursor()

    cursor.execute("select job.job, user_values.text3, user_values.note_text, job.open_operations, job.part_number, job.description, job.ext_description, job.order_quantity, job.customer_po, job.customer from user_values left join job on user_values.user_values = job.user_values left join change_history on job.job = change_history.job where job.user_values not like 'None' and user_values.text3 not like 'None' and user_values.note_text not like 'None' and change_history.change_type = '14' and change_history.change_date > DATEADD(HOUR, -1, GETDATE()) and change_history.new_text = 'C' and job.job not like '%-%'")
    query = [list(x) for x in cursor.fetchall()]

    data = []

    query.sort(key=itemgetter(0,3))
    i = 0
    while i < len(query)-1:
        if query[i][0] == query[i+1][0]:
            pass
        else:
            data.append(query[i])

        i = i + 1

    if query:
        data.append(query[-1])

    update_jobs = []

    for job in data:
        job[3] = int(job[3]) - 1
        if job[1].lower() == 'routing':
            cursor.execute("select work_center, sequence, operation_service from job_operation where job = '{0}' and job_operation.status = 'o'".format(job[0]))
            data = [list(x) for x in cursor.fetchall()]
            if data == []:
                job.append('COMPLETE')
                job.append(100)
            else:
                data.sort(key=itemgetter(1))
                if data[0][0] is None:
                    job.append(data[0][2])
                elif data[0][0] == 'TOYOKOKI':
                    job.append('BENDING')
                elif data[0][0] == 'PROGRAMMIN':
                    job.append('NESTING')
                elif data[0][0] == 'SHOP':
                    job.append('ASSEMBLY')
                else:
                    job.append(data[0][0])

                job.append(round((float(data[0][1])/float(data[-1][1]))*100))

            update_jobs.append(job)

        elif job[1].lower() == 'complete':
            cursor.execute("select work_center, sequence, operation_service from job_operation where job = '{0}' and job_operation.status = 'o'".format(job[0]))
            data = [list(x) for x in cursor.fetchall()]
            if data == []:
                job.append('COMPLETE')
                update_jobs.append(job)

    for job in update_jobs:
#        msg = Message("Order Update",
#            sender="no-reply@iconicmetalgear.com",
#            recipients=['colin@iconicmetalgear.com'])
        msg = Message("Order Update",
            sender="no-reply@iconicmetalgear.com",
            recipients=job[2].split(', '),
            bcc=['colin@iconicmetalgear.com'])

        msg.html = render_template('update_mailer.html', update_jobs = [job])
        try:
            mail.send(msg)
        except Exception, e:
            job[3] = str(e)

    return render_template('update_mailer.html', update_jobs = [update_jobs[0]])

@app.route("/update_viewer")
def update_viewer():
    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')

    cursor = connection.cursor()

    cursor.execute("select job.job, user_values.text3, user_values.note_text, job.open_operations from user_values left join job on user_values.user_values = job.user_values where job.user_values not like 'None' and user_values.text3 not like 'None' and user_values.note_text not like 'None' and job.job not like '%-%' and job.open_operations != 0")
    data = [list(x) for x in cursor.fetchall()]

    return render_template('update_viewer.html', rows = data, head = ['Job', 'Frequency', 'Mail To', 'Remaining Operations'], title = 'Update Viewer')

@app.route("/chart/long_orders") # Chart with weekly totals for Shipped, Ordered, and PO values. Also lines of best fit for each.
def ato():
    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select job.job, job.total_price, cast(job.order_date as date) from job where Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%' AND Job.Job Not Like '%-%' and job.order_date > DATEADD(day, DATEDIFF(day, 0, getDate() - 1460), 0)")
    query = [list(x) for x in cursor.fetchall()]
    weekly_hours_data = []
    for job in query:
        job.append(job[2].strftime('%d-%b-%y'))
        job[2] = job[2].strftime('%Y-%V')
        if not any(j['date'] == job[2] for j in weekly_hours_data):
            weekly_hours_data.append({'date': job[2], 'close': job[1], 'fdate': job[3]})
        else:
            for d in weekly_hours_data:
                if d['date'] == job[2]:
                    d['close'] += job[1]
    weekly_hours_data.sort(key=itemgetter('date'))

    prev = [0,0,0,0]
    for each in weekly_hours_data:
        prev.append(each['close'])
        each['sm_close'] = sum(prev)/5
        prev.pop(0)

    prev = []
    for each in weekly_hours_data:
        prev.append(each['close'])
        each['long_close'] = sum(prev)/len(prev)
        if len(prev) >= 20:
            prev.pop(0)
        each['date'] = each['fdate']
        del each['fdate']

    data = {}
    data['all_time_orders'] = json.dumps(weekly_hours_data, indent=2, default=str)
    return render_template('all_time_orders.html', data = data)

@app.route("/orders_report") # Chart with weekly totals for Shipped, Ordered, and PO values. Also lines of best fit for each.
def orders_report():
    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select cast(job.order_date as date), job.total_price, job.trade_currency from job where Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%' AND job.order_date > Dateadd(month, -1, getdate()) AND Job.Job Not Like '%-%' order by job.order_date asc")

    data = [list(x) for x in cursor.fetchall()]

    data_dict = []

    for each in data:
        try:
            if each[2] == 1: #if currency is USD convert to CAD
                each[1] = Decimal(each[1])*Decimal(1.34)
            else:
                pass
        except:
            pass
        each[0] = each[0].strftime('%d-%b-%y')
        if not any(j['date'] == each[0] for j in data_dict):
            data_dict.append({'date': each[0], 'value': each[1]})
        else:
            for d in data_dict:
                if d['date'] == each[0]:
                    d['value'] += each[1]

    prev = []
    for each in data_dict:
        prev.append(each['value'])
        each['sm_value'] = sum(prev)/len(prev)
        if len(prev) >= 10:
            prev.pop(0)

    chart_data = {}
    chart_data['orders'] = json.dumps(data_dict, indent=2, default=str)

    cursor.execute("select cast(packlist_header.packlist_date as date), packlist_detail.unit_price, packlist_detail.quantity, job.trade_currency from (packlist_header inner join packlist_detail on packlist_header.packlist = packlist_detail.packlist) left join job on packlist_detail.job = job.job where Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%' AND packlist_header.packlist_date > Dateadd(month, -1, getdate()) AND Job.Job Not Like '%-%' order by packlist_header.packlist_date asc")

    data = [list(x) for x in cursor.fetchall()]

    data_dict = []

    for each in data:
        try:
            if each[3] == 1: #if currency is USD convert to CAD
                each[1] = Decimal(each[1])*Decimal(1.34)
            else:
                pass
        except:
            pass
        price = round(each[1] * each[2], 2)
        each.append(price)
        each[0] = each[0].strftime('%d-%b-%y')
        if not any(j['date'] == each[0] for j in data_dict):
            data_dict.append({'date': each[0], 'value': each[-1]})
        else:
            for d in data_dict:
                if d['date'] == each[0]:
                    d['value'] += each[-1]

    prev = []
    for each in data_dict:
        prev.append(each['value'])
        each['sm_value'] = sum(prev)/len(prev)
        if len(prev) >= 10:
            prev.pop(0)

    chart_data['shipments'] = json.dumps(data_dict, indent=2, default=str)

    cursor.execute("select packlist_detail.unit_price, packlist_detail.quantity, job.trade_currency, job.customer, job.part_number, job.description, job.job, cast(job.order_date as date), cast(packlist_header.packlist_date as date) from (packlist_header inner join packlist_detail on packlist_header.packlist = packlist_detail.packlist) left join job on packlist_detail.job = job.job where Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%' AND packlist_header.packlist_date > Dateadd(week, -1, getdate()) AND Job.Job Not Like '%-%'")
    top_shipments = []
    data = [list(x) for x in cursor.fetchall()]
    for each in data:
        try:
            if each[2] == 1: #if currency is USD convert to CAD
                each[0] = Decimal(each[0])*Decimal(1.34)
            else:
                pass
        except:
            each[1] = 0
        lead_time = int((each[8] - each[7]).days)/7
        each.append(lead_time)
        price = round(each[0] * each[1], 2)
        top_shipments.append({'customer': each[3], 'part': each[4], 'description': each[5], 'price': price, 'job': each[6], 'quantity': each[1], 'lead': lead_time})

    top_shipments.sort(key=itemgetter('price'), reverse = True)
    chart_data['top_shipments'] = top_shipments[:4]

    cursor.execute("select job.total_price, job.order_quantity, job.trade_currency, job.customer, job.part_number, job.description, job.job, job.customer_po from job where Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%' AND job.order_date > Dateadd(week, -1, getdate()) AND Job.Job Not Like '%-%'")
    top_orders = []
    data = [list(x) for x in cursor.fetchall()]
    for each in data:
        try:
            if each[2] == 1: #if currency is USD convert to CAD
                each[0] = Decimal(each[0])*Decimal(1.34)
            else:
                pass
        except:
            pass
        price = round(each[0], 2)
        top_orders.append({'customer': each[3], 'part': each[4], 'description': each[5], 'price': price, 'job': each[6], 'quantity': each[1], 'po': each[7]})

    top_orders.sort(key=itemgetter('price'), reverse = True)
    chart_data['top_orders'] = top_orders[:4]

    cursor.execute("select cast(job.order_date as date), cast(packlist_header.packlist_date as date) from (packlist_header inner join packlist_detail on packlist_header.packlist = packlist_detail.packlist) left join job on packlist_detail.job = job.job where Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%' AND packlist_header.packlist_date > Dateadd(day, -30, getdate()) AND Job.Job Not Like '%-%'")
    data = [list(x) for x in cursor.fetchall()]
    lead_times = []
    for each in data:
        lead_time = int((each[1] - each[0]).days)
        if lead_time > 1: lead_times.append(lead_time)

    avg_lead_time = sum(lead_times)/len(lead_times)
    lead_times.sort()
    med_lead_time = lead_times[int(len(lead_times)/2)]
    max_lead_time = lead_times[-1]

    cursor.execute("select cast(job.order_date as date), cast(packlist_header.packlist_date as date) from (packlist_header inner join packlist_detail on packlist_header.packlist = packlist_detail.packlist) left join job on packlist_detail.job = job.job where Job.Customer Not Like '%GARAGESCAP%' And Job.Customer Not Like '%I-H%' AND packlist_header.packlist_date < Dateadd(day, -30, getdate()) AND Job.Job Not Like '%-%' and packlist_header.packlist_date > Dateadd(day, -60, getdate())")
    data = [list(x) for x in cursor.fetchall()]
    lead_times = []
    for each in data:
        lead_time = int((each[1] - each[0]).days)
        if lead_time > 1: lead_times.append(lead_time)

    prev_avg_lead_time = sum(lead_times)/len(lead_times)

    chart_data['avg_lead_time'] = avg_lead_time
    chart_data['prev_avg_lead_time'] = prev_avg_lead_time
    chart_data['med_lead_time'] = med_lead_time
    chart_data['max_lead_time'] = max_lead_time

    cursor.execute("select job, wc_vendor from change_history where change_date > Dateadd(day, -30, getdate()) and new_text = 'C'")
    return render_template('orders_report.html', data = chart_data)

@app.route('/reports/customer_sales')
def customer_sales_search(name=None):
    return render_template('customer_sales_search.html')

@app.route('/reports/customer_sales/<cust>/<length>')
def customer_sales(cust, length):
    if not cust:
        return render_template('customer_sales_search.html')

    if not length:
        length = 30

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select job, part_number, customer, cast(order_date as date), trade_currency, total_price from job where order_date > DATEADD(DAY, DATEDIFF(DAY, 0, getDate() - {0}), 0) and customer = '{1}' and job not like '%-%' order by order_date".format(length, cust))
    data = [list(x) for x in cursor.fetchall()]

    if not data:
        cursor.execute("select job, part_number, customer, cast(order_date as date), trade_currency, total_price from job where order_date > DATEADD(DAY, DATEDIFF(DAY, 0, getDate() - {0}), 0) and customer like '%{1}%' and job not like '%-%' order by order_date".format(length, cust))
        data = [list(x) for x in cursor.fetchall()]

    jobs = []
    delta = datetime.date.today() - data[0][3]
    for i in range(delta.days + 1):
        d = data[0][3] + datetime.timedelta(days=i)
        d = d.strftime('%d-%b-%y')
        jobs.append({'date': d, 'price': 0})

    for job in data:
        if job[4] == 2: #if currency is CAD do nothing
            pass
        elif job[4] == 1: #if currency is USD convert to CAD
            job[5] = round(Decimal(job[5])*Decimal(1.3), 2)
        job[3] = job[3].strftime('%d-%b-%y')
        if not any(j['date'] == job[3] for j in jobs):
            jobs.append({'date': job[3], 'price': job[5]})
        else:
            for d in jobs:
                if d['date'] == job[3]:
                    d['price'] += job[5]

    for job in jobs:
        job['price'] = str(job['price'])

    data_json = json.dumps(jobs, indent=2, default=str)
    chart_data = {'jobs': data_json}

    try:
        customer = data[0][2]
    except:
        customer = ''

    return render_template('customer_sales.html', customer = customer, length = length, title = '{0} Sales'.format(cust), chart_data = chart_data)


'''
@app.route("reports/orders/<cust>/<length>")
def customer_orders(cust):
    if not cust:
        return render_template('customer_orders.html')

    if not length:
        length = 30

    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')
    cursor = connection.cursor()

    cursor.execute("select job.job, job.part, job.")

@app.route("/sales_analytics")
def sales_analytics():
    connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};Server=192.168.2.157;DATABASE=Production;UID=support;PWD=lonestar;')

    cursor = connection.cursor()

    cursor.execute("select cast(order_date as date), total_price from job where Order_Date > Dateadd(Month, Datediff(Month, 0, DATEADD(m, -1, current_timestamp)), 0) and total_price > 0 and job not like '%-%' and customer not like 'I-H%'")
    job_data = [list(x) for x in cursor.fetchall()]

    cursor.execute("select cast(rfq.quote_date as date), quote_qty.total_price from (quote inner join rfq on quote.rfq = rfq.rfq) left join quote_qty on quote.quote = quote_qty.quote where rfq.quote_date > Dateadd(Month, Datediff(Month, 0, DATEADD(m, -1, current_timestamp)), 0)")
    quote_data = [list(x) for x in cursor.fetchall()]


    return render_template('sales_analytics.html', rows = data)
'''

if __name__ == '__main__':
    app.run()
