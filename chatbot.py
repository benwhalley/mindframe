import os
import sys
import traceback

import gradio as gr

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import logging

from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)


def main():
    import django

    django.setup()

    from django.conf import settings
    from django.contrib.sessions.models import Session
    from django.core import signing
    from django.core.exceptions import SuspiciousOperation
    from django.shortcuts import get_object_or_404
    from django.urls import reverse

    from mindframe.conversation import listen, respond
    from mindframe.models import CustomUser, RoleChoices, Turn
    from mindframe.tree import conversation_history

    def verify_gradio_chat_token(request: gr.Request):
        """
        Verifies the signed token produced by mindframe.views.general.start_gradio_chat.
        Expects the token to include 'turn_uuid'.
        Returns (turn, None) on success, or (None, error_message) on failure.
        """

        token = request.query_params.get("token")
        if not token:
            return None, None, "Error: No token provided."

        try:
            # Unsigned token returns a dictionary with 'session_key' and 'turn_uuid'.
            # max age of link is 1 day
            data = signing.loads(token, salt="gradio-chatbot-auth", max_age=60 * 60 * 24)
            turn_uuid = data.get("turn_uuid")
            human_user = get_object_or_404(CustomUser, pk=data.get("human_user"))
        except signing.BadSignature as e:
            return None, None, f"Error: Invalid token: \n{e}"

        turn = get_object_or_404(Turn, uuid=turn_uuid)
        return turn, human_user, None

    def initialize_chat(request: gr.Request):
        turn, human_user, error = verify_gradio_chat_token(request)
        if error:
            raise Exception(error)

        turns = conversation_history(turn)

        history = []

        for turn in turns:
            role = "assistant" if turn.speaker.role == RoleChoices.BOT else "user"
            txt = turn.text and turn.text.strip() or None
            logger.info("here!!")
            logger.info(txt)
            txt = f"{turn.uuid[:3]}{txt}"
            if txt and len(txt) > 0:
                if role == "user":
                    history.append((turn.text, None))
                else:
                    history.append((None, turn.text))

        if turns.count() == 0:
            history.append(("", "Error: No turns found in conversation"))

        conversation_detail_url = settings.WEB_URL + reverse(
            "conversation_detail_to_leaf",
            args=[
                turn.uuid,
            ],
        )
        conversation_link_html = f'<a href="{conversation_detail_url}" target="_self">View Conversation Detail {turn.uuid[:4]}</a>'
        conversation_link_md = gr.Markdown(conversation_link_html)

        return history, turn.uuid, conversation_link_md, str(human_user.id)

    def chat_with_bot(turn_id, human_user_id, history, user_input):
        logger.info(f"loading {turn_id}")

        # Ensure turn_id exists
        turn = get_object_or_404(Turn, uuid=turn_id)
        human_user = get_object_or_404(CustomUser, id=human_user_id)

        hist = conversation_history(turn)

        # Create new turn with the human user as speaker
        client_turn = listen(hist.last(), speaker=human_user, text=user_input)
        bot_turn = respond(client_turn)

        # Create a new tuple for the history instead of modifying the existing one
        new_history = list(history)
        new_history.append((user_input, bot_turn.text))

        return bot_turn.uuid, new_history, ""

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
        conversation_link_md = gr.Markdown()

        with gr.Row(equal_height=True):
            with gr.Column():
                chatbot = gr.Chatbot()
                user_input = gr.Textbox(show_label=False, placeholder="Type your message here...")

        turn_id_box = gr.Textbox(visible=False)
        human_user_box = gr.Textbox(visible=False)

        iface.load(
            initialize_chat,
            inputs=None,
            outputs=[chatbot, turn_id_box, conversation_link_md, human_user_box],
        )

        def handle_input(turn_id, human_user_id, history, text_input):
            try:
                if text_input.strip():
                    new_turn_id, history, new_log = chat_with_bot(
                        turn_id, human_user_id, history, text_input
                    )

                    # Generate updated conversation link
                    conversation_detail_url = settings.WEB_URL + reverse(
                        "conversation_detail_to_leaf",
                        args=[new_turn_id],
                    )
                    conversation_link_md = (
                        f"[View Conversation Detail {new_turn_id[:4]}]({conversation_detail_url})"
                    )

                    return new_turn_id, history, new_log, conversation_link_md
                else:
                    return turn_id, history, "---", "ERRROR: NO LINK AVAILABLE"

            except Exception as e:
                logger.error(f"Error handling input: {e}")
                history.append(("", str(e)))
                history.append(("", str(traceback.format_exc())))
                logger.error(str(traceback.format_exc()))

                conversation_detail_url = settings.WEB_URL + reverse(
                    "conversation_detail_to_leaf",
                    args=[turn_id],
                )
                conversation_link_md = (
                    f"[View Conversation Detail {turn_id[:4]}]({conversation_detail_url})"
                )

                return turn_id, history, text_input, conversation_link_md

        inputs = [turn_id_box, human_user_box, chatbot, user_input]
        outputs = [turn_id_box, chatbot, user_input, conversation_link_md]

        user_input.submit(handle_input, inputs, outputs)

    iface.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 8000)))


if __name__ == "__main__":
    main()
