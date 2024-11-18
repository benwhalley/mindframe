import sys
import os
import django
import gradio as gr
import logging


def main():
    project_root = os.getcwd()
    sys.path.append(project_root)
    print(project_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    logger = logging.getLogger(__name__)

    from mindframe.models import TreatmentSession, CustomUser, RoleChoices, Cycle, Turn

    def get_session(id):
        return TreatmentSession.objects.get(uuid=id)

    # Function to initialize chat history based on session_id from request
    def initialize_chat(request: gr.Request):
        # Get session_id from query parameters
        session_id = request.query_params.get("session_id")

        session = get_session(session_id)
        print(f"Selected session: {session}")

        # Prepopulate history from existing turns in this session
        history = []
        for turn in Turn.objects.filter(session_state__session=session).order_by("timestamp"):
            role = "assistant" if turn.speaker.role == RoleChoices.THERAPIST else "user"
            if role == "user":
                history.append((turn.text, ""))
            else:
                history.append(("", turn.text))

        if session.turns.all().count() == 0:
            history.append(("", session.respond()))

        return history, session_id

    # Chat function to handle user input and bot responses
    def chat_with_bot(session_id, history, user_input):
        session = get_session(session_id)
        user = session.cycle.client
        session.listen(speaker=user, text=user_input)
        bot_response = session.respond()
        history.append((user_input, bot_response))
        return history, ""  # Return updated history and clear input box

    with gr.Blocks() as iface:
        chatbot = gr.Chatbot()
        user_input = gr.Textbox(show_label=False, placeholder="Type your message here...")
        session_id_box = gr.Textbox(visible=False)  # Hidden textbox for session_id

        # Initialize chat history with session_id from query string and store session_id in hidden textbox
        iface.load(initialize_chat, inputs=None, outputs=[chatbot, session_id_box])

        # Handle user input with session_id in the chat function
        user_input.submit(
            chat_with_bot, [session_id_box, chatbot, user_input], [chatbot, user_input]
        )

    iface.launch(server_name="0.0.0.0", server_port=int(os.environ.get("CHAT_PORT", 8000)))


if __name__ == "__main__":
    main()
