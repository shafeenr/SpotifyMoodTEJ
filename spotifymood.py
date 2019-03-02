import os
import sys
import requests
import webbrowser
import pyaudio
import wave
import json
from json.decoder import JSONDecodeError
import spotipy
import spotipy.util as util
import cognitive_face as CF
import speech_recognition as sr
from os import path
import time
import subprocess
from picamera import PiCamera
import cloudinary
from cloudinary.api import delete_resources_by_tag, resources_by_tag
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url

class TextToSpeech(object):
    def __init__(self, subscription_key):
        self.subscription_key = subscription_key
        self.access_token = None

    def get_token(self):
        fetch_token_url = "https://eastus.api.cognitive.microsoft.com/sts/v1.0/issuetoken"
        headers = {
            'Ocp-Apim-Subscription-Key': self.subscription_key
        }
        response = requests.post(fetch_token_url, headers=headers)
        self.access_token = str(response.text)

    def audio(self, text):
        base_url = 'https://eastus.tts.speech.microsoft.com/'
        path = 'cognitiveservices/v1'
        constructed_url = base_url + path
        headers = {
            'Authorization': 'Bearer ' + self.access_token,
            'Content-Type': 'application/ssml+xml',
            'X-Microsoft-OutputFormat': 'riff-24khz-16bit-mono-pcm',
            'User-Agent': 'SpotifySpeech',
            'cache-control': 'no-cache'
        }
        body = "<speak version='1.0' xml:lang='en-US'><voice xml:lang='en-US' xml:gender='Female' name='Microsoft Server Speech Text to Speech Voice (en-US, JessaNeural)'>" + \
            text + "</voice></speak>"

        response = requests.post(constructed_url, headers=headers, data=body)
        if response.status_code == 200:
            fn = 'responsetts.wav'
            with open(fn, 'wb') as audio:
                audio.write(response.content)
                print("\nStatus code: " + str(response.status_code) +
                      "\nYour TTS is ready for playback.\n")
            self.play_audio(fn)
        else:
            print("\nStatus code: " + str(response.status_code) +
                  "\nSomething went wrong. Check your subscription key and headers.\n")

    def play_audio(self, filename):
        CHUNK_SIZE = 1024
        file = wave.open(r"%s" % filename, "rb")
        p = pyaudio.PyAudio()
        stream = p.open(format=p.get_format_from_width(file.getsampwidth()),
                        channels=file.getnchannels(),
                        rate=file.getframerate(),
                        output=True)

        data = file.readframes(CHUNK_SIZE)

        while data != b'':
            stream.write(data)
            data = file.readframes(CHUNK_SIZE)

        stream.stop_stream()
        stream.close()
        p.terminate()


class SpeechToText(object):
    def __init__(self, subscription_key):
        self.subscription_key = subscription_key

    def get_text(self, duration):
        r = sr.Recognizer()
        os.system("arecord --device=plughw:2,0 -d " + duration + " speech.wav")

        with sr.AudioFile(path.join(path.dirname(path.realpath(__file__)), "speech.wav")) as source:
            audio = r.record(source)
            print("Got it! Now to recognize it...")
        try:
            value = r.recognize_bing(audio, key=self.subscription_key)
            return value
        except sr.UnknownValueError:
            print("Oops! Didn't catch that")
        except sr.RequestError as e:
            print(
                "Uh oh! Couldn't request results from Google Speech Recognition service; {0}".format(e))


class FaceAnalysis(object):
    def __init__(self, key, baseurl="https://canadacentral.api.cognitive.microsoft.com/face/v1.0/"):
        CF.Key.set(key)
        CF.BaseUrl.set(baseurl)

    def analyze(self, imageUrl="https://raw.githubusercontent.com/Microsoft/Cognitive-Face-Windows/master/Data/detection1.jpg"):
        faces = CF.face.detect(imageUrl, attributes="emotion")
        faces = [
            ('anger', faces[0]['faceAttributes']['emotion']['anger']),
            ('contempt', faces[0]['faceAttributes']['emotion']['contempt']),
            ('disgust', faces[0]['faceAttributes']['emotion']['disgust']),
            ('fear', faces[0]['faceAttributes']['emotion']['fear']),
            ('happiness', faces[0]['faceAttributes']['emotion']['happiness']),
            ('neutral', faces[0]['faceAttributes']['emotion']['neutral']),
            ('sadness', faces[0]['faceAttributes']['emotion']['sadness']),
            ('surprise', faces[0]['faceAttributes']['emotion']['surprise'])
        ]
        return sorted(faces, key=lambda faces: faces[1], reverse=True)


