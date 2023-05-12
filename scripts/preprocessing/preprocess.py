"""
process the train/dev/test file
"""
import json
import os
import re

from allennlp.data.tokenizers.sentence_splitter import SpacySentenceSplitter
from collections import OrderedDict
from tqdm import tqdm
from typing import *


DATA_DIR = "data/semiprocessed/"
OUTPUT_DIR = "data/processed/"

ENTITY_KEYS = """
perp_individual_id
perp_organization_id
phys_tgt_id
hum_tgt_name
hum_tgt_description
incident_instrument_id
incident_location
""".split()

# Typos in the dataset
MANUAL_FIXES = {
    "RUTH ESPERANA AGUILAR MARROQUIN": "RUTH ESPERANZA AGUILAR MARROQUIN",
    "TERRORIST SQUADS": "TERRORISTS SQUADS",
    "FARABUNDO MARTI NATIONAL LIBERATION MARTI FRONT": "FARABUNDO MARTI NATIONAL LIBERATION FRONT",
    "ARMY OF NATIONAL LIBERATION ( ELN)": "ARMY OF NATIONAL LIBERATION (ELN)",
    "FARABUNDO MARTI NATIONAL LIBERATION FRONT ( FMLN)": "FARABUNDO MARTI NATIONAL LIBERATION FRONT (FMLN)",
    "CAMILIST UNION OF THE ARMY OF NATIONAL  LIBERATION": "CAMILIST UNION OF THE SO-CALLED ARMY OF NATIONAL LIBERATION",
    "LONG RANGE WEAPON": "LONG-RANGE WEAPON",
    "LONG RANGE WEAPONS": "LONG-RANGE WEAPONS",
}

# These are mostly discontiguous mentions
MENTIONS_TO_REMOVE = {
    "TST1-MUC3-0024": "MEMBER OF THE SEPARATIST ETA GROUP",
    "TST1-MUC3-0061": "BUILDING NEXT TO THE U.S. EMBASSY",
    "TST2-MUC4-0090": 'GONZALO RODRIGUEZ GACHA ALIAS "THE MEXICAN"',
}


def is_subset(candidate, entity):
    for m in candidate:
        if m not in entity:
            return False

    return True


def clean_muc_text(document: str) -> List[str]:
    # segment into paragraphs (sections) and strip newlines and extra spaces
    # NOTE: the preprocessing script at the following URL does not strip extra spaces:
    #       https://github.com/xinyadu/gtt/blob/master/data/muc/scripts/preprocess.py
    cleaned_sections = [
        re.sub(r"\s+", " ", paragraph.strip(), flags=re.DOTALL)
        for paragraph in document.split("\n\n")
        if paragraph.strip()
    ]
    return cleaned_sections


