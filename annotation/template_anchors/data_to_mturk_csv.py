import argparse
import json
import html
import os
import re
import spacy
import tokenizations

from typing import *

DATA_PATH = "data/processed/"

nlp = spacy.load("en_core_web_sm")


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


def create_hit(
    sentences: List[List[str]],
    tokens: List[str],
    template: Dict[str, Any],
    hit_id: int,
    tok2char: Dict[int, List[int]],
    char2tok: Dict[int, List[int]],
) -> str:
    return (
        '"'
        + replace_string(
            json.dumps(
                {
                    "sentences": sentences,
                    "tokens": tokens,
                    "template": template,
                    "hit_id": hit_id,
                    "tok2char": tok2char,
                    "char2tok": char2tok,
                }
            )
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
        lowercase_text = doc_data["text"].lower()
        toks = [t.text for t in nlp(lowercase_text)]
        tok2char, char2tok = tokenizations.get_alignments(toks, lowercase_text)
        sentences = []
        tok_offset = 0
        for start, end in doc_data["sentences"]:
            first_tok, last_tok = char2tok[start][0], char2tok[end - 1][0]  # inclusive
            sentences.append(
                {
                    "text": " ".join(
                        [
                            html.escape(f"[{tok_offset + i}] {t}")
                            for (i, t) in enumerate(toks[first_tok : last_tok + 1])
                        ]
                    )
                }
            )
            tok_offset = last_tok + 1

        # one template per HIT. Is this what we want to do?
        for template in doc_data["templates"]:
            for slot, slot_data in template.items():
                if not isinstance(slot_data, list):
                    continue
                for filler_data in slot_data:
                    if "strings" in filler_data:
                        filler_data["strings"] = [
                            html.escape(s.lower()) for s in filler_data["strings"]
                        ]
                    if "strings_lhs" in filler_data:
                        try:
                            filler_data["strings_lhs"] = [
                                html.escape(s.lower())
                                for s in filler_data["strings_lhs"]
                            ]
                        except AttributeError:
                            print(
                                f"WARNING: Invalid LHS value '{filler_data['strings_lhs']}' for slot {slot} in document {doc}. Could not properly HTML escape this value. Continuing."
                            )
                    if "strings_rhs" in filler_data:
                        filler_data["strings_rhs"] = [
                            html.escape(s.lower()) for s in filler_data["strings_rhs"]
                        ]
            rows.append(
                create_hit(
                    sentences,
                    [html.escape(t) for t in toks],
                    template,
                    hit_id,
                    tok2char,
                    char2tok,
                )
            )
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
