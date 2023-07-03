import openai
import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import SpeechConfig
import wave
from io import BytesIO
import io
import os
import sys
import pyaudio
import time
import sqlalchemy as db
import json
from PIL import Image as PilImage
from threading import Timer
from dotenv import dotenv_values, find_dotenv, load_dotenv
import PySimpleGUI as sg
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)  # for exponential backoff 
import asyncio
import robAiUtility

#----------------------------------------------------------------
# decorator per gestire l'asincronicità di una funzione
def background(f):
    def wrapped(*args, **kwargs):
        return asyncio.get_event_loop().run_in_executor(None, f, *args, **kwargs)
    return wrapped


# Define a function to open a file and return its contents as a string
def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()

# Define a function to save content to a file
def save_file(filepath, content):
    with open(filepath, 'a', encoding='utf-8') as outfile:
        outfile.write(content)

#define a function to remove a file
def remove_file(filepath):
    try:
        os.remove(filepath)
        #print("Il file è stato cancellato con successo.")
    except FileNotFoundError:
        print("Errore: Il file "+filepath+" non è stato trovato.")
    except PermissionError:
        print("Errore: Non hai i permessi per cancellare il file " + filepath)
    except Exception as e:
        print("Errore: Si è verificato un errore:", e)

#----------------------------------------------------------------
# inizia la registrazione dell'audio in modo asincrono
@background
def startRecording():
    global recording
    global user_stream
    global p
    global frames
    global bot
   
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
   

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def completion_with_backoff(**kwargs):
    return openai.Completion.create(**kwargs)


def initAzureVoice():
    # Creates an instance of a speech config with specified subscription key and service region.
    # Replace with your own subscription key and service region (e.g., "westus").
    
    os.environ["COGNITIVE_SERVICE_KEY"]=config["AZURE_ISABELLA_KEY"]
    speech_key, service_region = config["AZURE_ISABELLA_KEY"], config["AZURE_SPEECH_REGION"]
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    # Creates a speech synthesizer using the default speaker as audio output.
    
    return speech_config


def speakAzure(speech_config:SpeechConfig ,voice:str="en-GB-OliviaNeural", text:str="", debug:bool=False)->bool:
    if DO_SPEAK==False:
        return
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



#----------------------------------------------------------------
# aggiorno la chat log
def updateScreen(chat):
    lastMsg = chat[len(chat)-1]
    if lastMsg["agent"] == "Bot":
        simulate_typing(lastMsg["text"], 'cyan', chunk_size=5, delay=0.02)
    if lastMsg["agent"] == "User":
        window['-AGENT-CHATLOG-'].print(lastMsg["text"], text_color='yellow', end='')
    window['-AGENT-CHATLOG-'].update()

#----------------------------------------------------------------
# scrive nella chat log simulando la digitazione tipo macchina da scrivere
def simulate_typing(text,  color, chunk_size=5, delay=0.1):
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i+chunk_size]
        window['-AGENT-CHATLOG-'].print(chunk, text_color=color, end='')
        window['-AGENT-CHATLOG-'].update()
        time.sleep(delay)
    window['-AGENT-CHATLOG-'].print('\n', text_color=color, end='')

#----------------------------------------------------------------
# qui vanno le cose da fare prima di chiudere il programma
def beforeExit():
    global running
    running = False
    p.terminate()
    rt.stop()

#----------------------------------------------------------------
# chiude l'esecuzione del programma e la finestra
def closeProgram():
    rt.stop() # better in a try/finally block to make sure the program ends!
    beforeExit()
    window.close()


#----------------------------------------------------------------
# nasconde il campo di input e il bottone enter mentre l'azione
# è al bot
def hideUserInput():
    global window
    window['-USER_INPUT-'].update('')
    window.find_element('-USER_INPUT-').Update(disabled=True)
    window.find_element('-ENTER-').Update(disabled=True)
    window['-REC-'].update(image_filename='gui/mic_icon_disabled.png', image_subsample=2)
    window.Refresh()

def switchButtonImage():
    global buttonImage
    if(buttonImage==1):
        window['-REC-'].update(image_filename='gui/mic_icon_on2.png', image_subsample=2)
        buttonImage = 2
    else:
        window['-REC-'].update(image_filename='gui/mic_icon_on.png', image_subsample=2)
        buttonImage = 1
    window.Refresh()


