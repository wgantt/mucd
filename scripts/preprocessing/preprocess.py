"""
process the train/dev/test file
"""
import json
import os
import re

from allennlp.data.tokenizers.sentence_splitter import SpacySentenceSplitter
from collections import defaultdict, OrderedDict
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


def clean_muc_text(document: str) -> str:
    # strip newlines and extra spaces
    # NOTE: the preprocessing script at the following URL does not strip extra spaces:
    #       https://github.com/xinyadu/gtt/blob/master/data/muc/scripts/preprocess.py
    cleaned_text = " ".join(
        [
            segment
            for paragraph in document.split("\n\n")
            for segment in paragraph.split("\n")
        ]
    )
    return re.sub(r" +", " ", cleaned_text)


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
    for document, document_text in tqdm(
        doc_dict.items(), desc=f'Processing split "{split}"'
    ):

        # split document text into sentences
        # NOTE: strangely, the SpaCy sentence splitter works terribly on
        #       text in all caps, which is why we lowercase the text here
        sentences = sentence_splitter.split_sentences(document_text.lower())
        sentence_idxs = []
        lowercase_document_text = document_text.lower()
        for s in sentences:
            start_idx = lowercase_document_text.index(s)
            end_idx = start_idx + len(s)
            sentence_idxs.append((start_idx, end_idx))

        # create augmented entry for this document
        output[document] = {
            "text": document_text,
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
        print(unlocatable_entity_mentions)
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
