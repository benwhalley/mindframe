import sys
import os
import gradio as gr
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import logging

logger = logging.getLogger(__name__)


def main():
    import django

    django.setup()

    from mindframe.models import Conversation, RoleChoices, Turn
    from mindframe.tree import conversation_history
    from django.conf import settings
    from django.urls import reverse
    from django.core import signing
    from django.core.exceptions import SuspiciousOperation
    from django.contrib.sessions.models import Session
    from django.shortcuts import get_object_or_404
    from mindframe.models import Turn

    def verify_gradio_chat_token(request: gr.Request):
        """
        Verifies the signed token produced by mindframe.views.general.start_gradio_chat.
        Expects the token to include both 'session_key' and 'turn_uuid'.
        Returns (turn, session_data, None) on success, or (None, None, error_message) on failure.
        """

        token = request.query_params.get("token")
        if not token:
            return None, None, "Error: No token provided."

        try:
            # Unsigned token returns a dictionary with 'session_key' and 'turn_uuid'.
            data = signing.loads(token, salt="gradio-chatbot-auth")
            token_session_key = data.get("session_key")
            turn_uuid = data.get("turn_uuid")
            if not token_session_key or not turn_uuid:
                return None, "Error: Invalid token data."
        except signing.BadSignature:
            return None, None, "Error: Invalid token."

        # Retrieve the session cookie from the request.
        session_cookie = request.cookies.get(settings.SESSION_COOKIE_NAME)
        if not session_cookie:
            return None, None, "Error: No session cookie found. Please login."

        # Ensure that the session cookie matches the session key stored in the token.
        if session_cookie != token_session_key:
            return None, None, "Error: Session mismatch. Please login again."

        logger.info(f"Session cookie: {session_cookie}")

        try:
            session_data = signing.loads(
                session_cookie, salt="django.contrib.sessions.backends.signed_cookies"
            )
        except Exception as e:
            return None, None, f"Error: Session not found. Please login. {e}"

        # Check if the user is authenticated (Django stores '_auth_user_id' in the session)
        if not session_data.get("_auth_user_id"):
            login_url = settings.LOGIN_URL if hasattr(settings, "LOGIN_URL") else "/login/"
            return None, None, f"Error: User not logged in. Please <a href='{login_url}'>login</a>."

        logger.info(f"Looking up turn {turn_uuid}")
        turn = get_object_or_404(Turn, uuid=turn_uuid)

        return turn, session_data, None

    def initialize_chat(request: gr.Request):

        turn, session_data, error = verify_gradio_chat_token(request)
        if error:
            raise SuspiciousOperation(error)

        turns = conversation_history(turn)

        history = []
        log_history = ["#### Bot's thoughts:\n\n"]

        for turn in turns:
            role = "assistant" if turn.speaker.role == RoleChoices.THERAPIST else "user"
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
        conversation_link_html = (
            f'<a href="{conversation_detail_url}" target="_self">View Conversation Detail</a>'
        )
        conversation_link_md = gr.HTML(conversation_link_html)

        formatted_log_history = "\n".join(log_history) if log_history else ""
        # outputs=[chatbot, conversation_id_box, conversation_link_md, log_window],
        return history, turn.uuid, conversation_link_md, formatted_log_history

    def chat_with_bot(turn_id, history, user_input, current_log):
        from mindframe.conversation import listen, respond

        turn = Turn.objects.get(uuid=turn_id)

        hist = conversation_history(turn)
        lastclientturn = hist.filter(speaker__role=RoleChoices.CLIENT).last()
        if lastclientturn:
            user = lastclientturn.speaker
        else:
            user = turn.speaker

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