#----------------------------------------------------------------
# mostra il campo di input e il bottone enter mentre l'azione
# è all'utente
def showUserInput():
    global window
    global buttonImage
    window['-USER_INPUT-'].update('')
    window.find_element('-USER_INPUT-').Update(disabled=False)
    window.find_element('-ENTER-').Update(disabled=False)
    window.find_element('-REC-').Update(disabled=False)
    window['-REC-'].update(image_filename='gui/mic_icon_off.png', image_subsample=2)
    buttonImage = 1
    window.Refresh()

#----------------------------------------------------------------
# gestione dell'input utente
def collect_messages(user_input, debug=False):
    global bot
    global stream
    global speech_config
    if debug: print(f"User Input = {user_input}")
    if user_input == "":
        return
    global context
    response, context = process_user_message(user_input, context, debug=False)
    context.append({'role':'assistant', 'content':f"{response}"})
    print ("Response: "+ response)
    chat_row ={"agent":"Bot", "text":response+"\n"}
    result = speakAzure(speech_config, "en-GB-OliviaNeural", str(response))
    chat.append(chat_row)
    updateScreen(chat)
    bot = False
    showUserInput()

#----------------------------------------------------------------
# gestione dell'input utente
def process_user_message(user_input, all_messages, debug=False):
    delimiter = "```"
    
    # Step 1: Check input to see if it flags the Moderation API or is a prompt injection
    if debug: print("step1")
    response = openai.Moderation.create(input=user_input) 
    moderation_output = response["results"][0]

    if moderation_output["flagged"]:
        if debug: print("Step 1: Input flagged by Moderation API.")
        return "Sorry, we cannot process this request."

    if debug: print("Step 1: Input passed moderation check.")
    
    category_and_product_response = find_category_and_product_only(user_input)
    
    # Step 2: Extract the list of products
    category_and_product_list = robAiUtility.read_string_to_list(category_and_product_response)
    if debug: print("category_and_product_list:\n" + str(category_and_product_list))

    if debug: print("Step 2: Extracted list of products.")

    # Step 3: If products are found, look them up
    product_information = generate_output_string(category_and_product_list)
    if product_information == "":
        neg_str = "Product not found! I'm unable to provide the information you're looking for. I'll connect you with a human representative for further assistance."
        return neg_str, all_messages
    if debug: print("Step 3: Looked up product information.")

    # Step 4: Answer the user question
    system_message = f"""
    You are a customer service assistant for a large electronic store. \
    Respond in a friendly and helpful tone, with concise answers. \
    Make sure to ask the user relevant follow-up questions.
    """
    messages = [
        {'role': 'system', 'content': system_message},
        {'role': 'user', 'content': f"{delimiter}{user_input}{delimiter}"},
        {'role': 'assistant', 'content': f"Relevant product information:\n{product_information}"}
    ]

    final_response = robAiUtility.get_completion_from_messages(all_messages + messages)
    if debug:print("Step 4: Generated response to user question.")
    all_messages = all_messages + messages[1:]

    # Step 5: Put the answer through the Moderation API
    response = openai.Moderation.create(input=final_response)
    moderation_output = response["results"][0]

    if moderation_output["flagged"]:
        if debug: print("Step 5: Response flagged by Moderation API.")
        return "Sorry, we cannot provide this information."

    if debug: print("Step 5: Response passed moderation check.")

    # Step 6: Ask the model if the response answers the initial user query well
    user_message = f"""
    Customer message: {delimiter}{user_input}{delimiter}
    Agent response: {delimiter}{final_response}{delimiter}

    Does the response sufficiently answer the question?
    """
    messages = [
        {'role': 'system', 'content': system_message},
        {'role': 'user', 'content': user_message}
    ]
    evaluation_response = robAiUtility.get_completion_from_messages(messages)
    if debug: print("Step 6: Model evaluated the response.")

    # Step 7: If yes, use this answer; if not, say that you will connect the user to a human
    if "Y" in evaluation_response:  # Using "in" instead of "==" to be safer for model output variation (e.g., "Y." or "Yes")
        if debug: print("Step 7: Model approved the response.")
        return final_response, all_messages
    else:
        if debug: print("Step 7: Model disapproved the response.")
        neg_str = "I'm unable to provide the information you're looking for. I'll connect you with a human representative for further assistance."
        return neg_str, all_messages

