import sys
import os
import django
import gradio as gr
from django.urls import reverse
from django.conf import settings
import logging
import traceback

logger = logging.getLogger(__name__)


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    from mindframe.models import Conversation, RoleChoices, Turn
    from mindframe.tree import conversation_history

    def get_history(turn):
        tip_ = turn.get_descendants().last()
        leaf_turn = tip_ or turn
        turns = conversation_history(leaf_turn)
        return turns

    def initialize_chat(request: gr.Request):
        turn_id = request.query_params.get("turn_id")
        turn = Turn.objects.get(uuid=turn_id)

        conversation = turn.conversation

        history = []
        log_history = ["#### Bot's thoughts:\n\n"]

        turns = get_history(turn)

        for turn in turns:
            role = "assistant" if turn.speaker.role == RoleChoices.THERAPIST else "user"
            if turn.text and len(turn.text.strip()) > 0:
                if role == "user":
                    history.append((turn.text, ""))
                else:
                    history.append(("", turn.text))

        if turns.count() == 0:
            history.append(("", "Error: No turns found in conversation"))

        conversation_detail_url = settings.WEB_URL + reverse(
            "conversation_detail",
            args=[
                turn.uuid,
            ],
        )

        conversation_link_html = (
            f'<a href="{conversation_detail_url}" target="_self">View Conversation Detail</a>'
        )
        conversation_link_md = gr.HTML(conversation_link_html)

        formatted_log_history = "\n".join(log_history) if log_history else ""
        return history, turn_id, conversation_link_md, formatted_log_history

    def chat_with_bot(turn_id, history, user_input, current_log):
        from mindframe.conversation import listen, respond

        turn = Turn.objects.get(uuid=turn_id)

        hist = get_history(turn)
        # TODO: check assumption that
        # the user is the last client user to have spoken
        user = hist.filter(speaker__role=RoleChoices.CLIENT).last().speaker
        client_turn = listen(hist.last(), speaker=user, text=user_input)
        bot_turn = respond(client_turn)

        utterance = bot_turn.text
        thoughts = bot_turn.notes_data() or "---"

        history.append((user_input, utterance))

        new_log_entry = f"{thoughts}\n\n---"
        updated_log = f"{current_log}\n\n{new_log_entry}" if current_log else new_log_entry

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
        conversation_link_md = gr.HTML()

        with gr.Row(equal_height=True):
            with gr.Column(scale=2):
                chatbot = gr.Chatbot()
                user_input = gr.Textbox(show_label=False, placeholder="Type your message here...")

            with gr.Column(scale=1):
                log_window = gr.Markdown(
                    label="Bot's Thoughts", elem_classes=["markdown-window"], visible=False
                )

        conversation_id_box = gr.Textbox(visible=False)

        iface.load(
            initialize_chat,
            inputs=None,
            outputs=[chatbot, conversation_id_box, conversation_link_md, log_window],
        )

        def handle_input(turn_id, history, text_input, current_log):
            try:
                if text_input.strip():
                    return chat_with_bot(turn_id, history, text_input, current_log)
                else:
                    return history, text_input, current_log
            except Exception as e:
                logger.error(f"Error handling input: {e}")
                history.append(("", str(e)))
                history.append(("", str(traceback.format_exc())))
                logger.error(str(traceback.format_exc()))
                return history, text_input, current_log

        inputs = [conversation_id_box, chatbot, user_input, log_window]
        outputs = [chatbot, user_input, log_window]

        user_input.submit(handle_input, inputs, outputs)

    iface.launch(server_name="0.0.0.0", server_port=int(os.environ.get("CHAT_PORT", 8000)))


if __name__ == "__main__":
    main()
