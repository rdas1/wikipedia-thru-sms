from flask import Flask, request
import wikipediaapi
import os
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from textwrap import wrap
import CONSTANTS

app = Flask(__name__)

wiki_wiki = wikipediaapi.Wikipedia(language='en', extract_format=wikipediaapi.ExtractFormat.WIKI)

#TWILIO_ACCOUNT_SID = "" #os.environ['TWILIO_ACCOUNT_SID']
#TWILIO_AUTH_TOKEN = os.environ['TWILIO_AUTH_TOKEN']
TWILIO_CLIENT = Client(CONSTANTS.TWILIO_ACCOUNT_SID, CONSTANTS.TWILIO_AUTH_TOKEN)

TWILIO_MESSAGE_LENGTH = 153
NUMBER_OF_CHARS = 150 * 4
NUMBER_OF_CHARS_LIST = 450

GREETINGS = ['wiki', 'wikipedia', 'yo', 'yo!', 'hi', 'hi!', 'hello', 'hello!', 'hey', 'u up?', 'start']

NAV_DESCRIPTIONS =     {
    "wiki" : "Type 'wiki ____' to search Wikipedia, e.g. 'wiki barack obama'.",
    "more" : "Type 'more' to read more from this section.",
    "next" : "Type 'next' to read the next section in this article ",
    "sections" : "Type 'sections' to get a list of the sections in this article.\nIf you know the section name or number, you can jump there directly by typing 'jump _____'.",
    "section number": "Type the section number to jump to that section.",
    "more sections" : "Type 'more' to see more sections",
    "article number": "Type the article number to load that article.",
    "disambiguation": "Type the number, and I'll find the article.",
     "random": "Type 'random' to get a random Wikipedia article.",
}

def send_message(m, number):
	TWILIO_CLIENT.messages.create(
	    from_= CONSTANTS.TWILIO_NUMBER, #os.environ['TWILIO_NUMBER'], # note: if number changes, just update PythonAnywhere environment variable
	    body=m,
	    to=number)

@app.route('/')
def hello_world():
    page = wiki_wiki.page('Barack_Obama')
    return f'{page.text[:100]}'

@app.route('/sms', methods=['GET', 'POST'])
def sms_reply():
    number = request.form['From']

    #counter = session.get("counter", 0)
    #counter += 1

    incoming_msg = request.values.get('Body', None).lower()
    outgoing_msg = "To learn about some topic X, text me 'wiki X' without quotes, and I'll fetch you info about that topic. E.g., you could text me 'wiki ice cream'"
    if "wiki " in incoming_msg:
        query = incoming_msg.split("wiki ")[1]
        page = wiki_wiki.page(query)
        if page.exists():
            send_message("Loading article...", number)
            outgoing_msg = page.summary[:800]
            if len(page.summary) > 800:
                outgoing_msg += "..." # LATER: implement message sectioning
        else:
            outgoing_msg = f"There is no Wikipedia page for {query}. Try some other topic, e.g. 'wiki cheesecake'"
    send_message(outgoing_msg, number)
    resp = MessagingResponse()
    return (str(resp), 200)