def preprocess(split: str) -> Tuple[Dict, Dict, Dict]:
    doc_file = os.path.join(DATA_DIR, split, f"{split}_docs.json")
    keys_file = os.path.join(DATA_DIR, split, f"{split}_keys.json")

    # get document text
    with open(doc_file) as f_doc:
        doc_dict = {k: clean_muc_text(v["text"]) for k, v in json.load(f_doc).items()}

    sentence_splitter = SpacySentenceSplitter()

    # read keys (annotations) from files
    output = {}
    with open(keys_file) as f_keys:
        all_keys = json.load(f_keys)

    # augment annotations with sentence- and document-level index information
    unlocatable_entity_mentions = {}
    unlocatable_location_mentions = {}
    for document, document_sections in tqdm(
        doc_dict.items(), desc=f'Processing split "{split}"'
    ):

        # postprocess document sections
        document_text = " ".join(document_sections)
        section_idxs = []
        for section in document_sections:
            start_idx = section_idxs[-1][1] + 1 if section_idxs else 0
            end_idx = start_idx + len(section)
            section_idxs.append((start_idx, end_idx))

        # split document sections into sentences
        # NOTE: strangely, the SpaCy sentence splitter works terribly on
        #       text in all caps, which is why we lowercase the text here
        sentence_idxs = []
        for ((section_start_idx, _), section_text) in zip(section_idxs, document_sections):
            lowercase_section_text = section_text.lower()
            sentence_idx_offset = 0
            for sentence in sentence_splitter.split_sentences(lowercase_section_text):
                start_idx_within_section = lowercase_section_text.index(sentence, sentence_idx_offset)
                start_idx = section_start_idx + start_idx_within_section
                end_idx = start_idx + len(sentence)
                sentence_idxs.append((start_idx, end_idx))
                sentence_idx_offset = start_idx_within_section + len(sentence)

        # create augmented entry for this document
        output[document] = {
            "text": document_text,
            "sections": section_idxs,
            "sentences": sentence_idxs,
            "templates": [],
        }

        # augment templates with sentence- and document-level index information
        templates = all_keys.get(document, [])
        mentions_to_remove = MENTIONS_TO_REMOVE.get(document, [])
        for template in templates:
            # skip empty templates
            if template["message_template"] == "*":
                continue

            # we only care about the slots with entity fillers
            # we also ignore here slots that describe features of those
            # of those entities, like 'hum_tgt_foreign_nation' or 'phys_tgt_number'
            for slot in ENTITY_KEYS:
                if slot not in template or not template[slot]:
                    continue
                fillers = template[slot]

                # locate mentions of each filler in the document and in each sentence
                for filler in fillers:
                    mentions = filler.get("strings")
                    mention_key = "strings"
                    if mentions is None:
                        if slot == "incident_location":
                            mentions = filler["strings_lhs"]
                            mention_key = "strings_lhs"
                        elif slot == "hum_tgt_description":
                            # colon clause mentions in the hum_tgt_description slot
                            # are already covered in the hum_tgt_name slot
                            continue
                        else:
                            raise ValueError(
                                f"Found no mentions for filler of the {slot} slot in document {document}."
                            )

                    if mentions_to_remove:
                        mentions = [m for m in mentions if m not in MENTIONS_TO_REMOVE]
                    filler["document_mentions"] = []
                    filler["sentence_mentions"] = OrderedDict()
                    for m in mentions:
                        m = MANUAL_FIXES.get(m, m)
                        m = m.replace("[", "(").replace("]", ")")
                        try:
                            mention_document_idxs = [
                                match.span()
                                for match in re.finditer(re.escape(m), document_text)
                            ]
                        except:
                            print(
                                f'WARNING: error while searching for mention "{m}" in document "{document}"'
                            )
                            continue

                        if mention_document_idxs:
                            filler["document_mentions"].extend(mention_document_idxs)
                            total_sentence_mentions = 0
                            for i, (sent_start, sent_end) in enumerate(sentence_idxs):
                                sentence = document_text[sent_start:sent_end]
                                mention_sentence_idxs = [
                                    match.span()
                                    for match in re.finditer(re.escape(m), sentence)
                                ]
                                total_sentence_mentions += len(mention_sentence_idxs)
                                if mention_sentence_idxs:
                                    if i not in filler["sentence_mentions"]:
                                        filler["sentence_mentions"][i] = []
                                    filler["sentence_mentions"][i].extend(
                                        mention_sentence_idxs
                                    )
                            if total_sentence_mentions != len(mention_document_idxs):
                                print(
                                    f"WARNING: number of document-level mentions ({len(mention_document_idxs)}) does not match "
                                    + f'number of sentence-level mentions ({total_sentence_mentions}) for mention "{m}" in document "{document}"'
                                )

                        else:
                            if slot == "incident_location":
                                if document not in unlocatable_location_mentions:
                                    unlocatable_location_mentions[document] = set()
                                unlocatable_location_mentions[document].add(m)
                            else:
                                if document not in unlocatable_entity_mentions:
                                    unlocatable_entity_mentions[document] = set()
                                unlocatable_entity_mentions[document].add(m)
                        filler[mention_key] = mentions
            output[document]["templates"].append(template)

        if unlocatable_entity_mentions.get(document):
            unlocatable_entity_mentions[document] = sorted(
                unlocatable_entity_mentions[document]
            )

        if unlocatable_location_mentions.get(document):
            unlocatable_location_mentions[document] = sorted(
                unlocatable_location_mentions[document]
            )

    return output, unlocatable_entity_mentions, unlocatable_location_mentions


if __name__ == "__main__":
    for split in ["train", "dev", "test"]:
        (
            preprocessed_data,
            unlocatable_entity_mentions,
            unlocatable_location_mentions,
        ) = preprocess(split)
        split_dir = os.path.join(OUTPUT_DIR, split)
        os.makedirs(split_dir, exist_ok=True)
        processed_file = os.path.join(split_dir, f"{split}.json")
        print("Unlocatable entity mentions:")
        print(json.dumps(unlocatable_entity_mentions, indent=4))
        with open(processed_file, "w") as f_processed:
            json.dump(preprocessed_data, f_processed, indent=4)
        unlocatable_entity_mentions_file = os.path.join(
            split_dir, f"{split}_unlocatable_entities.json"
        )
        with open(unlocatable_entity_mentions_file, "w") as f_unlocatable_entities:
            json.dump(unlocatable_entity_mentions, f_unlocatable_entities, indent=4)
        unlocatable_location_mentions_file = os.path.join(
            split_dir, f"{split}_unlocatable_locations.json"
        )
        with open(unlocatable_location_mentions_file, "w") as f_unlocatable_locations:
            json.dump(unlocatable_location_mentions, f_unlocatable_locations, indent=4)
