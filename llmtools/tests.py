from typing import List, Optional

from django.test import TestCase
from pydantic import BaseModel, Field

from llmtools.llm_calling import chatter, split_multipart_prompt
from mindframe.models import LLM


class LLMToolsTestCase(TestCase):
    def setUp(self):
        self.mini = LLM.objects.create(model_name="gpt-4o-mini")

    def test_chatter_joke(self):
        jk = chatter(
            "Think about mammals very briefly, in one or 2 lines: [[THOUGHTS]] Now tell me a joke. [[speak:JOKE]]",
            self.mini,
        )

        self.assertIsInstance(jk["JOKE"], str)
        self.assertEqual(len(jk.keys()), 3)
        self.assertEqual(set(jk.keys()), {"THOUGHTS", "JOKE", "RESPONSE_"})

    def test_split_multipart_prompt(self):
        with self.assertRaises(Exception):
            split_multipart_prompt("one[[]]two[[RESP]]dddd")

        parsed_prompt = split_multipart_prompt("one[[x]]two[[RESP]]dddd")
        self.assertEqual(len(parsed_prompt.items()), 3)

        parsed_prompt_talk = split_multipart_prompt("one[[talk:y]]two[[RESP]]dddd")
        self.assertEqual(parsed_prompt_talk["talk:y"], "one")

    def test_chatter_topic_choice(self):
        rr = chatter(
            "Which is more interesting for nerds: art, science or magic? [[pick:topic|art,science,magic]]",
            self.mini,
        )

        self.assertIn(rr["topic"], ["art", "science", "magic"])
        self.assertEqual(rr["topic"], "science")

    def test_structured_chat(self):
        class UserInfo(BaseModel):
            name: str
            age: Optional[int] = Field(description="The age in years of the user.", default=None)

        class UserList(BaseModel):
            peeps: List[UserInfo]

        newusers, completions = structured_chat(
            "Create a list of 3 imaginary users. Use consistent field names for each item. Use the tools [[users]]",
            self.mini,
            return_type=UserList,
        )

        self.assertEqual(len(newusers.peeps), 3)