#----------------------------------------------------------------
# crea una stringa con tutte le categorie e i relativi prodotti
# questo serve all'AI a capire quali sono i prodotti venduti
# +++ bisogna capire come fare quando i prodotti sono molti +++
def get_allowed_products():
    allowed_products = ''
    # Crea la query per trovare i prodotti di ogni categoria
    query = db.select(category_tb.c.description, db.func.group_concat(product_tb.c.name, '§').label('products')).select_from(
        category_tb.join(product_tb, product_tb.c.category_id == category_tb.c.id_category)
    ).group_by(category_tb.c.description)

    with engine.connect() as connection:
        result = connection.execute(query)
        for row in result:
            allowed_products += row[0] + ':\n'
            p_list = row[1].split('§')
            for p in p_list:
                allowed_products += p + '\n'
            allowed_products += '\n'
    return allowed_products

#----------------------------------------------------------------
# prende una list di categorie e la trasforma in una lista
# +++ forse bastava str? +++
def get_category(category_list):
    category = ''
    for i in range(len(category_list)):
        category += category_list[i]
        if (i<len(category_list)-1):
            category += ','
    return category

#----------------------------------------------------------------
# legge dal db la lista delle categorie e tramite la funzione
# get_category crea una stringa con tutte le categorie
def get_category_from_db():
    category_list = []
    query = db.select(category_tb.c.description)
    with engine.connect() as connection:
        result = connection.execute(query)
        for row in result:
            category_list.append(row[0])
    category = get_category(category_list)
    return category

def get_product_by_category_name(category_name):
    query = db.select(product_tb.c.name).select_from(product_tb.join(category_tb, product_tb.c.category_id == category_tb.c.id_category)).where(category_tb.c.description == category_name)
    with engine.connect() as connection:
        result = connection.execute(query)
    product_list = []
    for row in result:
        product_list.append(row[0])
    return product_list

def get_product_by_name(name):
    info = get_product_info_by_name(name)

    return info

#----------------------------------------------------------------
# usa chatgpt per capire quali sono i prodotti e/o le categorie
# che interessano al cliente
def get_products_from_query(user_msg):

    delimiter = "####"
    system_message = f"""
    You will be provided with customer service queries. \
    The customer service query will be delimited with {delimiter} characters.
    Output a python list of json objects, where each object has the following format:
        'category': <one of {get_category_from_db()}>,
    OR
        'products': <a list of products that must be found in the allowed products below>

    Where the categories and products must be found in the customer service query.
    If a product is mentioned, it must be associated with the correct category in the allowed products list below.
    if only a category is mentioned, you should output a a python dictonary which key is the category whith a list of all products in that category.
    If no products or categories are found, output an empty list.

    The allowed products are provided in JSON format.
    The keys of each item represent the category.
    The values of each item is a list of products that are within that category.
    Allowed products: {get_allowed_products()}

    """
    
    messages =  [  
    {'role':'system', 'content': system_message},    
    {'role':'user', 'content': f"{delimiter}{user_msg}{delimiter}"},  
    ] 
    category_and_product_response = robAiUtility.get_completion_from_messages(messages)
       
    return robAiUtility.read_string_to_list(category_and_product_response)

#----------------------------------------------------------------
# legge dal db la descrizione di un brand con un certo id_brand
def get_brand_description(brand_id):
    query = db.select(brand_tb.c.description).select_from(brand_tb).where(brand_tb.c.id_brand == brand_id)
    with engine.connect() as connection:
        result = connection.execute(query)
        row = result.first()
        if not(row is None):
            return row[0]
        else:
            return None
#----------------------------------------------------------------
# legge dal db la descrizione di una categoria con un certo id_category
def get_category_description(category_id):
    query = db.select(category_tb.c.description).select_from(category_tb).where(category_tb.c.id_category == category_id)
    with engine.connect() as connection:
        result = connection.execute(query)
        row = result.first()
        if not(row is None):
            return row[0]
        else:
            return None