class SentimentAnalysis(object):
    def __init__(self, subscription_key):
        self.subscription_key = subscription_key

    def get_mood(self, text):
        url = 'https://canadacentral.api.cognitive.microsoft.com/text/analytics/v2.0/sentiment'
        headers = {
            'Content-Type': 'application/json',
            'Ocp-Apim-Subscription-Key': self.subscription_key
        }
        body = {
            "documents": [
                {"language": "en", "id": "1", "text": text}
            ]
        }

        response = requests.post(url, headers=headers, data=json.dumps(body))
        if response.status_code == 200:
            r = response.json()
            return r["documents"][0]["score"]
        else:
            return -1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("PROVIDE EITHER face OR speech AS ARG")
        sys.exit()
    elif sys.argv[1] == "face":
        tts = TextToSpeech("")
        tts.get_token()
        
        camera = PiCamera()
        camera.resolution = (1024, 768)
        camera.start_preview()
        time.sleep(2)
        camera.capture('capture.jpg')
        p = subprocess.Popen(["display", "capture.jpg", "-size", "1024x768"])
        time.sleep(5)
        p.kill()
        cloudpic = cloudinary.uploader.upload("capture.jpg")
        cloudpic = cloudpic["url"]
        print(cloudpic)
        
        face = FaceAnalysis("")
        faceResult = face.analyze(imageUrl=cloudpic)
        faceResult = faceResult[0][0]

        if faceResult == "happiness" or faceResult == "surprise":
            tts.audio("You look happy!")
        else:
            tts.audio("You look sad!")
        username = ""
        scope = "playlist-read-collaborative playlist-read-private user-library-read streaming app-remote-control user-read-playback-state user-modify-playback-state user-read-currently-playing"
        try:
            token = util.prompt_for_user_token(username, scope, "",
                                               "", "http://localhost/")  # add scope
        except (AttributeError, JSONDecodeError):
            os.remove(".cache-%s" % username)
            token = util.prompt_for_user_token(username, scope)  # add scope

        spotifyObject = spotipy.Spotify(auth=token)
        spotifyObject.shuffle(True)

        if faceResult == "happiness" or faceResult == "surprise":
            spotifyObject.start_playback(
                context_uri="spotify:user::playlist:")
        else:
            spotifyObject.start_playback(
                context_uri="spotify:user::playlist:")
        spotifyObject.shuffle(False)
        spotifyObject.next_track()
        spotifyObject.shuffle(True)

        time.sleep(2)

        full = spotifyObject.current_playback()
        artist = full["item"]["artists"][0]["name"]
        track = full["item"]["name"]
        tts.audio("Now Playing " + track + " by " + artist)
    elif sys.argv[1] == "speech":
        tts = TextToSpeech("")
        tts.get_token()

        text = SpeechToText("")
        tts.audio("Speak now")
        sst = text.get_text("6")
        
        tts.audio("I think you said" + sst)
        
        textanalysis = SentimentAnalysis("")
        num = textanalysis.get_mood(sst)

        if num <= 0.5:
            tts.audio("You sound sad.")
        elif num == -1:
            tts.audio("Error")
        else:
            tts.audio("You sound happy.")

        username = ""
        scope = "playlist-read-collaborative playlist-read-private user-library-read streaming app-remote-control user-read-playback-state user-modify-playback-state user-read-currently-playing"
        try:
            token = util.prompt_for_user_token(username, scope, "",
                                               "", "http://localhost/")  # add scope
        except (AttributeError, JSONDecodeError):
            os.remove(".cache-%s" % username)
            token = util.prompt_for_user_token(username, scope)  # add scope

        spotifyObject = spotipy.Spotify(auth=token)
        spotifyObject.shuffle(True)

        if num <= 0.5:
            spotifyObject.start_playback(
                context_uri="spotify:user::playlist:")
        else:
            spotifyObject.start_playback(
                context_uri="spotify:user::playlist:")
        spotifyObject.shuffle(False)
        spotifyObject.next_track()
        spotifyObject.shuffle(True)

        time.sleep(2)

        full = spotifyObject.current_playback()
        artist = full["item"]["artists"][0]["name"]
        track = full["item"]["name"]
        tts.audio("Now Playing " + track + " by " + artist)