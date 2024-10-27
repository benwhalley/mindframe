
from magentic import prompt
from magentic import OpenaiChatModel

from pydantic import BaseModel
import os
from typing import List, Optional



annomi = """therapist	00:00:13	Thanks for filling it out. We give this form to everyone once a year regardless of why they come in. It helps us provide better care. Is it okay if I take a look at what you put down?
client	00:00:24	Sure.
therapist	00:00:25	So, let's see. It looks that you put-- You drink alcohol at least four times a week on average-
client	00:00:34	Mm-hmm.
therapist	00:00:34	#NAME?
client	00:00:39	Usually three drinks and glasses of wine.
therapist	00:00:42	Okay. That's at least 12 drinks a week.
client	00:00:46	Something like that.
therapist	00:00:47	Okay. Just so you know, my role, um, when we talk about alcohol use, is just to share information about risk and to help patients who want help. This is different than telling them what I think they should do. I don't do that.
client	00:01:03	Okay.
therapist	00:01:05	Uh, what else can you tell me about your drinking.
client	00:01:08	Well, I usually drink when I'm at home trying to unwind and I drink while I'm watching a movie. And sometimes, um, I take a bath but I also drink when I take a bath sometimes.
therapist	00:01:22	Okay. So, can I share with you some information on alcohol use?
client	00:01:28	Okay.
therapist	00:01:29	Okay. So, there has been a lot of research on alcohol use and the guidelines we use in this country says that having seven or more drinks per week can raise the risk of health problems for women.
client	00:01:44	Hmm. Seven?
therapist	00:01:45	Seven.
client	00:01:47	Wow. I knew my doctor didn't like me drinking the amount that I did but I didn't know that seven was the limit.
therapist	00:01:55	Yeah, you're surprised to hear that?
client	00:01:57	Yes. What-what kind of health problems?
therapist	00:02:00	Well things like heart disease, cancer, liver problems, uh, stomach pains, insomnia. Unfortunately, uh, people who drink at a risky level are more likely to be diagnosed with depression and alcohol can make depression worse or harder to treat."""




class Utterance(BaseModel):
    speaker: str
    text: str

class Conversation(BaseModel):
    utterances: List[Utterance]



@prompt("""{transcript}\n\nTurn this into a conversation in JSON""")
def parse_conversation(transcript: str) -> Conversation: ... 




def make_session_from_text(t):
    cc = parse_conversation(t)
    ss = TreatmentSession.objects.all().first()
    ssn = TreatmentSession.objects.create(cycle=ss.cycle)
    ssn.save()
    tpst = CustomUser.objects.get(role="bot")
    for u in cc.utterances:
        tt = Turn.objects.create(text=u.text, speaker = u.speaker=="therapist" and tpst or ssn.cycle.client, session=ssn)
        tt.save()
    return ssn


ns = make_session_from_text("""therapist	00:00:02	You did your values clarification handout, and that was part of what I wanted to go over with you today. I wanted to hear about your values and just talk to you a little bit more about that. Do-do you wanna tell me what some of your top five values are?
client	00:00:17	Yes, um, my top value is family happiness, um, that's-
therapist	00:00:23	That's number one?
client	00:00:24	-that's number one to me, especially now. I usually do this values clarification sheet, like, every two to three months-
therapist	00:00:33	Mm-hmm.
client	00:00:34	#NAME?
therapist	00:00:39	Oh. So, right now family value is the most important thing to you?
client	00:00:43	Yes.
therapist	00:00:43	Family happiness?
client	00:00:45	Yes, it's the most important because it's a little lacking, so I know that that's something that is very important to me.
therapist	00:00:55	Okay. Would you like to talk more about that?""")

ns.id












