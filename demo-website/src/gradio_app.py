import os
import django
import gradio as gr

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from mindframe.models import TreatmentSession, CustomUser, RoleChoices

def initialize_chat():
    # todo - this should be passed in rather than looked up here?
    session = TreatmentSession.objects.first()
    print(session.pk)
    # prepopulate history from existing turns in this session
    history = []
    for turn in session.turns.all().order_by('timestamp'):
        role = "assistant" if turn.speaker.role == RoleChoices.BOT else "user"
        if role == "user":
            history.append((turn.text, ""))
        else:
            history.append(("", turn.text))
    
    if session.turns.all().count()==0:
        history.append(("", session.respond()))
    
    return history

# Gradio handler for user input in chat
def chat_with_bot(history, user_input):
    # TODO retrieve a session from a URL param or create a new one for demo purposes
    # Retrieve the session and assume `session.cycle.client` is the speaker
    session = TreatmentSession.objects.first()
    print(session.pk)
    
    user = session.cycle.client
    
    session.listen(speaker=user, text=user_input)
    bot_response = session.respond()

    history.append((user_input, bot_response))
    
    return history, ""  # Return updated history and clear input box


with gr.Blocks() as iface:
    chatbot = gr.Chatbot()
    user_input = gr.Textbox(show_label=False, placeholder="Type your message here...")
    
    # Load the initial chat history on page load
    iface.load(initialize_chat, inputs=None, outputs=chatbot)
    user_input.submit(chat_with_bot, [chatbot, user_input], [chatbot, user_input])

iface.launch()
