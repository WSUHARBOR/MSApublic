import update
update.check_for_dependency_update()
update.perform_database_migration()

# Normal imports come after the dependency check
from typing import Optional
import logging
import os
import platform

from flask import Flask, request, jsonify, Response

import data_logging
from gps import gps_receiver
from sensors import sensor_receiver
import download


STATIC_FOLDER = os.environ.get('WEB_STATIC', '../web/build')
app = Flask(__name__,
            static_url_path='',
            static_folder=STATIC_FOLDER)


@app.route('/')
@app.route('/data')
def root():
    return app.send_static_file('index.html')


@app.route('/api/v1/status')
def get_status():
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
    _, is_collecting = sensor_receiver.get_recording_state()
    status = {
        'is_collecting': is_collecting
    }
    if is_collecting:
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
    hostname = platform.node()
    return jsonify({
        'hostname': hostname,
    })


@app.route('/api/v1/start', methods=['POST'])
def start_recording():
    description: Optional[str] = request.json.get('description')
    logging.info(f"Starting recording with description={description}")
    collection_id = data_logging.start_collection(description)
    if collection_id == -1:
        return "Failed to startup", 503
    return str(collection_id), 200


@app.route('/api/v1/stop', methods=['POST'])
def stop_recording():
    collection_id = data_logging.stop_collection()
    if collection_id == -1:
        return "Failed to shut down", 503
    return str(collection_id), 200


@app.route('/api/v1/list_collections')
def list_collections():
    return jsonify({'data': data_logging.get_collection_list()})


@app.route('/api/v1/collection/<int:collection_id>/details')
def get_collection_details(collection_id: int):
    return jsonify(data_logging.get_collection_details(collection_id))


@app.route('/api/v1/collection/<int:collection_id>/download')
def download_collection_file(collection_id: int):
    collection_name = download.get_collection_name_from_id(collection_id)
    response = Response(download.download_collection_data(collection_name), mimetype='text/csv')
    response.headers['Content-Disposition'] = f"attachment; filename={collection_name}.csv"
    return response


@app.route('/api/v1/download_all')
def download_all():
    raise NotImplemented


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="[%(asctime)s] %(levelname)s - %(message)s")
    gps_receiver.start()
    sensor_receiver.start()
    data_logging.recorder.start()
    app.run(host="0.0.0.0", port=8080, threaded=True)