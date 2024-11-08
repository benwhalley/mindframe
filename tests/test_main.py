import unittest
from mindframe import greet


class TestMindframe(unittest.TestCase):
    def test_greet(self):
        self.assertEqual(greet(), "Hello from Mindframe!")


if __name__ == "__main__":
    unittest.main()
