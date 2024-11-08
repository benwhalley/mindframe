# Tests of creating pydantic models, using them as a schema for judgement return types and then processing judgements to make Notes

from django.test import TestCase
from mindframe.models import (
    Judgement,
    JudgementReturnType,
    Intervention,
    TreatmentSession,
    Cycle,
    CustomUser,
    Note,
)
from pydantic import BaseModel
from typing import List

# An example of testing the bot interactions

tt = TreatmentSession.objects.all().first()

TreatmentSession.objects.exclude(id=tt.id).delete()
Cycle.objects.exclude(id=tt.cycle.id).delete()
tt.turns.all().delete()
tt.notes.all().delete()
tt.progress.all().delete()


tt.notes.all().count() == 0

tt.respond()
tt.listen(tt.cycle.client, "yes I am ready")
tt.respond()

tt.notes.all().count()


tt.listen(tt.cycle.client, "My name is Ben")
tt.respond()
tt.notes.all().count() == 4


tt.listen(
    tt.cycle.client,
    "I don't have any questions - can we get started? I'm feeling unusually happy today",
)
tt.respond()

tt.progress.all().count()  # should be > 1


# class TransitionTestCase(TestCase):

#     @classmethod
#     def setUpTestData(cls):
#         # Create mocks
#         cls.intervention = Intervention.objects.create(title="Test Intervention")
#         cls.client = CustomUser.objects.create(username="joe")
#         cls.cycle = Cycle.objects.create(intervention=cls.intervention, client=cls.client)
#         cls.session = TreatmentSession.objects.create(cycle=cls.cycle)


#         # Define and create JudgementReturnType for ComplexNote
#         complex_note_schema = ComplexNote.schema()
#         cls.complex_judgement_return_type = JudgementReturnType.objects.create(schema=complex_note_schema, title="ComplexNote")

#     def test_brief_note_judgement(self):
#         # Create Judgement for BriefNote
#         jj = Judgement.objects.create(
#             intervention=self.intervention,
#             title="Brief note",
#             prompt_template="Write a brief clinical note from these data: {input}",
#             return_type=self.brief_judgement_return_type,
#         )
#         # Process the input through the judgement
#         newnote = jj.process_inputs(session=self.session, inputs={"input": self.anno_eg})

#         # Assert that the result is in expected format and fields
#         self.assertIn('text', newnote.data)


#     def test_complex_note_judgement(self):
#         # Create Judgement for ComplexNote
#         jj = Judgement.objects.create(
#             intervention=self.intervention,
#             title="Complex note with patient ID and open question count",
#             prompt_template="Write a brief clinical note from these data. Find the patient name if present. Also count the number of open questions used by the therapist, and include the text of each open question.\n\n {input}",
#             return_type=self.complex_judgement_return_type,
#         )

#         # Process the input through the judgement
#         newnote = jj.process_inputs(session=self.session, inputs={"input": self.anno_eg})

#         # Assert that the result includes the expected complex fields
#         self.assertIn('text', newnote.data)
#         self.assertIn('number_open_questions', newnote.data)
#         self.assertIn('open_question_texts', newnote.data)
#         self.assertIn('patient_name_if_included', newnote.data)

#         # Example checks to ensure expected types and values (assuming your processing logic includes these values)
#         self.assertIsInstance(newnote.data['number_open_questions'], int)

#     def tearDown(self):
#         # Clean up any created objects
#         Note.objects.all().delete()
#         Judgement.objects.all().delete()
#         JudgementReturnType.objects.all().delete()
#         TreatmentSession.objects.all().delete()
#         Cycle.objects.all().delete()
#         Intervention.objects.all().delete()
#         CustomUser.objects.all().delete()
