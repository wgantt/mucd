import argparse
import json
import html
import os
import re

from typing import *

DATA_PATH = "data/processed/"


def replace_string(s):
    """
    Make some changes to the input string to make it Turk readable
    """

    # replace all single quotes by double quotes : except at the start/end of the list
    # s = re.sub(r'([^\]])\"', r'\1""', s)
    s = re.sub(r"(?<!\}\])\"", r'""', s)

    # replace single quotes
    s = re.sub(r"\'\{", r"{", s)
    s = re.sub(r"\}\'", r"}", s)

    # replace two backslashes with three
    s = re.sub(r"\\\\", r"\\\\\\", s)

    # remove spaces before and after span
    s = re.sub(r"> ", r">", s)
    s = re.sub(r" <", r"<", s)

    return s


def create_hit(sentences: List[str], template: Dict[str, Any], hit_id: int) -> str:
    return (
        '"'
        + replace_string(
            json.dumps({"sentences": sentences, "template": template, "hit_id": hit_id})
        )
        + '"\n'
    )


def create_csv(split: str, output_csv: str) -> None:
    split_path = os.path.join(DATA_PATH, split, split + ".json")
    with open(split_path) as f:
        data = json.load(f)
    rows = []
    hit_id = 0
    for doc, doc_data in data.items():
        sentences = [
            {"text": html.escape(doc_data["text"][start:end])}
            for (start, end) in doc_data["sentences"]
        ]
        # one template per HIT. Is this what we want to do?
        for template in doc_data["templates"]:
            for slot, slot_data in template.items():
                if not isinstance(slot_data, list):
                    continue
                for filler_data in slot_data:
                    if "strings" in filler_data:
                        filler_data["strings"] = [
                            html.escape(s) for s in filler_data["strings"]
                        ]
                    if "strings_lhs" in filler_data:
                        try:
                            filler_data["strings_lhs"] = [
                                html.escape(s) for s in filler_data["strings_lhs"]
                            ]
                        except AttributeError:
                            print(
                                f"WARNING: Invalid LHS value '{filler_data['strings_lhs']}' for slot {slot} in document {doc}. Could not properly HTML escape this value. Continuing."
                            )
                    if "strings_rhs" in filler_data:
                        filler_data["strings_rhs"] = [
                            html.escape(s) for s in filler_data["strings_rhs"]
                        ]
            rows.append(create_hit(sentences, template, hit_id))
            hit_id += 1
    with open(output_csv, "w") as f:
        f.write("var_arrays\n")
        f.writelines(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["train", "dev", "test"], required=True)
    parser.add_argument(
        "--output-csv",
        type=str,
        required=True,
        help="The name of the CSV file to output",
    )
    args = parser.parse_args()
    create_csv(args.split, args.output_csv)
