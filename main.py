import json
import requests
from base64 import b64encode
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for
import mux_python
import string
import random  # define the random module

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'

db = SQLAlchemy(app)


class LiveStream(db.Model):
    __tablename__ = 'livestream'
    id = db.Column('id', db.Integer, primary_key=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    live_stream_id = db.Column(db.String(200))  # Mux ID
    play_back_id = db.Column(db.String(200))
    stream_key = db.Column(db.String(200))
    simulcasts = db.relationship('Simulcast', cascade="all,delete", backref='livestream', lazy=True)

    def __init__(self, live_stream_id, play_back_id, stream_key):
        self.live_stream_id = live_stream_id
        self.play_back_id = play_back_id
        self.stream_key = stream_key


class Simulcast(db.Model):
    __tablename__ = 'simulcast'
    id = db.Column('id', db.Integer, primary_key=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    simulcast_id = db.Column(db.String(200))  # Mux ID
    url = db.Column(db.String(200))
    stream_key = db.Column(db.String(200))
    livestream_id = db.Column(db.Integer, db.ForeignKey('livestream.id'), nullable=False)

    def __init__(self, simulcast_id, url, stream_key, livestream_id):
        self.simulcast_id = simulcast_id
        self.url = url
        self.stream_key = stream_key
        self.livestream_id = livestream_id


# Development
# MUX_TOKEN_ID = '9cd0c460-23d8-4de1-9ee3-a6fd6dabb826'
# MUX_SECRET_KEY = 'prtPtRcn1/RrA7OqsrBPlru5T1/b72DSzl70sSlvi8MUKDK/fcgfZhPlV62eZhKVyF7DmQqXpEp'

# Production
MUX_TOKEN_ID = '9c4e0783-6410-4614-b578-91cac6f02241'
MUX_SECRET_KEY = '9fxqcgpBbe2+5lxeI8D07SfuJp5PlNx0PtbJhOTFuvYnk6vmPSToWKNg7xrTwbB2vOnrtQ7Z6gV'

configuration = mux_python.Configuration()
configuration.username = MUX_TOKEN_ID
configuration.password = MUX_SECRET_KEY


@app.route('/create_database')
def create_database():
    db.create_all()
    return redirect(url_for('all_stream'))


@app.route('/stream')
def start_stream():
    # Create a Live Stream Object
    live_api = mux_python.LiveStreamsApi(mux_python.ApiClient(configuration))
    new_asset_settings = mux_python.CreateAssetRequest(playback_policy=[mux_python.PlaybackPolicy.PUBLIC])
    create_live_stream_request = mux_python.CreateLiveStreamRequest(playback_policy=[mux_python.PlaybackPolicy.PUBLIC],
                                                                    new_asset_settings=new_asset_settings)
    create_live_stream_response = live_api.create_live_stream(create_live_stream_request)
    stream_object = LiveStream(live_stream_id=create_live_stream_response.data.id,
                               play_back_id=create_live_stream_response.data.playback_ids[0].id,
                               stream_key=create_live_stream_response.data.stream_key)
    db.session.add(stream_object)
    db.session.commit()
    return redirect(url_for('all_stream'))


@app.route('/simulcast', methods=['POST'])
def create_simulcast():
    url = request.form.get('url')
    stream_key = request.form.get('stream_key')
    live_stream_id = request.form.get('live_stream_id')

    live_stream_obj = LiveStream.query.filter_by(id=live_stream_id).first()
    mux_livestream_id = live_stream_obj.live_stream_id

    # Create a Simulcast Object

    keys = "{}:{}".format(MUX_TOKEN_ID, MUX_SECRET_KEY)
    auth_hash = b64encode(str.encode(keys)).decode("ascii")
    mux_url = "https://api.mux.com/video/v1/live-streams/" + mux_livestream_id + "/simulcast-targets"
    payload = {
        "url": url,
        "stream_key": stream_key,
        "passthrough": "nice"
    }
    payload = json.dumps(payload)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + auth_hash
    }
    response = requests.post(url=mux_url, data=payload, headers=headers)
    print('MUX Simulcast Response: ', response.text)

    S = 10  # number of characters in the string.
    # call random.choices() string module to find the string in Uppercase + numeric data.
    ran = ''.join(random.choices(string.ascii_uppercase + string.digits, k=S))
    ran2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=S))

    # if response.status_code == 201:

    obj = Simulcast(simulcast_id=str(ran), url=url, livestream_id=live_stream_id, stream_key=str(ran2))
    db.session.add(obj)
    db.session.commit()
    return redirect(url_for('all_stream'))


@app.route('/delete_simulcast/<id>')
def delete_simulcast(id):

    obj = Simulcast.query.filter_by(id=id).first()
    print('Simulcast Mux ID to delete : '+obj.simulcast_id )
    mux_livestream_id=obj.livestream.live_stream_id
    print('LiveStream Mux ID connected : ' + mux_livestream_id)

    # Delete a Simulcast Object

    keys = "{}:{}".format(MUX_TOKEN_ID, MUX_SECRET_KEY)
    auth_hash = b64encode(str.encode(keys)).decode("ascii")
    mux_url = "https://api.mux.com/video/v1/live-streams/" + mux_livestream_id + "/simulcast-targets/" + obj.simulcast_id
    payload = {}
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + auth_hash
    }
    response = requests.delete(url=mux_url, data=payload, headers=headers)
    print('MUX Simulcast Response: ', response.text)

    if response.status_code == 204:
        db.session.delete(obj)
        db.session.commit()
    else:
        db.session.delete(obj)
        db.session.commit()

    return redirect(url_for('all_stream'))


@app.route('/play_stream/<playback_id>')
def play_stream(playback_id):
    id = LiveStream.query.filter_by(play_back_id=playback_id).first()

    return render_template('player.html', PLAYBACK_ID=playback_id, id=id)


@app.route('/delete_stream/<id>')
def delete_stream(id):

    keys = "{}:{}".format(MUX_TOKEN_ID, MUX_SECRET_KEY)
    auth_hash = b64encode(str.encode(keys)).decode("ascii")

    url = "https://api.mux.com/video/v1/live-streams/" + id
    payload = {}
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + auth_hash
    }
    response = requests.request("DELETE", url, headers=headers, data=payload)
    if response.status_code == 204:
        obj = LiveStream.query.filter_by(live_stream_id=id).first()
        db.session.delete(obj)
        db.session.commit()

        return redirect(url_for('all_stream'))
    else:
        obj = LiveStream.query.filter_by(live_stream_id=id).first()
        db.session.delete(obj)
        db.session.commit()

        return redirect(url_for('all_stream'))


@app.route('/')
def all_stream():
    livestreams = LiveStream.query.all()
    simulcasts = Simulcast.query.all()
    return render_template('index.html', livestreams=livestreams, simulcasts=simulcasts)


if __name__ == "__main__":
    app.run(debug=True)
