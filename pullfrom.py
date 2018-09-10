import pyodbc

from flask import Flask
from flask import render_template
app = Flask(__name__)

connection = pyodbc.connect(r'DRIVER={ODBC Driver 13 for SQL Server};SERVER=192.168.2.110;DATABASE=Production;UID=support;PWD=lonestar;')
	
cursor = connection.cursor()
cursor.execute("select t1.job, t1.customer, t1.description, t1.order_date, t1.order_quantity, t1.part_number, t2.customer, t2.job, t2.order_quantity, delivery.remaining_quantity from ((select job.job, job.customer, job.description, job.order_date, job.order_quantity, job.part_number, job_operation.floor_notes, job.status from job inner join job_operation on job.job = job_operation.job where job_operation.work_center like '%pull from%' and job.status = 'active' and job_operation.status = 'o') t1 left join (select job.job, job.customer, job.description, job.order_date, job.order_quantity, job.part_number, job.status from job where job.customer = 'i-h prod' and job.status = 'active' and job.job not like '%-%' and job.part_number <> '0202') t2 on t1.part_number = t2.part_number) left join delivery on t2.job = delivery.job")

rows = cursor.fetchall()

@app.route("/")
def pullfrom(name=None):
	return render_template('generic_table.html', rows=rows)