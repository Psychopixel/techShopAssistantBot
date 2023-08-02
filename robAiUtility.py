version="<!#FV> 0.0.1 </#FV>"
import os
import openai
import tiktoken
import json 
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)  # for exponential backoff



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


def read_string_to_list(input_string):
    if input_string is None:
        return []

    try:
        input_string = input_string.replace("'", "\"")  # Replace single quotes with double quotes for valid JSON
        data = json.loads(input_string)
        return data
    except json.JSONDecodeError:
        print("Error: Invalid JSON string")
        return []  
    


def get_completion(prompt, model="gpt-3.5-turbo"):
    messages = [{"role": "user", "content": prompt}]
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=0,
    )
    return response.choices[0].message["content"]

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def chatCompletion_with_backoff(**kwargs):
    return openai.ChatCompletion.create(**kwargs)

def get_completion_from_messages(messages, 
                                model="gpt-3.5-turbo", 
                                temperature=0, 
                                max_tokens=500):
    
    response = chatCompletion_with_backoff(
        model=model,
        messages=messages,
        temperature=temperature, # this is the degree of randomness of the model's output
        max_tokens=max_tokens, # the maximum number of tokens the model can ouptut 
    )

    return response.choices[0].message["content"]


def get_completion_and_token_count(messages, 
                                model="gpt-3.5-turbo", 
                                temperature=0, 
                                max_tokens=500):
    
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=temperature, 
        max_tokens=max_tokens,
    )
    
    content = response.choices[0].message["content"]
    
    token_dict = {
    'prompt_tokens':response['usage']['prompt_tokens'],
    'completion_tokens':response['usage']['completion_tokens'],
    'total_tokens':response['usage']['total_tokens'],
        }

    return content, token_dict

