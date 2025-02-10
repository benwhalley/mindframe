import os
import django
from datetime import timedelta
from django.utils import timezone

# If running outside of the Django shell, uncomment these lines:
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "your_project.settings")
# django.setup()

from mindframe.models import CustomUser, Conversation, Turn, Transition, Note, Judgement, LLM, Intervention
from mindframe.tree import iter_conversation_path  # for traversing the conversation
from mindframe.tree import conversation_history
from mindframe.templatetags.turns import format_turns

from mindframe.conversation import *

model, _ = LLM.objects.get_or_create(model_name="gpt-4o-mini")

Intervention.objects.all().delete()

# Create (or fetch) our users
client, _ = CustomUser.objects.get_or_create(
    username="client", defaults={"role": "client", "email": "client@example.com"}
)
therapist, _ = CustomUser.objects.get_or_create(
    username="therapist", defaults={"role": "therapist", "email": "therapist@example.com"}
)

# Create a new conversation instance (saved in DB)
conversation = Conversation.objects.create()

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

tr1, _ = Transition.objects.get_or_create(from_step=cbtwelcome, to_step=cbtstep2, 
                                       conditions = "anxiety_level.value < 5")





# Create the root turn using Treebeard's add_root (sets proper tree fields)
turn0 = Turn.add_root(
    conversation=conversation,
    speaker=therapist,
    text="Welcome to the session. How are you feeling today?",
    timestamp=timezone.now(),
    branch=False,
    text_source="HUMAN",
    step=cbtwelcome,
)

turn1 = turn0.add_child(
    conversation=conversation,
    speaker=client,
    text="Hi, I'm feeling anxious.",
    timestamp=timezone.now(),
    branch=False,
    text_source="HUMAN",
)


turn2 = turn1.listen("Oh, that's sad", speaker=therapist)
turn3 = turn2.listen("Yea, it's a real pita", speaker=client)



j1, _  = Judgement.objects.get_or_create(
        variable_name="anxiety_level", 
        title="Anxiety Level", 
        prompt_template="""{% turns 'all' %}\n How anxious does the client seem?\nGive a score on 1-5 scale. Return valid json.\n[[int:value]]""",
        intervention=cbt)

stpjd1, _ = StepJudgement.objects.get_or_create(step=cbtwelcome, judgement=j1)


cturn = respond(turn3)
cturn = cturn.listen("Yea, it's a real pita", speaker=client)
cturn = respond(cturn)
cturn = cturn.listen("what can you do for me?", speaker=client)
cturn = respond(cturn)


# get notes
Note.objects.filter(turn__conversation=cturn.conversation)


print(format_turns(conversation_history(cturn)))



turn = cturn
# turn = new_turn
# step = new_turn.step
# judgement = j1
# transition = tr1




# need to refetch to get children to get accurate count
Turn.objects.get(pk=cturn.pk).get_children().count()
Turn.objects.get(pk=cturn.pk).get_children()[0].get_siblings().count()

# the whole conversation branch
list(iter_conversation_path(turn3.get_root()))


# Create an alternative branch turn as another therapist response,
# attached to the same parent as turn2. Note: branch=True.
branch_turn = turn1.add_child(
    conversation=conversation,
    speaker=therapist,
    text="Have you considered trying some relaxation techniques?",
    timestamp=timezone.now() + timedelta(minutes=1, seconds=30),
    branch=True,
    text_source="HUMAN",
)


branch_turn2 = turn1.add_child(
    conversation=conversation,
    speaker=therapist,
    text="Have a nice hot bath?",
    timestamp=timezone.now() + timedelta(minutes=1, seconds=30),
    branch=True,
    text_source="HUMAN",
)

print(transcript(conversation_history(branch_turn)))

