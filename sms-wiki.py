from flask import Flask, request, redirect, session, jsonify
import os, requests, math, wikipedia, random, json
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

import sys

SECRET_KEY = 'a secret key'
app = Flask(__name__)
app.config.from_object(__name__)

account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']
subaccount_sid = os.environ['TWILIO_SUBACCOUNT_SID']
master_client = Client(account_sid, auth_token)
client = Client(account_sid, auth_token, subaccount_sid)

TWILIO_MESSAGE_LENGTH = 153
NUMBER_OF_CHARS = 150 * 4
NUMBER_OF_CHARS_LIST = 450

GREETINGS = ['wiki', 'wikipedia', 'yo', 'yo!', 'hi', 'hi!', 'hello', 'hello!', 'hey', 'u up?', 'start']

NAV_DESCRIPTIONS = 	{
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

responded = False

@app.route("/", methods=['GET', 'POST'])
def hello_world():
	#debug

	print("os.environ['TWILIO_NUMBER']: ", os.environ['TWILIO_NUMBER'])

	#send_image("Barack Obama", "+16038092751")

	summary = wikipedia.summary("New York City", chars=1530)
	page = wikipedia.page("obama")
	#print("yo", sys.getsizeof(format_section_list(page.sections)))
	return page.html()
	#return page.section("Etymology")
	#return 'Hello, World!'

@app.route("/sms", methods=['GET', 'POST'])
def sms_reply():
	number = request.form['From']

	#page = session.get('page', '')
	global responded

	number = request.form['From']
	counter = session.get('counter', 0)
	counter += 1

	query = session.get('query', '')
	text = session.get('text', '')
	position = session.get('position', 0)
	state = session.get('state', '')
	options = session.get('options', ['random', 'wiki'])
	more_text = session.get('more_text', False)
	sections = session.get('sections', [])
	curr_section = session.get('curr_section', -1)
	more_in_list = session.get('more_in_list', False)
	#navigation = ""

	print("state before: ", state)

	incoming_msg = request.values.get('Body', None).lower()

	if incoming_msg == 'reset':
		print("clearing session")
		session.clear()
		print(session)
		return ('', 204)

	elif counter == 1 or incoming_msg in GREETINGS:
		send_message("Hello! I'm WikiBot.", number)
		print("Responded: " + str(responded))
		options = ['random', 'wiki']
		#state = 'init'

	elif "wiki " in incoming_msg or "wikipedia " in incoming_msg:

		if "wiki " in incoming_msg:
			query = incoming_msg.split("wiki ", 1)[1]
		else:
			query = incoming_msg.split("wikipedia ", 1)[1]

		try:
			send_message("Loading article '" + query + "' ...", number)
			page = wikipedia.page(query)
			# reset session vars
			query = page.title
			#send_image(query, number)
			text = page.summary
			position = 0
			#state = 'reading'
			sections = page.sections
			curr_section = 0

			(text, query, position, state,  more_text, options, sections, curr_section, number) = sendWikiText(text, query, position, state,  more_text, options, sections, curr_section, number)
			print("responded: " + str(responded))

		except wikipedia.exceptions.DisambiguationError as e:

			state = 'disambiguation'
			msg = "Did you mean:\n"		
			numOptionsPresented = min(10,len(e.options))

			for i in range(0, numOptionsPresented):
				msg += str(i+1) + ". " + e.options[i] + "\n"

			sections = e.options[:numOptionsPresented]

			options = ['disambiguation', 'random', 'wiki']
			send_message(msg, number)

		except wikipedia.exceptions.PageError:
			send_message("'{}' doesn't match any pages. Try another query!".format(query), number)
			state = 'init'

	elif incoming_msg == 'random':
			send_message("Loading random article ...", number)
			print("curr_section: ", curr_section)
			try:
				query = wikipedia.random()
				page = wikipedia.page(query)
			except wikipedia.exceptions.DisambiguationError as e:
				query = e.options[random.randint(0,1)]
				page = wikipedia.page(query)
			# reset session vars
			query = page.title
			text = page.summary
			position = 0
			#state = 'reading'
			sections = page.sections
			curr_section = 0

			(text, query, position, state,  more_text, options, sections, curr_section, number) = sendWikiText(text, query, position, state,  more_text, options, sections, curr_section, number)		

	#elif (state == 'reading' or state == 'section list' or state == 'disambiguation') \
	#and (incoming_msg == 'more' or incoming_msg == 'next' or 'sections' in incoming_msg or 'jump' in incoming_msg):
	#elif state == 'reading' and (incoming_msg == 'next' or incoming_msg == 'sections' or 'jump' in incoming_msg):
	#elif state == 'reading' or (incoming_msg == 'next' or incoming_msg == 'sections' or 'jump' in incoming_msg):
	if incoming_msg == 'more':
		if (state == 'reading'):
			if not more_text:
				send_message('You have reached the end of this section.', number)
				if curr_section == (len(sections)-1):
					options = ['sections', 'random', 'wiki']
				else:
					options = ['next', 'sections', 'random', 'wiki']
			else:
				if curr_section == 0 or curr_section == -1:
					section_report = query
				else:
					section_report = sections[curr_section]
				send_message("Loading next " + str(NUMBER_OF_CHARS) + " chars from '" + section_report + "' ...", number)
				(text, query, position, state,  more_text, options, sections, curr_section, number) = sendWikiText(text, query, position, state,  more_text, options, sections, curr_section, number)
		else: # section list or disambiguation
			if incoming_msg == 'more':
				if more_in_list:
					send_message("Loading more sections...")
					section_list = format_section_list(sections)
					section_list = section_list[len(section_list)//2:]
					for msg in section_list:
						send_message(msg, number)
					options = ['section number', 'random', 'wiki']
				else:
					send_message('There are no more sections.', number)


	elif incoming_msg == 'next':
		# check if there is a next section
		if curr_section == (len(sections)-1):
			send_message('There are no more sections.', number)
			options = ['']
		else:
			curr_section += 1
			send_message("Loading section '" + sections[curr_section] + "' ...", number)
			text = wikipedia.page(query).section(sections[curr_section])
			if (not text):
				curr_section += 1
				text = wikipedia.page(query).section(sections[curr_section])
			(text, query, position, state,  more_text, options, sections, curr_section, number) = sendWikiText(text, query, position, state,  more_text, options, sections, curr_section, number, reset_pos=True)

	elif incoming_msg == 'sections':

		state = 'section list'
		send_message("Loading list of sections...", number)
		list_page = 0

		section_list = format_section_list(sections)

		if len(section_list) > 2:
			section_list = section_list[:len(section_list)//2]
			more_in_list = True
		else:
			more_in_list = False

		for msg in section_list:
			send_message(msg, number)

		options = ['section number']
		if more_in_list:
			options.append('more sections')
		options.append('random')
		options.append('wiki')

	elif 'jump ' in incoming_msg:
		section_to_jump_to = incoming_msg.split("jump ", 1)[1]
		if section_to_jump_to.isnumeric():
			section_to_jump_to = int(section_to_jump_to) - 1 # offset shift from display
			if section_to_jump_to == 0:
				send_message("Loading article '" + query + "' ...", number)
				text = wikipedia.page(query).summary
				curr_section = section_to_jump_to
				(text, query, position, state,  more_text, options, sections, curr_section, number) = sendWikiText(text, query, position, state,  more_text, options, sections, curr_section, number, reset_pos=True)
			else:
				try:
					send_message("Loading section '" + sections[section_to_jump_to] + "' ...", number)
					text = wikipedia.page(query).section(sections[section_to_jump_to])
					while (not text):
						send_message(sections[section_to_jump_to].upper() + ": (subsection)\n", number)
						section_to_jump_to += 1
						text = wikipedia.page(query).section(sections[section_to_jump_to])
					curr_section = section_to_jump_to
					(text, query, position, state,  more_text, options, sections, curr_section, number) = sendWikiText(text, query, position, state,  more_text, options, sections, curr_section, number, reset_pos=True)
				except IndexError:
					send_message("There is no section " + str(section_to_jump_to), number)
					options = ['sections', 'random', 'wiki']
		else:
			try:
				sections_lower = [s.lower() for s in sections]
				curr_section = sections_lower.index(section_to_jump_to)
				send_message("Loading section '" + sections[curr_section] + "' ...", number)
				text = wikipedia.page(query).section(sections[curr_section])
				(text, query, position, state,  more_text, options, sections, curr_section, number) = sendWikiText(text, query, position, state,  more_text, options, sections, curr_section, number, reset_pos=True)
			except (ValueError, wikipedia.exceptions.PageError):
				send_message("There is no section " + section_to_jump_to, number)
				options = ['sections', 'random', 'wiki']		

	elif incoming_msg.isnumeric():
		if (state == "section list" or state == 'reading'):
			curr_section = int(incoming_msg) - 1
			send_message("Loading section '" + sections[curr_section] + "' ...", number)
			text = wikipedia.page(query).section(sections[curr_section])
			(text, query, position, state,  more_text, options, sections, curr_section, number) = sendWikiText(text, query, position, state,  more_text, options, sections, curr_section, number, reset_pos=True)
		elif(state == "disambiguation"):
			try:
				query = sections[int(incoming_msg) - 1] # offset display shift
				send_message("Loading article '" + query + "' ...", number)
				page = wikipedia.page(query)
				curr_section = 0
				sections = page.sections
				text = page.summary
				(text, query, position, state,  more_text, options, sections, curr_section, number) = sendWikiText(text, query, position, state,  more_text, options, sections, curr_section, number, reset_pos=True)
			except (IndexError, wikipedia.exceptions.PageError):
				send_message("There is no article #" + incoming_msg, number)			

	elif state == 'section list':
		
		incoming_msg.strip('jump ')

		# check for section by name
		try:
			sections_lower = [s.lower() for s in sections]
			curr_section = sections_lower.index(incoming_msg)
			send_message("Loading section " + sections[curr_section], number)
			text = wikipedia.page(query).section(sections[curr_section])
			(text, query, position, state,  more_text, options, sections, curr_section, number) = sendWikiText(text, query, position, state,  more_text, options, sections, curr_section, number, reset_pos=True)
		except (ValueError, wikipedia.exceptions.PageError):
			send_message("There is no section " + incoming_msg, number)
			options = ['sections', 'section number', 'random', 'wiki']				
	
	if not responded and incoming_msg not in GREETINGS:
		try:
			send_message("Loading article '" + incoming_msg + "' ...", number)
			page = wikipedia.page(incoming_msg)
			# reset session vars
			query = page.title
			#send_image(query, number)
			text = page.summary
			position = 0
			#state = 'reading'
			sections = page.sections
			curr_section = 0

			(text, query, position, state,  more_text, options, sections, curr_section, number) = sendWikiText(text, query, position, state,  more_text, options, sections, curr_section, number)
		except wikipedia.exceptions.DisambiguationError as e:

			state = 'disambiguation'
			msg = "Did you mean:\n"		
			numOptionsPresented = min(10,len(e.options))

			for i in range(0, numOptionsPresented):
				msg += str(i+1) + ". " + e.options[i] + "\n"

			sections = e.options[:numOptionsPresented]

			msg += "\nType the number, and I'll find the article."
			send_message(msg, number)
		except:
			send_message("Sorry, I'm having trouble understanding :/", number)
		finally:
			print("STATE: " + state)
			if state != 'reading':
				options = ['random', 'wiki']

	print("position: " + str(position))

	# update session
	if options == ['']:
		options = ['random', 'wiki']

	navigation = "\n"
	for keyword in options:
		if keyword == 'next':
			if (curr_section != (len(sections)-1)):
				navigation += NAV_DESCRIPTIONS[keyword] + '("' + sections[curr_section + 1] + '")' + '\n\n'
			else:
				navigation += "There are no more sections in this article."
		elif keyword == 'more':
			navigation += NAV_DESCRIPTIONS[keyword] + " (" + str(len(text) - position) + " chars left)" + '\n\n'
		else:
			navigation += NAV_DESCRIPTIONS[keyword] + '\n\n'

	send_message(navigation, number) # resp.message() is noticeably slower than using send_message() and returning 204: No Content
	session['counter'] = counter
	session['query'] = query
	session['text'] = text
	session['position'] = position
	session['state'] = state
	session['options'] = options
	session['more_text'] = more_text
	session['sections'] = sections
	session['curr_section'] = curr_section
	session['more_in_list'] = more_in_list

	#print(session.get('state'))
	#print(session.get('position'))
	resp = MessagingResponse()
	return (str(resp), 200)

@app.route("/error", methods=['GET', 'POST'])
def sms_reply_error():
    resp = MessagingResponse()
    resp.message("Sorry, I'm having some issues on my end; I promise to fix them as soon as I can!")
    return str(resp)

@app.route("/suspend", methods=['GET', 'POST'])
def suspend_account():
	resp = MessagingResponse()
	resp.message("Suspending myself for now -- I'm sending too many messages. Sorry :/")
	account = master_client.api.accounts(subaccount_sid).update(status='suspended')
	return str(resp)

@app.route("/fixed_loop", methods=['GET', 'POST'])
def reactivate_account():
	resp = MessagingResponse()
	resp.message("Fixed the problem -- WikiBot is now reactivated and at your service!")
	account = master_client.api.accounts(subaccount_sid).update(status='active')
	return str(resp)


''' helpers: '''

def sendWikiText(text, query, position, state,  more_text, options, sections, curr_section, number, reset_pos = False):
	
	options = []
	more_sections = (curr_section != (len(sections)-1))

	if reset_pos:
		position = 0

	msg = ""

	if position == 0:
		if curr_section == 0:
			msg += query.upper() + ":\n\n"
		else:
			msg += sections[curr_section].upper() + ":\n\n"

	last_period = sys.maxsize
	print("len(text): ", len(text))
	if (position + NUMBER_OF_CHARS) >= len(text):
		more_text = False
		msg += text[position:] + "\n [end of section]"
	else:
		more_text = True
		options.append('more')
		last_period = text.rfind(".", position, position+NUMBER_OF_CHARS) + 1 #msg += text[position:(position+NUMBER_OF_CHARS)] + "\n..."
		msg += text[position:last_period] + "\n[...]"

	send_message(msg, number)
	position += min(NUMBER_OF_CHARS, last_period)
	#position += NUMBER_OF_CHARS

	if more_sections:
		options.append('next')

	options.append('sections')
	options.append('random')
	options.append('wiki')

	state = 'reading'
	global responded
	responded = True

	return (text, query, position, state,  more_text, options, sections, curr_section, number)

def send_message(m, number):
	client.messages.create(
	    from_=os.environ['TWILIO_NUMBER'],
	    body=m,
	    to=number)
	    #to="+16038092751")
	global responded
	responded = True

def send_image(title, number):
    url = 'https://en.wikipedia.org/w/api.php'
    data = {
        'action' :'query',
        'format' : 'json',
        'formatversion' : 2,
        'prop' : 'pageimages|pageterms',
        'piprop' : 'thumbnail',
        #'pithumbsize': 50,
        'titles' : title
    }
    response = requests.get(url, data)
    json_data = json.loads(response.text)
    #print(str(json_data))
    if len(json_data['query']['pages']) > 0:
    	image_url = json_data['query']['pages'][0]['thumbnail']['source']
    	print(image_url)
    	
    	client.messages.create(
    		from_=os.environ['TWILIO_NUMBER'],
    		body =image_url,
    		media_url=image_url,
    		to=number)
    else:
    	print("image not found")


    #return json_data['query']['pages'][0]['original']['source'] if len(json_data['query']['pages']) >0 else 'Not found'

def format_section_list(sections):

	total_chars = sum(len(s) for s in sections)
	formatted = []
	text = ''
	for i in range(len(sections)):
		label = str(i+1) + ". " + sections[i] + "\n"
		if (len(text) + len(label)) > NUMBER_OF_CHARS_LIST-4: # for '\n...'
			text += '... ({} more)'.format(len(sections)-i+1)
			formatted.append(text)
			text = ''
		text += label
	formatted.append(text)
	return formatted

if __name__ == "__main__":
    app.run(debug=True)
