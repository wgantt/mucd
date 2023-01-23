import argparse
import json
import os
import sys
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

global outfile


def fprint(text: str = ""):
    print(text, file=outfile)


def pretty_print_entities(template: Dict[str, Any], slot: str) -> None:
    fprint(f"{slot}:")
    if template.get(slot) is not None:
        for item in template[slot]:
            if item["type"] == "colon_clause":
                fprint(
                    f"{OFFSET_STR + str(item['strings_lhs'][0])}: {' ,'.join(item['strings_rhs'])}"
                )
            else:
                fprint(f"{OFFSET_STR + ', '.join(item['strings'])}")


def pretty_print_effect_of_incident(
    template: Dict[str, Any], is_human: bool = True
) -> None:
    slot = "hum_tgt_effect_of_incident" if is_human else "phys_tgt_effect_of_incident"
    fprint(f"{slot}:")
    if template.get(slot) is not None:
        for item in template[slot]:
            fprint(
                f"{OFFSET_STR + str(item['strings_lhs'][0])}: {', '.join(item['strings_rhs'])}"
            )

def pretty_print_organization_confidence(
    template: Dict[str, Any]
) -> None:
    fprint(f"perp_organization_confidence:")
    if template.get("perp_organization_confidence") is not None:
        for item in template["perp_organization_confidence"]:
            fprint(
                f"{OFFSET_STR + str(item['strings_lhs'][0])}: {', '.join(item['strings_rhs'])}"
            )



def pretty_print_date(template: Dict[str, Any]) -> None:
    fprint("incident_date:")
    incident_date = template.get("incident_date")
    if incident_date is not None:
        assert len(template["incident_date"]) == 1
        incident_dates = template["incident_date"][0]["strings"]
        fprint(f"{OFFSET_STR + ', '.join(incident_dates)}")


def pretty_print_location(template: Dict[str, Any]) -> None:
    to_print = []
    fprint(f"incident_location:")
    if template.get("incident_location") is not None:
        for loc in template["incident_location"]:
            if loc["type"] == "simple_strings":
                assert len(loc["strings"]) == 1
                to_print.append(loc["strings"][0])
            elif loc["type"] == "colon_clause":
                assert len(loc["strings_lhs"]) == len(loc["strings_rhs"]) == 1
                to_print.append(f"{loc['strings_lhs'][0]} ({loc['strings_rhs'][0]})")
        for loc in to_print:
            fprint(f"{OFFSET_STR + loc}")
    else:
        print(
            f"WARNING ({template['message_id']}): incident_location was missing from template {template['message_template']}",
            file=sys.stderr,
        )


def pretty_print_template(template: Dict[str, Any]) -> None:
    for k in NON_LIST_VALUED_KEYS:
        if k in {"message_id", "message_template_optional"}:
            continue
        if k not in template:
            print(
                f"WARNING ({template['message_id']}): slot {k} is missing from template {template['message_template']}",
                file=sys.stderr,
            )
            continue
        value = template[k]
        if isinstance(value, dict):
            value = value["strings"]
            if not len(value) == 1:
                print(
                    f"WARNING ({template['message_id']}): slot {k} in template {template['message_template']} had multiple values: {value}",
                    file=sys.stderr,
                )
            value = value[0]
        fprint(f"{k}:")
        fprint(f"{OFFSET_STR + str(value)}")
    pretty_print_date(template)
    pretty_print_location(template)
    pretty_print_effect_of_incident(template, is_human=True)
    pretty_print_effect_of_incident(template, is_human=False)
    for slot in ENTITY_KEYS:
        pretty_print_entities(template, slot)
    pretty_print_organization_confidence(template)
    fprint("-" * 80)


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
    if template_type is not None:
        print(
            f"Visualizing {len(docs)} documents annotated with {template_type} templates..."
        )
    elif keep_irrelevant:
        print(
            f"Visuauzling {len(docs)} documents, including those without annotated templates..."
        )
    else:
        print(f"Visualizing {len(docs)} documents...")
    time.sleep(2)

    ordered_docs = sorted(docs.keys())
    if viewing_mode == "interactive":
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
    else:
        for doc in ordered_docs:
            fprint("=============")
            fprint(docs[doc]["docid"])
            fprint("=============\n")
            fprint(f"{docs[doc]['text']}\n")
            fprint("---------")
            fprint("Templates")
            fprint("---------")
            for template in keys[doc]:
                fprint()
                pretty_print_template(template)


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
        choices=["interactive", "to_file"],
        default="interactive",
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
    parser.add_argument("--outfile", required=False, type=str, default="stdout")
    args = parser.parse_args()
    if args.outfile == "stdout":
        outfile = sys.stdout
    else:
        outfile = open(args.outfile, "w")
    view_annotations(
        args.split, args.viewing_mode, args.keep_irrelevant, args.template_type
    )
    outfile.close()
