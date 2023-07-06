import wave
import pyaudio
import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import SpeechConfig
import os
import sys
from dotenv import dotenv_values, find_dotenv, load_dotenv
import openai
import asyncio
from threading import Timer, Thread
import threading


MAX_REC_TIME = 60
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
DO_SPEAK=True

def init():
# Record Some audio
    global frames
    global p
    global user_stream
    global config
    global speech_config
    global recording
    recording = False
    frames = []
    user_stream = ''

    if (find_dotenv()==""):
        print("File Configurazione mancante")
        sys.exit(1)
    config = dotenv_values(find_dotenv())
    speech_config = initAzureVoice()

def background(f):
    '''
    a threading decorator
    use @background above the function you want to run in the background
    '''
    def bg_f(*a, **kw):
        threading.Thread(target=f, args=a, kwargs=kw).start()
    return bg_f

#----------------------------------------------------------------
# inizia la registrazione dell'audio in modo asincrono
@background
def startRecording():
    global recording
    global user_stream
    global p
    global frames
    global bot
    recording = True
    p = pyaudio.PyAudio()
    user_stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    frames = []

    for i in range(0, int(RATE / CHUNK * MAX_REC_TIME)):
        if(recording==True):
            data = user_stream.read(CHUNK)
            frames.append(data)
        else:
            break
    if(recording):
        recording = False
    bot = True
    

#----------------------------------------------------------------
# ferma la registrazione e ritorna la trascrizione dell'audio
def stopRecording():
    global recording
    global user_stream
    global p
    global frames
    global bot
    recording = False
    user_stream.stop_stream()
    user_stream.close()


    wf=wave.open('output.wav', "wb")
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    try:
        audio_file = open("output.wav", "rb")
    except:
        print("Something went wrong")
        return ''
    else:
        print("Nothing went wrong")
    response={}
    response["text"] = ""
    try:
        response = openai.Audio.transcribe(
            model="whisper-1",
            file=audio_file
        )
    except:
        print("Something went wrong")
        return ''
    else:
        print("Nothing went wrong")
    bot = True
    #chat_row ={"agent":"User", "text":response["text"]+"\n\n"}
    #chat.append(chat_row)
    #updateScreen(chat)
    recording = False
    p.terminate()
    return response
    
#----------------------------------------------------------------
def record_audio(seconds: int, output_path = "output.wav"):
    p = pyaudio.PyAudio()
    user_stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    frames = []
    for i in range(0, int(RATE / CHUNK * seconds)):
        data = user_stream.read(CHUNK)
        frames.append(data)
    p.terminate()

def initAzureVoice():
    # Creates an instance of a speech config with specified subscription key and service region.
    # Replace with your own subscription key and service region (e.g., "westus").
    global config
    global speech_config
    os.environ["COGNITIVE_SERVICE_KEY"]=config["AZURE_ISABELLA_KEY"]
    speech_key, service_region = config["AZURE_ISABELLA_KEY"], config["AZURE_SPEECH_REGION"]
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    # Creates a speech synthesizer using the default speaker as audio output.
    
    return speech_config


def speakAzure(voice:str="en-GB-OliviaNeural", text:str="", debug:bool=False)->bool:
    if DO_SPEAK==False:
        return
    global speech_config
    # Set the voice name, refer to https://aka.ms/speech/voices/neural for full list.
    speech_config.speech_synthesis_voice_name = voice
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
    #result = speech_synthesizer.speak_text_async(text).get()
    result = speech_synthesizer.speak_text(text)
    # Checks result.
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        if debug:
            print("Speech synthesized to speaker for text [{}]".format(text))
        return True
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        if debug:
            print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            if cancellation_details.error_details:
                if debug:
                    print("Error details: {}".format(cancellation_details.error_details))
        if debug:
            print("Did you update the subscription info?")
        return False

