import update
update.check_for_dependency_update()
update.perform_database_migration()

# Normal imports come after the dependency check
from typing import Optional
import logging
import os
import platform

from flask import Flask, request, jsonify, Response
from werkzeug import serving

import data_logging
from gps import gps_receiver
from sensors import sensor_receiver
import download

parent_log_request = serving.WSGIRequestHandler.log_request


def log_request(self, *args, **kwargs):
    if self.path in ['/api/v1/status', '/api/v1/live_sensors', '/api/v1/msa_status']:
        return

    parent_log_request(self, *args, **kwargs)


serving.WSGIRequestHandler.log_request = log_request

# Load the filepath for the web resources from the environment variable $WEB_STATIC
STATIC_FOLDER = os.environ.get('WEB_STATIC', '../web/build')

# Construct a Flask web service that automatically serves result from the static folder
app = Flask(__name__,
            static_url_path='',
            static_folder=STATIC_FOLDER)


@app.route('/')
@app.route('/data')
def root():
    """Serve the web root file for all user-facing web addresses"""
    return app.send_static_file('index.html')


@app.route('/api/v1/status')
def get_status():
    """Describe the current status of the data logger"""
    _, is_collecting = data_logging.recorder.get_recording_state()
    status = {
        'is_collecting': is_collecting
    }
    if is_collecting:
        status['elapsed_s'] = data_logging.recorder.get_elapsed_s()
        status['datapoints'] = data_logging.recorder.get_datapoints()
    return jsonify(status)


@app.route('/api/v1/live_sensors')
def get_live_sensors():
    """If data logging, return the latest instantaneous value from the sensors"""
    _, is_collecting = sensor_receiver.get_recording_state()
    status = {
        'is_collecting': is_collecting
    }
    if is_collecting:
        # Only populate sensor values if data is up to date
        raw_sensors, latency_s = sensor_receiver.get_current_status()
        if latency_s > 60:
            status['is_collecting'] = False
        else:
            status['sensors'] = [
                {
                    'name': s.name,
                    'value': s.value,
                    'unit': s.unit,
                }
                for s in raw_sensors
            ]
            status['latency_s'] = latency_s
    return jsonify(status)


@app.route('/api/v1/msa_status')
def get_health():
    """Provide information about the MSA service itself"""
    hostname = platform.node()
    return jsonify({
        'hostname': hostname,
    })


@app.route('/api/v1/start', methods=['POST'])
def start_recording():
    """Start a recording session with an optional session description string"""
    description: Optional[str] = request.json.get('description')
    logging.info(f"Starting recording with description={description}")
    collection_id = data_logging.start_collection(description)
    if collection_id == -1:
        return "Failed to startup", 503
    return str(collection_id), 200


@app.route('/api/v1/stop', methods=['POST'])
def stop_recording():
    """Stop the current recording session"""
    collection_id = data_logging.stop_collection()
    if collection_id == -1:
        return "Failed to shut down", 503
    return str(collection_id), 200


@app.route('/api/v1/list_collections')
def list_collections():
    """List all known collections and high level metadata about each collection"""
    return jsonify({'data': data_logging.get_collection_list()})


@app.route('/api/v1/collection/<int:collection_id>/details')
def get_collection_details(collection_id: int):
    """Return detailed metadata and sensor values from a specific collection"""
    return jsonify(data_logging.get_collection_details(collection_id))


@app.route('/api/v1/collection/<int:collection_id>/download')
def download_collection_file(collection_id: int):
    """Download a collection csv file to the user"""
    collection_name = download.get_collection_name_from_id(collection_id)
    response = Response(download.download_collection_data(collection_name), mimetype='text/csv')
    # Name the file that will be emitted to the user
    response.headers['Content-Disposition'] = f"attachment; filename={collection_name}.csv"
    return response


@app.route('/api/v1/download_all')
def download_all():
    raise NotImplemented


if __name__ == '__main__':
    # Configure logging to contain debug messages (this can be turned down later)
    logging.basicConfig(level=logging.DEBUG, format="[%(asctime)s] %(levelname)s - %(message)s")
    # Start the GPS receiver service process
    gps_receiver.start()
    # Start the Winsen sensor service process
    sensor_receiver.start()
    # Start the Data Logger service process. Must be started AFTER the GPS and sensor services
    data_logging.recorder.start()
    # Start the Flask development web server
    app.run(host="0.0.0.0", port=8080, threaded=True)