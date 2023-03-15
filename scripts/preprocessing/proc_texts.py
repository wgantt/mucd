"""
Lightly adapted version of this script:
    https://github.com/brendano/muc4_proc/blob/master/scripts/proc_texts.py
Adaptions are to use Python3 instead of Python2 and a change to
how outputs are written to JSON files.
"""
import argparse
import json
import os
import re

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="the raw MUC input file or directory")
    parser.add_argument("output", help="the output JSON file")
    args = parser.parse_args()

    if os.path.isfile(args.input):
        texts = [args.input]
    elif os.path.isdir(args.input):
        path = os.path.abspath(args.input)
        texts = [os.path.join(path, f) for f in os.listdir(args.input)]
    else:
        raise ValueError("Could not find input file or directory!")
    assert texts, f"No texts found!"

    output = {}
    for text in texts:
        doc_infos = []
        with open(text) as f:
            data = f.read()
            matches = list(re.finditer(r"(DEV-\S+) *\(([^\)]*)\)", data))
            has_source = bool(matches)
            if not matches:
                matches = list(re.finditer(r"(TST\d+-\S+)", data))

        for match in matches:
            docid = match.group(1)
            d = {
                "docid": docid,
                "char_start": match.end(),
                "char_before": match.start(),
            }
            if has_source:
                d["source"] = match.group(2)
            doc_infos.append(d)

        for i in range(len(doc_infos) - 1):
            doc_infos[i]["char_end"] = doc_infos[i + 1]["char_before"]
        doc_infos[-1]["char_end"] = len(data)

        for d in doc_infos:
            raw_text = data[d["char_start"] : d["char_end"]].strip()

            # issue: there are sometimes recursive (multiple?) datelines.  we only get the first in that case.

            tag_re = r"\[[^\]]+\]"
            tags_re = "(?:%s\s+)+" % tag_re
            full_re = r"^(.*?)--\s+(%s)(.*)" % tags_re
            m = re.search(full_re, raw_text, re.DOTALL)
            if not m:
                print(raw_text[:1000])
                assert False

            dateline = m.group(1).replace("\n", " ").strip()
            tags = m.group(2).replace("\n", " ")
            text = m.group(3)

            assert tags.upper() == tags
            tags = re.findall(tag_re, tags)
            tags = [x.lstrip("[").rstrip("]").lower() for x in tags]

            d["dateline"] = dateline
            d["tags"] = tags

            text = text.strip()
            text = text.replace("[", "(").replace("]", ")")

            d["text"] = text
            output[d["docid"]] = d

    # outside loop over texts
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
