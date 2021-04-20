from flask import Flask, render_template, send_file
import os
import miniMSA_Version2 as MSA
import shutil

app = Flask(__name__)



@app.route("/")
def index():
	return render_template('index.html')

@app.route('/run')
def run_MSA():
	print('Running MSA python script')
	print(MSA.stop)
	MSA.MT = 0 
	MSA.stop = False
	#path = "/home/pi/Desktop/MSA_Webpage/miniMSA_Version2.py"
	print(MSA.stop)
	

	return MSA.run()

@app.route('/stop')
def stop_msa():
	#f = open("STOP.txt", "x")
	#f.close()
	print(MSA.stop)
	MSA.stop = True
	print(MSA.stop)

	
	
	return render_template('index.html')
	
@app.route('/download')
def download():
	MSADATA = "MSADATA"
	DATA = "/home/pi/Desktop/MSA_Webpage/DATA"
	shutil.make_archive(MSADATA, 'zip', DATA)
	path = "MSADATA.zip"
	download = send_file(path, as_attachment=True)
	
	return download

	
	


	
if  __name__ == "__main__":
	app.run(host="0.0.0.0", port=8080, debug=True)
