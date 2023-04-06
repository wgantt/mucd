"""
Converts MUC files in data/processed into Concrete data format.
Output is written to data/concrete. Currently only writes slot
values for four five slots (apart from incident_type):
- hum_tgt_name (Victim)
- perp_individual_id (Perpetrator Individual)
- perp_organization_id (Perpetrator Organization)
- phys_tgt_id (Target)
- incident_instrument_id (Weapon)

Author: Will Gantt
Date: 4/4/23
"""
import json
import os
import spacy
import tokenizations

from cement.cement_common import augf
from cement.cement_document import CementDocument
from cement.cement_utils import (
    create_section_from_tokens,
    InputTokenWithSpan,
    InputSentenceWithSpan,
    InputSectionWithSpan,
)
from cement.cement_entity_mention import CementEntityMention
from concrete import (
    AnnotationMetadata,
    Argument,
    Communication,
)
import datetime
from tqdm import tqdm

PROCESSED_DATA_ROOT = "data/processed/"
OUTPUT_DIR = "data/concrete/"
SPLITS = ["train", "dev", "test"]

SLOTS_OF_INTEREST = [
    "hum_tgt_name",
    "perp_individual_id",
    "perp_organization_id",
    "phys_tgt_id",
    "incident_instrument_id",
]

TOKENIZER = spacy.load("en_core_web_sm")


def to_concrete():
    for split in SPLITS:
        data = json.load(
            open(os.path.join(PROCESSED_DATA_ROOT, split, split + ".json"))
        )
        for doc_id, doc in tqdm(
            data.items(), desc=f"Processing documents in split {split}"
        ):
            text = doc["text"]
            all_tokens = []
            input_sentences = []
            for (start, end) in doc["sentences"]:
                input_tokens = []
                for tok in TOKENIZER(text[start:end]):
                    global_tok_start = start + tok.idx
                    global_tok_end = global_tok_start + len(tok)
                    input_tokens.append(InputTokenWithSpan(text=tok.text, start=global_tok_start, end=global_tok_end))
                    all_tokens.append(tok.text)
                input_sentences.append(InputSentenceWithSpan(tokens=input_tokens, start=start, end=end))
            input_section = InputSectionWithSpan(sentences=input_sentences, start=0, end=len(text))
            tok2char, char2tok = tokenizations.get_alignments(all_tokens, text)

            communication_metadata = AnnotationMetadata(
                "cement", int(datetime.datetime.now().timestamp())
            )
            comm = Communication(
                uuid=augf.next(),
                id=doc_id,
                type="muc_document",
                text=text,
                sectionList=[create_section_from_tokens(input_section)],
                metadata=communication_metadata,
            )
            cement_doc = CementDocument.from_communication(comm)
            for template in doc["templates"]:
                template_fillers = []
                for slot in SLOTS_OF_INTEREST:
                    if slot in template and template[slot] is not None:
                        for filler in template[slot]:
                            entity_mentions = []
                            for (char_start, char_end) in filler["document_mentions"]:
                                tok_start, tok_end = (
                                    char2tok[char_start],
                                    char2tok[char_end - 1],
                                )
                                assert len(tok_start) == 1
                                assert len(tok_end) == 1
                                entity_mentions.append(
                                    CementEntityMention(
                                        tok_start[0],
                                        tok_end[0],
                                        text=text[char_start:char_end],
                                        document=cement_doc,
                                    )
                                )
                            entity_uuid = cement_doc.add_entity(
                                entity_mentions, entity_type="ENTITY"
                            )
                            template_fillers.append(
                                Argument(role=slot, entityId=entity_uuid)
                            )
                cement_doc.add_raw_situation(
                    situation_type="incident_type",
                    situation_kind=template["incident_type"],
                    arguments=template_fillers,
                )
            cement_doc.to_communication_file(
                os.path.join(OUTPUT_DIR, split, doc_id + ".comm")
            )


if __name__ == "__main__":
    to_concrete()
