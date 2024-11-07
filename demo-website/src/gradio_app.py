import os
import django
import gradio as gr

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from mindframe.models import TreatmentSession, CustomUser, RoleChoices

# get all session IDs and titles for dropdown
def get_sessions():
    sessions = TreatmentSession.objects.all()
    return [(str(session), str(session.pk)) for session in sessions]  

def initialize_chat(session_id):
    session = TreatmentSession.objects.get(pk=int(session_id)) 
    print(f"Selected session: {session.pk}")
    # prepopulate history from existing turns in this session
    history = []
    for turn in session.turns.all().order_by('timestamp'):
        role = "assistant" if turn.speaker.role == RoleChoices.BOT else "user"
        if role == "user":
            history.append((turn.text, ""))
        else:
            history.append(("", turn.text))
    
    if session.turns.all().count() == 0:
        history.append(("", session.respond()))
    
    return history


def chat_with_bot(session_id, history, user_input):
    session = TreatmentSession.objects.get(pk=int(session_id))  # Convert session_id to integer    
    user = session.cycle.client
    session.listen(speaker=user, text=user_input)
    bot_response = session.respond()
    history.append((user_input, bot_response))
    return history, ""  # return updated history and clear input box


with gr.Blocks() as iface:
    chs = get_sessions()
    session_dropdown = gr.Dropdown(
        label="Select Treatment Session",
        choices=chs,  
        value=None
    )
    
    chatbot = gr.Chatbot()
    user_input = gr.Textbox(show_label=False, placeholder="Type your message here...")
    
    # update chat history when a session is selected
    session_dropdown.change(
        initialize_chat, 
        inputs=session_dropdown, 
        outputs=chatbot
    )

    # handle user input for the selected session
    user_input.submit(
        chat_with_bot, 
        [session_dropdown, chatbot, user_input], 
        [chatbot, user_input]
    )

iface.launch()
