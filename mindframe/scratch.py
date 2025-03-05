import os
from datetime import timedelta

import django
from django.utils import timezone

from mindframe.conversation import *
from mindframe.models import (
    LLM,
    Conversation,
    CustomUser,
    Intervention,
    Judgement,
    Note,
    StepJudgement,
    Transition,
    Turn,
)
from mindframe.settings import TurnTextSourceTypes
from mindframe.templatetags.turns import format_turns
from mindframe.tree import conversation_history, iter_conversation_path

# setup intervention

Intervention.objects.all().delete()
Conversation.objects.all().delete()
Note.objects.all().delete()

model, _ = LLM.objects.get_or_create(model_name="gpt-4o-mini")

client, _ = CustomUser.objects.get_or_create(
    username="client", defaults={"role": "client", "email": "client@example.com"}
)
therapist, _ = CustomUser.objects.get_or_create(
    username="therapist", defaults={"role": "therapist", "email": "therapist@example.com"}
)

cbt = Intervention.objects.create(title="CBT")
cbtwelcome, _ = Step.objects.get_or_create(
    intervention=cbt,
    title="Welcome to CBT",
    prompt_template="Conversation so far: {% turns 'all' %}\n\nWelcome the client to CBT and continue the conversation\n[[speak:response]]",
)

cbtstep2, _ = Step.objects.get_or_create(
    intervention=cbt,
    title="CBT step 2",
    prompt_template="Ask the client about their diary",
)

tr1, _ = Transition.objects.get_or_create(
    from_step=cbtwelcome, to_step=cbtstep2, conditions="anxiety_level.value < 5"
)

fakeclient, _ = Intervention.objects.get_or_create(title="Fake Client")
fakeclientstep1, _ = Step.objects.get_or_create(
    intervention=fakeclient,
    title="Fake Client Step 1",
    prompt_template="Conversation so far: {% turns 'all' %}\n\nYou are the client in a conversation between a depressed person and a CBT therapist. Role play the client. Always continue the conversation above.\n[[speak:response]]",
)


judge_anxiety, _ = Judgement.objects.get_or_create(
    variable_name="anxiety_level",
    prompt_template="""{% turns 'all' %}\n How anxious does the client seem?\nGive a score on 1-5 scale. Return valid json.\n[[int:value]]""",
    intervention=cbt,
)


stepjudgementexample, _ = StepJudgement.objects.get_or_create(
    step=cbtwelcome, judgement=judge_anxiety
)


judge_summaryofconvo, _ = Judgement.objects.get_or_create(
    variable_name="summary",
    prompt_template="""{% turns 'all' %}\n Summarise the contents of this conversation. Imagine you are the therapist, looking at a list of conversations. Write it for yourself, making it as easy as possible to recall and distinguish the conversation. Don't label, title or prefix the summary: just 3-4 sentences of prose, starting with 'Discussed' or 'Spoke about' or similar \n[[summary]]""",
    intervention=cbt,
)
stepjudgementexample2, _ = StepJudgement.objects.get_or_create(
    step=cbtwelcome, judgement=judge_summaryofconvo
)
stepjudgementexample3, _ = StepJudgement.objects.get_or_create(
    step=cbtstep2, judgement=judge_summaryofconvo
)


judge_progress, _ = Judgement.objects.get_or_create(
    variable_name="progress",
    prompt_template="""{% turns 'all' %}\n How complete is this CBT treatment session. Return valid json.\n[[pick|just_started,half_done,nearly_done,complete]]""",
    intervention=cbt,
)


stepjudgeentryexample, _ = StepJudgement.objects.get_or_create(
    step=cbtstep2, judgement=judge_progress, when=StepJudgementFrequencyChoices.ENTER
)


conversation = Conversation.objects.create(is_synthetic=True)

# Create the root turn using Treebeard's add_root (sets proper tree fields)
turn0 = Turn.add_root(
    conversation=conversation,
    speaker=therapist,
    text="Welcome to the session. How are you feeling today?",
    timestamp=timezone.now(),
    branch=False,
    text_source=TurnTextSourceTypes.OPENING,
    step=cbtwelcome,
)

turn1 = turn0.add_child(
    conversation=conversation, speaker=client, text="Hi, I'm feeling anxious.", step=fakeclientstep1
)

new_tip = add_turns(turn1, 4)


hist = conversation_history(new_tip)

hist.first().step
hist.last().step


# we should have made 2 notes, because we have 2 therapist-completed turns
Note.objects.filter(turn__in=hist)
Note.objects.filter(turn__in=hist).count()

print(format_turns(conversation_history(new_tip)))
