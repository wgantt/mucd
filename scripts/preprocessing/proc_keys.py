"""
Lightly adapted version of this script:
    https://github.com/brendano/muc4_proc/blob/master/scripts/proc_keys.py
Adaptions are to use Python3 instead of Python2 and a change to
how outputs are written to JSON files.
"""
import os
import re
import json
from codecs import decode
from collections import defaultdict


def cleankey(keystr):
    return re.sub(r"[^A-Z]+", "_", keystr).strip("_").lower()


def clean_docid(value):
    return re.sub(r"\s*\(.*$", "", value)


ALL_KEYS = """
MESSAGE: ID
MESSAGE: TEMPLATE
INCIDENT: DATE
INCIDENT: LOCATION
INCIDENT: TYPE
INCIDENT: STAGE OF EXECUTION
INCIDENT: INSTRUMENT ID
INCIDENT: INSTRUMENT TYPE
PERP: INCIDENT CATEGORY
PERP: INDIVIDUAL ID
PERP: ORGANIZATION ID
PERP: ORGANIZATION CONFIDENCE
PHYS TGT: ID
PHYS TGT: TYPE
PHYS TGT: NUMBER
PHYS TGT: FOREIGN NATION
PHYS TGT: EFFECT OF INCIDENT
PHYS TGT: TOTAL NUMBER
HUM TGT: NAME
HUM TGT: DESCRIPTION
HUM TGT: TYPE
HUM TGT: NUMBER
HUM TGT: FOREIGN NATION
HUM TGT: EFFECT OF INCIDENT
HUM TGT: TOTAL NUMBER
""".strip().split(
    "\n"
)

LOCATION_RE = r"([\w ]+)(\(\w+ ?\w*\))*"

ALL_KEYS = set(cleankey(k) for k in ALL_KEYS)

NON_LIST_VALUED_KEYS = """
message_id
message_template
message_template_optional
incident_type
incident_stage_of_execution
perp_incident_category
""".split()

SELECTED_KEYS = """
perp_individual_id
perp_organization_id
perp_organization_confidence
perp_incident_category
phys_tgt_id
hum_tgt_name
hum_tgt_description
hum_tgt_effect_of_incident
phys_tgt_effect_of_incident
incident_instrument_id
incident_location
incident_date
incident_stage_of_execution
""".split()


SET_FILL_KEYS_ALLOWED_VALUES = {
    "incident_stage_of_execution": {"ACCOMPLISHED", "ATTEMPTED", "THREATENED"},
    "perp_incident_category": {
        "TERRORIST ACT",
        "STATE-SPONSORED VIOLENCE",
        "? TERRORIST ACT",
        "? STATE-SPONSORED VIOLENCE",
    },
    "perp_organization_confidence": {
        "REPORTED AS FACT",
        "ACQUITTED",
        "CLAIMED OR ADMITTED",
        "SUSPECTED OR ACCUSED",
        "SUSPECTED OR ACCUSED BY AUTHORITIES",
        "POSSIBLE",
    },
    "hum_tgt_effect_of_incident": {
        "DEATH",
        "NO DEATH",
        "INJURY",
        "NO INJURY",
        "NO INJURY OR DEATH",
        "REGAINED FREEDOM",
        "ESCAPED",
        "RESIGNATION",
        "NO RESIGNATION",
        "PROPERTY TAKEN FROM TARGET",
    },
    "phys_tgt_effect_of_incident": {
        "DESTROYED",
        "SOME DAMAGE",
        "NO DAMAGE",
        "MONEY TAKEN FROM TARGET",
        "PROPERTY TAKEN FROM TARGET",
        "TARGET TAKEN",
        None,  # Not sure why this seems to be the only set-fill value that needs a none slot...
    },
}

SELECTED_KEYS = set(SELECTED_KEYS)

assert SELECTED_KEYS <= ALL_KEYS

cur_docid = None


def warning(s):
    global cur_docid
    print(f"WARNING docid={cur_docid} | {s}")


def yield_keyvals(chunk):
    """
    Processes the raw MUC "key file" format.  Parses one entry ("chunk").
    Yields a sequence of (key,value) pairs.
    A single key can be repeated many times.
    This function cleans up key names, but passes the values through as-is.
    """
    curkey = None
    for line in chunk.split("\n"):
        if line.startswith(";"):
            yield "comment", line
            continue
        middle = 33  ## Different in dev vs test files... this is the minimum size to get all keys.
        keytext = line[:middle].strip()
        valtext = line[middle:].strip()
        if not keytext:
            ## it's a continuation
            assert curkey
        else:
            curkey = cleankey(keytext)
            assert curkey in ALL_KEYS

        yield curkey, valtext


