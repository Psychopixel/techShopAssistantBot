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
import time
from elevenlabs import generate, play, voices, set_api_key
from google.cloud import texttospeech
import simpleaudio as sa


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

def speakChat(text:str, voice:str)->bool:
    if DO_SPEAK==False:
        time.sleep(2)
        return True
    voice_type = config["TEXT_TO_SPEECH_TYPE"]
    if voice_type == "azure":
        result = speakAzure(voice=voice, text=text)
        return result
    elif voice_type == "eleven":
        eleven_api_key = config["ELEVEN_API_KEY"]
        set_api_key(eleven_api_key)
        playVoiceWithElevenlabs(voice, text)
        return True
    elif voice_type == "google":
        result = playVoiceWithGoogle(text, voice=voice)
        return result

def speak(text:str)->bool:
    if DO_SPEAK==False:
        time.sleep(2)
        return True
    voice_type = config["TEXT_TO_SPEECH_TYPE"]
    if voice_type == "azure":
        voice = "en-GB-OliviaNeural"
        result = speakAzure(voice=voice, text=text)
        return result
    elif voice_type == "eleven":
        eleven_api_key = config["ELEVEN_API_KEY"]
        set_api_key(eleven_api_key)
        agentVoice = voices()
        voice = "Sloane"
        playVoiceWithElevenlabs(voice, text)
        return True
    elif voice_type == "google":
        voice = "en-US-Standard-C"
        result = playVoiceWithGoogle(text, voice=voice)
        return result
        

def stopSpeak():
    voice_type = config["TEXT_TO_SPEECH_TYPE"]
    if voice_type=="azure":
        stopSpeakAzure()

#----------------------------------------------------------------------
# elevenlabs tts
def playVoiceWithElevenlabs(voice, text):
    audio = generate(
        text=text,
        voice=voice,
        model='eleven_multilingual_v1'
    )
    play(audio)


#----------------------------------------------------------------------
# google tts
def playVoiceWithGoogle(text, language="en-US", voice:str=""):
   
    # Instantiates a client
    client = texttospeech.TextToSpeechClient(client_options={"api_key": config["GOOGLE_APPLICATION_CREDENTIALS"], "quota_project_id": config["GOOGLE_PROJECT_ID"]})

    # Set the text input to be synthesized
    synthesis_input = texttospeech.SynthesisInput(text=text)

    # Build the voice request
    if(voice==""):
        return
    else:
        choose_voice = texttospeech.VoiceSelectionParams(
            language_code=language, name=voice
        )

    # Select the type of audio file you want returned
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )

    # Perform the text-to-speech request on the text input with the selected
    # voice parameters and audio file type
    response = client.synthesize_speech(
        input=synthesis_input, voice=choose_voice, audio_config=audio_config
    )
  
    wave_obj = sa.WaveObject(response.audio_content, 1, 2, 24000)
    play_obj = wave_obj.play()
    play_obj.wait_done()  # Wait until sound has finished playing

#---------------------------------------------------------------
# azure
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
    global speech_synthesizer
    speech_config = initAzureVoice()
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

def stopSpeakAzure():
    global speech_synthesizer
    if speech_synthesizer != "":
        speech_synthesizer.stop_speaking()