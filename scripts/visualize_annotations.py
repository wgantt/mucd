import argparse
import json
import os
import time

from typing import *

from preprocessing.proc_keys import SELECTED_KEYS, NON_LIST_VALUED_KEYS

DATA_DIR = "data/processed/"

ENTITY_KEYS = """
perp_individual_id
perp_organization_id
phys_tgt_id
hum_tgt_name
hum_tgt_description
incident_instrument_id
""".split()

OFFSET = max([len(k) for k in SELECTED_KEYS]) + 2
OFFSET_STR = " " * OFFSET


def pretty_print_entities(template: Dict[str, Any], slot: str) -> None:
    print(f"{slot}:")
    if template.get(slot) is not None:
        for item in template[slot]:
            if item["type"] == "colon_clause":
                assert len(item["strings_lhs"]) == 1
                print(
                    f"{OFFSET_STR + item['strings_lhs'][0]}: {' ,'.join(item['strings_rhs'])}"
                )
            else:
                print(f"{OFFSET_STR + ', '.join(item['strings'])}")


def pretty_print_effect_of_incident(
    template: Dict[str, Any], is_human: bool = True
) -> None:
    slot = "hum_tgt_effect_of_incident" if is_human else "phys_tgt_effect_of_incident"
    print(f"{slot}:")
    if template.get(slot) is not None:
        for item in template[slot]:
            assert len(item["strings_lhs"]) == 1
            print(
                f"{OFFSET_STR + item['strings_lhs'][0]}: {', '.join(item['strings_rhs'])}"
            )


def pretty_print_date(template: Dict[str, Any]) -> None:
    assert len(template["incident_date"]) == 1
    incident_dates = template["incident_date"][0]["strings"]
    print("incident_date:")
    print(f"{OFFSET_STR + ', '.join(incident_dates)}")


def pretty_print_location(template: Dict[str, Any]) -> None:
    to_print = []
    for loc in template["incident_location"]:
        if loc["type"] == "simple_strings":
            assert len(loc["strings"]) == 1
            to_print.append(loc["strings"][0])
        elif loc["type"] == "colon_clause":
            assert len(loc["strings_lhs"]) == len(loc["strings_rhs"]) == 1
            to_print.append(f"{loc['strings_lhs'][0]} ({loc['strings_rhs'][0]})")
    print(f"incident_location:")
    for loc in to_print:
        print(f"{OFFSET_STR + loc}")


def pretty_print_template(template: Dict[str, Any]) -> None:
    for k in NON_LIST_VALUED_KEYS:
        if k in {"message_id", "message_template_optional"}:
            continue
        value = template[k]
        if isinstance(value, dict):
            value = value["strings"]
            assert len(value) == 1, f"{template['message_id']}"
            value = value[0]
        print(f"{k}:")
        print(f"{OFFSET_STR + str(value)}")
    pretty_print_date(template)
    pretty_print_location(template)
    pretty_print_effect_of_incident(template, is_human=True)
    pretty_print_effect_of_incident(template, is_human=False)
    for slot in ENTITY_KEYS:
        pretty_print_entities(template, slot)
    print("-" * 80)


def get_annotated_documents(all_docs: Dict[str, Any]) -> Dict[str, Any]:
    return {
        k: v
        for k, v in all_docs.items()
        if not (len(v) == 1 and v[0]["message_template"] == "*")
    }


def get_annotated_documents_for_template_type(
    all_docs: Dict[str, Any], template_type: str
) -> Dict[str, Any]:
    filtered = {}
    for k, v in all_docs.items():
        target_templates = [t for t in v if t["incident_type"].lower() == template_type]
        if target_templates:
            filtered[k] = target_templates
    return filtered


def view_annotations(
    split: str,
    viewing_mode: str,
    keep_irrelevant: bool = False,
    template_type: Optional[str] = None,
) -> None:
    with open(os.path.join(DATA_DIR, split, f"{split}_keys.json")) as f:
        keys = json.load(f)
        if template_type:
            keys = get_annotated_documents_for_template_type(keys, template_type)
        if not keep_irrelevant:
            keys = get_annotated_documents(keys)
    with open(os.path.join(DATA_DIR, split, f"{split}_docs.json")) as f:
        docs = json.load(f)
        if not keep_irrelevant:
            docs = {k: v for k, v in docs.items() if k in keys}
    assert len(keys) == len(docs)
    if viewing_mode == "sequential":
        ordered_docs = sorted(docs.keys())
        num_docs = len(ordered_docs) - 1
        curr_doc = 0
        while True:
            print("=============")
            print(docs[ordered_docs[curr_doc]]["docid"])
            print("=============\n")
            print(f"{docs[ordered_docs[curr_doc]]['text']}\n")
            print("---------")
            print("Templates")
            print("---------")
            for template in keys[ordered_docs[curr_doc]]:
                print()
                pretty_print_template(template)
            cmd = input(
                "\n(n): next (p): previous (q): quit (g <id>): go to document <id> \n> "
            )
            if cmd == "q":
                break
            elif cmd == "p":
                if curr_doc == 0:
                    print("This is the first document: No previous document to view!")
                    time.sleep(1)
                else:
                    curr_doc -= 1
            elif cmd == "n":
                if curr_doc == num_docs:
                    print("This is the last document: no more documents to view!")
                    time.sleep(1)
                else:
                    curr_doc += 1
            elif cmd.startswith("g "):
                doc_id = cmd[2:]
                docs.get(doc_id)
                if doc_id is None:
                    print(f"Unrecognized document ID {doc_id}!")
                    time.sleep(1)
                else:
                    curr_doc = ordered_docs.index(doc_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--split",
        required=False,
        type=str,
        choices=["train", "dev", "test"],
        default="train",
    )
    parser.add_argument(
        "--viewing-mode",
        required=False,
        type=str,
        choices=["sequential"],
        default="sequential",
    )
    parser.add_argument(
        "--template-type",
        required=False,
        type=str,
        choices=[
            "attack",
            "arson",
            "bombing",
            "forced work stoppage",
            "kidnapping",
            "robbery",
        ],
    )
    parser.add_argument(
        "--keep-irrelevant",
        action="store_true",
        help="also print documents that do not have any annotated templates",
    )
    args = parser.parse_args()
    view_annotations(
        args.split, args.viewing_mode, args.keep_irrelevant, args.template_type
    )
