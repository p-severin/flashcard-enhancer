from pydantic import BaseModel, Field


class RawCard(BaseModel):
    front: str
    back: str
    deck_name: str


class AdditionalFields(BaseModel):
    example_sentence_front: str = Field(
        description="An example sentence using the front field value"
    )
    example_sentence_back: str = Field(
        description="A translation of the example sentence"
    )