def parse_location(location_expr: str):
    out = []
    seen = set()
    for loc1 in location_expr.split(" / "):
        loc1 = loc1.strip()
        for loc2 in loc1.split(":"):
            loc2 = loc2.strip()
            if loc2[0] == "(" and loc2[-1] == ")":
                loc2 = loc2[1:-1]
            for loc3 in loc2.split("-"):
                loc3 = loc3.strip()
                if loc3.startswith("? "):
                    loc3 = loc3[2:]
                match = re.search(LOCATION_RE, loc3)
                assert match is not None
                groups = match.groups()
                assert len(groups) == 2
                g0 = groups[0].strip()
                if groups[1] is None:
                    if g0 not in seen:
                        out.append({"type": "simple_strings", "strings": [g0]})
                        seen.add(g0)
                else:
                    assert groups[1][0] == "(" and groups[1][-1] == ")"
                    g1 = groups[1][1:-1]
                    if g0 + g1 not in seen:
                        out.append(
                            {
                                "type": "colon_clause",
                                "strings_lhs": [g0],
                                "strings_rhs": [g1],
                            }
                        )
                        seen.add(g0 + g1)
    return out


def parse_values(keyvals):
    """
    Takes key,value pairs as input, where the values are unparsed.
    Filter down to the slots we want, and parse their values as well.
    """
    for key, value in keyvals:
        if key == "message_id":
            yield key, clean_docid(value)
            continue
        if key == "message_template":
            if re.search(r"^\d+$", value):
                yield key, int(value)
            elif value == "*":
                yield key, value
            elif re.search(r"^\d+ \(OPTIONAL\)$", value):
                yield key, int(value.split()[0])
                yield "message_template_optional", True
            else:
                assert False, "bad message_template format"
            continue
        if key == "incident_type":
            yield key, clean_docid(value)
            continue

        if key in SELECTED_KEYS:
            if value == "*":
                continue

            if value == "-":
                yield key, None
                continue

            if key == "incident_location":
                yield key, parse_location(value)
                continue

            if '"' not in value:
                if key not in {
                    "incident_date",
                    "incident_stage_of_execution",
                    "perp_incident_category",
                    "perp_organization_confidence",
                }:
                    warning(
                        f"apparent data error, missing quotes. adding back in. value was ||| {value}"
                    )
                    value = '"' + value + '"'

            value = parse_one_value(value, key)
            if key in SET_FILL_KEYS_ALLOWED_VALUES:
                strings_key = "strings" if "strings" in value else "strings_lhs"
                for v in value[strings_key]:
                    assert v in SET_FILL_KEYS_ALLOWED_VALUES[key], f"{key}: {v}"

            yield key, value


def parse_one_value(namestr, slotname=None):
    """
    Returns a dictionary with 'type' either
        'simple_strings' ==> has a field 'strings'
        'colon_clause'   ==> has two fields 'strings_lhs' and 'strings_rhs'
    Furthermore, has 'optional':true  if this valueline is optional, which I think means the entity is optional.
    (There is only one example of a colon clause having optional=true; I suspect it's an annotation error.)
    """

    global cur_docid
    # Fix bugs in the data
    if cur_docid == "DEV-MUC3-0604" and "BODYGUARD OF EL ESPECTADOR" in namestr:
        # DEV-MUC3-0604 (MDESC)
        # ? ("BODYGUARD OF EL ESPECTADOR'S CHIEF OF DISTRIBUTION IN MEDELLIN" / "BODYGUARD"): "PEDRO LUIS OSORIO"
        namestr = '''? "BODYGUARD OF EL ESPECTADOR'S CHIEF OF DISTRIBUTION IN MEDELLIN" / "BODYGUARD" / "PEDRO LUIS OSORIO"'''
    if namestr == 'MACHINEGUNS"':
        # DEV-MUC3-0217
        namestr = '"' + namestr

    d = {}
    match = re.search(r"\? *(.*)", namestr)
    if match:
        d["optional"] = True
        namestr = match.group(1)

    if ":" in namestr:
        assert len(re.findall(":", namestr)) == 1
        lhs, rhs = re.split(r" *: *", namestr)
        if lhs[0] == "(":
            lhs = lhs[1:]
        if lhs[-1] == ")":
            lhs = lhs[:-1]
        rhs_value = parse_strings_possibly_with_alternations(rhs)
        lhs_value = parse_strings_possibly_with_alternations(lhs, slotname)
        d.update(
            {"type": "colon_clause", "strings_lhs": lhs_value, "strings_rhs": rhs_value}
        )
        return d

    else:
        strings = parse_strings_possibly_with_alternations(namestr, slotname)
        d.update({"type": "simple_strings", "strings": strings})
        return d


