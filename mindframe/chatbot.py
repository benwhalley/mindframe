import sys
import os
import django
import gradio as gr
from django.urls import reverse
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    from mindframe.models import TreatmentSession, RoleChoices, Turn

    def get_session(id):
        return TreatmentSession.objects.get(uuid=id)

    def initialize_chat(request: gr.Request):
        session_id = request.query_params.get("session_id")
        session = get_session(session_id)

        history = []
        log_history = ["#### Bot's thoughts:\n\n"]

        for turn in Turn.objects.filter(session_state__session=session).order_by("timestamp"):
            role = "assistant" if turn.speaker.role == RoleChoices.THERAPIST else "user"
            if role == "user":
                history.append((turn.text, ""))
            else:
                history.append(("", turn.text))

        if session.turns.all().count() == 0:
            bot_response = session.respond()
            history.append(("", bot_response.get("utterance", "Error: No response")))
            thoughts = bot_response.get("thoughts", "")
            if thoughts:
                log_history.append(f"\n\n{thoughts}\n---\n")

        session_detail_url = (
            f"{settings.WEB_URL}{reverse('treatment_session_detail', args=[session_id])}"
        )
        session_link = f"[View Treatment Session Details]({session_detail_url})"

        formatted_log_history = "\n".join(log_history) if log_history else ""
        print(formatted_log_history)
        return history, session_id, session_link, formatted_log_history

    def chat_with_bot(session_id, history, user_input, current_log):
        session = get_session(session_id)
        user = session.cycle.client

        session.listen(speaker=user, text=user_input)
        bot_response = session.respond()
        utterance = bot_response.get("utterance", "Error: No response")
        thoughts = "\n\n".join(bot_response.get("thoughts", ""))

        history.append((user_input, utterance))

        if thoughts:
            new_log_entry = f"{thoughts}\n\n---"
            updated_log = f"{current_log}\n\n{new_log_entry}" if current_log else new_log_entry
        else:
            updated_log = current_log

        return history, "", updated_log

    # Custom CSS for the markdown window
    custom_css = """
    .markdown-window {
        size: 10pt !important;
        font-weight: normal !important;
        height: 80vh !important;
        overflow-y: auto !important;
        padding: 1rem !important;
        background-color: white !important;
        border: 1px solid #e5e7eb !important;
        border-radius: 0.5rem !important;
    }
    """

    with gr.Blocks(css=custom_css) as iface:
        session_link_md = gr.Markdown()

        with gr.Row(equal_height=True):
            with gr.Column(scale=2):
                chatbot = gr.Chatbot()
                user_input = gr.Textbox(show_label=False, placeholder="Type your message here...")

            with gr.Column(scale=1):
                log_window = gr.Markdown(
                    label="Bot's Thoughts", elem_classes=["markdown-window"], visible=False
                )

        session_id_box = gr.Textbox(visible=False)

        iface.load(
            initialize_chat,
            inputs=None,
            outputs=[chatbot, session_id_box, session_link_md, log_window],
        )

        def handle_input(session_id, history, text_input, current_log):
            try:
                if text_input.strip():
                    return chat_with_bot(session_id, history, text_input, current_log)
                else:
                    return history, text_input, current_log
            except Exception as e:
                logger.error(f"Error handling input: {e}")
                history.append(("", str(e)))
                return history, text_input, current_log

        inputs = [session_id_box, chatbot, user_input, log_window]
        outputs = [chatbot, user_input, log_window]

        user_input.submit(handle_input, inputs, outputs)

    iface.launch(server_name="0.0.0.0", server_port=int(os.environ.get("CHAT_PORT", 8000)))


if __name__ == "__main__":
    main()