#----------------------------------------------------------------
# legge sul db quale sono le feature di un certo prodotto
# partendo con un id_product, restituisce una lista
def get_feature_for_product(product_id):
    # Query
    features = []
    query = db.select(features_tb.c.description).select_from(product_tb.join(product_feature_tb, product_tb.c.id_product == product_feature_tb.c.product_id).join(features_tb, product_feature_tb.c.feature_id == features_tb.c.id_feature)).where(product_tb.c.id_product == product_id)
    # Execute the query
    with engine.connect() as connection:
        result = connection.execute(query)
        for row in result:
            features.append(row[0])
    return features

#----------------------------------------------------------------
# legge sul db quali immagini sono collegate ad un certo prodotto
# partendo con un id_product, restituisce una lista
def get_images_for_product(product_id):
    # Query
    images_list = []
    query = db.select(images_tb.c.name, images_tb.c.caption, images_tb.c.id_image).select_from(product_tb.join(product_image_tb, product_tb.c.id_product == product_image_tb.c.product_id).join(images_tb, product_image_tb.c.image_id == images_tb.c.id_image)).where(product_tb.c.id_product == product_id)
    # Execute the query
    with engine.connect() as connection:
        result = connection.execute(query)
        for row in result:
            image = {}
            image["name"] = row[0]
            if not(row[1] == None):
                image["caption"] = row[1]
            else:
                image["caption"] = ''
            image["id_image"] = row[2]
            images_list.append(image)
    return images_list

#----------------------------------------------------------------
# legge dal db una immagine e la restituisce in formato PIL
def read_image_from_db(image_id):
    try:
        # Eseguire la query sul database
        query = db.select(images_tb).where(images_tb.columns.id_image == image_id)
        ResultProxy = connection.execute(query)
        ResultSet = ResultProxy.fetchall()
    except Exception as e:
        print(f"Error executing query: {e}")
        return

    if not ResultSet:
        print(f"No image found with id {image_id}")
        return

    image = ResultSet[0][1]

    try:
        # Creare un oggetto PIL Image dai dati dell'immagine
        pil_image = PilImage.open(io.BytesIO(image))
    except IOError as e:
        print(f"Error creating PIL Image: {e}")
        return
    return pil_image

#----------------------------------------------------------------
# carica tutte le informazioni relative ad un certo prodotto dal db
# a partire dal nome del prodotto stesso
def get_product_info_by_name(name):
    product_info = {}
    # Crea la query
    query = db.select(
        product_tb.c.name,
        product_tb.c.description,
        product_tb.c.model_number,
        product_tb.c.warranty,
        product_tb.c.rating,
        product_tb.c.price,
        product_tb.c.category_id,
        product_tb.c.brand_id,
        product_tb.c.id_product,
        ).select_from(product_tb).where(product_tb.c.name == name)
    with engine.connect() as connection:
        result = connection.execute(query)
        row = result.first()
        if not(row is None):
            product_info["name"] = row[0]
            product_info["description"] = row[1]
            product_info["model_number"] = row[2]
            product_info["warranty"] = row[3]
            product_info["rating"] = str(row[4])
            product_info["price"] = "$"+str(row[5])
            product_info["category"] = get_category_description(row[6])
            product_info["brand"] = get_brand_description(row[7])
            product_info["features"] = get_feature_for_product(row[8])
            product_info["images"] = get_images_for_product(row[8])

    return product_info


def find_category_and_product_only(user_input):
    delimiter = "####"
    system_message = f"""
    You will be provided with customer service queries. \
    The customer service query will be delimited with {delimiter} characters.
    Output a python list of objects, where each object has the following format:
    'category': <one of {get_category_from_db()}>,
    OR
    'products': <a list of products that must be found in the allowed products below>

    Where the categories and products must be found in the customer service query.
    If a product is mentioned, it must be associated with the correct category in the allowed products list below.
    If no products or categories are found, output an empty list.

    Allowed products: 
    {get_allowed_products()}
    
    Only output the list of objects, nothing else.
    """
    messages =  [  
    {'role':'system', 'content': system_message},    
    {'role':'user', 'content': f"{delimiter}{user_input}{delimiter}"},  
    ] 
    return robAiUtility.get_completion_from_messages(messages)

