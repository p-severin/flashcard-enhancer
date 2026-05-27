import unittest

from flashcard_enhancer.enhancer import RawCard
from flashcard_enhancer.prompts import PROMPT_VERSION, PromptSettings, build_example_prompt


class PromptTests(unittest.TestCase):
    def test_prompt_includes_language_context_level_and_version(self) -> None:
        prompt = build_example_prompt(
            RawCard(front="ciao", back="hello", deck_name="Italian"),
            PromptSettings(
                source_language="Italian",
                target_language="English",
                level="A1",
            ),
        )

        self.assertIn(PROMPT_VERSION, prompt)
        self.assertIn("Italian", prompt)
        self.assertIn("English", prompt)
        self.assertIn("A1", prompt)
        self.assertIn("ciao", prompt)
        self.assertIn("hello", prompt)


if __name__ == "__main__":
    unittest.main()
