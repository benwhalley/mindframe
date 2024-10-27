from mindframe.models import TreatmentSession, Turn, Cycle
from mindframe.multipart_llm import chatter


s = TreatmentSession.objects.create(cycle=Cycle.objects.first())
# s = TreatmentSession.objects.first()
t = Turn.objects.create(text="Hello", speaker=s.cycle.client, session=s)


with open('../../docs/typical-client.md', 'r') as f:
    tc = f.read()
    print(tc)

specifics = """
Name: alex
Needs to lose weight
Would like to be more active
Would like to attend family wedding and wear a nice dress
Find gym intimidating
IF really pressed, will admit to liking swimming
Could use help with meal planning
"""


for i in range(10):
    s.respond()
    history = "\n".join([f"{i.speaker.role=='bot' and 'therapist' or 'client'}: {i.text}" for i in s.turns.all()[:5]])
    clires = chatter(tc.format(**{'history': history, 'specifics': specifics}))
    Turn.objects.create(text=clires['RESPONSE'].value, 
                        speaker=s.cycle.client, 
                        session=s)