def get_products_from_query(user_msg):
    delimiter = "####"
    system_message = f"""
    You will be provided with customer service queries. \
    The customer service query will be delimited with {delimiter} characters.
    Output a python list of json objects, where each object has the following format:
        'category': <one of {get_category_from_db()}>,
    OR
        'products': <a list of products that must be found in the allowed products below>

    Where the categories and products must be found in the customer service query.
    If a product is mentioned, it must be associated with the correct category in the allowed products list below.
    If no products or categories are found, output an empty list.

    The allowed products are provided in JSON format.
    The keys of each item represent the category.
    The values of each item is a list of products that are within that category.
    Allowed products: {get_allowed_products()}

    """
    
    messages =  [  
    {'role':'system', 'content': system_message},    
    {'role':'user', 'content': f"{delimiter}{user_msg}{delimiter}"},  
    ] 
    category_and_product_response = robAiUtility.get_completion_from_messages(messages)
    
    return category_and_product_response


def generate_output_string(data_list):
    output_string = ""

    if data_list is None:
        return output_string

    for data in data_list:
        try:
            if "products" in data:
                if type(data) is dict:
                    products_list = data["products"]
                else:
                    pass
                for product_name in products_list:
                    product = get_product_by_name(product_name)
                    if product:
                        output_string += json.dumps(product, indent=4) + "\n"
                    else:
                        print(f"Error: Product '{product_name}' not found")
            elif "category" in data:
                if type(data) is dict:
                    category_name = data['category']
                else:
                    category_name = data_list["category"]
                category_products = get_product_by_category_name(category_name)
                for product in category_products:
                    output_string += json.dumps(product, indent=4) + "\n"
            else:
                print("Error: Invalid object format")
        except Exception as e:
            print(f"Error: {e}")

    return output_string


#----------------------------------------------------------------
# classe che gestisce il main loop del programma
class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False

#----------------------------------------------------------------
#logica di funzionamento del programma
def logic():
    global running
    global chat
    global bot
    global firstMessage
    global speech_config
    if running:
        return
    else:
        running = True
    if firstMessage:
        text_input = "Welcome to our store! We have a large assortment of computers, cameras and televisions. How can I help you?"
        chat_row ={"agent":"Bot", "text":text_input+"\n"}
        chat.append(chat_row)
        updateScreen(chat)
        showUserInput()
        firstMessage = False
        bot = False
        running = True
        result = speakAzure(speech_config, "en-GB-OliviaNeural", text_input)
    

#----------------------------------------------------------------
# MAIN
#----------------------------------------------------------------
bot = True
firstMessage = True
buttonPressed = False
buttonImage = 1
recording = False

# Record Some audio
MAX_REC_TIME = 60
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
DO_SPEAK=True

p = pyaudio.PyAudio()
frames = []
stream = ''
user_stream = ''
shop_agent_voice = "en-GB-OliviaNeural"

global config
if (find_dotenv()==""):
    print("File Configurazione mancante")
    sys.exit(1)

config = dotenv_values(find_dotenv())
openai.api_key = config["OPENAI_API_KEY"]
  
speech_config = initAzureVoice()
#----------------------------------------------------------------
# inizialize db

engine = db.create_engine("sqlite+pysqlite:///products.db")
connection = engine.connect()
metadata = db.MetaData()
product_tb = db.Table('product', metadata,  autoload_with=engine)
category_tb = db.Table('category', metadata,  autoload_with=engine)
brand_tb = db.Table('brand', metadata,  autoload_with=engine)
features_tb = db.Table('features', metadata,  autoload_with=engine)
product_feature_tb = db.Table('product_feature', metadata,  autoload_with=engine)
product_image_tb = db.Table('product_image', metadata, autoload_with=engine)
images_tb = db.Table('images', metadata, autoload_with=engine)

#----------------------------------------------------------------
#list containg the conversation
chat=[]
context = [ {'role':'system', 'content':"You are Tech Shop Customer Service Assistant"} ] 
# create interface
sg.theme('DarkGrey15')

