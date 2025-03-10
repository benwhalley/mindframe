# # Tests of creating pydantic models, using them as a schema for judgement return types and then processing judgements to make Notes

# import json
# from typing import List

# from django.test import TestCase
# from pydantic import BaseModel

# from mindframe.models import (
#     CustomUser,
#     Intervention,
#     Judgement,
#     Note,
# )


# # Define the Pydantic models for return types
# class BriefNote(BaseModel):
#     text: str


# class ComplexNote(BaseModel):
#     text: str
#     number_open_questions: int
#     open_question_texts: List[str]
#     patient_name_if_included: str = ""


# class CommentedBooleanResponse(BaseModel):
#     commentary: str = Field(
#         ...,
#         description="Think carefully about your classification and give a 1 or 2 sentence explanation of your rationale here.",
#     )
#     response: bool = Field(
#         ..., description="Only return true if you are confident in your classification."
#     )


# from mindframe.structured_judgements import (
#     data_extraction_function_factory,
#     pydantic_model_from_schema,
# )

# # tt = TreatmentSession.objects.all().first()
# # tt.respond()


# class JudgementTestCase(TestCase):
#     @classmethod
#     def setUpTestData(cls):
#         # Example data for testing
#         cls.anno_eg = """therapist	00:00:02	You did your values clarification handout, and that was part of what I wanted to go over with you today. I wanted to hear about your values and just talk to you a little bit more about that. Do-do you wanna tell me what some of your top five values are?
# client	00:00:17	Yes, um, my top value is family happiness, um, that's-
# therapist	00:00:23	That's number one?
# client	00:00:24	-that's number one to me, especially now. I usually do this values clarification sheet, like, every two to three months-
# therapist	00:00:33	Mm-hmm.
# client	00:00:34	#NAME?
# therapist	00:00:39	Oh. So, right now family value is the most important thing to you?
# client	00:00:43	Yes.
# therapist	00:00:43	Family happiness?
# client	00:00:45	Yes, it's the most important because it's a little lacking, so I know that that's something that is very important to me.
# therapist	00:00:55	Okay. Would you like to talk more about that?"""

#         # Create mock intervention and session
#         cls.intervention = Intervention.objects.create(title="Test Intervention")
#         cls.client = CustomUser.objects.create(username="joe")
#         cls.cycle = Cycle.objects.create(intervention=cls.intervention, client=cls.client)

#         cls.session = TreatmentSession.objects.create(cycle=cls.cycle)

#         # Define and create JudgementReturnType for BriefNote
#         brief_note_schema = json.loads(BriefNote.schema_json())
#         cls.brief_judgement_return_type = JudgementReturnType.objects.create(
#             schema=brief_note_schema, title="BriefNote"
#         )

#         # Define and create JudgementReturnType for ComplexNote
#         complex_note_schema = ComplexNote.schema()
#         cls.complex_judgement_return_type = JudgementReturnType.objects.create(
#             schema=complex_note_schema, title="ComplexNote"
#         )

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
#         self.assertIn("text", newnote.data)

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
#         self.assertIn("text", newnote.data)
#         self.assertIn("number_open_questions", newnote.data)
#         self.assertIn("open_question_texts", newnote.data)
#         self.assertIn("patient_name_if_included", newnote.data)

#         # Example checks to ensure expected types and values (assuming your processing logic includes these values)
#         self.assertIsInstance(newnote.data["number_open_questions"], int)

#     def tearDown(self):
#         # Clean up any created objects
#         Note.objects.all().delete()
#         Judgement.objects.all().delete()
#         JudgementReturnType.objects.all().delete()
#         TreatmentSession.objects.all().delete()
#         Cycle.objects.all().delete()
#         Intervention.objects.all().delete()
#         CustomUser.objects.all().delete()