def parse_strings_possibly_with_alternations(namestr, slotname=None):
    namestr = namestr.strip()
    assert ":" not in namestr, namestr
    assert not namestr.startswith("?")
    parts = re.split(" */ *", namestr)
    parts = [ss.strip() for ss in parts]
    strings = []
    for ss in parts:
        if ss == "-":
            # We should see this only inside a colon clause. There are a few of these, e.g.
            # 21. HUM TGT: NUMBER                 -: "ORLANDO LETELIER"
            strings.append(None)
            continue
        if slotname in {
            "hum_tgt_effect_of_incident",
            "phys_tgt_effect_of_incident",
            "incident_stage_of_execution",
            "perp_incident_category",
            "perp_organization_confidence",
        }:
            # These slots should not have strings escaped
            try:
                assert ss in SET_FILL_KEYS_ALLOWED_VALUES[slotname], f"{slotname}: {ss}"
            except:
                breakpoint()
        elif slotname == "incident_date":
            if ss[0] == "(":
                ss = ss[1:]
            if ss[-1] == ")":
                ss = ss[:-1]
        else:
            if not (ss[0] == '"' and ss[-1] == '"'):
                warning("WTF ||| " + ss)
            ss = ss[1:-1]
        # ss = ss.decode('string_escape')  # They seem to use C-style backslash escaping
        ss = decode(ss, "unicode-escape")
        ss = ss.strip()
        strings.append(ss)
    return strings


def test_parsestrings():
    f = parse_strings_possibly_with_alternations
    s = '"CAR DEALERSHIP"'
    assert set(f(s)) == {"CAR DEALERSHIP"}
    s = '"TUPAC AMARU REVOLUTIONARY MOVEMENT" / "MRTA"'
    assert set(f(s)) == {"TUPAC AMARU REVOLUTIONARY MOVEMENT", "MRTA"}


def test_parse_one_value():
    s = '"U.S. JOURNALIST": "BERNARDETTE PARDO"'
    d = parse_one_value(s)
    assert d["strings_lhs"] == ["U.S. JOURNALIST"]
    assert d["strings_rhs"] == ["BERNARDETTE PARDO"]


def fancy_json_print(keyvals):
    lines = [json.dumps(kv, sort_keys=True) for kv in keyvals]
    s = ""
    s += "[\n  "
    s += ",\n  ".join(lines)
    s += "\n]"
    return s


def keyvals_to_dict(keyvals):
    out = defaultdict(list)
    for (k, v) in keyvals:
        if v is None or k == "incident_location" or k in NON_LIST_VALUED_KEYS:
            out[k] = v
        else:
            assert isinstance(v, dict), f"{k}: {v}"
            if out[k] is None:
                out[k] = []
            out[k].append(v)
    return out


if __name__ == "__main__":

    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("input", help="the raw MUC keyfiles to be processed")
    p.add_argument("output", help="the JSON file where the output will be written")
    args = p.parse_args()

    if os.path.isfile(args.input):
        keyfiles = [args.input]
    elif os.path.isdir(args.input):
        path = os.path.abspath(args.input)
        keyfiles = [
            os.path.join(path, f)
            for f in os.listdir(args.input)
            if f.startswith("key-")
        ]
    else:
        raise ValueError("Could not find input file or directory!")
    assert keyfiles, f"No keyfiles found!"
    lines = []
    for keyfile in keyfiles:
        with open(keyfile) as f:
            for line in f:
                l = line.rstrip()
                if not re.search(r"^\s*;", l):
                    lines.append(l)
    data = "\n".join(lines)
    chunks = re.split(r"\n\n+|\n(?=0\. )", data)
    chunks = [c.strip() for c in chunks if c.strip()]

    output = defaultdict(list)
    for chunk in chunks:
        keyvals1 = list(yield_keyvals(chunk))
        assert all(k in ALL_KEYS or k == "comment" for k, v in keyvals1)
        cur_docid = clean_docid(dict(keyvals1)["message_id"])
        keyvals2 = list(parse_values(keyvals1))
        keyvals_dict = keyvals_to_dict(keyvals2)
        output[keyvals_dict["message_id"]].append(keyvals_dict)

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    # print("%%%")
    # print(fancy_json_print(keyvals2))