header_row = [[sg.Image(source="gui/logo150x150.png", pad=(10,10)),sg.Text('Roberto Scordino', font=('Arial 15')),
               sg.Push()], [sg.Push(), sg.Text('Shop Bot Project', pad=30, text_color="#ebb806"), sg.Push()]]



agent_chat_column = [[sg.Push(),sg.Text('AGENTS CHAT LOG', font=('Arial 17'), text_color="#ebb806", pad = 10),sg.Push()],
                     [sg.Push(),sg.Multiline(font=('Arial, 10'),size=(200,15),autoscroll = True, disabled=True, write_only=True, key="-AGENT-CHATLOG-"),sg.Push()],
                     [sg.Push(),sg.Input(font=('Arial 10'), text_color="#ffff00", background_color="#333", pad=10, size=(194,3), key="-USER_INPUT-", do_not_clear=False, disabled_readonly_background_color="#333"),
                       sg.Button('Enter', font=('Arial 10'), auto_size_button=True, pad=10, key="-ENTER-", bind_return_key=True),
                       sg.Button('', image_filename='gui/mic_icon_off.png', image_subsample=2, key='-REC-', button_color=(sg.theme_background_color(), sg.theme_background_color()), border_width=0, pad=10),sg.Push()]]

layout = [  header_row, agent_chat_column,
            [sg.Push(),sg.Button('Exit', pad=30)] ]

window = sg.Window('The Shop Bot Project', layout, grab_anywhere=False, no_titlebar=True, margins=(0, 0), element_padding=(0, 0),
            location=(0,0), size=(sg.Window.get_screen_size()), 
            keep_on_top=False, font='_ 25', finalize=True, return_keyboard_events=True)
window.maximize()
window.bind("<Control-KeyPress-Delete>", "CTRL-Delete")
window.bind("<Control-KeyPress-period>", "CTRL-Delete")

button = window['-REC-']
button.bind('<ButtonPress>', " Press", propagate=False)
button.bind('<ButtonRelease>', " Release", propagate=False)


hideUserInput()

#----------------------------------------------------------------
# start the loop of program logic
running = False
rt = RepeatedTimer(1, logic) # it auto-starts, no need of rt.start()
rt.start()

#----------------------------------------------------------------
# interface loop
loop = True
#count = 0
while loop:  # Event Loop
    event, values = window.read(timeout=100)
    if event == sg.WIN_CLOSED:
        closeProgram()
        loop = False
    elif event != "__TIMEOUT__":
        #print("event: " + event)
        if event in (sg.WIN_CLOSED, 'Exit'):
            closeProgram()
            loop = False
        elif event == sg.WIN_CLOSED or event == 'Exit':
            closeProgram()
            loop = False
        elif event == 'Escape:27':
            closeProgram()
            loop = False
        elif event == 'CTRL-Delete':
            closeProgram()
            loop = False
        elif event == '-ENTER-':
            text_input = values['-USER_INPUT-']
            if(text_input!=''):
                window['-USER_INPUT-'].update('')
                chat_row ={"agent":"User", "text":text_input+"\n\n"}
                chat.append(chat_row)
                updateScreen(chat)
                hideUserInput()
                collect_messages(text_input, debug=False)
        elif event == '-REC- Press':
            if(bot==False):
                recording = True
                startRecording()
                buttonPressed = True
                window['-REC-'].update(image_filename='gui/mic_icon_on.png', image_subsample=2)
                window.Refresh()
        elif event == '-REC- Release':
            recording = False
            buttonPressed = False
            window['-REC-'].update(image_filename='gui/mic_icon_off.png', image_subsample=2)
            window.Refresh()
            userText = stopRecording()["text"]
            if(userText!=''):
                window['-USER_INPUT-'].update('')
                chat_row ={"agent":"User", "text":userText+"\n\n"}
                chat.append(chat_row)
                updateScreen(chat)
                hideUserInput()
                collect_messages(userText, debug=False)
            
    else:
        if(buttonPressed):
            switchButtonImage()
        
    if event == 'Word':
        window['-AGENT-CHATLOG-'].widget.config(wrap='word')
    elif event == 'None':
        window['-AGENT-CHATLOG-'].widget.config(wrap='none')