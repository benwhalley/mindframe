import sys
import os
import django
import gradio as gr
import logging

# import whisper

from django.urls import reverse
from django.conf import settings


def main():
    project_root = os.getcwd()
    sys.path.append(project_root)
    print(project_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    from django.conf import settings

    # if settings.MINDFRAME_AUDIO_INPUT:
    #     try:
    #         model = whisper.load_model("turbo")
    #     except Exception as e:
    #         logger.warning(f"Error loading whisper model: {e}")
    #         model = None
    # else:
    #     model = None
    model = None

    logger = logging.getLogger(__name__)

    from mindframe.models import TreatmentSession, RoleChoices, Turn

    def get_session(id):
        return TreatmentSession.objects.get(uuid=id)

    # Function to initialize chat history based on session_id from request
    def initialize_chat(request: gr.Request):
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

        # Generate the URL to the treatment session detail view
        session_detail_url = (
            f"{settings.WEB_URL}{reverse('treatment_session_detail', args=[session_id])}"
        )
        session_link = f"[View Treatment Session Details]({session_detail_url})"

        return history, session_id, session_link

    # External API call for audio transcription
    def transcribe_audio(audio_file):
        transcription = model.transcribe(audio_file)
        return transcription

    # Chat function to handle user input and bot responses
    def chat_with_bot(session_id, history, user_input, audio_input):
        session = get_session(session_id)
        user = session.cycle.client

        # TODO: Add more sanity checking and cleaning for the audio input here
        if audio_input is not None:
            transcription = transcribe_audio(audio_input).get("text", "Audio not transcribed")
            logger.info(f"Transcribed audio input: {transcription}")
            if transcription:  # Process only if there's valid input
                user_input = transcription

        session.listen(speaker=user, text=user_input)
        bot_response = session.respond()
        history.append((user_input, bot_response))

        return history, "", None  # Clear text and audio inputs

    with gr.Blocks() as iface:
        # Markdown component for the session link, placed at the top
        session_link_md = gr.Markdown()

        chatbot = gr.Chatbot()
        user_input = gr.Textbox(show_label=False, placeholder="Type your message here...")

        if model is not None:
            logger.info("Adding audio input")
            audio_input = gr.Audio(
                sources=["microphone"], type="filepath", label="Speak your message"
            )
        else:
            logger.warning("No audio input shown as whisper model is not available")
            audio_input = gr.Textbox(visible=False)

        session_id_box = gr.Textbox(visible=False)  # Hidden textbox for session_id

        # Initialize chat history with session_id from query string and store session_id in hidden textbox
        iface.load(initialize_chat, inputs=None, outputs=[chatbot, session_id_box, session_link_md])

        # Function to handle input selection logic
        def handle_input(session_id, history, text_input, audio_path):
            if text_input.strip():  # Prioritize text input if available
                return chat_with_bot(session_id, history, text_input, None)
            elif audio_path:  # Process audio input only if no text is provided
                return chat_with_bot(session_id, history, "", audio_path)
            else:  # Do nothing if no input is provided
                return history, text_input, audio_path  # Preserve current state without resetting

        # Bind the input submission to the shared logic
        inputs = [session_id_box, chatbot, user_input, audio_input]
        outputs = [chatbot, user_input, audio_input]

        user_input.submit(handle_input, inputs, outputs)
        audio_input.change(handle_input, inputs, outputs)

    iface.launch(server_name="0.0.0.0", server_port=int(os.environ.get("CHAT_PORT", 8000)))


if __name__ == "__main__":
    main()
