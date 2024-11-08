from mindframe.models import TreatmentSession, format_turns
from mindframe.multipart_llm import chatter

tt = TreatmentSession.objects.all().first()
tt.turns.all().delete()
tt.notes.all().delete()
tt.progress.all().delete()


with open("../mindframe/docs/typical-client.md", "r") as f:
    tc = f.read()

specifics = """
Name: Ben
Needs to lose weight
Would like to be more active
Is willing to start FIT now, but will need to be pressed and asked at least a few times before agreeing to a direct question.
Would like to attend family wedding and wear a nice suit
Finds gym intimidating
IF really pressed, will admit to liking swimming
Could use help with meal planning
"""

for i in range(15):
    print("RESPONSE", tt.respond())
    cli_res = chatter(
        tc.format(**{"history": format_turns(tt.turns.all()), "specifics": specifics})
    )["__RESPONSE__"].value
    print("CLIENT", cli_res)
    tt.listen(tt.cycle.client, cli_res)

print(format_turns(tt.turns.all()))
pass
