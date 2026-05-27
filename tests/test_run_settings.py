import unittest

from flashcard_enhancer.prompts import PROMPT_VERSION
from flashcard_enhancer.run_settings import GenerationSettings


class GenerationSettingsTests(unittest.TestCase):
    def test_builds_prompt_settings_and_metadata_from_one_interface(self) -> None:
        settings = GenerationSettings(
            model="openai:test",
            source_language="Italian",
            target_language="English",
            level="A1",
        )

        prompt_settings = settings.prompt_settings()

        self.assertEqual("Italian", prompt_settings.source_language)
        self.assertEqual("English", prompt_settings.target_language)
        self.assertEqual("A1", prompt_settings.level)
        self.assertEqual(
            {
                "prompt_version": PROMPT_VERSION,
                "model": "openai:test",
                "source_language": "Italian",
                "target_language": "English",
                "level": "A1",
            },
            settings.metadata(),
        )


if __name__ == "__main__":
    unittest.main()
